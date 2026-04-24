"""
Skill Context - 技能上下文

提供 AgentLoop 和工具之间的桥梁，让工具能够访问和管理技能。
"""

from typing import List, Optional, Dict, Any


class SkillContext:
    """
    技能上下文单例

    提供全局访问点，让工具能够管理技能而不直接依赖 AgentLoop 实例。
    """

    _instance: Optional['SkillContext'] = None
    _skill_manager = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_skill_manager(cls, skill_manager):
        """设置技能管理器（由 AgentLoop 在初始化时调用）"""
        cls._skill_manager = skill_manager

    @classmethod
    def get_available_skills(cls) -> List[Dict[str, Any]]:
        """获取可用技能列表"""
        if cls._skill_manager is None:
            return []
        return cls._skill_manager.get_available_skills()

    @classmethod
    def activate_skill(cls, name: str) -> str:
        """激活技能"""
        if cls._skill_manager is None:
            return "错误: 技能系统未初始化"

        try:
            cls._skill_manager.activate_skill(name)
            return f"技能 '{name}' 已激活"
        except ValueError as e:
            return f"激活失败: {str(e)}"

    @classmethod
    def deactivate_skill(cls, name: str) -> str:
        """停用技能"""
        if cls._skill_manager is None:
            return "错误: 技能系统未初始化"

        success = cls._skill_manager.deactivate_skill(name)
        if success:
            return f"技能 '{name}' 已停用"
        else:
            return f"技能 '{name}' 未激活或不存在"

    @classmethod
    def list_skills(cls, detailed: bool = False) -> str:
        """列出所有技能"""
        if cls._skill_manager is None:
            return "错误: 技能系统未初始化"

        return cls._skill_manager.list_skills(detailed=detailed)

    @classmethod
    def get_active_skills(cls) -> List[str]:
        """获取已激活的技能列表"""
        if cls._skill_manager is None:
            return []
        return cls._skill_manager.get_active_skills()

    @classmethod
    def is_initialized(cls) -> bool:
        """检查是否已初始化"""
        return cls._skill_manager is not None


# 全局实例
skill_context = SkillContext()
