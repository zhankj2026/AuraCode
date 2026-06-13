"""
Model 命令 - 运行时模型切换

功能:
- 查看当前模型
- 切换到指定模型
- 列出可用模型
- 显示 fallback 模型状态

用法:
  /model              显示当前模型
  /model <name>       切换到指定模型
  /model list         列出可用模型
  /model reset        恢复默认模型
"""

from commands.registry import register_command
from core.session_state import MODEL_PRICING, get_model_pricing


# 内置可用模型列表（常见模型）
AVAILABLE_MODELS = [
    # Claude 系列
    "claude-opus-4",
    "claude-sonnet-4",
    "claude-3.5-sonnet",
    "claude-3.5-haiku",
    # GLM 系列
    "glm-4-plus",
    "glm-4",
    "glm-4.5",
    "glm-4.7",
    # GPT 系列
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "o1",
    "o3-mini",
    # DeepSeek
    "deepseek-chat",
    "deepseek-reasoner",
    # Qwen
    "qwen-max",
    "qwen-plus",
    "qwen-turbo",
]


def model_handler(args: list, loop=None) -> str:
    """model 命令处理函数"""
    if loop is None:
        return "❌ AgentLoop 未初始化"

    state = getattr(loop, 'state', None)
    base_model = getattr(loop, 'model', 'unknown')
    active_model = state.get_active_model(base_model) if state else base_model

    # 无参数 → 显示当前模型
    if not args:
        lines = []
        lines.append("🤖 当前模型配置")
        lines.append("=" * 60)
        lines.append(f"  基础模型:   {base_model}")
        lines.append(f"  活跃模型:   {active_model}")
        if state and state.fallback_model:
            lines.append(f"  Fallback:   {state.fallback_model}")
            if state._active_model_override:
                lines.append(f"  ⚠️  当前使用 fallback 模型")
        pricing = get_model_pricing(active_model)
        lines.append(f"  定价:       ${pricing.input_per_mtok}/M 输入, ${pricing.output_per_mtok}/M 输出")
        lines.append("")
        lines.append("  使用 /model <name> 切换模型")
        lines.append("  使用 /model list 查看可用模型")
        lines.append("  使用 /model reset 恢复默认模型")
        lines.append("=" * 60)
        return "\n".join(lines)

    action = args[0].lower()

    # list → 列出可用模型
    if action in ('list', 'ls', '列表'):
        lines = []
        lines.append("🤖 可用模型列表")
        lines.append("=" * 60)
        lines.append(f"  {'模型':<24} {'输入':>8} {'输出':>8}")
        lines.append(f"  {'-' * 44}")
        for m in AVAILABLE_MODELS:
            p = get_model_pricing(m)
            marker = " ← 当前" if m == active_model else ""
            lines.append(
                f"  {m:<24} ${p.input_per_mtok:>6.2f} ${p.output_per_mtok:>6.2f}{marker}"
            )
        lines.append("")
        lines.append("  提示: 也可输入任意 OpenAI 兼容模型名")
        lines.append("=" * 60)
        return "\n".join(lines)

    # reset → 恢复默认模型
    if action in ('reset', 'default', '默认'):
        if state:
            state.reset_model_override()
        lines = []
        lines.append(f"✅ 已恢复默认模型: {base_model}")
        return "\n".join(lines)

    # <name> → 切换模型
    target_model = " ".join(args)
    lines = []

    # 验证模型（尝试 API 调用）
    try:
        client = getattr(loop, 'client', None)
        if client:
            # 轻量验证
            resp = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": "."}],
                max_tokens=1,
                temperature=0,
            )
            validation_ok = True
        else:
            validation_ok = False
    except Exception as e:
        # 模型可能有效但当前无法验证，仍然允许切换
        lines.append(f"⚠️  无法验证模型: {str(e)[:60]}")
        lines.append(f"   将尝试切换，如模型无效将在下次调用时报错")
        validation_ok = None  # 未确定

    # 执行切换
    loop.model = target_model
    if state:
        state.reset_model_override()
        state.set_current_model(target_model)

    pricing = get_model_pricing(target_model)
    lines.insert(0, f"✅ 模型已切换: {active_model} → {target_model}")
    lines.append(f"   定价: ${pricing.input_per_mtok}/M 输入, ${pricing.output_per_mtok}/M 输出")
    if validation_ok is True:
        lines.append(f"   ✅ API 验证通过")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("model", {
    "description": "查看/切换 AI 模型 - 支持 list/reset/直接切换",
    "handler": model_handler,
    "category": "config",
    "args_help": "[模型名|list|reset]"
})
