#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
自动记忆提取引擎

设计理念:
- 每轮 query loop 结束时（LLM 产生最终回复、无工具调用）自动运行
- 使用 LLM 分析对话记录，提取值得跨会话保留的信息
- 互斥机制: 主 Agent 在本轮已写入记忆文件 → 跳过后台提取
- 节流控制: 可配置每 N 轮才执行一次提取
- 后台线程运行: 不阻塞主响应返回

触发时机:
    agent_loop.run() → 无工具调用 → 任务完成 → _extract_memories_background()

用法:
    extractor = AutoMemoryExtractor(memory_manager, llm_client, model)
    # 在 run() 成功完成时调用:
    extractor.request_extraction(messages, is_background=True)
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.memory import (
    MemoryManager,
    scan_memory_files,
    format_memory_manifest,
    MEMORY_TYPES,
)

logger = logging.getLogger(__name__)


# ── 提取系统提示词 ──────────────────────────────────────────

_EXTRACT_SYSTEM_PROMPT = """\
You are a memory extraction agent. Analyze the conversation transcript and \
identify information worth remembering for future sessions.

## What to extract

Focus on these four types of durable, cross-session information:

1. **user** — Role, goals, responsibilities, knowledge level, preferences.
   Example: "User is a data scientist focused on observability", "10 years Go experience"

2. **feedback** — Guidance the user gave about HOW to work (both corrections and confirmations).
   Include *why* so future sessions can judge edge cases.
   Example: "Integration tests must use real databases, never mock", "User prefers concise responses"

3. **project** — Ongoing work, goals, deadlines, team info NOT derivable from code/git.
   Convert relative dates to absolute dates.
   Example: "Merge freeze after 2026-03-05 for mobile release"

4. **reference** — Pointers to external systems (bug trackers, dashboards, docs).
   Example: "Bug tracking in Linear INGEST project"

## What NOT to extract

- Code patterns, conventions, architecture — derivable from the project
- Git history, recent changes — `git log` is authoritative
- Debugging solutions — the fix is in the code
- Ephemeral task details, in-progress work, current conversation context
- Anything already documented in project config files

## Existing memories

Check the existing memory manifest below. Do NOT create duplicates.
If an existing memory should be updated (e.g., information has changed), include it with action="update".
If an existing memory is now wrong or outdated, include it with action="delete".

## Output format

Return a JSON object with this exact schema:
```json
{
  "memories": [
    {
      "action": "save",
      "type": "user|feedback|project|reference",
      "title": "short descriptive title",
      "content": "detailed content with Why and How-to-apply for feedback/project types"
    }
  ]
}
```

- "action" must be one of: "save", "update", "delete"
- For "update"/"delete", "title" must match an existing memory title exactly.
- Keep "content" concise — under 200 words per memory.
- If nothing worth extracting was found, return `{"memories": []}`.
- Be selective. Only extract information you are CERTAIN is worth remembering.
"""


def _build_extraction_prompt(
    new_message_count: int,
    existing_manifest: str,
    transcript_summary: str,
) -> str:
    """构建提取请求的用户提示词"""
    parts = [
        f"Analyze the following conversation ({new_message_count} new messages) "
        "and extract any durable memories worth remembering.",
        "",
    ]

    if existing_manifest:
        parts.extend([
            "## Existing memories",
            "",
            existing_manifest,
            "",
        ])
    else:
        parts.extend([
            "## Existing memories",
            "",
            "(No existing memories)",
            "",
        ])

    parts.extend([
        "## Conversation transcript (recent messages)",
        "",
        transcript_summary,
        "",
        "Return your analysis as JSON.",
    ])

    return "\n".join(parts)


def _summarize_messages(
    messages: List[Dict[str, Any]],
    since_index: int = 0,
    max_chars: int = 8000,
) -> str:
    """
    将消息列表压缩为文本摘要（供提取 LLM 阅读）。
    只取 since_index 之后的消息，总长度限制在 max_chars 以内。
    """
    relevant = messages[since_index:]
    lines = []
    total = 0

    for msg in relevant:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        # 跳过系统消息（已在 system prompt 中）
        if role == "system":
            continue

        # 工具调用结果：只保留工具名和简短结果
        if role == "tool":
            tool_call_id = msg.get("tool_call_id", "")
            # 截断过长的工具输出
            if len(str(content)) > 300:
                content = str(content)[:300] + "... [truncated]"
            lines.append(f"[{role}] (tool_call_id={tool_call_id}): {content}")
        elif role == "assistant" and msg.get("tool_calls"):
            # 助手消息带工具调用：只记录调用了什么工具
            tool_names = [
                tc.get("function", {}).get("name", "?")
                for tc in msg.get("tool_calls", [])
            ]
            text_preview = str(content)[:200] if content else ""
            lines.append(
                f"[{role}] Called tools: {', '.join(tool_names)}. "
                f"Text: {text_preview}"
            )
        else:
            # 普通消息：截断到 500 字符
            preview = str(content)[:500]
            lines.append(f"[{role}]: {preview}")

        total = sum(len(l) for l in lines)
        if total > max_chars:
            lines.append("... [transcript truncated for brevity]")
            break

    return "\n".join(lines)


class AutoMemoryExtractor:
    """
    自动记忆提取器

    参考标准 extractMemories 的 initExtractMemories() + runExtraction()。
    使用闭包状态跟踪: 上次处理的消息索引、提取节流计数、防重入锁。

    触发方式:
    - AgentLoop.run() 成功完成时调用 request_extraction()
    - 可选后台线程运行（不阻塞主响应）
    """

    def __init__(
        self,
        memory_manager: MemoryManager,
        llm_client=None,
        llm_model: str = None,
        min_turns_between: int = 1,
    ):
        """
        Args:
            memory_manager: 记忆管理器实例
            llm_client: OpenAI 客户端
            llm_model: 模型名称
            min_turns_between: 最少间隔轮次（1 = 每轮都提取，2 = 隔一轮提取）
        """
        self.memory_manager = memory_manager
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.min_turns_between = max(1, min_turns_between)

        # 闭包状态（对应 extractMemories.ts 的闭包变量）
        self._last_processed_index: int = 0  # 上次处理到的消息索引
        self._turns_since_extraction: int = 0  # 距上次提取的轮次计数
        self._in_progress: bool = False  # 防重入锁
        self._lock = threading.Lock()

        # 统计
        self.total_extractions = 0
        self.total_memories_saved = 0

        logger.info(
            f"AutoMemoryExtractor initialized (min_turns={self.min_turns_between})"
        )

    def request_extraction(
        self,
        messages: List[Dict[str, Any]],
        is_background: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        请求执行记忆提取（对应 executeExtractMemories）。

        Args:
            messages: 完整消息历史
            is_background: True=后台线程运行, False=同步阻塞

        Returns:
            同步模式返回提取结果 dict，后台模式返回 None
        """
        if not self.llm_client or not self.llm_model:
            logger.debug("Auto-memory skipped: no LLM client/model")
            return None

        # 防重入
        if self._in_progress:
            logger.debug("Auto-memory skipped: extraction already in progress")
            return None

        # 节流检查
        self._turns_since_extraction += 1
        if self._turns_since_extraction < self.min_turns_between:
            return None

        # 计算新消息数量
        new_count = len(messages) - self._last_processed_index
        if new_count < 2:  # 至少需要 2 条新消息才有意义
            return None

        if is_background:
            thread = threading.Thread(
                target=self._run_extraction_safe,
                args=(list(messages),),  # 复制消息列表，避免并发修改
                daemon=True,
                name="auto-memory-extract",
            )
            thread.start()
            return None
        else:
            return self._run_extraction_safe(messages)

    def _run_extraction_safe(
        self, messages: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """安全包装的提取执行（捕获所有异常）"""
        with self._lock:
            if self._in_progress:
                return None
            self._in_progress = True

        try:
            result = self._run_extraction(messages)
            return result
        except Exception as e:
            # 提取是 best-effort，失败不影响主流程
            logger.warning(f"Auto-memory extraction failed: {e}")
            return None
        finally:
            with self._lock:
                self._in_progress = False

    def _run_extraction(
        self, messages: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        执行记忆提取。

        流程:
        1. 检查主 Agent 是否已在本轮写入记忆（互斥）
        2. 扫描现有记忆 → 生成清单
        3. 压缩对话记录为摘要
        4. 调用 LLM 分析 → 返回要保存的记忆
        5. 通过 MemoryManager 写入
        """
        start_time = time.time()
        since_index = self._last_processed_index
        new_count = len(messages) - since_index

        logger.info(
            f"Auto-memory extraction starting: {new_count} new messages "
            f"(since index {since_index})"
        )

        # ── 1. 互斥检查: 主 Agent 是否已在本轮写入记忆 ──
        if self._main_agent_wrote_memories(messages, since_index):
            logger.info(
                "Auto-memory skipped: main agent already wrote memories this turn"
            )
            self._last_processed_index = len(messages)
            self._turns_since_extraction = 0
            return {"skipped": True, "reason": "main_agent_wrote"}

        # ── 2. 扫描现有记忆 ──
        headers = scan_memory_files(self.memory_manager.memory_dir)
        existing_manifest = format_memory_manifest(headers) if headers else ""

        # ── 3. 压缩对话记录 ──
        transcript = _summarize_messages(messages, since_index=since_index)

        # ── 4. 调用 LLM 分析 ──
        user_prompt = _build_extraction_prompt(
            new_count, existing_manifest, transcript
        )

        try:
            resp = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=2048,
                temperature=0.0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "extracted_memories",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "memories": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "action": {
                                                "type": "string",
                                                "enum": ["save", "update", "delete"],
                                            },
                                            "type": {
                                                "type": "string",
                                                "enum": list(MEMORY_TYPES.keys()),
                                            },
                                            "title": {"type": "string"},
                                            "content": {"type": "string"},
                                        },
                                        "required": ["action", "type", "title"],
                                        "additionalProperties": False,
                                    },
                                }
                            },
                            "required": ["memories"],
                            "additionalProperties": False,
                        },
                    },
                },
            )

            text = resp.choices[0].message.content
            if not text:
                logger.info("Auto-memory: LLM returned empty response")
                self._last_processed_index = len(messages)
                self._turns_since_extraction = 0
                return {"saved": 0, "duration_ms": 0}

            parsed = self._parse_llm_json(text)
            if parsed is None:
                logger.warning(f"Auto-memory: failed to parse LLM response as JSON (first 200 chars): {text[:200]!r}")
                # 不推进游标，下次重试
                return None
            memory_actions = parsed.get("memories", [])

        except Exception as e:
            logger.warning(f"Auto-memory LLM call failed: {e}")
            # 不推进游标，下次重试
            return None

        # ── 5. 执行记忆操作 ──
        saved_count = 0
        for mem in memory_actions:
            action = mem.get("action", "save")
            mem_type = mem.get("type")
            title = mem.get("title", "")
            content = mem.get("content", "")

            if not title:
                continue

            try:
                if action == "save":
                    success = self.memory_manager.save_memory(
                        mem_type, title, content
                    )
                    if success:
                        saved_count += 1
                        logger.info(f"Auto-memory saved: {mem_type}/{title}")

                elif action == "update":
                    # 先删旧的，再存新的
                    self.memory_manager.delete_memory(mem_type, title)
                    self.memory_manager.save_memory(mem_type, title, content)
                    saved_count += 1
                    logger.info(f"Auto-memory updated: {mem_type}/{title}")

                elif action == "delete":
                    self.memory_manager.delete_memory(mem_type, title)
                    logger.info(f"Auto-memory deleted: {mem_type}/{title}")

            except Exception as e:
                logger.warning(f"Auto-memory action failed ({action} {title}): {e}")

        # ── 6. 更新状态 ──
        duration_ms = int((time.time() - start_time) * 1000)
        self._last_processed_index = len(messages)
        self._turns_since_extraction = 0
        self.total_extractions += 1
        self.total_memories_saved += saved_count

        if saved_count > 0:
            print(f"\n💾 自动提取了 {saved_count} 条记忆 ({duration_ms}ms)")

        logger.info(
            f"Auto-memory extraction complete: {saved_count} saved, "
            f"{len(memory_actions)} total actions, {duration_ms}ms"
        )

        return {
            "saved": saved_count,
            "total_actions": len(memory_actions),
            "duration_ms": duration_ms,
        }

    def _main_agent_wrote_memories(
        self,
        messages: List[Dict[str, Any]],
        since_index: int,
    ) -> bool:
        """
        检查主 Agent 在本轮是否已通过 save_memory 工具写入了记忆。
        对应 hasMemoryWritesSince()。

        检查方式:
        1. 查看 tool_calls 中是否有 save_memory 调用
        2. 查看 tool 结果中是否有 save_memory 成功响应
        """
        for msg in messages[since_index:]:
            # 检查助手的工具调用
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    if fn.get("name") == "save_memory":
                        return True

            # 检查工具结果中的 save_memory 成功标记
            if msg.get("role") == "tool":
                content = str(msg.get("content", ""))
                if "save_memory" in content.lower() and "success" in content.lower():
                    return True

        return False

    @staticmethod
    def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
        """
        容错解析 LLM 返回的 JSON。

        LLM 可能返回以下格式：
        1. 纯 JSON: {"memories": [...]}
        2. Markdown包裹: ```json\n{"memories": [...]}\n```
        3. 文本+JSON混合: ...some text... {"memories": [...]} ...more text...

        Returns:
            解析后的字典，或 None（解析失败时）
        """
        import re

        text = text.strip()
        if not text:
            return None

        # 尝试 1: 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试 2: 剥离 markdown 代码块
        md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if md_match:
            try:
                return json.loads(md_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试 3: 查找第一个 { ... } 块
        brace_start = text.find('{')
        if brace_start >= 0:
            # 从后向前找最后一个 }
            brace_end = text.rfind('}')
            if brace_end > brace_start:
                candidate = text[brace_start:brace_end + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass

        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取提取器统计信息"""
        return {
            "total_extractions": self.total_extractions,
            "total_memories_saved": self.total_memories_saved,
            "last_processed_index": self._last_processed_index,
            "turns_since_extraction": self._turns_since_extraction,
            "in_progress": self._in_progress,
        }
