#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.tool_dispatcher — 工具调用批量调度

从 ``AgentLoop._run_inner`` 提取的工具调度逻辑(原 Step 4,约 90 行):
    - 连续的只读工具批量化并行(ThreadPoolExecutor)
    - 写入/执行类工具顺序执行
    - 结果按 OpenAI 规范以 ``role=tool`` 写入消息历史(按原始顺序)

与 ``ToolExecutor``(单工具生命周期:钩子/权限/缓存)的区别:
本类只负责「调度多个工具何时并行 / 何时顺序」与「统一记录结果」。

旧逻辑 → 新位置:
    AgentLoop._run_inner 的 Step 4 工具批量调度段  ->  ToolDispatcher.dispatch
    (并行/顺序两分支重复的结果记录)              ->  ToolDispatcher._record

顺带完成的清理:
    - #10  parallel_safe 集合提为类常量 PARALLEL_SAFE_TOOLS(避免每轮重建)
    - #6   并行分支补发 tool_execute 事件(与顺序分支行为一致)
    - #16  抽取 _record 消除并行/顺序两分支的重复结果记录逻辑
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ToolDispatcher:
    """工具调用的批量调度:并行/顺序分批执行 + 结果统一记录。"""

    # 可并行执行的只读工具(只读 → 无副作用 → 可安全并行)
    PARALLEL_SAFE_TOOLS = frozenset({
        "read_file", "list_directory", "grep", "find",
        "glob_tool", "search_code", "web_fetch", "web_search",
        "tool_search", "sleep", "get_relevant_memories",
        "list_memories", "lsp_tool", "brief_tool",
        "task_get", "task_list",
    })

    MAX_PARALLEL_WORKERS = 8

    def __init__(self, loop):
        self.loop = loop

    def dispatch(self, tool_calls_list: List[Any]) -> None:
        """
        执行一批工具调用。

        连续的只读工具批量化并行,写入/执行类工具顺序执行。
        结果按 OpenAI 规范以 ``role=tool`` 写入消息历史(按原始顺序)。
        """
        loop = self.loop

        # 将工具调用分组: 连续的只读工具批量化并行,其他顺序执行
        batches = []
        current_batch = []
        for tc in tool_calls_list:
            if tc.function.name in self.PARALLEL_SAFE_TOOLS:
                current_batch.append(tc)
            else:
                if current_batch:
                    batches.append(("parallel", current_batch))
                    current_batch = []
                batches.append(("sequential", [tc]))
        if current_batch:
            batches.append(("parallel", current_batch))

        for batch_type, batch_calls in batches:
            if loop.state.is_aborted():
                break

            if batch_type == "parallel" and len(batch_calls) > 1:
                self._run_parallel(batch_calls)
            else:
                # 单个只读工具或写入/执行类工具 → 顺序执行
                self._run_sequential(batch_calls)

    def _run_parallel(self, batch_calls: List[Any]) -> None:
        """并行执行多个只读工具,完成后按原始顺序写入消息。"""
        loop = self.loop
        loop.events.status(f"⚡ 并行执行 {len(batch_calls)} 个工具...")

        results_map: Dict[str, tuple] = {}
        with ThreadPoolExecutor(max_workers=min(len(batch_calls), self.MAX_PARALLEL_WORKERS)) as executor:
            futures = {
                executor.submit(loop.tool_executor.execute, tc): tc
                for tc in batch_calls
            }
            for future in as_completed(futures):
                tc = futures[future]
                try:
                    result = future.result()
                except Exception as ex:
                    result = {"success": False, "error": str(ex)}
                results_map[tc.id] = (tc, result)

        # 按原始顺序写入消息(保证 OpenAI 规范)
        for tc in batch_calls:
            if tc.id in results_map:
                tc_obj, tool_result = results_map[tc.id]
            else:
                tc_obj, tool_result = tc, {"success": False, "error": "并行执行超时"}

            # 并行分支也补发 tool_execute 事件(#6),与顺序分支行为一致
            loop.events.emit("tool_execute", {"tool_name": tc_obj.function.name})
            self._record(tc_obj, tool_result)

    def _run_sequential(self, batch_calls: List[Any]) -> None:
        """顺序执行(写入/执行类工具或单个工具)。"""
        loop = self.loop
        for tool_call in batch_calls:
            if loop.state.is_aborted():
                break

            loop.events.emit("tool_execute", {"tool_name": tool_call.function.name})
            tool_result = loop.tool_executor.execute(tool_call)
            self._record(tool_call, tool_result)

    def _record(self, tool_call, tool_result: Dict[str, Any]) -> None:
        """
        统一记录工具结果(并行/顺序共用,#16 去重):
        构建元数据 → emit tool_complete → 写 role=tool 消息 → 打印。

        失败时附加 recovery_hint(StopHook 恢复),让 LLM 尝试替代方案。
        """
        loop = self.loop
        # 构建结果元数据(供前端显示上下文信息)
        result_meta = loop.events.build_result_metadata(tool_result)
        loop.events.emit("tool_complete", {
            "tool_name": tool_call.function.name,
            "success": tool_result.get("success", False),
            "result": result_meta,
        })

        # 工具结果以 role=tool 返回(OpenAI 规范)
        if tool_result.get("success"):
            result_content = tool_result.get("result")
        else:
            result_content = f"Error: {tool_result.get('error')}"
            # StopHook 恢复: 附加恢复提示让 LLM 尝试替代方案
            recovery = tool_result.get("recovery_hint")
            if recovery:
                result_content += f"\n\nHint: {recovery}"

        loop.state.messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result_content),
        })

        # 打印工具执行结果
        status_icon = "✅" if tool_result.get("success") else "❌"
        loop.events.status(
            f"{status_icon} [{tool_call.function.name}] {str(result_content)[:200]}",
            kind="success" if tool_result.get("success") else "error",
        )
