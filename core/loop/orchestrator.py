#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.orchestrator — Agent 主循环编排

从 ``AgentLoop._run_inner`` 提取的 TAOR 主循环（原 ~310 行）:
    - 轮次调度（turn 计数 / 检查点 / 预算-中断守卫）
    - 单轮编排（上下文维护 → LLM 流式 → 工具调度）
    - 错误恢复策略（prompt_too_long / 瞬时重试 / 连续服务器错误 / fallback）

旧逻辑 → 新位置:
    AgentLoop._run_inner              ->  LoopOrchestrator.run
    预算 + 中断 + 检查点段            ->  _check_budget_abort / _create_checkpoint
    上下文压缩 / ContextWarning 段    ->  _run_context_maintenance
    except 错误恢复段                 ->  _handle_turn_error
    任务完成 / 达到最大轮次           ->  _finish_success / _finish_max_turns

顺带完成的清理:
    - #3  _turn_retry_count 改为实例属性，每轮开头重置（原为 query 级局部
          变量，整个会话只触发一次 turn-level retry）
    - #15 _prompt_retried / _ctx_warned 收编为实例属性，每个 query 开头
          重置（原先挂在 loop 裸属性上，跨 query 不重置）
"""

import logging
import time
from typing import Any, Dict, Optional, Tuple

from core.session_state import QueryResult
from core.loop.retry import classify_error, is_transient_error, is_server_error

logger = logging.getLogger(__name__)

# 输出截断恢复提示（finish_reason == "length" 时追加，引导 LLM 续写）
_OUTPUT_TRUNCATION_RECOVERY_MSG = (
    "Output token limit hit. Resume directly — no apology, "
    "no recap. Pick up mid-thought if that is where the cut happened. "
    "Break remaining work into smaller pieces."
)


class LoopOrchestrator:
    """Agent TAOR 主循环编排：轮次调度 / 预算守卫 / 错误恢复。"""

    # 连续服务器错误后触发 fallback
    _MAX_CONSECUTIVE_SERVER_ERRORS = 2

    def __init__(self, loop):
        self.loop = loop
        # per-query 重试 / 警告标志（#15：收编到此处，每个 query 重置，
        # 修复原先挂在 loop 裸属性上跨 query 不重置的问题）
        self._prompt_retried = False
        self._ctx_warned = False
        # 错误恢复计数器（#3：_turn_retry_count 每轮重置）
        self._turn_retry_count = 0
        self._consecutive_server_errors = 0

    # ========== 主循环 ==========

    def run(self, user_input: str) -> QueryResult:
        """
        主循环入口（原 AgentLoop._run_inner）。

        Args:
            user_input: 用户的自然语言指令

        Returns:
            QueryResult 结构化结果
        """
        loop = self.loop
        logger.info(f"Starting agent loop with input: {user_input[:50]}...")
        loop.state.start_query()

        # 重置 per-query 标志（#15）
        self._prompt_retried = False
        self._ctx_warned = False
        self._consecutive_server_errors = 0

        # 触发 UserMessage 钩子
        loop.events.fire_lifecycle_hook("UserMessage", {"user_input": user_input[:500]})

        # 1. 初始化消息（系统提示词 + 用户输入）
        loop.prompt_builder.init_messages(user_input)

        last_assistant_text = ""

        while loop.max_iterations is None or loop.state.turn_count < loop.max_iterations:
            loop.state.increment_turn()
            self._turn_retry_count = 0  # #3：轮次级瞬时错误重试计数，每轮重置
            if loop.max_iterations:
                logger.info(f"Turn {loop.state.turn_count}/{loop.max_iterations}")
            else:
                logger.info(f"Turn {loop.state.turn_count} (unlimited)")
            loop.events.emit("turn_start", {"turn": loop.state.turn_count})

            self._create_checkpoint()

            # 预算 / 中断守卫
            guard = self._check_budget_abort(last_assistant_text)
            if guard is not None:
                return guard

            try:
                self._run_context_maintenance()
                self._increment_plan_turn()

                # Step 1: 调用 LLM（流式输出）
                stream_result = loop.llm_client.call_streaming()
                assistant_content = stream_result.content
                active_m = loop.state.get_active_model(loop.model)
                loop.state.record_usage(stream_result.usage, model=active_m)

                # SessionTranscript: 记录费用
                loop.persistence.transcript_record_cost(active_m, stream_result.usage)

                # LLM 调用成功 → 重置连续服务器错误计数
                self._consecutive_server_errors = 0

                # 构建助手消息
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": assistant_content,
                }
                if stream_result.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in stream_result.tool_calls
                    ]
                loop.state.messages.append(assistant_msg)
                last_assistant_text = assistant_content or last_assistant_text

                # SessionTranscript: 记录助手消息
                loop.persistence.transcript_record_assistant(assistant_msg, active_m, stream_result.usage)

                loop.events.emit("turn_complete", {
                    "turn": loop.state.turn_count,
                    "content_preview": assistant_content[:200] if assistant_content else "",
                    "tool_calls": len(stream_result.tool_calls),
                })

                # 中断检查（流式后）
                if loop.state.is_aborted():
                    return loop.state.to_result(
                        status="aborted",
                        text=last_assistant_text,
                        stop_reason="aborted",
                    )

                # Step 3: 检查是否有工具调用
                if not stream_result.tool_calls:
                    # 无工具调用 → 检查输出是否被截断（max_output_tokens 恢复）
                    if stream_result.finish_reason == "length" and \
                            loop.state.output_truncation_count < loop.max_output_recovery_limit:
                        loop.state.output_truncation_count += 1
                        logger.info(
                            f"Output truncated, recovery attempt "
                            f"{loop.state.output_truncation_count}/{loop.max_output_recovery_limit}"
                        )
                        loop.state.messages.append({
                            "role": "user",
                            "content": _OUTPUT_TRUNCATION_RECOVERY_MSG,
                        })
                        continue  # 重试

                    # 任务完成
                    return self._finish_success(last_assistant_text)

                # 重置截断计数器（有工具调用说明输出正常结束）
                loop.state.output_truncation_count = 0

                # Step 4: 执行所有工具调用（并行/顺序批量调度 → ToolDispatcher）
                loop.tool_dispatcher.dispatch(stream_result.tool_calls)

                # Step 6: 继续循环
                # SessionMemory: 每轮结束后尝试更新记忆
                loop.persistence.update_session_memory_turn()

            except Exception as e:
                outcome = self._handle_turn_error(e, last_assistant_text)
                if outcome[0] == "continue":
                    continue
                return outcome[1]

        # 达到最大迭代次数
        return self._finish_max_turns(last_assistant_text)

    # ========== 守卫与检查点 ==========

    def _create_checkpoint(self):
        """Rewind 检查点：在每轮开始前保存消息快照。"""
        loop = self.loop
        try:
            from commands.builtin.rewind_command import get_checkpoint_manager
            get_checkpoint_manager().create_checkpoint(
                loop.state.turn_count,
                list(loop.state.messages),
            )
        except Exception:
            pass  # 检查点创建失败不影响主流程

    def _check_budget_abort(self, last_assistant_text: str) -> Optional[QueryResult]:
        """
        中断 + 预算守卫：返回 QueryResult 表示应当立即结束循环，返回 None 表示继续。

        包含：中断检查、token 预算、美元预算、SessionState 内置预算（向后兼容）。
        """
        loop = self.loop

        # 中断检查
        if loop.state.is_aborted():
            logger.info("Aborted by user")
            return loop.state.to_result(
                status="aborted",
                text=last_assistant_text,
                stop_reason="aborted",
            )

        # 1. Token 预算检查
        if loop.max_budget_tokens is not None:
            total_tokens = loop.state.total_usage.total_tokens
            if total_tokens >= loop.max_budget_tokens:
                logger.warning(f"Token budget exceeded: {total_tokens}/{loop.max_budget_tokens}")
                return loop.state.to_result(
                    status="error_max_tokens",
                    text=last_assistant_text,
                    error=f"超出 token 预算上限 {loop.max_budget_tokens} (已使用: {total_tokens})",
                    stop_reason="max_tokens_reached",
                )

        # 2. 美元预算检查
        if loop.max_budget_usd is not None:
            if loop.state.total_cost_usd >= loop.max_budget_usd:
                logger.warning(
                    f"USD budget exceeded: ${loop.state.total_cost_usd:.4f}/${loop.max_budget_usd:.4f}"
                )
                return loop.state.to_result(
                    status="error_max_budget",
                    text=last_assistant_text,
                    error=(
                        f"超出费用预算上限 ${loop.max_budget_usd:.4f} "
                        f"(已使用: ${loop.state.total_cost_usd:.4f})"
                    ),
                    stop_reason="max_budget_reached",
                )

        # 3. SessionState 内置预算检查（向后兼容）
        if loop.state.is_budget_exceeded():
            logger.warning(f"Budget exceeded: ${loop.state.total_cost_usd:.4f}")
            return loop.state.to_result(
                status="error_max_budget",
                text=last_assistant_text,
                error=f"超出预算上限 ${loop.state.max_budget_usd:.4f}",
            )

        return None

    # ========== 上下文维护 ==========

    def _run_context_maintenance(self):
        """
        上下文维护：超过阈值则全量压缩，否则轻量预清理 + 接近阈值警告。
        """
        loop = self.loop
        msg_count = len(loop.state.messages)
        if msg_count > loop.context_compact_threshold:
            loop.context_manager.compact()
            return

        # ContextWarning: 接近阈值时发出警告（每 query 一次）
        warn_threshold = int(loop.context_compact_threshold * 0.8)
        if msg_count > warn_threshold and msg_count > 8:
            if not self._ctx_warned:
                self._ctx_warned = True
                loop.events.fire_lifecycle_hook("ContextWarning", {
                    "message_count": msg_count,
                    "threshold": loop.context_compact_threshold,
                    "usage_pct": round(msg_count / loop.context_compact_threshold * 100),
                })
        # Microcompact: 轻量级预清理（在触发全量压缩之前运行）
        loop.context_manager.microcompact()
        # ContextCollapse: 折叠过时文件读取
        loop.context_manager.context_collapse()

    def _increment_plan_turn(self):
        """计划模式轮次递增（用于周期性提醒判断）。"""
        try:
            from tools.builtin.plan_mode import increment_plan_turn
            increment_plan_turn()
        except ImportError:
            pass

    # ========== 错误恢复 ==========

    def _handle_turn_error(self, e: Exception, last_assistant_text: str) -> Tuple[str, Optional[QueryResult]]:
        """
        处理单轮异常，按优先级尝试 4 套恢复策略。

        Returns:
            ("continue", None)     — 已触发重试/fallback，继续循环
            ("return", QueryResult) — 恢复手段耗尽，返回该结果结束
        """
        loop = self.loop
        error_str = str(e).lower()
        error_category = classify_error(e)
        logger.error(f"Turn {loop.state.turn_count} failed [{error_category}]: {e}", exc_info=True)

        # 1. Prompt-too-long 恢复: 压缩上下文后重试一次
        if error_category == 'prompt_too_long' or "context_length" in error_str or "too long" in error_str:
            if not self._prompt_retried:
                self._prompt_retried = True
                print("\n⚠️ 上下文过长，正在压缩后重试...")
                loop.context_manager.snip_old_tool_results()
                loop.context_manager.compact()
                loop.events.emit("prompt_too_long_recovery", {
                    "messages_before": len(loop.state.messages),
                })
                return ("continue", None)
            else:
                self._prompt_retried = False
                return ("return", loop.state.to_result(
                    status="error",
                    text=last_assistant_text,
                    error=f"上下文过长，压缩后仍无法处理: {e}",
                ))
        self._prompt_retried = False

        # 2. 瞬时网络错误（超时/服务器过载）— 轮次级重试
        # 注意: 速率限制 (429) 不做 turn-level retry，内层 call_streaming 已有
        # 10 次重试，足够覆盖速率窗口。此处仅处理服务器错误/超时/连接问题。
        if is_transient_error(e) and error_category != 'rate_limit' and self._turn_retry_count < 1:
            self._turn_retry_count += 1
            wait = 10  # 服务器错误统一等 10s
            error_label = "网络故障"
            logger.info(f"Transient error, turn-level retry in {wait:.0f}s: {e}")
            print(f"\n⚠️ API {error_label}，{wait:.0f}s 后重试当前轮次...")
            loop.events.emit("turn_retry", {
                "turn": loop.state.turn_count,
                "error": str(e),
                "wait_seconds": round(wait, 1),
                "category": error_category,
                "is_rate_limit": False,
            })
            time.sleep(wait)
            return ("continue", None)

        # 3. 连续服务器错误（5xx/529）→ 累计计数，触发 fallback 模型
        if is_server_error(e):
            self._consecutive_server_errors += 1
            logger.info(
                f"Consecutive server errors: {self._consecutive_server_errors}/"
                f"{self._MAX_CONSECUTIVE_SERVER_ERRORS}"
            )
            if (
                self._consecutive_server_errors >= self._MAX_CONSECUTIVE_SERVER_ERRORS
                and loop.state.fallback_model
                and not loop.state._active_model_override
            ):
                activated = loop.state.activate_fallback()
                if activated:
                    # 先保存计数用于显示，再归零（否则日志/事件永远显示 0 次）
                    error_count = self._consecutive_server_errors
                    self._consecutive_server_errors = 0
                    print(
                        f"\n⚠️ 主模型连续 {error_count} 次服务器错误，"
                        f"已切换到备用模型: {activated}"
                    )
                    loop.events.emit("fallback_activated", {
                        "model": activated,
                        "reason": f"连续 {error_count} 次服务器错误",
                    })
                    return ("continue", None)
        else:
            # 非服务器错误 → 重置连续计数
            self._consecutive_server_errors = 0

        # 4. Fallback 模型 — 其他 API 错误时尝试切换
        if loop.state.fallback_model and not loop.state._active_model_override:
            activated = loop.state.activate_fallback()
            if activated:
                print(f"\n⚠️ 主模型不可用，已切换到备用模型: {activated}")
                loop.events.emit("fallback_activated", {"model": activated})
                return ("continue", None)

        # 所有重试手段耗尽，返回错误
        return ("return", loop.state.to_result(
            status="error",
            text=last_assistant_text,
            error=str(e),
        ))

    # ========== 完成处理 ==========

    def _finish_success(self, last_assistant_text: str) -> QueryResult:
        """任务完成（无工具调用且输出未截断）。"""
        loop = self.loop
        logger.info("No tool calls, task completed")
        # 自动记忆提取
        loop.events.trigger_auto_memory_extraction()
        # 关闭会话持久化存储
        loop.persistence.close()

        # 生成会话总结（仅多轮对话时生成，单轮无需总结）
        summary = None
        if last_assistant_text and loop.state.turn_count > 1:
            summary = loop.summary_builder.build(last_assistant_text)

        return loop.state.to_result(
            status="success",
            text=last_assistant_text,
            stop_reason="end_turn",
            summary=summary,
        )

    def _finish_max_turns(self, last_assistant_text: str) -> QueryResult:
        """达到最大迭代次数（或无限循环异常终止）。"""
        loop = self.loop
        if loop.max_iterations:
            logger.warning(f"Reached max iterations: {loop.max_iterations}")
            error_msg = f"达到最大轮次 {loop.max_iterations}，任务未完成"
        else:
            logger.warning("Loop terminated (should not reach here with unlimited iterations)")
            error_msg = "循环异常终止"

        # 即使未完成任务，也尝试提取记忆（对话中可能有值得记录的信息）
        loop.events.trigger_auto_memory_extraction()
        # 关闭会话持久化存储
        loop.persistence.close()
        result = loop.state.to_result(
            status="error_max_turns",
            text=last_assistant_text,
            error=error_msg,
        )
        loop.events.fire_lifecycle_hook("Stop", {"status": result.status})
        return result
