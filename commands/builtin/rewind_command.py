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
Rewind 命令 — 会话回退 / Checkpoint

允许用户将对话回退到之前的某个检查点，撤销后续的对话轮次。

功能:
- /rewind list    — 列出所有检查点（每轮对话的入口）
- /rewind <N>     — 回退到第 N 轮对话
- /rewind last    — 撤销最后一轮对话
- /rewind status  — 显示当前检查点状态
"""
import copy
import logging
from commands.registry import register_command

logger = logging.getLogger(__name__)


# ── 检查点管理 ─────────────────────────────────────────────────


class CheckpointManager:
    """
    对话检查点管理器

    在每轮对话开始前自动创建检查点快照，
    支持回退到任意检查点。
    """

    def __init__(self, max_checkpoints: int = 50):
        self.max_checkpoints = max_checkpoints
        self._checkpoints = []  # [(turn, message_count, timestamp, snapshot_preview)]

    def create_checkpoint(self, turn: int, messages: list, timestamp: str = ""):
        """在每轮对话前创建检查点"""
        import time as _time
        if not timestamp:
            timestamp = _time.strftime("%H:%M:%S")

        # 提取用户消息作为预览
        preview = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str) and content and not content.startswith("["):
                    preview = content[:80]
                    break

        checkpoint = {
            "turn": turn,
            "message_count": len(messages),
            "timestamp": timestamp,
            "preview": preview,
        }
        self._checkpoints.append(checkpoint)

        # 限制检查点数量
        if len(self._checkpoints) > self.max_checkpoints:
            self._checkpoints = self._checkpoints[-self.max_checkpoints:]

        logger.debug(f"Checkpoint created: turn={turn}, msgs={len(messages)}")

    def list_checkpoints(self) -> list:
        """列出所有检查点"""
        return list(self._checkpoints)

    def get_checkpoint(self, turn: int) -> dict:
        """获取指定轮次的检查点"""
        for cp in self._checkpoints:
            if cp["turn"] == turn:
                return cp
        return None

    def get_last_checkpoint(self) -> dict:
        """获取最后一个检查点"""
        if len(self._checkpoints) >= 2:
            return self._checkpoints[-2]  # 倒数第二个（当前轮之前）
        return self._checkpoints[-1] if self._checkpoints else None

    def rewind_to(self, turn: int, messages: list) -> list:
        """
        回退到指定轮次的检查点

        Returns:
            截断后的消息列表（到检查点的消息数）
        """
        cp = self.get_checkpoint(turn)
        if not cp:
            return messages

        target_count = cp["message_count"]
        if target_count >= len(messages):
            return messages

        truncated = messages[:target_count]

        # 清除被回退的检查点
        self._checkpoints = [
            c for c in self._checkpoints if c["turn"] <= turn
        ]

        logger.info(f"Rewound to turn {turn}: {len(messages)} → {len(truncated)} messages")
        return truncated

    def get_status(self) -> dict:
        """当前状态"""
        return {
            "total_checkpoints": len(self._checkpoints),
            "latest_turn": self._checkpoints[-1]["turn"] if self._checkpoints else 0,
        }


# 全局实例
_checkpoint_mgr = None


def get_checkpoint_manager() -> CheckpointManager:
    """获取全局检查点管理器"""
    global _checkpoint_mgr
    if _checkpoint_mgr is None:
        _checkpoint_mgr = CheckpointManager()
    return _checkpoint_mgr


# ── /rewind 命令 ─────────────────────────────────────────────────


def rewind_handler(args: list, loop=None) -> str:
    """
    会话回退命令。

    用法:
        /rewind list    — 列出所有检查点
        /rewind <N>     — 回退到第 N 轮
        /rewind last    — 撤销最后一轮
        /rewind status  — 当前状态
    """
    mgr = get_checkpoint_manager()
    sub = args[0] if args else "status"

    lines = []
    lines.append("=" * 50)
    lines.append("⏪ 会话回退 (Rewind)")
    lines.append("=" * 50)

    if sub == "list":
        checkpoints = mgr.list_checkpoints()
        if not checkpoints:
            lines.append("\n无检查点（会话刚开始）")
        else:
            lines.append(f"\n共 {len(checkpoints)} 个检查点:")
            lines.append("")
            for cp in checkpoints:
                turn = cp["turn"]
                ts = cp["timestamp"]
                msgs = cp["message_count"]
                preview = cp["preview"][:50] if cp["preview"] else "(系统)"
                lines.append(f"  Turn {turn:>3}  [{ts}]  {msgs:>3} msgs  | {preview}")
            lines.append("")
            lines.append("使用 /rewind <N> 回退到指定轮次")

    elif sub == "last":
        cp = mgr.get_last_checkpoint()
        if not cp or not loop:
            lines.append("\n无法回退: 无可用检查点或无 AgentLoop")
        else:
            target_turn = cp["turn"]
            old_count = len(loop.state.messages)
            loop.state.messages = mgr.rewind_to(target_turn, loop.state.messages)
            new_count = len(loop.state.messages)
            removed = old_count - new_count
            lines.append(f"\n已回退到 Turn {target_turn}")
            lines.append(f"消息数: {old_count} → {new_count} (移除 {removed} 条)")
            lines.append("可以继续对话")

    elif sub == "status":
        status = mgr.get_status()
        lines.append(f"\n检查点数: {status['total_checkpoints']}")
        lines.append(f"最新轮次: Turn {status['latest_turn']}")
        if loop:
            lines.append(f"当前消息数: {len(loop.state.messages)}")
            lines.append(f"当前轮次: {loop.state.turn_count}")

    elif sub.isdigit():
        target_turn = int(sub)
        if not loop:
            lines.append("\n错误: 无 AgentLoop 可用")
        else:
            cp = mgr.get_checkpoint(target_turn)
            if not cp:
                lines.append(f"\n错误: 未找到 Turn {target_turn} 的检查点")
                lines.append("使用 /rewind list 查看可用检查点")
            else:
                old_count = len(loop.state.messages)
                loop.state.messages = mgr.rewind_to(target_turn, loop.state.messages)
                new_count = len(loop.state.messages)
                removed = old_count - new_count
                lines.append(f"\n已回退到 Turn {target_turn}")
                lines.append(f"消息数: {old_count} → {new_count} (移除 {removed} 条)")
                lines.append("可以继续对话")

    else:
        lines.append(f"\n未知子命令: {sub}")
        lines.append("用法: /rewind [list|<N>|last|status]")

    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)


register_command("rewind", {
    "description": "会话回退 — 撤销对话轮次，回到之前的检查点",
    "handler": rewind_handler,
    "category": "session",
    "args_help": "[list|<N>|last|status]  列出/回退到指定轮次/撤销上一轮/状态",
})
