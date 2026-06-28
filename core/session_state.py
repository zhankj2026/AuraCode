"""会话状态管理

参考 AppStateStore + QueryEngine 设计，
为 auracode 提供集中式会话状态管理、Token 累计追踪和结构化结果报告。

增强功能:
- 发布/订阅: on_change 回调，状态变更事件广播
- 状态快照/恢复: 保存和恢复完整状态快照
"""

import threading
import time
import copy
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal, Callable
from datetime import datetime

import logging

logger = logging.getLogger(__name__)


# ── 状态变更事件类型 ──
class StateEvent:
    """状态变更事件"""
    MESSAGE_ADDED = "message_added"
    MESSAGE_CLEARED = "message_cleared"
    USAGE_RECORDED = "usage_recorded"
    TURN_INCREMENTED = "turn_incremented"
    ABORT_TRIGGERED = "abort_triggered"
    ABORT_CLEARED = "abort_cleared"
    BUDGET_EXCEEDED = "budget_exceeded"
    MODEL_CHANGED = "model_changed"
    PERMISSION_DENIED = "permission_denied"
    QUERY_STARTED = "query_started"
    QUERY_COMPLETED = "query_completed"
    SNAPSHOT_CREATED = "snapshot_created"
    SNAPSHOT_RESTORED = "snapshot_restored"
    CONFIG_CHANGED = "config_changed"


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

    参考 QueryEngine.submitMessage 末尾 yield 的 result 消息。
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


# ── 模型定价表 (USD per million tokens) ──
@dataclass
class ModelPricing:
    """模型定价信息"""
    input_per_mtok: float = 3.0       # $3/M tokens
    output_per_mtok: float = 15.0     # $15/M tokens
    cache_read_per_mtok: float = 0.3  # $0.3/M tokens
    cache_write_per_mtok: float = 3.75  # $3.75/M tokens

# 常见模型定价（参考主流 LLM 公开定价）
MODEL_PRICING: Dict[str, ModelPricing] = {
    # 主流模型系列
    "claude-opus-4":     ModelPricing(15.0, 75.0, 1.5, 18.75),
    "claude-sonnet-4":   ModelPricing(3.0, 15.0, 0.3, 3.75),
    "claude-3.5-sonnet": ModelPricing(3.0, 15.0, 0.3, 3.75),
    "claude-3.5-haiku":  ModelPricing(0.8, 4.0, 0.08, 1.0),
    "claude-3-opus":     ModelPricing(15.0, 75.0, 1.5, 18.75),
    # GLM 系列（按人民币换算估算）
    "glm-4-plus":  ModelPricing(2.0, 10.0, 0.2, 2.5),
    "glm-4":       ModelPricing(1.0, 5.0, 0.1, 1.25),
    "glm-4.5":     ModelPricing(2.0, 10.0, 0.2, 2.5),
    "glm-4.7":     ModelPricing(3.0, 15.0, 0.3, 3.75),
    # GPT 系列
    "gpt-4o":        ModelPricing(2.5, 10.0, 1.25, 2.5),
    "gpt-4o-mini":   ModelPricing(0.15, 0.6, 0.075, 0.15),
    "gpt-4-turbo":   ModelPricing(10.0, 30.0, 0.0, 0.0),
    "o1":            ModelPricing(15.0, 60.0, 7.5, 15.0),
    "o3-mini":       ModelPricing(1.1, 4.4, 0.55, 1.1),
    # DeepSeek
    "deepseek-chat":   ModelPricing(0.27, 1.1, 0.07, 0.27),
    "deepseek-reasoner": ModelPricing(0.55, 2.19, 0.14, 0.55),
    # Qwen
    "qwen-max":    ModelPricing(1.6, 5.0, 0.4, 1.6),
    "qwen-plus":   ModelPricing(0.4, 1.2, 0.1, 0.4),
    "qwen-turbo":  ModelPricing(0.1, 0.3, 0.025, 0.1),
}

# 默认兜底定价
DEFAULT_PRICING = ModelPricing(3.0, 15.0, 0.3, 3.75)


def get_model_pricing(model: str) -> ModelPricing:
    """获取模型定价（支持模糊匹配）"""
    # 精确匹配
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    # 子串匹配
    model_lower = model.lower()
    for key, pricing in MODEL_PRICING.items():
        if key in model_lower or model_lower in key:
            return pricing
    return DEFAULT_PRICING


@dataclass
class ModelUsageEntry:
    """单个模型的使用量记录"""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    api_calls: int = 0

    def accumulate(self, usage, pricing: ModelPricing) -> float:
        """累加一次 API 调用，返回本次费用"""
        inp = 0
        out = 0
        cr = 0
        cw = 0
        if isinstance(usage, dict):
            inp = usage.get("prompt_tokens", 0) or 0
            out = usage.get("completion_tokens", 0) or 0
            cr = usage.get("cache_read_input_tokens", 0) or usage.get("prompt_cache_hit_tokens", 0) or 0
            cw = usage.get("cache_creation_input_tokens", 0) or usage.get("prompt_cache_miss_tokens", 0) or 0
        else:
            inp = getattr(usage, "prompt_tokens", 0) or 0
            out = getattr(usage, "completion_tokens", 0) or 0
            cr = getattr(usage, "cache_read_input_tokens", 0) or getattr(usage, "prompt_cache_hit_tokens", 0) or 0
            cw = getattr(usage, "cache_creation_input_tokens", 0) or getattr(usage, "prompt_cache_miss_tokens", 0) or 0

        self.input_tokens += inp
        self.output_tokens += out
        self.cache_read_tokens += cr
        self.cache_write_tokens += cw
        self.api_calls += 1

        cost = (
            (inp / 1_000_000) * pricing.input_per_mtok
            + (out / 1_000_000) * pricing.output_per_mtok
            + (cr / 1_000_000) * pricing.cache_read_per_mtok
            + (cw / 1_000_000) * pricing.cache_write_per_mtok
        )
        self.cost_usd += cost
        return cost


# 粗略成本估算（每 1K token 的 USD 价格）—— 向后兼容
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

    发布/订阅:
    - subscribe(event, callback) — 注册状态变更回调
    - unsubscribe(sub_id) — 注销回调
    - _emit(event, data) — 触发状态变更事件

    快照/恢复:
    - create_snapshot() — 创建完整状态快照
    - restore_snapshot(snapshot) — 从快照恢复状态

    参考 AuraCode:
    - AppStateStore.ts (集中状态 + Store 发布订阅)
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

        # === 每模型使用量追踪 ===
        self.model_usage: Dict[str, ModelUsageEntry] = {}
        self._current_model: Optional[str] = None  # 当前模型名（用于归类费用）

        # === 时间追踪 ===
        self._query_start_time: Optional[float] = None

        # === max_output_tokens 恢复 ===
        self.output_truncation_count: int = 0  # 连续截断次数

        # === 发布/订阅 ===
        self._subscribers: Dict[int, Dict[str, Any]] = {}
        self._sub_counter: int = 0

    # ========== 发布/订阅 ==========

    def subscribe(
        self,
        event: str,
        callback: Callable[[str, Dict[str, Any]], None],
        label: str = "",
    ) -> int:
        """注册状态变更回调

        Args:
            event: 事件类型（StateEvent 常量）
            callback: 回调函数 callback(event, data)
            label: 可选标签（用于调试）

        Returns:
            订阅 ID（用于 unsubscribe）
        """
        self._sub_counter += 1
        sub_id = self._sub_counter
        self._subscribers[sub_id] = {
            "event": event,
            "callback": callback,
            "label": label,
        }
        logger.debug(f"订阅: [{sub_id}] {event} ({label})")
        return sub_id

    def subscribe_all(
        self,
        callback: Callable[[str, Dict[str, Any]], None],
        label: str = "",
    ) -> int:
        """注册全事件回调（监听所有事件）"""
        return self.subscribe("*", callback, label)

    def unsubscribe(self, sub_id: int) -> bool:
        """注销回调"""
        if sub_id in self._subscribers:
            del self._subscribers[sub_id]
            return True
        return False

    def _emit(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """触发状态变更事件"""
        payload = data or {}
        for sub in list(self._subscribers.values()):
            if sub["event"] == event or sub["event"] == "*":
                try:
                    sub["callback"](event, payload)
                except Exception as e:
                    logger.warning(f"订阅回调异常: {sub.get('label', '')} -> {e}")

    def get_subscriber_count(self) -> int:
        """获取当前订阅数"""
        return len(self._subscribers)

    # ========== 快照/恢复 ==========

    def create_snapshot(self, label: str = "") -> Dict[str, Any]:
        """创建完整状态快照

        Args:
            label: 快照标签（用于标识）

        Returns:
            快照字典（可序列化存储）
        """
        snapshot = {
            "label": label,
            "timestamp": datetime.now().isoformat(),
            "messages": copy.deepcopy(self.messages),
            "total_usage": self.total_usage.to_dict(),
            "total_cost_usd": self.total_cost_usd,
            "turn_count": self.turn_count,
            "permission_denials": copy.deepcopy(self.permission_denials),
            "model_usage": {
                name: {
                    "model": e.model,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "cache_read_tokens": e.cache_read_tokens,
                    "cache_write_tokens": e.cache_write_tokens,
                    "cost_usd": e.cost_usd,
                    "api_calls": e.api_calls,
                }
                for name, e in self.model_usage.items()
            },
            "current_model": self._current_model,
            "active_model_override": self._active_model_override,
            "fallback_model": self.fallback_model,
            "max_budget_usd": self.max_budget_usd,
            "output_truncation_count": self.output_truncation_count,
        }
        self._emit(StateEvent.SNAPSHOT_CREATED, {"label": label, "turn": self.turn_count})
        logger.info(f"快照已创建: {label} (turn={self.turn_count})")
        return snapshot

    def restore_snapshot(self, snapshot: Dict[str, Any]) -> bool:
        """从快照恢复状态

        Args:
            snapshot: create_snapshot 生成的快照字典

        Returns:
            是否恢复成功
        """
        try:
            label = snapshot.get("label", "")
            self.messages = copy.deepcopy(snapshot.get("messages", []))

            # 恢复 Token 追踪
            usage = snapshot.get("total_usage", {})
            self.total_usage = TokenUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )
            self.total_cost_usd = snapshot.get("total_cost_usd", 0.0)
            self.turn_count = snapshot.get("turn_count", 0)
            self.permission_denials = copy.deepcopy(snapshot.get("permission_denials", []))

            # 恢复每模型使用量
            self.model_usage = {}
            for name, data in snapshot.get("model_usage", {}).items():
                entry = ModelUsageEntry(model=data["model"])
                entry.input_tokens = data.get("input_tokens", 0)
                entry.output_tokens = data.get("output_tokens", 0)
                entry.cache_read_tokens = data.get("cache_read_tokens", 0)
                entry.cache_write_tokens = data.get("cache_write_tokens", 0)
                entry.cost_usd = data.get("cost_usd", 0.0)
                entry.api_calls = data.get("api_calls", 0)
                self.model_usage[name] = entry

            self._current_model = snapshot.get("current_model")
            self._active_model_override = snapshot.get("active_model_override")
            self.fallback_model = snapshot.get("fallback_model", self.fallback_model)
            self.max_budget_usd = snapshot.get("max_budget_usd", self.max_budget_usd)
            self.output_truncation_count = snapshot.get("output_truncation_count", 0)

            self._emit(StateEvent.SNAPSHOT_RESTORED, {"label": label, "turn": self.turn_count})
            logger.info(f"快照已恢复: {label} (turn={self.turn_count})")
            return True

        except Exception as e:
            logger.error(f"快照恢复失败: {e}")
            return False

    # ========== Token 追踪 ==========

    def record_usage(self, usage, model: Optional[str] = None) -> None:
        """记录一次 API 调用的 token 用量

        Args:
            usage: OpenAI API usage 对象或 dict
            model: 模型名称（用于归类每模型费用）
        """
        if usage is None:
            return
        self.total_usage.accumulate(usage)
        self.last_turn_usage.accumulate(usage)

        # 每模型使用量追踪
        model_name = model or self._current_model or "unknown"
        if model_name not in self.model_usage:
            self.model_usage[model_name] = ModelUsageEntry(model=model_name)
        pricing = get_model_pricing(model_name)
        self.model_usage[model_name].accumulate(usage, pricing)

        # 总成本（从每模型记录汇总）
        self.total_cost_usd = sum(e.cost_usd for e in self.model_usage.values())

        # 发布用量事件
        self._emit(StateEvent.USAGE_RECORDED, {
            "model": model_name,
            "total_tokens": self.total_usage.total_tokens,
            "cost_usd": self.total_cost_usd,
        })

        # 预算检查
        if self.is_budget_exceeded():
            self._emit(StateEvent.BUDGET_EXCEEDED, {
                "cost": self.total_cost_usd,
                "budget": self.max_budget_usd,
            })

    def set_current_model(self, model: str) -> None:
        """设置当前模型名（用于 record_usage 自动归类）"""
        self._current_model = model

    def get_cost_breakdown(self) -> List[Dict[str, Any]]:
        """获取每模型费用明细"""
        result = []
        for name, entry in sorted(self.model_usage.items(), key=lambda x: x[1].cost_usd, reverse=True):
            pricing = get_model_pricing(name)
            result.append({
                "model": name,
                "input_tokens": entry.input_tokens,
                "output_tokens": entry.output_tokens,
                "cache_read": entry.cache_read_tokens,
                "cache_write": entry.cache_write_tokens,
                "api_calls": entry.api_calls,
                "cost_usd": entry.cost_usd,
                "pricing": {
                    "input": pricing.input_per_mtok,
                    "output": pricing.output_per_mtok,
                },
            })
        return result

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
        self._emit(StateEvent.PERMISSION_DENIED, {
            "tool": tool_name,
            "reason": reason,
        })

    # ========== 中断控制 ==========

    def abort(self) -> None:
        """触发中断信号"""
        self.abort_event.set()
        self._emit(StateEvent.ABORT_TRIGGERED, {})

    def is_aborted(self) -> bool:
        """检查是否已触发中断"""
        return self.abort_event.is_set()

    def clear_abort(self) -> None:
        """清除中断信号"""
        self.abort_event.clear()
        self._emit(StateEvent.ABORT_CLEARED, {})

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
        self._emit(StateEvent.QUERY_STARTED, {"turn": self.turn_count})

    def elapsed_ms(self) -> int:
        """返回自 start_query 以来的毫秒数"""
        if self._query_start_time is None:
            return 0
        return int((time.time() - self._query_start_time) * 1000)

    def increment_turn(self) -> None:
        """增加轮次计数"""
        self.turn_count += 1
        self._emit(StateEvent.TURN_INCREMENTED, {"turn": self.turn_count})

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
        self._emit(StateEvent.MESSAGE_CLEARED, {})

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
        self.model_usage = {}
        self._current_model = None
        self.reset_model_override()
