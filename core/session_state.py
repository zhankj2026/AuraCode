"""
会话状态管理

参考 Claude Code 的 AppStateStore + QueryEngine 设计，
为 opencode 提供集中式会话状态管理、Token 累计追踪和结构化结果报告。
"""

import threading
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime

import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token 使用量追踪（跨轮次累计）"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def accumulate(self, usage) -> None:
        """累加一次 API 调用的 token 用量

        Args:
            usage: OpenAI API 返回的 usage 对象，或 dict
        """
        if usage is None:
            return
        if isinstance(usage, dict):
            self.prompt_tokens += usage.get("prompt_tokens", 0) or 0
            self.completion_tokens += usage.get("completion_tokens", 0) or 0
            self.total_tokens += usage.get("total_tokens", 0) or 0
        else:
            self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
            self.total_tokens += getattr(usage, "total_tokens", 0) or 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class QueryResult:
    """结构化查询结果报告

    参考 Claude Code QueryEngine.submitMessage 末尾 yield 的 result 消息。
    用于 CLI 展示、Bridge 远程返回、日志记录等场景。
    """
    status: str  # 'success', 'error_max_turns', 'error_max_budget', 'error', 'aborted'
    text: str
    duration_ms: int
    num_turns: int
    total_cost_usd: float
    total_usage: Dict[str, int]
    error: Optional[str] = None
    stop_reason: Optional[str] = None
    permission_denials: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（供 Bridge JSON 返回等场景使用）"""
        return {
            "status": self.status,
            "text": self.text,
            "duration_ms": self.duration_ms,
            "num_turns": self.num_turns,
            "total_cost_usd": self.total_cost_usd,
            "total_usage": self.total_usage,
            "error": self.error,
            "stop_reason": self.stop_reason,
            "permission_denials": self.permission_denials,
        }

    def format_summary(self) -> str:
        """格式化为可读摘要（CLI 展示用）"""
        lines = []
        icon = {"success": "✅", "aborted": "⏹️"}.get(self.status, "❌")
        lines.append(f"{icon} 状态: {self.status}")
        lines.append(f"   轮次: {self.num_turns}  |  耗时: {self.duration_ms / 1000:.1f}s")
        lines.append(f"   Token: {self.total_usage.get('total_tokens', 0)}"
                     f" (输入={self.total_usage.get('prompt_tokens', 0)},"
                     f" 输出={self.total_usage.get('completion_tokens', 0)})")
        if self.total_cost_usd > 0:
            lines.append(f"   费用: ${self.total_cost_usd:.6f}")
        if self.permission_denials:
            lines.append(f"   权限拒绝: {len(self.permission_denials)} 次")
        if self.error:
            lines.append(f"   错误: {self.error}")
        return "\n".join(lines)


# 粗略成本估算（每 1K token 的 USD 价格）
_DEFAULT_COST_RATES = {
    "prompt_per_1k": 0.003,       # ~$3/M tokens
    "completion_per_1k": 0.015,   # ~$15/M tokens
}


class SessionState:
    """集中式会话状态管理

    替代 AgentLoop 中散落的实例属性：
    - messages → state.messages
    - iteration → state.turn_count
    - 新增 total_usage, total_cost_usd, abort_event, permission_denials

    参考 Claude Code:
    - AppStateStore.ts (集中状态)
    - QueryEngine (usage/cost tracking)
    - query.ts (loop state machine)
    """

    def __init__(
        self,
        max_budget_usd: Optional[float] = None,
        fallback_model: Optional[str] = None,
        cost_rates: Optional[Dict[str, float]] = None,
    ):
        # === 消息历史 ===
        self.messages: List[Dict[str, Any]] = []

        # === Token 追踪 ===
        self.total_usage = TokenUsage()
        self.last_turn_usage = TokenUsage()  # 当轮用量（用于展示）

        # === 成本 ===
        self.total_cost_usd: float = 0.0
        self.max_budget_usd: Optional[float] = max_budget_usd
        self._cost_rates = cost_rates or _DEFAULT_COST_RATES

        # === 循环控制 ===
        self.turn_count: int = 0
        self.abort_event = threading.Event()

        # === 权限追踪 ===
        self.permission_denials: List[Dict[str, Any]] = []

        # === 模型配置 ===
        self.fallback_model: Optional[str] = fallback_model
        self._active_model_override: Optional[str] = None  # fallback 触发后的当前模型

        # === 时间追踪 ===
        self._query_start_time: Optional[float] = None

        # === max_output_tokens 恢复 ===
        self.output_truncation_count: int = 0  # 连续截断次数

    # ========== Token 追踪 ==========

    def record_usage(self, usage) -> None:
        """记录一次 API 调用的 token 用量

        Args:
            usage: OpenAI API usage 对象或 dict
        """
        if usage is None:
            return
        self.total_usage.accumulate(usage)
        self.last_turn_usage.accumulate(usage)
        self._update_cost(usage)

    def _update_cost(self, usage) -> None:
        """根据 token 用量估算成本"""
        if usage is None:
            return
        if isinstance(usage, dict):
            prompt = usage.get("prompt_tokens", 0) or 0
            completion = usage.get("completion_tokens", 0) or 0
        else:
            prompt = getattr(usage, "prompt_tokens", 0) or 0
            completion = getattr(usage, "completion_tokens", 0) or 0

        cost = (
            prompt / 1000 * self._cost_rates["prompt_per_1k"]
            + completion / 1000 * self._cost_rates["completion_per_1k"]
        )
        self.total_cost_usd += cost

    # ========== 预算控制 ==========

    def is_budget_exceeded(self) -> bool:
        """检查是否超出预算上限"""
        if self.max_budget_usd is None:
            return False
        return self.total_cost_usd >= self.max_budget_usd

    def budget_remaining(self) -> Optional[float]:
        """返回剩余预算（None 表示无上限）"""
        if self.max_budget_usd is None:
            return None
        return max(0, self.max_budget_usd - self.total_cost_usd)

    # ========== 权限追踪 ==========

    def record_permission_denial(self, tool_name: str, tool_input: Dict, reason: str = "") -> None:
        """记录一次权限拒绝"""
        self.permission_denials.append({
            "tool_name": tool_name,
            "tool_input": tool_input,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })

    # ========== 中断控制 ==========

    def abort(self) -> None:
        """触发中断信号"""
        self.abort_event.set()

    def is_aborted(self) -> bool:
        """检查是否已触发中断"""
        return self.abort_event.is_set()

    def clear_abort(self) -> None:
        """清除中断信号"""
        self.abort_event.clear()

    # ========== 模型管理 ==========

    def get_active_model(self, default_model: str) -> str:
        """获取当前应使用的模型（fallback 后可能是备用模型）"""
        return self._active_model_override or default_model

    def activate_fallback(self) -> Optional[str]:
        """激活 fallback 模型，返回被激活的模型名或 None（无 fallback）"""
        if self.fallback_model:
            self._active_model_override = self.fallback_model
            logger.info(f"Activated fallback model: {self.fallback_model}")
            return self.fallback_model
        return None

    def reset_model_override(self) -> None:
        """重置模型覆盖（新查询开始时调用）"""
        self._active_model_override = None

    # ========== 查询生命周期 ==========

    def start_query(self) -> None:
        """标记一次查询开始"""
        self._query_start_time = time.time()
        self.last_turn_usage = TokenUsage()
        self.output_truncation_count = 0
        self.reset_model_override()

    def elapsed_ms(self) -> int:
        """返回自 start_query 以来的毫秒数"""
        if self._query_start_time is None:
            return 0
        return int((time.time() - self._query_start_time) * 1000)

    def increment_turn(self) -> None:
        """增加轮次计数"""
        self.turn_count += 1

    # ========== 结果生成 ==========

    def to_result(
        self,
        status: str,
        text: str = "",
        error: Optional[str] = None,
        stop_reason: Optional[str] = None,
    ) -> QueryResult:
        """从当前状态生成结构化结果"""
        return QueryResult(
            status=status,
            text=text,
            duration_ms=self.elapsed_ms(),
            num_turns=self.turn_count,
            total_cost_usd=self.total_cost_usd,
            total_usage=self.total_usage.to_dict(),
            error=error,
            stop_reason=stop_reason,
            permission_denials=list(self.permission_denials),
        )

    # ========== 重置 ==========

    def reset_messages(self) -> None:
        """清空消息历史（保留 token/cost 累计）"""
        self.messages = []
        self.turn_count = 0

    def reset_all(self) -> None:
        """完全重置所有状态"""
        self.messages = []
        self.total_usage = TokenUsage()
        self.last_turn_usage = TokenUsage()
        self.total_cost_usd = 0.0
        self.turn_count = 0
        self.permission_denials = []
        self.abort_event.clear()
        self._query_start_time = None
        self.output_truncation_count = 0
        self.reset_model_override()
