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
import re
from typing import Dict, List

from core.tool_categories import FILE_WRITE_TOOLS

logger = logging.getLogger(__name__)

# read_file 结果的行范围元信息头: "[path: lines 1-120 of 617]"
_READ_RANGE_RE = re.compile(r'lines (\d+)-(\d+) of (\d+)')


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
    MICROCOMPACT_CLEARABLE_INPUTS = FILE_WRITE_TOOLS

    MICROCOMPACT_CLEARED_MSG = "[result cleared to save context]"
    MICROCOMPACT_TRIGGER_MSGS = 12   # 消息数超过此值时触发
    # 保留最近 N 个可清除工具的结果。
    # 6 → 10: 实测（demo10 会话）重读间隔约 7-8 轮，KEEP=6 时调试中的
    # 文件内容总在需要时已被清掉，触发"读→清→重读"循环（enemy.js 全文
    # 被重读 3 遍）。
    MICROCOMPACT_KEEP_RECENT = 10
    # 活跃文件窗口: 最近 N 条消息内被写过的文件视为"正在调试"，
    # 其读取结果不被 Microcompact 清理（demo10 实测写入到重读的
    # 间隔可达 30+ 条消息，窗口需足够宽）
    MICROCOMPACT_ACTIVE_WINDOW = 40
    # 热点文件: 窗口内被读取 ≥2 次的路径（模型反复依赖同一文件），
    # 其最近一次读取结果同样保护，直接打断重读循环
    MICROCOMPACT_HOT_READ_THRESHOLD = 2

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

        # 设置开关: auto_compact_enabled=False 时跳过（此前该设置无消费方）
        if getattr(loop.state, "auto_compact_enabled", True) is False:
            logger.debug("Auto-compact 已禁用（auto_compact_enabled=False），跳过压缩")
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

        # 压后目标控制：估算保留部分仍明显超过目标线时收缩 keep_count，
        # 避免"只压掉一点点"的高位稳态导致每轮重复触发
        # （目标 ≈ 窗口 50% 的字符当量，token→字符按 ~2.5 折中估算）
        target_chars = self._context_window() * 0.5 * 2.5
        while keep_count > 6:
            recent = msgs[-keep_count:]
            if self._msgs_est_chars(recent) + 2000 <= target_chars:
                break
            keep_count = max(6, keep_count - max(4, keep_count // 4))

        old_msgs = msgs[1:-keep_count]
        recent_msgs = msgs[-keep_count:]

        if not old_msgs:
            return

        # LLM 驱动摘要（优先）或简单摘要（降级）。
        # 摘要输入用"读取指针占位"替代文件全文：既缩小摘要输入，
        # 又保留"读过哪个文件、哪一段"的指针，模型需要时可精确
        # 重读，而不是压缩后丢失感知、盲目重读整个文件。
        summary = self.compact_messages_llm(self._shadow_old_reads(old_msgs))
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
        loop.events.status(f"📦 上下文压缩: {old_count} -> {len(new_msgs)} 条消息")
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

    # ========== 压缩辅助 ==========

    def _context_window(self) -> int:
        """当前模型的上下文窗口大小（未知时按 200k）"""
        try:
            from commands.builtin.context_command import _get_context_window
            return _get_context_window(self.loop.model) or 200_000
        except Exception:
            return 200_000

    @staticmethod
    def _msgs_est_chars(msgs: List[Dict]) -> int:
        """粗略估算一组消息的字符量（content + tool_calls.arguments）"""
        total = 0
        for m in msgs:
            content = m.get("content")
            if isinstance(content, str):
                total += len(content)
            for tc in (m.get("tool_calls") or []):
                args = tc.get("function", {}).get("arguments")
                if isinstance(args, str):
                    total += len(args)
        return total

    def _shadow_old_reads(self, old_msgs: List[Dict]) -> List[Dict]:
        """返回 old_msgs 的副本列表，read_file 的长结果替换为指针占位。

        原消息不做修改（摘要失败时历史保持完整）。占位保留
        "读过哪个文件、哪一段"的指针，模型需要时可精确重读。
        """
        # tool_call_id -> (tool_name, arguments)
        tc_index = self._build_tool_meta_index()

        PLACEHOLDER_MIN_CHARS = 600  # 小读取不值得占位
        result = []
        for m in old_msgs:
            if m.get("role") != "tool":
                result.append(m)
                continue
            name, args = tc_index.get(m.get("tool_call_id", ""), ("", ""))
            if name != "read_file":
                result.append(m)
                continue
            content = m.get("content", "") or ""
            if len(content) < PLACEHOLDER_MIN_CHARS:
                result.append(m)
                continue
            path = self._extract_read_path(args)
            lines_info = self._extract_lines_info(content)
            result.append({**m, "content": (
                f"[已读取 {path} {lines_info}，内容已随压缩省略；"
                f"需要时可用 read_file 重新读取该文件]"
            )})
        return result

    @staticmethod
    def _extract_read_path(args: str) -> str:
        """从 read_file 调用参数中提取文件路径"""
        try:
            d = json.loads(args) if args else {}
            return d.get("path") or d.get("file_path") or "?"
        except (json.JSONDecodeError, TypeError):
            return "?"

    @staticmethod
    def _extract_lines_info(content: str) -> str:
        """从读取结果中提取行范围信息（兼容范围头与全文两种形态）"""
        m = _READ_RANGE_RE.search(content)
        if m:
            return f"第 {m.group(1)}-{m.group(2)}/{m.group(3)} 行"
        n = len(content.splitlines())
        return f"(约 {n} 行)"

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
                "Output MUST use this structure (工作记忆，供恢复后直接续作，避免重读文件):\n"
                "## 任务目标\n(1-2 句)\n"
                "## 已完成工作\n- 文件清单: 每行 `路径 — 职责/导出的关键 API(函数名与签名)`\n"
                "## 进行中\n(当前正在做什么、进行到哪一步)\n"
                "## 已知问题/待办\n(编号列出)\n"
                "## 关键决策与约定\n(命名/架构/技术选型等必须记住的约定)\n\n"
                "Be concise but preserve critical details, especially the file list "
                "with exported function signatures.\n\n"
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

        # 一次性构建 tool_call_id -> (tool_name, arguments) 索引，避免对每个
        # tool 消息都遍历全表(原 _find_tool_name_for_result → O(n²))
        tool_meta_by_id = self._build_tool_meta_index()

        # 收集所有可清除的 tool 消息索引（按出现顺序）
        clearable_indices = []
        for i, msg in enumerate(msgs):
            if msg.get("role") != "tool":
                continue
            tool_call_id = msg.get("tool_call_id", "")
            tool_name = tool_meta_by_id.get(tool_call_id, ("", ""))[0]
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
        # 活跃/热点文件保护：清掉调试中文件的内容会触发"读→清→重读"循环
        active_paths, hot_msg_idx = self._protected_read_paths()

        for idx in to_clear:
            msg = msgs[idx]
            content = msg.get("content", "")
            if content == self.MICROCOMPACT_CLEARED_MSG:
                continue  # 已清除
            if content.startswith("[已读取 "):
                continue  # 已替换为读取指针占位
            name, args = tool_meta_by_id.get(msg.get("tool_call_id", ""), ("", ""))

            # 写活跃文件全保护; 热点文件仅保护最近一次读取
            if idx in hot_msg_idx:
                continue
            if name == "read_file":
                p = self._extract_read_path(args)
                if p and os.path.normcase(os.path.abspath(p)) in active_paths:
                    continue

            total_chars_saved += len(content)

            # read_file 的结果替换为指针占位而非空清除消息：
            # 保留"读过哪个文件、哪一段"的感知，模型需要时可精确重读，
            # 而不是发现内容凭空消失后盲目重读整个文件
            new_content = self.MICROCOMPACT_CLEARED_MSG
            if name == "read_file" and len(content) > 200:
                path = self._extract_read_path(args)
                lines_info = self._extract_lines_info(content)
                new_content = (
                    f"[已读取 {path} {lines_info}，内容已清理以节省上下文；"
                    f"需要时可用 read_file 重新读取]"
                )
            msgs[idx] = {
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": new_content,
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

    def _protected_read_paths(self):
        """Microcompact 清理保护信息。

        Returns:
            (protected_paths, protected_msg_idx)
            - protected_paths: 写活跃文件路径集合（normcase，窗口内被写过
              → 该文件所有读取保留）
            - protected_msg_idx: 热点文件最近一次读取的消息索引集合
              （窗口内被读 ≥2 次 → 仅保留最新一次，旧版本清理）

        demo10 实证: enemy.js 全文被重读 3 遍，根因是调试中文件的内容
        被 Microcompact 清掉后模型被迫重读。数据来自 loop._cc_file_ops
        （file_tracker 维护，op_idx 即对应 tool 消息索引）。
        """
        msgs = self.loop.state.messages
        window_start = max(0, len(msgs) - self.MICROCOMPACT_ACTIVE_WINDOW)
        writes = set()
        read_counts: Dict[str, int] = {}
        read_latest: Dict[str, int] = {}
        for op_idx, op_type, op_path in (getattr(self.loop, "_cc_file_ops", None) or []):
            if op_idx < window_start:
                continue
            key = os.path.normcase(op_path)
            if op_type == "write":
                writes.add(key)
            elif op_type == "read":
                read_counts[key] = read_counts.get(key, 0) + 1
                read_latest[key] = max(read_latest.get(key, 0), op_idx)
        hot_idx = {idx for path, idx in read_latest.items()
                   if read_counts[path] >= self.MICROCOMPACT_HOT_READ_THRESHOLD}
        return writes, hot_idx

    def _build_tool_meta_index(self) -> Dict[str, tuple]:
        """
        构建 tool_call_id -> (tool_name, arguments) 的映射（单次遍历）。

        供 microcompact / _shadow_old_reads 批量查表使用，替代对每个
        tool 消息都遍历全表的 O(n²) 查找。
        """
        index: Dict[str, tuple] = {}
        for msg in self.loop.state.messages:
            if msg.get("role") != "assistant":
                continue
            for tc in msg.get("tool_calls", []):
                tc_id = tc.get("id")
                if tc_id:
                    func = tc.get("function", {})
                    index[tc_id] = (func.get("name", ""),
                                   func.get("arguments", ""))
        return index

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

            # 计算折叠摘要（从行范围头提取信息；read_file 的头格式为
            # "[path: lines s-e of total]"，原先按 "总行数:" 解析永远取不到）
            lines_info = ""
            m = _READ_RANGE_RE.search(content)
            if m:
                lines_info = f", 第 {m.group(1)}-{m.group(2)}/{m.group(3)} 行"

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
