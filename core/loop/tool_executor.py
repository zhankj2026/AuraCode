#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.tool_executor — 工具调用执行

封装单个工具调用的完整生命周期：
JSON 解析 → PreToolUse 钩子 → 权限检查 → 计划模式检查 → 缓存 →
路径解析 → 执行（含幂等重试）→ 截断/裁剪 → PostToolUse 钩子 → 自动验证。
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict

from tools.registry import TOOL_REGISTRY
from core.loop.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ToolExecutor:
    """执行工具调用(经过钩子和权限检查)。"""

    def __init__(self, loop):
        self.loop = loop

    def execute(self, tool_call) -> Dict[str, Any]:
        """执行工具调用(经过钩子和权限检查)"""
        loop = self.loop
        tool_name = tool_call.function.name

        # 解析工具参数（LLM 有时返回截断/不完整的 JSON）
        raw_args = tool_call.function.arguments
        try:
            arguments = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            # 尝试修复截断的 JSON：补全缺失的引号和括号
            fixed = LLMClient.try_fix_json(raw_args)
            if fixed is not None:
                arguments = fixed
                logger.warning(f"Fixed malformed JSON for tool '{tool_name}': {raw_args[:100]}...")
            else:
                error_msg = f"工具参数 JSON 解析失败: {raw_args[:200]}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

        logger.info(f"Executing tool: {tool_name}, args: {arguments}")

        # 1. 查找工具
        tool = TOOL_REGISTRY.get(tool_name)
        if not tool:
            error_msg = f"未知工具: {tool_name}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        # 2. PreToolUse 钩子
        if loop.hooks_enabled and loop.hook_manager:
            try:
                # 在新事件循环中执行异步钩子
                evloop = asyncio.new_event_loop()
                asyncio.set_event_loop(evloop)

                pre_result = evloop.run_until_complete(
                    loop.hook_manager.execute_hooks(
                        "PreToolUse",
                        tool_name=tool_name,
                        input=arguments
                    )
                )

                evloop.close()

                # 检查钩子是否阻止执行
                if not pre_result.allow:
                    error_msg = f"Hook denied: {pre_result.block_reason or 'blocked by hook'}"
                    logger.warning(error_msg)

                    # 触发 PostToolUseFailure 钩子
                    if loop.hooks_enabled:
                        self._trigger_failure_hook(tool_name, arguments, error_msg)

                    # StopHook 恢复: 提供恢复提示让 LLM 尝试替代方案
                    recovery_hint = (
                        f"Tool '{tool_name}' was blocked by safety hook. "
                        f"Reason: {pre_result.block_reason or 'unknown'}. "
                        f"Please try an alternative approach or ask the user for guidance."
                    )
                    return {"success": False, "error": error_msg, "recovery_hint": recovery_hint}

                # 应用钩子修改的输入
                if pre_result.modified_input:
                    arguments.update(pre_result.modified_input)
                    logger.debug(f"钩子修改了输入参数")

                # 记录附加上下文
                if pre_result.additional_context:
                    logger.debug(f"钩子附加上下文: {pre_result.additional_context}")

            except Exception as e:
                logger.warning(f"PreToolUse 钩子执行失败: {e}")

        # 3. 权限检查
        if not loop.permission_manager.check_permission(tool_name, arguments):
            error_msg = f"权限拒绝: {tool_name} 操作被安全策略拦截"
            logger.warning(error_msg)

            # P2: 记录权限拒绝
            loop.state.record_permission_denial(tool_name, arguments, error_msg)

            # 触发 PostToolUseFailure 钩子
            if loop.hooks_enabled:
                self._trigger_failure_hook(tool_name, arguments, error_msg)

            return {"success": False, "error": error_msg}

        # 3.5 计划模式检查：禁止写入/执行类工具（仅允许 write_file 写入 plan 文件）
        try:
            from tools.builtin.plan_mode import (
                is_plan_mode_active, is_tool_allowed_in_plan_mode,
                is_write_allowed_for_plan, get_plan_file_path,
            )
            if is_plan_mode_active():
                if not is_tool_allowed_in_plan_mode(tool_name):
                    plan_path = get_plan_file_path()
                    error_msg = (
                        f"Plan mode: tool '{tool_name}' is not allowed. "
                        f"Only read-only tools and write_file to the plan file "
                        f"(`{plan_path}`) are permitted. "
                        f"Use exit_plan_mode when your plan is ready for approval."
                    )
                    logger.warning(error_msg)
                    return {"success": False, "error": error_msg}

                # write_file 特殊检查：只允许写入 plan 文件
                if tool_name == "write_file":
                    write_path = arguments.get("path", "")
                    if not is_write_allowed_for_plan(write_path):
                        plan_path = get_plan_file_path()
                        error_msg = (
                            f"Plan mode: write_file is only allowed for the plan file.\n"
                            f"Allowed path: `{plan_path}`\n"
                            f"Your path: `{write_path}`\n"
                            f"Please write your plan to the plan file instead."
                        )
                        logger.warning(error_msg)
                        return {"success": False, "error": error_msg}
        except ImportError:
            pass  # plan_mode 模块未加载，跳过检查

        # 3.8 工具追踪 + 缓存检查
        from core.tool_tracker import get_tool_tracker, get_tool_cache
        tracker = get_tool_tracker()
        cache = get_tool_cache()
        current_turn = loop.state.turn_count
        tracker.start_call(tool_name, arguments, turn=current_turn)

        # 缓存命中 → 直接返回
        cached_result = cache.get(tool_name, arguments)
        if cached_result is not None:
            tracker.end_call(success=True, result_preview="[cached] " + str(cached_result)[:180])
            logger.info(f"Tool {tool_name} cache hit")
            return {"success": True, "result": cached_result, "_cached": True}

        # 4. 执行工具（含 ToolEnhancer 幂等重试）
        max_retries = 3
        attempt = 0
        while attempt <= max_retries:
            try:
                # 路径解析：将相对路径转换为绝对路径（基于 project_root）
                for pk in ("path", "file_path", "directory"):
                    if pk in arguments and isinstance(arguments[pk], str):
                        p = arguments[pk]
                        original_p = p
                        if not os.path.isabs(p):
                            # 相对路径：基于 project_root 解析为绝对路径
                            arguments[pk] = os.path.abspath(os.path.join(loop.project_root, p))
                        else:
                            # 绝对路径：规范化（处理 ./ 和 ../）
                            arguments[pk] = os.path.abspath(p)
                        logger.info(f"Path resolution [{pk}]: {original_p} -> {arguments[pk]} (project_root={loop.project_root})")

                # plan_mode: 每次执行前刷新 project_root（多线程 Bridge 安全）
                if tool_name in ("enter_plan_mode", "exit_plan_mode"):
                    try:
                        from tools.builtin.plan_mode import set_project_root
                        set_project_root(loop.project_root)
                    except ImportError:
                        pass

                # file-history: 在写入前自动备份
                loop.file_tracker.track_file_history(tool_name, arguments)

                handler = tool["handler"]
                logger.info(f"Executing handler for {tool_name} with args: {list(arguments.keys())}")

                # 注入当前会话模型到线程局部，供 Subagent/Workflow 默认继承
                # （否则 spawn 链路会用硬编码 glm-4-plus，与目标 API 不兼容）
                try:
                    from core.subagent import set_current_model
                    set_current_model(loop.model)
                except Exception:
                    pass

                # 为文件写入类工具传递 project_root
                if tool_name in ("write_file", "edit_file", "search_replace"):
                    if "project_root" not in arguments:
                        arguments["project_root"] = loop.project_root

                # 为命令执行类工具传递 working_directory（基于 project_root）
                if tool_name in ("run_command", "run_powershell"):
                    if "working_directory" not in arguments:
                        arguments["working_directory"] = loop.project_root
                    # SessionEnv: 注入会话环境脚本（venv/conda 等）
                    loop.persistence.inject_session_env(arguments, tool_name)

                # 为搜索类工具传递 project_root（用于解析相对路径）
                if tool_name in ("glob", "grep"):
                    if "project_root" not in arguments:
                        arguments["project_root"] = loop.project_root

                result = handler(**arguments)
                logger.info(f"Handler returned: {str(result)[:200]}")

                # SessionTranscript: 记录工具调用及结果
                loop.persistence.transcript_record_tool(tool_name, arguments, result)

                # 5. 输出截断（基础保护）
                if isinstance(result, str) and len(result.splitlines()) > 500:
                    lines = result.splitlines()
                    truncated = (
                        lines[:250] +
                        [f"... (截断 {len(lines) - 500} 行) ..."] +
                        lines[-250:]
                    )
                    result = "\n".join(truncated)

                # 5.5 ToolEnhancer: 智能裁剪 + 摘要
                if isinstance(result, str) and result:
                    result = loop.tool_enhancer.process_tool_result(tool_name, result)

                logger.info(f"Tool {tool_name} executed successfully")

                # 追踪 + 缓存写入
                tracker.end_call(success=True, result_preview=str(result)[:200])
                cache.put(tool_name, arguments, result)

                # 4.5 ContextCollapse: 追踪文件操作
                loop.file_tracker.track_file_operation(tool_name, arguments)

                # 6. PostToolUse 钩子
                if loop.hooks_enabled and loop.hook_manager:
                    try:
                        evloop = asyncio.new_event_loop()
                        asyncio.set_event_loop(evloop)

                        post_result = evloop.run_until_complete(
                            loop.hook_manager.execute_hooks(
                                "PostToolUse",
                                tool_name=tool_name,
                                input=arguments,
                                output={"success": True, "result": result}
                            )
                        )

                        evloop.close()

                        if post_result.additional_context:
                            logger.info(f"PostToolUse 钩子: {post_result.additional_context}")

                    except Exception as e:
                        logger.warning(f"PostToolUse 钩子执行失败: {e}")

                # 7. 自动验证（代码修改后）
                if tool_name in ("write_file", "edit_file", "search_replace"):
                    loop.file_tracker.auto_validate_after_change(tool_name, arguments)

                return {"success": True, "result": result}

            except Exception as e:
                error_msg = f"工具执行失败: {str(e)}"
                logger.error(error_msg, exc_info=True)

                # ToolEnhancer: 幂等工具自动重试
                attempt += 1
                if attempt <= max_retries and loop.tool_enhancer.should_retry(tool_name, str(e), attempt):
                    delay = loop.tool_enhancer.get_retry_delay(attempt)
                    logger.info(f"Tool {tool_name} failed, retrying ({attempt}/{max_retries}) after {delay:.1f}s")
                    loop.events.emit("tool_retry", {
                        "tool_name": tool_name,
                        "attempt": attempt,
                        "error": str(e)[:200],
                        "delay": delay,
                    })
                    time.sleep(delay)
                    continue  # 重试

                # 不再重试，记录失败
                tracker.end_call(success=False, error=str(e)[:200])

                # 触发 ToolError 钩子
                if loop.hooks_enabled:
                    self._trigger_tool_error_hook(tool_name, arguments, e)

                return {"success": False, "error": error_msg}

    def _trigger_failure_hook(self, tool_name: str, arguments: Dict[str, Any], error: str):
        """触发工具失败钩子（权限拒绝/钩子阻止）"""
        try:
            evloop = asyncio.new_event_loop()
            asyncio.set_event_loop(evloop)

            evloop.run_until_complete(
                self.loop.hook_manager.execute_hooks(
                    "PostToolUseFailure",
                    tool_name=tool_name,
                    input=arguments,
                    error=error
                )
            )

            evloop.close()
        except Exception as e:
            logger.warning(f"PostToolUseFailure 钩子执行失败: {e}")

    def _trigger_tool_error_hook(self, tool_name: str, arguments: Dict[str, Any], exception: Exception):
        """触发 ToolError 钩子（工具抛出异常时，区别于权限拒绝）"""
        try:
            evloop = asyncio.new_event_loop()
            asyncio.set_event_loop(evloop)

            evloop.run_until_complete(
                self.loop.hook_manager.execute_hooks(
                    "ToolError",
                    tool_name=tool_name,
                    input=arguments,
                    exception=exception,
                    error_type=type(exception).__name__,
                )
            )

            evloop.close()
        except Exception as e:
            logger.warning(f"ToolError 钩子执行失败: {e}")
