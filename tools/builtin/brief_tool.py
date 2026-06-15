"""
BriefTool — 简洁模式切换

控制 LLM 输出的详细程度，支持 brief（简洁）/ normal / verbose（详细）三种模式。
参考 BriefTool 实现。
"""
from tools.registry import register_tool


# 全局模式状态
_BRIEF_STATE = {
    "mode": "normal",  # brief / normal / verbose
}


def get_brief_mode() -> str:
    """供其他模块读取当前输出模式"""
    return _BRIEF_STATE["mode"]


def brief_handler(
    mode: str = "",
    toggle: bool = False,
) -> str:
    """
    切换输出详细程度。

    Args:
        mode: 目标模式（brief/normal/verbose）
        toggle: 是否在 brief ↔ normal 之间切换

    Returns:
        当前模式及说明
    """
    if toggle:
        if _BRIEF_STATE["mode"] == "brief":
            _BRIEF_STATE["mode"] = "normal"
        else:
            _BRIEF_STATE["mode"] = "brief"
        return _format_mode_response()

    if mode:
        valid_modes = {"brief", "normal", "verbose"}
        if mode not in valid_modes:
            return f"错误: 无效模式 '{mode}'，可选: {', '.join(sorted(valid_modes))}"
        _BRIEF_STATE["mode"] = mode
        return _format_mode_response()

    # 无参数 → 显示当前模式
    return _format_mode_response()


def _format_mode_response() -> str:
    """格式化模式切换响应"""
    mode = _BRIEF_STATE["mode"]
    descriptions = {
        "brief": (
            "📝 简洁模式已启用\n"
            "• 回复将尽量简短，只给出关键信息\n"
            "• 省略解释和背景说明\n"
            "• 代码注释最小化"
        ),
        "normal": (
            "📄 标准模式\n"
            "• 适度详细的回复\n"
            "• 包含必要的解释和上下文\n"
            "• 代码注释适中"
        ),
        "verbose": (
            "📚 详细模式已启用\n"
            "• 回复将包含完整解释和背景\n"
            "• 详细的步骤说明和推理过程\n"
            "• 代码注释详尽"
        ),
    }
    return descriptions.get(mode, f"未知模式: {mode}")


def build_brief_system_hint() -> str:
    """
    构建注入到 system prompt 中的简洁模式提示。
    供 agent_loop._build_system_prompt() 调用。
    """
    mode = _BRIEF_STATE["mode"]
    if mode == "brief":
        return (
            "\n\n[OUTPUT MODE: BRIEF]\n"
            "Respond concisely. Skip explanations unless asked. "
            "Code with minimal comments. No preamble."
        )
    elif mode == "verbose":
        return (
            "\n\n[OUTPUT MODE: VERBOSE]\n"
            "Provide thorough explanations. Include reasoning steps, "
            "alternatives considered, and detailed code comments."
        )
    return ""  # normal → 不注入


register_tool("brief", {
    "description": "切换输出详细程度（brief=简洁/normal=标准/verbose=详细）",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": "目标模式: brief/normal/verbose",
                "default": "",
            },
            "toggle": {
                "type": "boolean",
                "description": "在 brief 和 normal 之间快速切换",
                "default": False,
            },
        },
    },
    "handler": brief_handler,
    "permission_level": "read",
})
