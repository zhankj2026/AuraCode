#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.tool_executor — 工具调用执行

封装单个工具调用的完整生命周期：
JSON 解析 → PreToolUse 钩子 → 权限检查 → 计划模式检查 → 缓存 →
路径解析 → 执行（含幂等重试）→ 截断/裁剪 → PostToolUse 钩子 → 自动验证。
"""

import json
import logging
import os
import time
from typing import Any, Dict

from tools.registry import TOOL_REGISTRY
from core.loop.llm_client import LLMClient
from core.tool_tracker import get_tool_tracker, get_tool_cache
from core.subagent import set_current_model
from core.tool_categories import (
    FILE_WRITE_TOOLS,
    PROJECT_ROOT_INJECT_TOOLS,
    COMMAND_EXEC_TOOLS,
    SEARCH_TOOLS,
    WORKSPACE_BOUND_TOOLS,
    PATH_ARG_KEYS,
)

logger = logging.getLogger(__name__)

# 扩展管理工具（extension_tools.py 注册）：执行前注入当前 loop，
# 供其以 loop.project_root 定位项目根
EXTENSION_MANAGEMENT_TOOLS = frozenset({
    "skill_create", "skill_delete",
    "mcp_add", "mcp_remove", "mcp_list_servers",
    "hook_add", "hook_remove", "hook_list",
    "plugin_create", "plugin_list",
})


def _path_outside_workspace(path_str: str, project_root: str) -> bool:
    """判断路径是否在项目工作区之外。

    相对路径按 project_root 解析（与执行期「路径解析」步骤的
    abspath(join(project_root, p)) 口径一致）。
    修复：此前按进程 cwd 解析，Bridge 模式下 cwd 是后端启动目录（引擎根），
    与会话 work_dir 不同，导致合法的项目内相对路径被误判越界。
    """
    try:
        p = path_str if os.path.isabs(path_str) else os.path.join(project_root, path_str)
        abs_p = os.path.normcase(os.path.abspath(p))
        abs_root = os.path.normcase(os.path.abspath(project_root))
        return os.path.commonpath([abs_p, abs_root]) != abs_root
    except ValueError:
        # Windows 不同盘符等 commonpath 无法比较 → 视为越界
        return True


def _syntax_check_python(path: str) -> str:
    """Python 语法检查，返回错误描述（无错误返回空串）"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            compile(f.read(), path, "exec")
        return ""
    except SyntaxError as e:
        return f"line {e.lineno}: {e.msg}"
    except Exception as e:
        return str(e)


def _syntax_check_node(path: str) -> str:
    """JS/TS 语法检查（node --check），返回错误描述（无错误/无 node 返回空串）"""
    try:
        import subprocess
        r = subprocess.run(
            ["node", "--check", path],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            err = (r.stderr or "").strip().splitlines()
            return " | ".join(err[-3:])[:400]
        return ""
    except FileNotFoundError:
        return ""  # node 不可用 → 跳过
    except Exception:
        return ""


# 写后即验: 扩展名 → 语法检查器（结果同步附进工具结果，模型当场修复，
# 而不是等后续测试运行才发现——demo10 实测 45 次 replace 中大量是延后发现的低级错误）
_SYNTAX_CHECKERS = {
    ".py": _syntax_check_python,
    ".js": _syntax_check_node,
    ".mjs": _syntax_check_node,
    ".cjs": _syntax_check_node,
}


class ToolExecutor:
    """执行工具调用(经过钩子和权限检查)。"""

    def __init__(self, loop):
        self.loop = loop

    @staticmethod
    def _append_syntax_check(arguments: Dict[str, Any], result: str) -> str:
        """写操作后附加语法检查结果（错误直接回流模型，当场修复）"""
        try:
            path = arguments.get("file_path") or arguments.get("path") or ""
            if not path:
                return result
            ext = os.path.splitext(path)[1].lower()
            checker = _SYNTAX_CHECKERS.get(ext)
            if not checker or not os.path.isfile(path):
                return result
            err = checker(path)
            if err:
                return (f"{result}\n\n⚠ 语法检查未通过（请在下一步立即修复）:\n"
                        f"{os.path.basename(path)}: {err}")
            return result + "\n✓ 语法检查通过"
        except Exception:
            return result

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
            pre_result = loop.events.run_hooks(
                "PreToolUse", tool_name=tool_name, input=arguments
            )
            if pre_result is not None:
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

        # 3.4 工作区边界检查：文件/搜索类工具的路径必须落在 project_root 内。
        # 防止 agent 通过绝对路径或 ../ 访问项目外文件（如兄弟 demo* 目录）。
        project_root = getattr(loop, "project_root", "") or ""
        if project_root and tool_name in WORKSPACE_BOUND_TOOLS:
            for key in PATH_ARG_KEYS:
                val = arguments.get(key)
                if val and isinstance(val, str) and val.strip():
                    if _path_outside_workspace(val, project_root):
                        error_msg = (
                            f"路径越界: {val} 不在工作区 {project_root} 内。"
                            f"除非用户明确要求，所有文件操作必须限制在主工作目录内，"
                            f"禁止访问其上级/兄弟目录。请改用项目内路径。"
                        )
                        logger.warning(f"Workspace bound: {tool_name} {val}")
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
                # 缺省路径注入：list_directory 的 handler 默认 path="." 会按进程 cwd
                # 解析，Bridge 模式下 cwd 是后端启动目录（引擎根）而非会话 work_dir，
                # 导致「列目录」显示引擎源码树、误导模型。这里显式注入 "."，让下面的
                # 路径解析步骤统一按 project_root 解析。
                if tool_name == "list_directory" and "path" not in arguments:
                    arguments["path"] = "."

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
                # （否则 spawn 链路会用硬编码 glm-4-flash，与目标 API 不兼容）
                try:
                    set_current_model(loop.model)
                except Exception:
                    pass

                # 为接受 project_root 的写入工具传递基准路径
                # (仅 write_file;replace_in_file_handler 不接受该参数)
                if tool_name in PROJECT_ROOT_INJECT_TOOLS:
                    if "project_root" not in arguments:
                        arguments["project_root"] = loop.project_root

                # 为命令执行类工具传递 working_directory（基于 project_root）
                if tool_name in COMMAND_EXEC_TOOLS:
                    if "working_directory" not in arguments:
                        arguments["working_directory"] = loop.project_root
                    # SessionEnv: 注入会话环境脚本（venv/conda 等）
                    loop.persistence.inject_session_env(arguments, tool_name)

                # 为搜索类工具传递 project_root（用于解析相对路径）
                if tool_name in SEARCH_TOOLS:
                    if "project_root" not in arguments:
                        arguments["project_root"] = loop.project_root

                # 扩展管理工具（extension_tools）：注入当前 loop 供其定位
                # 项目根。Bridge 会话线程初始化后会 chdir 回引擎目录，
                # 这些工具若靠 cwd 定位会把配置写到引擎根。
                if tool_name in EXTENSION_MANAGEMENT_TOOLS:
                    try:
                        from tools.builtin import extension_tools as _et
                        _et._CURRENT_LOOP["loop"] = loop
                    except Exception:
                        pass

                result = handler(**arguments)
                logger.info(f"Handler returned: {str(result)[:200]}")

                # SessionTranscript: 记录工具调用及结果
                loop.persistence.transcript_record_tool(tool_name, arguments, result)

                # 4.6 写后即验: 代码文件语法检查结果同步回流给模型
                #    （对标主流工具的 PostToolUse 验证回流；后台
                #    auto_validate 的事件无消费者，模型此前看不到）
                if tool_name in FILE_WRITE_TOOLS and isinstance(result, str):
                    result = self._append_syntax_check(arguments, result)

                # 5. ToolEnhancer: 智能裁剪 + 摘要（唯一的输出裁剪层，
                #    read_file 有豁免逻辑，见 tool_enhancer.process_tool_result）
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
                    post_result = loop.events.run_hooks(
                        "PostToolUse",
                        tool_name=tool_name,
                        input=arguments,
                        output={"success": True, "result": result},
                    )
                    if post_result is not None and post_result.additional_context:
                        logger.info(f"PostToolUse 钩子: {post_result.additional_context}")

                # 7. 自动验证（代码修改后）
                if tool_name in FILE_WRITE_TOOLS:
                    loop.file_tracker.auto_validate_after_change(tool_name, arguments)

                return {"success": True, "result": result}

            except Exception as e:
                error_msg = f"工具执行失败: {str(e)}"
                logger.error(error_msg, exc_info=True)

                # 缺参 TypeError（如 "missing 1 required positional argument:
                # 'path'"）是 LLM 输出的参数不完整——自动重试同样的坏参数没意义，
                # 追加 schema 提示让模型立即补参重发（实测此类错误曾让 agent
                # 在文档任务里反复碰壁）。
                if isinstance(e, TypeError) and "required positional argument" in str(e):
                    schema = tool.get("parameters") or {}
                    error_msg += (
                        f"\n提示: 参数不完整。工具 {tool_name} 需要 "
                        f"{list(schema.get('properties', {}).keys())}，"
                        f"实际收到 {list(arguments.keys())}。"
                        f"请带上缺失参数重新调用。"
                    )

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
        if not (self.loop.hooks_enabled and self.loop.hook_manager):
            return
        self.loop.events.run_hooks(
            "PostToolUseFailure",
            tool_name=tool_name,
            input=arguments,
            error=error,
        )

    def _trigger_tool_error_hook(self, tool_name: str, arguments: Dict[str, Any], exception: Exception):
        """触发 ToolError 钩子（工具抛出异常时，区别于权限拒绝）"""
        if not (self.loop.hooks_enabled and self.loop.hook_manager):
            return
        self.loop.events.run_hooks(
            "ToolError",
            tool_name=tool_name,
            input=arguments,
            exception=exception,
            error_type=type(exception).__name__,
        )
