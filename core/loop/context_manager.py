#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.context_manager — 多级上下文压缩

实现消息历史的分层压缩，在上下文接近模型窗口时释放 token：
    Level -1: ImageStrip       剥离大图片 / base64 / 超大工具结果
    Level 0 : Snip             裁剪旧工具输出
    Level 0.5: Microcompact    清除旧可丢弃工具结果
    Level 1 : ContextCollapse  折叠过时文件读取
    Level 2 : AutoCompact      LLM / 简单摘要替换旧消息
"""

import json
import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


class ContextManager:
    """多级上下文压缩器。"""

    # ImageStrip: 大内容阈值（超过此值的工具结果将被剥离 base64/大数据）
    IMAGE_STRIP_THRESHOLD = 8 * 1024  # 8KB

    # ========== Microcompact 常量 ==========

    # 可清除结果的工具（读类型 — 结果大但可丢弃）
    MICROCOMPACT_CLEARABLE_TOOLS = {
        "run_command", "run_powershell", "grep", "glob", "find",
        "read_file", "list_directory", "web_fetch", "web_search",
        "analyze_file", "lint", "run_tests", "lsp_tool",
    }

    # 可清除输入的工具（写类型 — 保留结果，清除旧输入）
    MICROCOMPACT_CLEARABLE_INPUTS = {
        "write_file", "replace_in_file",
    }

    MICROCOMPACT_CLEARED_MSG = "[result cleared to save context]"
    MICROCOMPACT_TRIGGER_MSGS = 12   # 消息数超过此值时触发
    MICROCOMPACT_KEEP_RECENT = 6     # 保留最近 N 个可清除工具的结果

    def __init__(self, loop):
        self.loop = loop

    def compact(self):
        """
        多级上下文压缩：Snip → Microcompact → ContextCollapse → LLM-driven AutoCompact。

        - Level 0: Snip — 裁剪旧工具输出
        - Level 0.5: Microcompact — 清除旧可丢弃工具结果
        - Level 1: ContextCollapse — 折叠过时文件读取
        - Level 2: AutoCompact — LLM 或简单摘要替换旧消息
        """
        loop = self.loop
        msgs = loop.state.messages
        if len(msgs) <= 4:
            return

        # 触发 PreCompact 钩子
        if loop.hooks_enabled:
            loop.events.fire_lifecycle_hook("PreCompact", {
                "message_count": len(msgs),
                "threshold": loop.context_compact_threshold,
            })

        # Level -1: ImageStrip — 剥离大图片和嵌入数据
        img_stripped = self.image_strip()
        if img_stripped:
            logger.info(f"ImageStrip removed {img_stripped} large content blocks")

        # 先执行 Snip
        self.snip_old_tool_results()

        # 再执行 Microcompact（在 AutoCompact 之前）
        mc_cleared = self.microcompact()
        if mc_cleared:
            logger.info(f"Microcompact cleared {mc_cleared} results before AutoCompact")

        # ContextCollapse: 折叠过时文件读取（在 AutoCompact 之前）
        cc_folded = self.context_collapse()
        if cc_folded:
            logger.info(f"ContextCollapse folded {cc_folded} stale reads before AutoCompact")

        # 保留系统提示词和最近消息
        keep_count = max(6, len(msgs) // 3)
        system_msg = msgs[0] if msgs[0].get("role") == "system" else None
        old_msgs = msgs[1:-keep_count]
        recent_msgs = msgs[-keep_count:]

        if not old_msgs:
            return

        # LLM 驱动摘要（优先）或简单摘要（降级）
        summary = self.compact_messages_llm(old_msgs)
        if not summary:
            return

        summary_text = (
            "[Auto-Compact Summary]\n"
            "以下是之前对话的压缩摘要（由 LLM 生成）:\n" + summary
        )

        # 重建消息列表
        new_msgs = []
        if system_msg:
            new_msgs.append(system_msg)
        new_msgs.append({"role": "user", "content": summary_text})
        new_msgs.append({"role": "assistant", "content": "好的，我已了解之前的对话内容，继续当前任务。"})
        new_msgs.extend(recent_msgs)

        old_count = len(msgs)
        loop.state.messages = new_msgs
        # compact 重建了消息列表,旧 _cc_file_ops 的 (msg_idx, ...) 全部失效
        # (FileChangeTracker 写、ContextCollapse 读)。清空避免后续 context_collapse
        # 用过期索引折叠到完全无关的消息上。
        if hasattr(loop, '_cc_file_ops'):
            loop._cc_file_ops.clear()
        logger.info(f"Context compacted: {old_count} -> {len(new_msgs)} messages")
        print(f"📦 上下文压缩: {old_count} -> {len(new_msgs)} 条消息")
        loop.events.emit("context_compacted", {
            "messages_before": old_count,
            "messages_after": len(new_msgs),
        })

        # 触发 PostCompact 钩子
        if loop.hooks_enabled:
            loop.events.fire_lifecycle_hook("PostCompact", {
                "messages_before": old_count,
                "messages_after": len(new_msgs),
                "mc_cleared": mc_cleared,
                "cc_folded": cc_folded,
            })

    def image_strip(self) -> int:
        """
        Level -1 - ImageStrip: 剥离消息中的大图片和 base64 数据。

        当上下文包含 base64 编码的图片或大型嵌入数据时，
        将其替换为占位符，释放 token 空间。

        Returns:
            剥离的消息数
        """
        import re
        msgs = self.loop.state.messages
        stripped = 0

        # base64 图片模式
        b64_pattern = re.compile(
            r'data:image/[^;]+;base64,[A-Za-z0-9+/=]{100,}'
        )

        for i, msg in enumerate(msgs):
            if msg.get("role") == "system":
                continue

            content = msg.get("content", "")
            if not isinstance(content, str):
                continue

            # 检查是否包含 base64 图片
            if b64_pattern.search(content):
                new_content = b64_pattern.sub(
                    "[image stripped]", content
                )
                if new_content != content:
                    msgs[i] = {**msg, "content": new_content}
                    stripped += 1
                    continue

            # 检查超大工具结果（可能是大型 JSON/diff）
            if msg.get("role") == "tool" and len(content) > self.IMAGE_STRIP_THRESHOLD:
                # 保留前 200 字符 + 后 200 字符
                preview_start = content[:200]
                preview_end = content[-200:]
                msgs[i] = {
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": (
                        f"{preview_start}\n"
                        f"... [image-stripped: {len(content)} chars] ...\n"
                        f"{preview_end}"
                    ),
                }
                stripped += 1

        if stripped > 0:
            logger.info(f"ImageStrip: stripped {stripped} messages")
        return stripped

    def snip_old_tool_results(self):
        """
        Level 0 - Snip: 激进裁剪旧的工具输出。

        保留最近 8 条消息完整内容，更早的 tool/assistant 消息
        只保留前 100 字符摘要。
        """
        msgs = self.loop.state.messages
        if len(msgs) <= 8:
            return

        snip_start = 1  # 跳过 system prompt
        snip_end = len(msgs) - 8
        snipped = 0

        for i in range(snip_start, snip_end):
            msg = msgs[i]
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                continue  # 永不裁剪 system

            if role == "tool" and len(content) > 100:
                msgs[i] = {
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": content[:100] + f"\n... [snipped {len(content)-100} chars]",
                }
                snipped += 1
            elif role == "assistant" and len(content) > 500:
                msgs[i] = {"role": "assistant", "content": content[:500] + "\n... [snipped]"}
                snipped += 1

        if snipped:
            logger.info(f"Snip: trimmed {snipped} old messages")

    def compact_messages_llm(self, old_msgs: List[Dict]) -> str:
        """
        Level 2 - LLM-driven summary: 用 LLM 生成旧消息的高质量摘要。
        """
        loop = self.loop
        try:
            # 构建摘要请求
            content_parts = []
            for m in old_msgs:
                role = m.get("role", "?")
                content = m.get("content", "")
                if content and role != "system":
                    truncated = content[:800] + "..." if len(content) > 800 else content
                    content_parts.append(f"[{role}]: {truncated}")

            if not content_parts:
                return ""

            summary_prompt = (
                "Summarize the following conversation history in Chinese. "
                "Focus on: key decisions made, files modified, errors encountered, "
                "and the current task state. Be concise but preserve critical details.\n\n"
                + "\n".join(content_parts)
            )

            active_model = loop.state.get_active_model(loop.model)
            resp = loop.client.chat.completions.create(
                model=active_model,
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.1,
                max_tokens=1000,
            )
            summary = resp.choices[0].message.content or ""
            if resp.usage:
                active_m = loop.state.get_active_model(loop.model)
                loop.state.record_usage(resp.usage, model=active_m)
            return summary

        except Exception as e:
            logger.warning(f"LLM summary failed, falling back to simple: {e}")
            # 降级为简单摘要
            parts = []
            for m in old_msgs:
                role = m.get("role", "?")
                content = m.get("content", "")
                if content:
                    parts.append(f"[{role}]: {content[:300]}..." if len(content) > 300 else f"[{role}]: {content}")
            return "\n".join(parts)

    def microcompact(self) -> int:
        """
        Level 0.5 - Microcompact: 清除旧工具结果内容，保留消息结构。

        - 识别可清除的工具（读类型：shell/grep/glob/read/web...）
        - 保留最近 keep_recent 个结果
        - 更早的结果替换为占位符文本
        - 不删除消息（不影响 tool_call_id 关联），只替换 content

        Returns:
            被清除的工具结果数量（0 表示无操作）
        """
        msgs = self.loop.state.messages
        if len(msgs) < self.MICROCOMPACT_TRIGGER_MSGS:
            return 0

        # 收集所有可清除的 tool 消息索引（按出现顺序）
        clearable_indices = []
        for i, msg in enumerate(msgs):
            if msg.get("role") != "tool":
                continue
            tool_call_id = msg.get("tool_call_id", "")
            # 查找对应的 assistant 消息以获取工具名
            tool_name = self._find_tool_name_for_result(tool_call_id)
            if tool_name in self.MICROCOMPACT_CLEARABLE_TOOLS:
                clearable_indices.append(i)

        if not clearable_indices:
            return 0

        # 保留最近 keep_recent 个，清除更早的
        keep_from = max(0, len(clearable_indices) - self.MICROCOMPACT_KEEP_RECENT)
        to_clear = clearable_indices[:keep_from]

        if not to_clear:
            return 0

        cleared = 0
        total_chars_saved = 0
        for idx in to_clear:
            msg = msgs[idx]
            content = msg.get("content", "")
            if content == self.MICROCOMPACT_CLEARED_MSG:
                continue  # 已清除
            total_chars_saved += len(content)
            msgs[idx] = {
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": self.MICROCOMPACT_CLEARED_MSG,
            }
            cleared += 1

        # 同时清除旧 write/replace 工具调用的 arguments（保留工具名和 ID）
        inputs_cleared = self._microcompact_old_tool_inputs(to_clear)

        if cleared > 0:
            logger.info(
                f"Microcompact: cleared {cleared} tool results "
                f"(~{total_chars_saved} chars saved) + {inputs_cleared} tool inputs"
            )

        return cleared

    def _microcompact_old_tool_inputs(self, cleared_result_indices: List[int]) -> int:
        """
        清除旧 write/replace 工具调用的 arguments（大文件内容）。

        保留 tool_call_id 和工具名，将 arguments 替换为摘要。
        """
        msgs = self.loop.state.messages
        cleared = 0
        max_result_idx = max(cleared_result_indices) if cleared_result_indices else 0

        # 扫描 assistant 消息中的工具调用
        for i, msg in enumerate(msgs):
            if msg.get("role") != "assistant":
                continue
            if i >= max_result_idx:
                break  # 只处理被清除结果之前的消息

            tool_calls = msg.get("tool_calls", [])
            if not tool_calls:
                continue

            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name", "")
                if name in self.MICROCOMPACT_CLEARABLE_INPUTS:
                    args = func.get("arguments", "")
                    if len(args) > 200:
                        # 保留文件路径，清除文件内容
                        try:
                            args_dict = json.loads(args)
                            path = args_dict.get("file_path", args_dict.get("path", "?"))
                            func["arguments"] = json.dumps({
                                "file_path": path,
                                "_note": "[input cleared to save context]",
                            })
                            cleared += 1
                        except (json.JSONDecodeError, TypeError):
                            pass
        return cleared

    def _find_tool_name_for_result(self, tool_call_id: str) -> str:
        """根据 tool_call_id 查找对应 assistant 消息中的工具名"""
        for msg in self.loop.state.messages:
            if msg.get("role") != "assistant":
                continue
            for tc in msg.get("tool_calls", []):
                if tc.get("id") == tool_call_id:
                    return tc.get("function", {}).get("name", "")
        return ""

    def context_collapse(self) -> int:
        """
        Level 1 - ContextCollapse: 折叠过时文件读取结果。

        当文件先被 read_file 读取、后被 write_file/replace_in_file 修改时，
        旧的读取结果已不再有意义，将其折叠为简短摘要。

        - 读时投影：在发送给 LLM 前替换旧消息
        - 保留文件元信息（路径、行数），清除完整文件内容

        Returns:
            折叠的消息数
        """
        loop = self.loop
        if not hasattr(loop, '_cc_file_ops') or not loop._cc_file_ops:
            return 0

        msgs = loop.state.messages
        if len(msgs) < 8:
            return 0

        # 构建「哪些文件被后续写入」的集合
        # 以及每个文件最后一次写入的消息索引
        written_files: Dict[str, List[int]] = {}  # {abs_path: [write_msg_indices]}
        read_entries: List[tuple] = []  # [(msg_idx, abs_path)]

        for op_idx, op_type, op_path in loop._cc_file_ops:
            if op_type == "write":
                written_files.setdefault(op_path, []).append(op_idx)
            elif op_type == "read":
                read_entries.append((op_idx, op_path))

        if not written_files or not read_entries:
            return 0

        collapsed = 0
        for read_idx, read_path in read_entries:
            # 只处理 read_file 的 tool 消息
            if read_idx >= len(msgs):
                continue
            msg = msgs[read_idx]
            if msg.get("role") != "tool":
                continue

            # 检查此文件是否在读取之后被写入
            write_indices = written_files.get(read_path, [])
            subsequent_writes = [w for w in write_indices if w > read_idx]
            if not subsequent_writes:
                continue  # 文件未被后续修改，保留原始内容

            # 检查是否已被折叠
            content = msg.get("content", "")
            if content.startswith("[collapsed:"):
                continue

            # 计算折叠摘要
            lines_info = ""
            if "总行数:" in content:
                # 从元信息头提取行数
                try:
                    lines_part = content.split("总行数:")[1].split("|")[0].split("]")[0]
                    lines_info = f", {lines_part.strip()} 行"
                except (IndexError, ValueError):
                    pass

            n_writes = len(subsequent_writes)
            filename = os.path.basename(read_path)
            collapse_msg = (
                f"[collapsed: {filename}{lines_info}, "
                f"subsequently modified {n_writes} time(s)]"
            )

            msgs[read_idx] = {
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": collapse_msg,
            }
            collapsed += 1

        if collapsed > 0:
            logger.info(f"ContextCollapse: folded {collapsed} stale file read(s)")
        return collapsed
