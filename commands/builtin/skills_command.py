"""
Skills 命令 - 技能管理

增强功能: 用户自定义 Skill 创建/删除/搜索/重载
"""

from commands.registry import register_command
from tools.builtin import skill_tools
from skills.context import SkillContext


def _get_skill_manager():
    """获取 SkillManager 实例"""
    if SkillContext.is_initialized():
        return SkillContext._skill_manager
    return None


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
    elif subcommand == 'create':
        return _cmd_create(args[1:])
    elif subcommand == 'delete' or subcommand == 'rm':
        return _cmd_delete(args[1:])
    elif subcommand == 'search':
        return _cmd_search(args[1:])
    elif subcommand == 'reload':
        return _cmd_reload()
    elif subcommand == 'info':
        return _cmd_info(args[1:])
    elif subcommand == 'sources':
        return _cmd_sources()
    elif subcommand == 'install':
        return _cmd_install(args[1:])
    else:
        return f"错误: 未知子命令 '{subcommand}'\n" \
               f"可用子命令: list, activate, deactivate, create, delete, search, reload, info, sources, install"


def _cmd_create(args) -> str:
    """创建自定义 Skill"""
    sm = _get_skill_manager()
    if sm is None:
        return "❌ 技能系统未初始化"
    if len(args) < 3:
        return "用法: /skills create <name> <description> <prompt_content>\n" \
               "示例: /skills create my-review 代码审查规范 请按PEP8标准审查代码..."
    name = args[0]
    description = args[1]
    prompt_content = " ".join(args[2:])
    # 默认项目级
    scope = "project"
    if "--user" in args:
        scope = "user"
        args_clean = [a for a in args if a != "--user"]
        name = args_clean[0] if args_clean else name
        description = args_clean[1] if len(args_clean) > 1 else description
        prompt_content = " ".join(args_clean[2:]) if len(args_clean) > 2 else prompt_content
    return sm.create_skill(name, description, f"手动激活 /skills activate {name}", prompt_content, scope)


def _cmd_delete(args) -> str:
    """删除自定义 Skill"""
    sm = _get_skill_manager()
    if sm is None:
        return "❌ 技能系统未初始化"
    if not args:
        return "用法: /skills delete <name>"
    return sm.delete_skill(args[0])


def _cmd_search(args) -> str:
    """搜索 Skill"""
    sm = _get_skill_manager()
    if sm is None:
        return "❌ 技能系统未初始化"
    if not args:
        return "用法: /skills search <关键词>"
    keyword = " ".join(args)
    results = sm.search_skills(keyword)
    if not results:
        return f"🔍 未找到匹配 '{keyword}' 的 Skill"
    lines = [f"🔍 搜索结果: '{keyword}' ({len(results)} 个匹配)", ""]
    for r in results:
        src = r.get('source', 'builtin')
        status = "✅" if r.get('is_active') else "⏸️"
        lines.append(f"  {status} [{src}] {r['name']} — {r['description']}")
    return "\n".join(lines)


def _cmd_reload() -> str:
    """重新加载所有 Skill"""
    sm = _get_skill_manager()
    if sm is None:
        return "❌ 技能系统未初始化"
    count = sm.reload_skills()
    return f"🔄 已重新加载 {count} 个 Skill"


def _cmd_info(args) -> str:
    """查看 Skill 详细信息"""
    sm = _get_skill_manager()
    if sm is None:
        return "❌ 技能系统未初始化"
    if not args:
        return "用法: /skills info <name>"
    info = sm.get_skill_info(args[0])
    if info is None:
        return f"❌ Skill 不存在: {args[0]}"
    lines = [
        f"📝 Skill 详情: {info['name']}",
        f"  描述: {info['description']}",
        f"  触发: {info['trigger']}",
        f"  来源: {info.get('source', 'builtin')}",
        f"  状态: {'✅ 已激活' if info.get('is_active') else '⏸️ 未激活'}",
    ]
    if info.get('prompt_length'):
        lines.append(f"  提示词长度: {info['prompt_length']} 字符")
    return "\n".join(lines)


def _cmd_sources() -> str:
    """显示 Skill 来源目录"""
    sm = _get_skill_manager()
    if sm is None:
        return "❌ 技能系统未初始化"
    import os
    lines = [
        "📂 Skill 来源目录:",
        f"  📦 内置: {sm.builtin_skills_dir} {'✅' if os.path.exists(sm.builtin_skills_dir) else '❌'}",
        f"  📁 项目级: {sm.project_skills_dir} {'✅' if os.path.exists(sm.project_skills_dir) else '📭'}",
        f"  👤 用户级: {sm.user_skills_dir} {'✅' if os.path.exists(sm.user_skills_dir) else '📭'}",
    ]
    return "\n".join(lines)


def _cmd_install(args) -> str:
    """从 Git 仓库安装 Skill"""
    sm = _get_skill_manager()
    if sm is None:
        return "❌ 技能系统未初始化"
    if not args:
        return "用法: /skills install <git-url> [--name <name>] [--project]\n\n" \
               "示例:\n" \
               "  /skills install https://github.com/user/my-skill\n" \
               "  /skills install https://github.com/user/my-skill --name custom-skill\n" \
               "  /skills install https://github.com/user/my-skill --project"
    url = args[0]
    name = None
    scope = "user"

    # 解析可选参数
    i = 1
    while i < len(args):
        if args[i] == '--name' and i + 1 < len(args):
            name = args[i + 1]
            i += 2
        elif args[i] == '--project':
            scope = "project"
            i += 1
        else:
            i += 1

    return sm.install_skill(url, name=name, scope=scope)


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
    "description": "技能管理 (激活/停用/创建/删除/搜索/重载)",
    "handler": skills_handler,
    "category": "skills",
    "args_help": "[list|activate|deactivate|create|delete|search|reload|info|sources|install]"
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
