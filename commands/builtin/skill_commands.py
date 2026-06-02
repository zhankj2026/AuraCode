"""
Skill 命令桥接器 - 将 skill 注册为斜杠命令

让 /simplify, /verify, /debug, /batch, /update-config 等 skill
可以通过斜杠命令直接调用，激活 skill 并将 prompt 注入 AgentLoop。
"""

from commands.registry import register_command
from skills.context import SkillContext


def _activate_and_report(skill_name: str, args: list, loop=None) -> str:
    """
    激活 skill 并将其 prompt 注入 AgentLoop 消息。
    
    如果有 loop (AgentLoop)，直接将 skill prompt 作为 system message 注入。
    如果没有 loop，返回 prompt 内容供显示。
    """
    # 激活 skill
    result = SkillContext.activate_skill(skill_name)
    if "错误" in result:
        return result
    
    # 获取 skill prompt
    skill_manager = SkillContext._skill_manager
    if skill_manager and skill_name in skill_manager.skills:
        skill = skill_manager.skills[skill_name]
        prompt_content = skill.prompt_content or ""
    else:
        return f"Skill '{skill_name}' 已激活，但无法获取 prompt 内容。"
    
    # 如果有额外参数，追加到 prompt
    extra_args = " ".join(args) if args else ""
    if extra_args:
        prompt_content += f"\n\n## 用户补充说明\n\n{extra_args}"
    
    # 如果有 AgentLoop，注入 prompt 到消息历史
    if loop and hasattr(loop, 'messages'):
        skill_message = {
            "role": "system",
            "content": f"[Skill: {skill_name} activated]\n\n{prompt_content}"
        }
        loop.messages.append(skill_message)
        return f"✅ Skill '{skill_name}' 已激活并注入对话上下文。\n\n" \
               f"Skill 内容 ({len(prompt_content)} 字符) 已作为 system message 注入。\n" \
               f"请描述你要处理的具体任务，我将按照 skill 指导执行。"
    
    # 无 loop 时返回 prompt 预览
    preview = prompt_content[:300]
    if len(prompt_content) > 300:
        preview += "..."
    
    return f"✅ Skill '{skill_name}' 已激活。\n\n" \
           f"Prompt 内容预览 ({len(prompt_content)} 字符):\n\n{preview}\n\n" \
           f"在对话模式下，skill 的完整指导将注入 AI 上下文。"


# ========== 注册 Skill 斜杠命令 ==========

def simplify_handler(args: list, loop=None) -> str:
    """/simplify - 代码审查与简化"""
    return _activate_and_report("simplify", args, loop)


def verify_handler(args: list, loop=None) -> str:
    """/verify - 验证代码变更"""
    return _activate_and_report("verify", args, loop)


def debug_handler(args: list, loop=None) -> str:
    """/debug - 调试诊断"""
    return _activate_and_report("debug", args, loop)


def batch_handler(args: list, loop=None) -> str:
    """/batch - 大规模并行变更"""
    return _activate_and_report("batch", args, loop)


def update_config_handler(args: list, loop=None) -> str:
    """/update-config - 配置管理"""
    return _activate_and_report("update-config", args, loop)


# 注册命令
register_command("simplify", {
    "description": "审查变更代码的代码复用、质量和效率，发现并修复问题",
    "handler": simplify_handler,
    "category": "skills",
    "args_help": "[额外关注点]"
})

register_command("verify", {
    "description": "验证代码变更是否按预期工作，通过运行应用/测试来确认",
    "handler": verify_handler,
    "category": "skills",
    "args_help": "[验证要求]"
})

register_command("debug", {
    "description": "调试和诊断当前会话中的问题",
    "handler": debug_handler,
    "category": "skills",
    "args_help": "[问题描述]"
})

register_command("batch", {
    "description": "大规模并行变更编排，分解为多个独立单元逐一实现",
    "handler": batch_handler,
    "category": "skills",
    "args_help": "<变更指令>"
})

register_command("update-config", {
    "description": "管理 opencode 配置（LLM/权限/钩子/日志）",
    "handler": update_config_handler,
    "category": "skills",
    "args_help": "[配置请求]"
})
