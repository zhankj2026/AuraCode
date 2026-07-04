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
Compact 命令 - 压缩对话历史，保留摘要

功能:
- 将当前对话历史压缩为精简摘要
- 保留关键上下文（文件操作、代码变更、决策等）
- 释放上下文窗口空间，支持更长的会话
- 可选自定义摘要指令

用法:
  /compact               使用默认压缩
  /compact <指令>         按指定方向压缩（如"重点保留代码重构部分"）
"""

import json
from commands.registry import register_command

COMPACT_SYSTEM_PROMPT = """你是一个对话历史压缩专家。请将以下对话历史压缩成精简的摘要。

压缩规则:
1. 保留关键决策和结论（做了什么、为什么这样做）
2. 保留文件操作记录（创建、修改、删除了哪些文件）
3. 保留代码变更的关键信息（修改了什么功能、修复了什么bug）
4. 保留未完成的任务和待处理的事项
5. 删除冗余的探索过程、错误的尝试、重复的信息
6. 保持摘要结构清晰，用 Markdown 列表格式

输出格式（仅输出摘要内容，不要解释）:
## 会话摘要

- **已完成**: ...
- **关键决策**: ...
- **文件变更**: ...
- **待处理**: ...
"""


def _format_messages_for_summary(messages: list) -> str:
    """将消息历史格式化为可读文本供 AI 总结"""
    parts = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if not content:
            # 工具调用消息，简要记录
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                tool_names = [tc["function"]["name"] for tc in tool_calls]
                parts.append(f"[调用了工具: {', '.join(tool_names)}]")
            continue
        # 截断过长内容
        content_str = str(content)[:500]
        if len(str(content)) > 500:
            content_str += "..."
        if role == "user":
            parts.append(f"[用户]: {content_str}")
        elif role == "assistant":
            parts.append(f"[助手]: {content_str}")
        elif role == "tool":
            parts.append(f"[工具结果]: {content_str[:200]}")
    return "\n".join(parts)


def compact_handler(args: list, loop=None) -> str:
    """compact 命令处理函数"""
    if loop is None:
        return "❌ AgentLoop 未初始化"

    lines = []
    lines.append("🗜️  对话压缩")
    lines.append("=" * 60)

    messages = loop.messages
    if not messages or len(messages) <= 2:
        lines.append("ℹ️  对话历史为空或过短，无需压缩")
        return "\n".join(lines)

    # 统计压缩前状态
    original_count = len(messages)
    original_chars = sum(len(str(m.get("content", ""))) for m in messages)
    lines.append(f"📊 压缩前: {original_count} 条消息，约 {original_chars} 字符")

    # 分离系统消息和对话消息
    system_messages = [m for m in messages if m.get("role") == "system"]
    conversation_messages = [m for m in messages if m.get("role") != "system"]

    if not conversation_messages:
        lines.append("ℹ️  没有对话消息可压缩")
        return "\n".join(lines)

    # 自定义压缩指令
    custom_instruction = " ".join(args) if args else ""
    lines.append("🤖 正在压缩对话历史...")

    try:
        # 构建压缩请求
        formatted_history = _format_messages_for_summary(conversation_messages)
        user_prompt = f"请压缩以下对话历史：\n\n{formatted_history}"
        if custom_instruction:
            user_prompt += f"\n\n特别关注：{custom_instruction}"

        response = loop.client.chat.completions.create(
            model=loop.model,
            messages=[
                {"role": "system", "content": COMPACT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        summary = response.choices[0].message.content.strip()

        # 重建消息历史：系统提示 + 压缩摘要 + 最后几条消息
        # 保留最后2条消息（最近一轮对话）以保持连贯性
        keep_recent = 2
        recent_messages = conversation_messages[-keep_recent:] if len(conversation_messages) > keep_recent else []

        # 重建消息列表
        new_messages = list(system_messages)
        # 以系统消息形式注入摘要（不占用 user/assistant 位置）
        new_messages.append({
            "role": "system",
            "content": f"<previous-conversation-summary>\n{summary}\n</previous-conversation-summary>"
        })
        new_messages.extend(recent_messages)

        loop.messages = new_messages

        # 统计压缩后状态
        new_count = len(new_messages)
        new_chars = sum(len(str(m.get("content", ""))) for m in new_messages)
        saved_chars = original_chars - new_chars
        saved_pct = (saved_chars / original_chars * 100) if original_chars > 0 else 0

        lines.append(f"📊 压缩后: {new_count} 条消息，约 {new_chars} 字符")
        lines.append(f"✅ 节省了约 {saved_chars} 字符 ({saved_pct:.1f}%)")
        lines.append(f"\n📝 摘要预览:\n{summary[:500]}")
        if len(summary) > 500:
            lines.append("...")

    except Exception as e:
        lines.append(f"❌ 压缩失败: {e}")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("compact", {
    "description": "压缩对话历史，保留摘要，释放上下文空间",
    "handler": compact_handler,
    "category": "system",
    "args_help": "[可选压缩指令，如: 重点保留代码重构部分]"
})
