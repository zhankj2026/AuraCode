"""
Skills 命令 - 技能管理
"""

from commands.registry import register_command
from tools.builtin import skill_tools


def skills_handler(args: list) -> str:
    """技能命令处理函数"""
    if not args:
        return skill_tools.show_available_skills_handler()

    subcommand = args[0]

    if subcommand == 'list':
        return skill_tools.show_available_skills_handler()
    elif subcommand == 'activate':
        if len(args) < 2:
            return "错误: 请指定技能名称\n用法: skills activate <name>"
        return skill_tools.activate_skill_handler(args[1])
    elif subcommand == 'deactivate':
        if len(args) < 2:
            return "错误: 请指定技能名称\n用法: skills deactivate <name>"
        return skill_tools.deactivate_skill_handler(args[1])
    else:
        return f"错误: 未知子命令 '{subcommand}'\n" \
               f"可用子命令: list, activate, deactivate"


def activate_handler(args: list) -> str:
    """激活技能（快捷方式）"""
    if not args:
        return "错误: 请指定技能名称\n用法: activate <name>"
    return skill_tools.activate_skill_handler(args[0])


def deactivate_handler(args: list) -> str:
    """停用技能（快捷方式）"""
    if not args:
        return "错误: 请指定技能名称\n用法: deactivate <name>"
    return skill_tools.deactivate_skill_handler(args[0])


def active_handler(args: list) -> str:
    """显示已激活的技能"""
    return skill_tools.get_active_skills_handler()


register_command("skills", {
    "description": "管理技能",
    "handler": skills_handler,
    "category": "skills",
    "args_help": "[list|activate|deactivate] [name]"
})

register_command("activate", {
    "description": "激活技能（快捷方式）",
    "handler": activate_handler,
    "category": "skills",
    "args_help": "<name>"
})

register_command("deactivate", {
    "description": "停用技能（快捷方式）",
    "handler": deactivate_handler,
    "category": "skills",
    "args_help": "<name>"
})

register_command("active", {
    "description": "显示已激活的技能",
    "handler": active_handler,
    "category": "skills",
    "args_help": ""
})
