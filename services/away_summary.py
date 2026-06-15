"""
AwaySummary 服务 — 离开时摘要

当用户恢复会话时，自动生成简短的 "while you were away" 回顾摘要。
使用 LLM 对最近 30 条消息生成 1-3 句总结，
帮助用户快速了解离开的期间进展。
"""
import time
import threading
from typing import List, Dict, Optional
from dataclasses import dataclass


# ── 配置 ─────────────────────────────────────────────────

RECENT_MESSAGE_WINDOW = 30  # 最近 N 条消息用于生成摘要
MAX_SUMMARY_LENGTH = 500    # 摘要最大字符数
SUMMARY_TIMEOUT = 30        # LLM 调用超时（秒）


@dataclass
class AwaySummaryResult:
    """摘要结果"""
    summary: str
    generated_at: float
    message_count: int
    success: bool
    error: Optional[str] = None


class AwaySummaryService:
    """离开时摘要生成器"""

    def __init__(self, llm_func=None):
        """
        Args:
            llm_func: 可选的 LLM 调用函数 (prompt, messages) -> str
                      如果不提供，使用默认的 _call_llm
        """
        self._llm_func = llm_func
        self._last_summary: Optional[AwaySummaryResult] = None
        self._lock = threading.Lock()

    def _build_prompt(self, memory_context: str = "") -> str:
        """构建摘要生成提示词"""
        memory_block = ""
        if memory_context:
            memory_block = f"\nSession memory (broader context):\n{memory_context}\n\n"

        return (
            f"{memory_block}"
            "The user stepped away and is coming back. "
            "Write exactly 1-3 short sentences. "
            "Start by stating the high-level task — what they are building or debugging, "
            "not implementation details. "
            "Next: the concrete next step. "
            "Skip status reports and commit recaps."
        )

    def _extract_messages_text(self, messages: List[Dict]) -> List[Dict]:
        """提取最近消息的文本内容，简化为 {role, content} 格式"""
        recent = messages[-RECENT_MESSAGE_WINDOW:] if len(messages) > RECENT_MESSAGE_WINDOW else messages
        simplified = []
        for msg in recent:
            role = msg.get("role", "unknown")
            content = ""

            # 处理不同消息格式
            if isinstance(msg.get("content"), str):
                content = msg["content"]
            elif isinstance(msg.get("content"), list):
                parts = []
                for block in msg["content"]:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            parts.append(f"[tool: {block.get('name', 'unknown')}]")
                        elif block.get("type") == "tool_result":
                            parts.append(f"[result: {str(block.get('content', ''))[:100]}]")
                    elif isinstance(block, str):
                        parts.append(block)
                content = " ".join(parts)
            elif isinstance(msg.get("text"), str):
                content = msg["text"]

            if content.strip():
                simplified.append({"role": role, "content": content[:500]})

        return simplified

    def _call_llm(self, prompt: str, messages: List[Dict]) -> str:
        """调用 LLM 生成摘要"""
        if self._llm_func:
            return self._llm_func(prompt, messages)

        # 默认实现：简单提取关键信息作为摘要（无需 LLM）
        return self._fallback_summary(messages)

    def _fallback_summary(self, messages: List[Dict]) -> str:
        """当 LLM 不可用时的后备摘要"""
        if not messages:
            return "没有足够的对话历史来生成摘要。"

        recent = messages[-5:]
        topics = []
        for msg in recent:
            content = msg.get("content", "")
            if isinstance(content, list):
                texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                content = " ".join(texts)
            if isinstance(content, str) and content.strip():
                # 提取前 80 字符作为主题
                snippet = content.strip()[:80]
                topics.append(snippet)

        if topics:
            return f"最近的对话涉及: {'; '.join(topics[-3:])}"
        return "对话历史为空，无法生成摘要。"

    def generate_summary(self, messages: List[Dict],
                         memory_context: str = "",
                         timeout: int = SUMMARY_TIMEOUT) -> AwaySummaryResult:
        """
        生成离开时摘要。

        Args:
            messages: 完整对话消息列表
            memory_context: 可选的会话记忆上下文
            timeout: LLM 调用超时秒数

        Returns:
            AwaySummaryResult
        """
        with self._lock:
            if not messages:
                result = AwaySummaryResult(
                    summary="",
                    generated_at=time.time(),
                    message_count=0,
                    success=False,
                    error="没有对话消息",
                )
                self._last_summary = result
                return result

            simplified = self._extract_messages_text(messages)
            if len(simplified) < 2:
                result = AwaySummaryResult(
                    summary="对话历史太短，无法生成有意义的摘要。",
                    generated_at=time.time(),
                    message_count=len(messages),
                    success=True,
                )
                self._last_summary = result
                return result

            prompt = self._build_prompt(memory_context)

            try:
                summary_text = self._call_llm(prompt, simplified)
                # 截断过长摘要
                if len(summary_text) > MAX_SUMMARY_LENGTH:
                    summary_text = summary_text[:MAX_SUMMARY_LENGTH].rsplit(" ", 1)[0] + "..."

                result = AwaySummaryResult(
                    summary=summary_text,
                    generated_at=time.time(),
                    message_count=len(messages),
                    success=True,
                )
            except Exception as e:
                result = AwaySummaryResult(
                    summary="",
                    generated_at=time.time(),
                    message_count=len(messages),
                    success=False,
                    error=str(e),
                )

            self._last_summary = result
            return result

    def get_last_summary(self) -> Optional[AwaySummaryResult]:
        """获取最后一次生成的摘要"""
        return self._last_summary

    def format_display(self, result: AwaySummaryResult) -> str:
        """格式化为显示文本"""
        if not result.success:
            return f"⚠️ 摘要生成失败: {result.error}"

        lines = [
            "─" * 40,
            "📝 While you were away...",
            f"   {result.summary}",
            f"   ({result.message_count} 条对话记录)",
            "─" * 40,
        ]
        return "\n".join(lines)


# ── 全局单例 ──────────────────────────────────────────────

_away_summary_service: Optional[AwaySummaryService] = None


def get_away_summary_service() -> AwaySummaryService:
    """获取全局 AwaySummary 服务实例"""
    global _away_summary_service
    if _away_summary_service is None:
        _away_summary_service = AwaySummaryService()
    return _away_summary_service


def generate_away_summary(messages: List[Dict], **kwargs) -> AwaySummaryResult:
    """快捷函数：生成离开时摘要"""
    return get_away_summary_service().generate_summary(messages, **kwargs)
