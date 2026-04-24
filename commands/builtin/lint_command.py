"""
Lint 命令 - 代码检查
"""

from commands.registry import register_command


def lint_handler(args: list) -> str:
    """代码检查命令处理函数"""
    from tools.builtin.lint import lint_handler

    path = args[0] if args else "."

    lines = []
    lines.append("🔍 代码检查")
    lines.append("-" * 60)

    result = lint_handler(path=path)
    lines.append(result)

    return "\n".join(lines)


register_command("lint", {
    "description": "代码检查",
    "handler": lint_handler,
    "category": "tools",
    "args_help": "[path]"
})
