#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.events — 事件回调 / 生命周期钩子 / LLM 日志 / 结果元数据

横切关注点：被主循环、工具执行、上下文压缩等多处调用，因此最先稳定。
通过 ``loop`` 访问共享状态（``loop.event_callback`` / ``loop.state`` /
``loop.hook_manager`` …）。
"""

import asyncio
import logging
import os
import threading
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class EventEmitter:
    """集中处理对外事件回调、生命周期钩子与 LLM 调试日志。"""

    def __init__(self, loop):
        self.loop = loop

    # ========== 事件回调 ==========

    def emit(self, event_type: str, data: Dict[str, Any] = None):
        """
        发射事件回调（供 Bridge、日志等外部系统订阅）。

        参考 QueryEngine 的 AsyncGenerator yield 机制。

        Args:
            event_type: 事件类型 (turn_start/turn_complete/tool_execute/
                        tool_complete/error/aborted/context_compacted/...)
            data: 事件数据
        """
        if self.loop.event_callback is None:
            return
        try:
            event = {
                "type": event_type,
                "data": data or {},
                "timestamp": time.time(),
                "turn": self.loop.state.turn_count,
            }
            self.loop.event_callback(event)
        except Exception as e:
            logger.warning(f"Event callback failed for {event_type}: {e}")

    def emit_text_chunk(self, content: str):
        """
        发射文本块事件（Token 级流式输出）。

        用于 Bridge 模式实现实时打字机效果。
        CLI 模式下 event_callback 为 None，自动跳过。

        Args:
            content: 文本内容（单个 token 或小块）
        """
        if self.loop.event_callback is None:
            return  # CLI 模式不使用
        try:
            event = {
                "type": "text_chunk",
                "data": {
                    "content": content,
                    "turn": self.loop.state.turn_count,
                },
                "timestamp": time.time(),
                "turn": self.loop.state.turn_count,
            }
            self.loop.event_callback(event)
        except Exception as e:
            # text_chunk 失败不影响主流程
            logger.debug(f"Text chunk emit failed: {e}")

    def fire_lifecycle_hook(self, event: str, kwargs: Dict[str, Any] = None):
        """
        触发生命周期钩子（同步封装）。

        用于 Stop/SessionEnd/UserMessage/Notification 等非工具类钩子。
        """
        if not self.loop.hooks_enabled or not self.loop.hook_manager:
            return
        try:
            evloop = asyncio.new_event_loop()
            asyncio.set_event_loop(evloop)
            evloop.run_until_complete(
                self.loop.hook_manager.execute_hooks(event, **(kwargs or {}))
            )
            evloop.close()
        except Exception as e:
            logger.warning(f"Lifecycle hook {event} failed: {e}")

    # ========== LLM 调试日志 ==========

    def write_llm_log(self, direction: str, model: str, attempt: int, data: Dict[str, Any] = None):
        """
        将 LLM 请求/响应写入调试日志文件（后台线程异步写入，避免阻塞流式主循环）。
        日志写入工作目录下的 .auraCode/llm_calls.log

        Args:
            direction: "REQUEST" 或 "RESPONSE"
            model: 使用的模型名称
            attempt: 重试次数
            data: 附加数据（响应时包含 finish_reason, content_preview 等）
        """
        loop = self.loop
        try:
            # 在调用线程快照可变状态，避免后台线程读到被主线程改写的列表
            snapshot = {
                "project_root": loop.project_root or os.getcwd(),
                "session_id": getattr(loop, '_session_id', '') or str(id(loop))[:8],
                "turn": loop.state.turn_count,
                "messages": list(loop.messages),      # 浅拷贝引用，迭代安全
                "tools": list(loop.tools) if loop.tools else [],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "date_str": time.strftime("%Y-%m-%d"),
            }
        except Exception as e:
            logger.warning(f"Failed to snapshot for LLM log: {e}")
            return

        def _write():
            try:
                log_dir = os.path.join(snapshot["project_root"], ".auraCode")
                os.makedirs(log_dir, exist_ok=True)
                # 日志文件名: llm_{session_id}_{date}.log (同一会话同一天写入同一文件)
                log_file = os.path.join(
                    log_dir, f'llm_{snapshot["session_id"]}_{snapshot["date_str"]}.log'
                )

                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(
                        f'[{snapshot["timestamp"]}] {direction} | '
                        f'turn={snapshot["turn"]} | attempt={attempt} | model={model}\n'
                    )
                    f.write(f"{'='*80}\n")

                    if direction == "REQUEST":
                        # 写入请求信息
                        msgs = snapshot["messages"]
                        f.write(f"\n--- MESSAGES ({len(msgs)} total) ---\n")
                        for i, msg in enumerate(msgs):
                            role = msg.get("role", "?")
                            content = msg.get("content", "")
                            if isinstance(content, str):
                                content_preview = content[:500] + ("..." if len(content) > 500 else "")
                            else:
                                content_preview = str(content)[:500]
                            f.write(f"\n[{i}] role={role}\n{content_preview}\n")

                            # 工具调用
                            tool_calls = msg.get("tool_calls", [])
                            if tool_calls:
                                f.write(f"  tool_calls: {len(tool_calls)}\n")
                                for tc in tool_calls:
                                    func = tc.get("function", {}) if isinstance(tc, dict) else {}
                                    f.write(f"    - {func.get('name', '?')}\n")

                        # 工具定义数量
                        tools = snapshot["tools"]
                        if tools:
                            f.write(f"\n--- TOOLS ({len(tools)} defined) ---\n")
                            tool_names = [t.get("function", {}).get("name", "?") for t in tools]
                            f.write(f"  {', '.join(tool_names)}\n")

                    elif direction == "RESPONSE" and data:
                        f.write(f"\n--- RESPONSE ---\n")
                        f.write(f"finish_reason: {data.get('finish_reason', '?')}\n")
                        f.write(f"duration: {data.get('duration_ms', 0)}ms\n")
                        f.write(f"tokens: prompt={data.get('prompt_tokens', 0)}, completion={data.get('completion_tokens', 0)}\n")
                        f.write(f"tool_calls: {data.get('tool_calls', 0)} ({', '.join(data.get('tool_names', []))})\n")
                        f.write(f"\n--- CONTENT PREVIEW ---\n")
                        f.write(data.get('content_preview', '')[:2000])
                        f.write("\n")

                logger.debug(f"LLM log written to {log_file}")
            except Exception as e:
                logger.warning(f"Failed to write LLM log: {e}")

        # 后台线程写入，不阻塞流式主循环（best-effort，daemon 线程进程退出时自动结束）
        threading.Thread(target=_write, daemon=True).start()

    # ========== 结果元数据 ==========

    def build_result_metadata(self, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        从工具结果中提取元数据（供前端显示上下文信息）。

        返回包含 size/lines/char_count/truncated 等字段的字典。
        """
        meta = {}
        try:
            result = tool_result.get("result")
            if result is None:
                return meta

            if isinstance(result, str):
                meta["char_count"] = len(result)
                lines = result.splitlines()
                meta["line_count"] = len(lines)
                # 检测是否被截断
                if "truncated" in result.lower() or "... (截断" in result:
                    meta["truncated"] = True
                # 检测文件数量（搜索结果）
                if "个文件" in result or "files found" in result.lower():
                    import re
                    m = re.search(r'(\d+)\s*(?:个文件|files)', result)
                    if m:
                        meta["file_count"] = int(m.group(1))
                # 检测匹配数量（grep 结果）
                if "个匹配" in result or "matches" in result.lower():
                    import re
                    m = re.search(r'(\d+)\s*(?:个匹配|matches)', result)
                    if m:
                        meta["match_count"] = int(m.group(1))
            elif isinstance(result, dict):
                # 某些工具直接返回字典
                if "size" in result:
                    meta["size"] = result["size"]
                if "lines" in result:
                    meta["lines"] = result["lines"]
                if "file_count" in result:
                    meta["file_count"] = result["file_count"]
        except Exception as e:
            logger.debug(f"Failed to build result metadata: {e}")
        return meta

    # ========== 自动记忆提取 ==========

    def trigger_auto_memory_extraction(self):
        """
        触发后台自动记忆提取。

        在 query loop 结束时调用（任务完成 / 达到最大轮次），
        后台线程分析对话记录并提取值得跨会话保留的信息。
        """
        if not self.loop.auto_memory_extractor:
            return
        try:
            self.loop.auto_memory_extractor.request_extraction(
                messages=list(self.loop.state.messages),
                is_background=True,
            )
        except Exception as e:
            # 记忆提取是 best-effort，不影响主流程
            logger.warning(f"Auto-memory extraction request failed: {e}")
