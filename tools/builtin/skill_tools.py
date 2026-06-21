"""
Skill 工具 - 让 LLM 能够激活和管理技能

通过 SkillContext 间接访问 SkillManager，避免直接依赖 AgentLoop 实例。
"""

from tools.registry import register_tool
from skills.context import SkillContext


def list_skills_handler(detailed: bool = False) -> str:
    """
    列出所有可用的技能

    显示所有可用技能的名称、描述和激活状态。

    Args:
        detailed: 是否显示详细信息（包括提示词预览）

    Returns:
        技能列表字符串
    """
    try:
        return SkillContext.list_skills(detailed=detailed)
    except Exception as e:
        return f"获取技能列表失败: {str(e)}"


def activate_skill_handler(skill_name: str) -> str:
    """
    激活指定的技能

    激活后，技能的完整提示词将被注入到系统提示词中，
    影响 AI 在后续对话中的行为和决策。

    使用场景:
    - 用户任务涉及特定领域（如 Python 编码规范）
    - 需要 AI 遵循特定的标准或工作流
    - 增强特定任务的专业性

    Args:
        skill_name: 技能名称（如 'python-standards', 'git-workflow'）

    Returns:
        激活结果

    示例:
        激活 Python 编码规范技能:
        activate_skill(skill_name="python-standards")
    """
    try:
        result = SkillContext.activate_skill(skill_name)

        # 添加激活后的提示信息
        if "已激活" in result:
            active = SkillContext.get_active_skills()
            return f"""{result}

当前已激活的技能: {', '.join(active)}

注意: 技能激活后将在下一次 LLM 调用时生效。"""

        return result

    except Exception as e:
        return f"激活技能失败: {str(e)}"


def deactivate_skill_handler(skill_name: str) -> str:
    """
    停用指定的技能

    停用后，该技能的提示词将不再注入到系统提示词中。

    使用场景:
    - 技能不再适用于当前任务
    - 减少 token 使用
    - 切换到不同的工作流

    Args:
        skill_name: 技能名称

    Returns:
        停用结果
    """
    try:
        result = SkillContext.deactivate_skill(skill_name)

        if "已停用" in result:
            remaining = SkillContext.get_active_skills()
            if remaining:
                return f"{result}\n\n当前仍激活的技能: {', '.join(remaining)}"
            else:
                return f"{result}\n\n当前没有激活的技能"

        return result

    except Exception as e:
        return f"停用技能失败: {str(e)}"


def get_active_skills_handler() -> str:
    """
    获取当前已激活的技能列表

    返回当前激活的技能名称列表，便于了解 AI 当前使用哪些专业技能。

    Returns:
        已激活技能列表
    """
    try:
        active = SkillContext.get_active_skills()

        if not active:
            return "当前没有激活的技能。\n\n使用 activate_skill 工具来激活需要的技能。"

        lines = ["当前已激活的技能:", ""]
        for skill_name in active:
            lines.append(f"- {skill_name}")

        lines.append("")
        lines.append("使用 deactivate_skill 工具来停用不需要的技能。")

        return "\n".join(lines)

    except Exception as e:
        return f"获取激活技能失败: {str(e)}"


def show_available_skills_handler() -> str:
    """
    显示所有可用技能的概览

    展示所有可用技能的名称、描述和触发条件，
    帮助决定是否需要激活特定技能。

    Returns:
        可用技能概览
    """
    try:
        available = SkillContext.get_available_skills()

        if not available:
            return "没有可用的技能。"

        lines = ["可用技能概览:", ""]

        for skill in available:
            status = "[已激活]" if skill['is_active'] else "[未激活]"
            lines.append(f"**{skill['name']}** {status}")
            lines.append(f"  描述: {skill['description']}")
            lines.append(f"  触发: {skill['trigger']}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"获取可用技能失败: {str(e)}"


def invoke_skill_handler(skill_name: str, args: str = "") -> str:
    """
    主动调用技能（模型根据 when_to_use 提示自动触发）

    根据技能名称和可选参数，激活并执行技能的完整 prompt。
    支持 Shell 命令执行和参数替换。

    Args:
        skill_name: 技能名称
        args: 传递给技能的参数

    Returns:
        技能的 prompt 内容（已处理）
    """
    try:
        sm = SkillContext._skill_manager
        if sm is None:
            return "❌ 技能系统未初始化"
        return sm.invoke_skill(skill_name, args)
    except Exception as e:
        return f"调用技能失败: {str(e)}"


# 注册工具
register_tool("list_skills", {
    "description": "列出所有可用的技能及其状态",
    "parameters": {
        "type": "object",
        "properties": {
            "detailed": {
                "type": "boolean",
                "description": "是否显示详细信息（包括提示词预览）",
                "default": False
            }
        },
        "required": []
    },
    "handler": list_skills_handler,
    "permission_level": "read"
})

register_tool("show_available_skills", {
    "description": "显示所有可用技能的概览（名称、描述、触发条件）",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    },
    "handler": show_available_skills_handler,
    "permission_level": "read"
})

register_tool("activate_skill", {
    "description": """激活指定的技能，将其专业知识注入到后续对话中。

技能激活后，AI 将在后续对话中遵循该技能的专业标准和最佳实践。

使用场景:
- 任务涉及特定领域（如 Python 编码规范、Git 工作流）
- 需要 AI 遵循特定标准
- 增强任务的专业性

示例: activate_skill(skill_name="python-standards")""",
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "技能名称（如 'python-standards', 'git-workflow'）"
            }
        },
        "required": ["skill_name"]
    },
    "handler": activate_skill_handler,
    "permission_level": "read"
})

register_tool("deactivate_skill", {
    "description": """停用指定的技能，将其专业知识从后续对话中移除。

使用场景:
- 技能不再适用于当前任务
- 减少 token 使用
- 切换到不同的工作流""",
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "要停用的技能名称"
            }
        },
        "required": ["skill_name"]
    },
    "handler": deactivate_skill_handler,
    "permission_level": "read"
})

register_tool("get_active_skills", {
    "description": "获取当前已激活的技能列表",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    },
    "handler": get_active_skills_handler,
    "permission_level": "read"
})

register_tool("invoke_skill", {
    "description": """主动调用技能。当系统提示中的 when_to_use 条件满足时，使用此工具激活并执行技能。

技能执行流程:
1. 激活技能并加载完整 prompt
2. 执行 prompt 中的 Shell 命令（!`...` 语法）
3. 替换参数占位符（${1}, ${2} 等）
4. 返回处理后的 prompt 内容

示例:
- invoke_skill(skill_name="simplify") — 代码审查
- invoke_skill(skill_name="verify") — 验证变更
- invoke_skill(skill_name="debug", args="error log content") — 调试问题""",
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "要调用的技能名称"
            },
            "args": {
                "type": "string",
                "description": "传递给技能的参数（可选）",
                "default": ""
            }
        },
        "required": ["skill_name"]
    },
    "handler": invoke_skill_handler,
    "permission_level": "read"
})
