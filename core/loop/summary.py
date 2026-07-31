#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.summary — 会话总结构建

从 ``AgentLoop`` 提取的程序化会话总结逻辑（原 ``_build_programmatic_summary``）。
从已有的会话数据（用户首条消息 / 工具调用 / 最终回复 / 迭代轮次 / 耗时）中
提取关键信息构建结构化总结,零失败率,无需额外 API 调用。

旧方法 → 新位置:
    AgentLoop._build_programmatic_summary  ->  SummaryBuilder.build
"""

import logging

logger = logging.getLogger(__name__)


class SummaryBuilder:
    """程序化构建会话总结(不依赖额外 LLM 调用)。"""

    def __init__(self, loop):
        self.loop = loop

    def build(self, final_text: str) -> str:
        """
        程序化生成会话总结(不依赖额外 LLM 调用)

        从已有的会话数据中提取关键信息,构建结构化总结。
        零失败率,无需额外 API 调用。

        Args:
            final_text: 最后的助手响应文本

        Returns:
            会话总结文本
        """
        loop = self.loop
        try:
            # 1. 提取用户首条消息(需求)
            user_request = ""
            for msg in loop.messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str) and content.strip():
                        user_request = content[:120].strip()
                        break

            # 2. 统计工具调用
            tool_names = []
            for msg in loop.messages:
                if msg.get("role") == "assistant":
                    for tc in msg.get("tool_calls", []):
                        func_name = tc.get("function", {}).get("name", "")
                        if func_name and func_name not in tool_names:
                            tool_names.append(func_name)

            # 3. 构建总结
            lines = []
            if user_request:
                lines.append(f"📋 需求：{user_request}")

            # 最终回复摘要(取前 200 字符)
            clean_text = final_text.strip()
            if clean_text:
                preview = clean_text[:200].replace('\n', ' ').strip()
                if len(clean_text) > 200:
                    preview += "..."
                lines.append(f"✅ 完成：{preview}")

            if tool_names:
                lines.append(f"🔧 工具：{', '.join(tool_names[:8])}")

            lines.append(f"📊 迭代：{loop.state.turn_count} 轮 | 耗时：{loop.state.elapsed_ms() / 1000:.1f}s")

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Programmatic summary failed: {e}")
            return ""
