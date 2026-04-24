"""
Plugins 命令 - 插件管理
"""

from commands.registry import register_command


def plugins_handler(args: list, loop=None) -> str:
    """插件命令处理函数"""
    if not loop:
        return "错误: AgentLoop 未初始化"

    if not loop.plugin_loader:
        return "插件系统未启用"

    lines = []
    lines.append("🔌 插件系统")
    lines.append("-" * 60)

    result = loop.list_plugins()
    lines.append(result)

    # 显示钩子
    hooks = loop.list_hooks()
    if hooks and "已注册的钩子" in hooks:
        lines.append("\n📌 已注册的钩子:")
        lines.append(hooks)

    return "\n".join(lines)


register_command("plugins", {
    "description": "显示插件信息",
    "handler": plugins_handler,
    "category": "system",
    "args_help": ""
})
