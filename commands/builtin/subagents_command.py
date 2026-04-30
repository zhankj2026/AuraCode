"""
Subagents 命令 - Subagent 管理 (增强版)

支持:
- 查看 agent 类型
- 统计信息
- 列出 subagent
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

        # 可用的 agent 类型
        available_types = subagent_manager.get_available_agent_types()
        lines.append(f"\n可用的 Agent 类型 ({len(available_types)}):")
        for agent_type in available_types:
            if agent_type == "general":
                lines.append(f"  - {agent_type}: 通用任务")
            else:
                agent_def = subagent_manager.get_agent_definition(agent_type)
                desc = agent_def.get('description', '无描述')[:50] if agent_def else '未找到定义'
                lines.append(f"  - {agent_type}: {desc}")

        lines.append("\n子命令:")
        lines.append("  list     - 列出所有 Subagent")
        lines.append("  stats    - 查看统计信息")
        lines.append("  types    - 查看 Agent 类型详情")

        return "\n".join(lines)

    subcommand = args[0]

    if subcommand == 'list':
        return skill_tools.list_subagents_handler()
    elif subcommand == 'stats':
        return skill_tools.subagent_stats_handler()
    elif subcommand == 'types':
        return skill_tools.list_agent_types_handler()
    else:
        return f"错误: 未知子命令 '{subcommand}'\n" \
               f"可用子命令: list, stats, types"


register_command("subagents", {
    "description": "管理 Subagent",
    "handler": subagents_handler,
    "category": "system",
    "args_help": "[list|stats|types]"
})
