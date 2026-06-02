"""
Context 命令 - 上下文使用情况可视化

功能:
- 分析当前会话的上下文使用情况
- 按角色（system/user/assistant/tool）统计消息数量和字符占比
- 可视化展示上下文占用比例
- 给出优化建议（如何时使用 /compact）

用法:
  /context        显示上下文使用情况
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
    "claude-3.5": 200000,
    "default": 128000,
}


def _estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数"""
    return int(len(str(text)) / CHARS_PER_TOKEN)


def _make_bar(ratio: float, width: int = 30) -> str:
    """生成进度条"""
    filled = int(ratio * width)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    pct = ratio * 100
    # 根据比例选择颜色标记
    if pct < 50:
        indicator = "🟢"
    elif pct < 75:
        indicator = "🟡"
    else:
        indicator = "🔴"
    return f"{indicator} [{bar}] {pct:.1f}%"


def context_handler(args: list, loop=None) -> str:
    """context 命令处理函数"""
    if loop is None:
        return "❌ AgentLoop 未初始化"

    messages = loop.messages
    lines = []
    lines.append("📊 上下文使用情况")
    lines.append("=" * 60)

    if not messages:
        lines.append("ℹ️  上下文为空")
        return "\n".join(lines)

    # 按角色分类统计
    stats = {
        "system": {"count": 0, "chars": 0},
        "user": {"count": 0, "chars": 0},
        "assistant": {"count": 0, "chars": 0},
        "tool": {"count": 0, "chars": 0},
    }

    total_chars = 0
    total_tool_calls = 0

    for msg in messages:
        role = msg.get("role", "unknown")
        content = str(msg.get("content", ""))
        chars = len(content)
        total_chars += chars

        if role in stats:
            stats[role]["count"] += 1
            stats[role]["chars"] += chars

        # 统计工具调用
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            total_tool_calls += len(tool_calls)

    # 估算总 token 数
    estimated_tokens = _estimate_tokens(str([m.get("content", "") for m in messages]))

    # 获取模型上下文窗口大小
    model = getattr(loop, "model", "default")
    context_window = MODEL_CONTEXT_SIZES.get(model, MODEL_CONTEXT_SIZES["default"])

    # 上下文使用比例
    usage_ratio = min(estimated_tokens / context_window, 1.0)

    lines.append(f"模型: {model}")
    lines.append(f"上下文窗口: ~{context_window:,} tokens")
    lines.append(f"已使用估算: ~{estimated_tokens:,} tokens ({total_chars:,} 字符)")
    lines.append(f"\n使用率: {_make_bar(usage_ratio)}")
    lines.append("")

    # 按角色细分
    lines.append("📋 消息分类统计:")
    lines.append(f"  {'角色':<12} {'消息数':>6} {'字符数':>10} {'占比':>8}")
    lines.append(f"  {'-'*40}")

    role_names = {
        "system": "系统提示",
        "user": "用户消息",
        "assistant": "助手回复",
        "tool": "工具结果",
    }

    for role in ["system", "user", "assistant", "tool"]:
        s = stats[role]
        if s["count"] == 0 and s["chars"] == 0:
            continue
        pct = (s["chars"] / total_chars * 100) if total_chars > 0 else 0
        name = role_names.get(role, role)
        bar = _make_bar(s["chars"] / total_chars if total_chars > 0 else 0, 15)
        lines.append(f"  {name:<12} {s['count']:>6} {s['chars']:>10,} {pct:>6.1f}%")

    # 工具调用统计
    if total_tool_calls > 0:
        lines.append(f"\n🔧 工具调用次数: {total_tool_calls}")

    # 对话轮次
    user_turns = stats["user"]["count"]
    assistant_turns = stats["assistant"]["count"]
    lines.append(f"💬 对话轮次: {min(user_turns, assistant_turns)} 轮")

    # 优化建议
    lines.append("")
    lines.append("💡 优化建议:")
    if usage_ratio > 0.75:
        lines.append("  ⚠️  上下文使用率超过 75%，建议执行 /compact 压缩历史")
    elif usage_ratio > 0.5:
        lines.append("  ℹ️  上下文使用率适中，可继续使用或执行 /compact 预防")
    else:
        lines.append("  ✅ 上下文使用率较低，可放心继续对话")

    if stats["tool"]["count"] > 20:
        lines.append("  📌 工具结果占比较大，/compact 可显著减少这部分内容")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("context", {
    "description": "查看上下文使用情况 - 消息统计、token估算、优化建议",
    "handler": context_handler,
    "category": "system",
    "args_help": ""
})
