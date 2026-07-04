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
Clear 命令 - 清空对话历史

功能:
- 清空当前会话的消息历史
- 保留系统提示
- 重置轮次计数
- 可选保留最近 N 条消息

用法:
  /clear          清空所有非系统消息
  /clear 5        保留最近 5 条消息
  /clear all      清空所有消息（含系统提示）
"""

from commands.registry import register_command


def clear_handler(args: list, loop=None) -> str:
    """clear 命令处理函数"""
    if loop is None:
        return "❌ AgentLoop 未初始化"

    messages = loop.messages
    if not messages:
        return "ℹ️  对话历史为空"

    lines = []
    lines.append("🧹 清空对话")
    lines.append("=" * 60)

    original_count = len(messages)
    original_chars = sum(len(str(m.get("content", ""))) for m in messages)

    # 解析参数
    keep_count = 0
    clear_all = False

    if args:
        first = args[0].lower()
        if first in ('all', '全部', '-a'):
            clear_all = True
        else:
            try:
                keep_count = int(first)
                if keep_count < 0:
                    keep_count = 0
            except ValueError:
                pass

    if clear_all:
        # 完全清空
        loop.messages = []
        lines.append(f"  模式: 完全清空（含系统提示）")
    elif keep_count > 0:
        # 保留最近 N 条
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        kept = non_system[-keep_count:] if len(non_system) > keep_count else non_system
        loop.messages = system_msgs + kept
        lines.append(f"  模式: 保留最近 {keep_count} 条消息")
    else:
        # 默认: 保留系统提示，清空对话
        system_msgs = [m for m in messages if m.get("role") == "system"]
        loop.messages = system_msgs
        lines.append(f"  模式: 保留系统提示，清空对话")

    # 重置状态
    state = getattr(loop, 'state', None)
    if state:
        state.turn_count = 0
        # 重置 context warning 标志
        if hasattr(loop, '_ctx_warned'):
            loop._ctx_warned = False

    new_count = len(loop.messages)
    new_chars = sum(len(str(m.get("content", ""))) for m in loop.messages)
    freed = original_chars - new_chars

    lines.append(f"")
    lines.append(f"  清空前: {original_count} 条消息 ({original_chars:,} 字符)")
    lines.append(f"  清空后: {new_count} 条消息 ({new_chars:,} 字符)")
    lines.append(f"  释放:   {freed:,} 字符")
    lines.append(f"  ✅ 对话已清空")
    lines.append("=" * 60)
    return "\n".join(lines)


register_command("clear", {
    "description": "清空对话历史 - 保留系统提示，释放上下文空间",
    "handler": clear_handler,
    "category": "session",
    "args_help": "[N] 保留最近 N 条 / [all] 完全清空"
})

# 注册别名
from commands.registry import COMMAND_REGISTRY
COMMAND_REGISTRY["reset"] = COMMAND_REGISTRY["clear"].copy()
COMMAND_REGISTRY["reset"]["description"] = "清空对话历史 (clear 别名)"
COMMAND_REGISTRY["new"] = COMMAND_REGISTRY["clear"].copy()
COMMAND_REGISTRY["new"]["description"] = "清空对话历史 (clear 别名)"
