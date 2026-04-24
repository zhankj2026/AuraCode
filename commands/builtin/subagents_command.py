"""
Subagents 命令 - Subagent 管理
"""

from commands.registry import register_command
from core.subagent import subagent_manager
from tools.builtin import skill_tools


def subagents_handler(args: list) -> str:
    """Subagent 命令处理函数"""
    if not args:
        # 显示概览
        lines = []
        lines.append("🤖 Subagent 管理")
        lines.append("-" * 60)

        stats = subagent_manager.get_stats()
        lines.append(f"总数: {stats['total']}")
        lines.append(f"运行中: {stats['running']}")
        lines.append(f"已完成: {stats['completed']}")
        lines.append(f"失败: {stats['failed']}")

        return "\n".join(lines)

    subcommand = args[0]

    if subcommand == 'list':
        return skill_tools.list_subagents_handler()
    elif subcommand == 'stats':
        return skill_tools.subagent_stats_handler()
    else:
        return f"错误: 未知子命令 '{subcommand}'\n" \
               f"可用子命令: list, stats"


register_command("subagents", {
    "description": "管理 Subagent",
    "handler": subagents_handler,
    "category": "system",
    "args_help": "[list|stats]"
})
