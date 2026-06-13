"""
Context 命令 - 上下文使用情况可视化

功能:
- 分析当前会话的上下文使用情况
- 按角色（system/user/assistant/tool）统计消息数量和字符/token占比
- Token 分布图（可视化柱状图）
- Top-N 最大消息排名
- 动态压缩阈值计算（根据模型上下文窗口自动调整）
- 给出优化建议（如何时使用 /compact）

用法:
  /context          显示上下文使用情况
  /context detail   显示详细信息（含 Top-N 消息排名）
  /context dist     显示 token 分布图
"""

from commands.registry import register_command

# 粗略估算 token 数（中文约1.5字符/token，英文约4字符/token，取平均）
CHARS_PER_TOKEN = 3.5

# 常见模型的上下文窗口大小（token 数）
MODEL_CONTEXT_SIZES = {
    "glm-4": 128000,
    "glm-4-plus": 128000,
    "glm-4.5": 128000,
    "glm-4.7": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "o1": 200000,
    "o3-mini": 200000,
    "claude-3.5-sonnet": 200000,
    "claude-3.5-haiku": 200000,
    "claude-opus-4": 200000,
    "claude-sonnet-4": 200000,
    "deepseek-chat": 64000,
    "deepseek-reasoner": 64000,
    "qwen-max": 32000,
    "qwen-plus": 128000,
    "qwen-turbo": 128000,
    "default": 128000,
}

# 动态压缩阈值比例（占上下文窗口的百分比）
COMPACT_THRESHOLD_PCT = 0.60  # 60%
COMPACT_WARN_PCT = 0.45       # 45%


def _estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数"""
    return int(len(str(text)) / CHARS_PER_TOKEN)


def _make_bar(ratio: float, width: int = 30) -> str:
    """生成进度条"""
    filled = int(ratio * width)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    pct = ratio * 100
    if pct < 50:
        indicator = "🟢"
    elif pct < 75:
        indicator = "🟡"
    else:
        indicator = "🔴"
    return f"{indicator} [{bar}] {pct:.1f}%"


def _get_context_window(model: str) -> int:
    """获取模型上下文窗口大小"""
    # 精确匹配
    if model in MODEL_CONTEXT_SIZES:
        return MODEL_CONTEXT_SIZES[model]
    # 子串匹配
    for key, val in MODEL_CONTEXT_SIZES.items():
        if key in model or model in key:
            return val
    return MODEL_CONTEXT_SIZES["default"]


def _get_dynamic_threshold(context_window: int) -> int:
    """根据上下文窗口动态计算压缩阈值（消息条数）"""
    # 粗略估算：每消息平均 ~800 token
    avg_tokens_per_msg = 800
    max_msgs = int(context_window * COMPACT_THRESHOLD_PCT / avg_tokens_per_msg)
    # 限制在合理范围内
    return max(20, min(max_msgs, 80))


def _token_distribution_chart(role_tokens: dict, total: int, width: int = 40) -> str:
    """生成 token 分布柱状图"""
    if total == 0:
        return "  (无数据)"
    lines = []
    role_labels = {
        "system": "📌 系统提示",
        "user": "👤 用户消息",
        "assistant": "🤖 助手回复",
        "tool": "🔧 工具结果",
    }
    for role in ["system", "user", "assistant", "tool"]:
        tokens = role_tokens.get(role, 0)
        if tokens == 0:
            continue
        ratio = tokens / total
        bar_len = max(1, int(ratio * width))
        bar = "█" * bar_len
        pct = ratio * 100
        label = role_labels.get(role, role)
        lines.append(f"  {label:<12} {bar:<{width}} {tokens:>7,} ({pct:5.1f}%)")
    return "\n".join(lines)


def context_handler(args: list, loop=None) -> str:
    """context 命令处理函数"""
    if loop is None:
        return "❌ AgentLoop 未初始化"

    messages = loop.messages
    subcmd = args[0].lower() if args else ""

    if subcmd == "dist":
        return _cmd_dist(loop, messages)
    elif subcmd == "detail":
        return _cmd_detail(loop, messages)

    # 默认：概览
    return _cmd_overview(loop, messages)


def _cmd_overview(loop, messages) -> str:
    """上下文概览"""
    lines = []
    lines.append("📊 上下文使用情况")
    lines.append("=" * 60)

    if not messages:
        lines.append("ℹ️  上下文为空")
        return "\n".join(lines)

    # 按角色分类统计
    stats = _collect_stats(messages)
    total_chars = stats["total_chars"]
    estimated_tokens = _estimate_tokens(
        str([m.get("content", "") for m in messages])
    )

    model = getattr(loop, "model", "default")
    context_window = _get_context_window(model)
    dynamic_threshold = _get_dynamic_threshold(context_window)
    usage_ratio = min(estimated_tokens / context_window, 1.0)

    lines.append(f"  模型: {model}")
    lines.append(f"  上下文窗口: {context_window:,} tokens")
    lines.append(f"  已使用估算: ~{estimated_tokens:,} tokens ({total_chars:,} 字符)")
    lines.append(f"  动态压缩阈值: {dynamic_threshold} 条消息")
    lines.append(f"\n  使用率: {_make_bar(usage_ratio)}")
    lines.append("")

    # Token 分布图
    lines.append("📋 Token 分布:")
    lines.append(_token_distribution_chart(stats["role_tokens"], estimated_tokens))

    # 消息统计
    total_msgs = len(messages)
    lines.append(f"\n  📊 消息总数: {total_msgs}")
    lines.append(f"  💬 对话轮次: {min(stats['user_count'], stats['assistant_count'])} 轮")
    if stats["tool_calls"] > 0:
        lines.append(f"  🔧 工具调用次数: {stats['tool_calls']}")

    # 优化建议
    lines.append("")
    lines.append(_make_suggestions(usage_ratio, total_msgs, dynamic_threshold, stats))
    lines.append("=" * 60)
    lines.append("  提示: /context detail 查看消息排名 | /context dist 查看分布图")
    return "\n".join(lines)


def _cmd_dist(loop, messages) -> str:
    """Token 分布详情"""
    if not messages:
        return "ℹ️  上下文为空"

    stats = _collect_stats(messages)
    estimated_tokens = _estimate_tokens(
        str([m.get("content", "") for m in messages])
    )
    model = getattr(loop, "model", "default")
    context_window = _get_context_window(model)

    lines = ["📊 Token 分布详情", "=" * 60]
    lines.append(f"  模型: {model} ({context_window:,} tokens)")
    lines.append(f"  当前估算: ~{estimated_tokens:,} tokens")
    lines.append("")

    # 分布图
    lines.append(_token_distribution_chart(stats["role_tokens"], estimated_tokens, width=50))

    # 角色明细
    lines.append("")
    lines.append(f"  {'角色':<12} {'消息数':>6} {'字符数':>10} {'估算Token':>10} {'占比':>8}")
    lines.append(f"  {'-'*52}")
    role_names = {"system": "系统提示", "user": "用户消息", "assistant": "助手回复", "tool": "工具结果"}
    total_t = sum(stats["role_tokens"].values()) or 1
    for role in ["system", "user", "assistant", "tool"]:
        tokens = stats["role_tokens"].get(role, 0)
        chars = stats["role_chars"].get(role, 0)
        count = stats["role_counts"].get(role, 0)
        if count == 0:
            continue
        pct = tokens / total_t * 100
        lines.append(f"  {role_names[role]:<12} {count:>6} {chars:>10,} {tokens:>10,} {pct:>6.1f}%")

    lines.append("=" * 60)
    return "\n".join(lines)


def _cmd_detail(loop, messages) -> str:
    """详细信息（含 Top-N 消息排名）"""
    if not messages:
        return "ℹ️  上下文为空"

    stats = _collect_stats(messages)
    estimated_tokens = _estimate_tokens(
        str([m.get("content", "") for m in messages])
    )
    model = getattr(loop, "model", "default")
    context_window = _get_context_window(model)
    dynamic_threshold = _get_dynamic_threshold(context_window)

    lines = ["📊 上下文详情 + Top-10 消息排名", "=" * 60]

    usage_ratio = min(estimated_tokens / context_window, 1.0)
    lines.append(f"  模型: {model} | 窗口: {context_window:,} | 使用率: {usage_ratio*100:.1f}%")
    lines.append(f"  动态压缩阈值: {dynamic_threshold} 条 (当前 {len(messages)} 条)")
    lines.append("")

    # Top-10 最大消息
    msg_sizes = []
    for i, msg in enumerate(messages):
        content = str(msg.get("content", ""))
        chars = len(content)
        tokens = _estimate_tokens(content)
        role = msg.get("role", "?")
        # 工具调用标记
        tc = msg.get("tool_calls", [])
        tc_info = f" [+{len(tc)}工具]" if tc else ""
        msg_sizes.append((chars, i, role, tokens, tc_info))

    msg_sizes.sort(reverse=True)
    lines.append("  🏆 Top-10 最大消息:")
    lines.append(f"  {'#':>3} {'位置':>4} {'角色':<10} {'字符数':>8} {'估算Token':>10} {'占比':>7}")
    lines.append(f"  {'-'*48}")
    for rank, (chars, idx, role, tokens, tc_info) in enumerate(msg_sizes[:10], 1):
        pct = chars / max(stats["total_chars"], 1) * 100
        lines.append(f"  {rank:>3} [{idx:>3}] {role:<10} {chars:>8,} {tokens:>10,} {pct:>5.1f}%{tc_info}")

    # 消息类型分布
    lines.append(f"\n  📋 消息角色分布:")
    for role in ["system", "user", "assistant", "tool"]:
        count = stats["role_counts"].get(role, 0)
        lines.append(f"    {role:<12} {count:>4} 条")

    lines.append(f"\n  总计: {len(messages)} 条消息")
    lines.append("=" * 60)
    return "\n".join(lines)


def _collect_stats(messages) -> dict:
    """收集消息统计信息"""
    role_chars = {"system": 0, "user": 0, "assistant": 0, "tool": 0}
    role_counts = {"system": 0, "user": 0, "assistant": 0, "tool": 0}
    total_chars = 0
    total_tool_calls = 0

    for msg in messages:
        role = msg.get("role", "unknown")
        content = str(msg.get("content", ""))
        chars = len(content)
        total_chars += chars
        if role in role_chars:
            role_chars[role] += chars
            role_counts[role] += 1
        tc = msg.get("tool_calls", [])
        if tc:
            total_tool_calls += len(tc)

    # 估算每角色 token
    total_t = max(_estimate_tokens(str([m.get("content", "") for m in messages])), 1)
    ratio = total_t / max(total_chars, 1)
    role_tokens = {r: int(c * ratio) for r, c in role_chars.items()}

    return {
        "total_chars": total_chars,
        "role_chars": role_chars,
        "role_counts": role_counts,
        "role_tokens": role_tokens,
        "tool_calls": total_tool_calls,
        "user_count": role_counts["user"],
        "assistant_count": role_counts["assistant"],
    }


def _make_suggestions(usage_ratio, total_msgs, dynamic_threshold, stats) -> str:
    """生成优化建议"""
    lines = ["💡 优化建议:"]
    if usage_ratio > 0.75:
        lines.append("  ⚠️  上下文使用率超过 75%，建议执行 /compact 压缩历史")
    elif usage_ratio > 0.5:
        lines.append("  ℹ️  上下文使用率适中，可继续使用或执行 /compact 预防")
    else:
        lines.append("  ✅ 上下文使用率较低，可放心继续对话")

    if total_msgs > dynamic_threshold:
        lines.append(f"  ⚠️  消息数 ({total_msgs}) 超过动态阈值 ({dynamic_threshold})，即将触发自动压缩")

    if stats["role_counts"].get("tool", 0) > 20:
        lines.append("  📌 工具结果占比较大，/compact 可显著减少这部分内容")

    tool_pct = stats["role_tokens"].get("tool", 0) / max(sum(stats["role_tokens"].values()), 1) * 100
    if tool_pct > 50:
        lines.append(f"  🔧 工具结果占总 token 的 {tool_pct:.0f}%，考虑优化工具调用频率")

    return "\n".join(lines)


register_command("context", {
    "description": "上下文可视化 - token分布图/Top-N排名/动态阈值/优化建议",
    "handler": context_handler,
    "category": "system",
    "args_help": "[detail|dist]"
})
