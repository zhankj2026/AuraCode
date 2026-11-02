#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
Skill Context - 技能上下文

提供 AgentLoop 和工具之间的桥梁，让工具能够访问和管理技能。
多会话隔离：技能管理器存储在线程局部（见 _tls），每个 BridgeSession 在独立线程
运行 AgentLoop，线程局部保证不同会话的技能管理器互不串台（此前是进程级单例，
后初始化的 loop 会覆盖前者，导致多会话技能串台）。
"""

import threading
from typing import List, Optional, Dict, Any


class SkillContext:
    """
    技能上下文

    提供全局访问点，让工具能够管理技能而不直接依赖 AgentLoop 实例。
    多会话隔离：技能管理器存储在线程局部（_tls），按会话线程区分。
    """

    _instance: Optional['SkillContext'] = None
    # 线程局部：每个会话线程一份技能管理器实例（替代原进程级 _skill_manager 单例）
    _tls = threading.local()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_skill_manager(cls, skill_manager):
        """设置技能管理器（由 AgentLoop 在初始化时调用，按会话线程隔离）"""
        cls._tls.skill_manager = skill_manager

    @classmethod
    def get_skill_manager(cls):
        """获取当前会话线程的技能管理器（线程局部）"""
        return getattr(cls._tls, "skill_manager", None)

    @classmethod
    def get_available_skills(cls) -> List[Dict[str, Any]]:
        """获取可用技能列表"""
        mgr = cls.get_skill_manager()
        if mgr is None:
            return []
        return mgr.get_available_skills()

    @classmethod
    def activate_skill(cls, name: str, args: str = "") -> str:
        """激活技能"""
        mgr = cls.get_skill_manager()
        if mgr is None:
            return "错误: 技能系统未初始化"

        try:
            mgr.activate_skill(name, args=args)
            return f"技能 '{name}' 已激活"
        except ValueError as e:
            return f"激活失败: {str(e)}"

    @classmethod
    def deactivate_skill(cls, name: str) -> str:
        """停用技能"""
        mgr = cls.get_skill_manager()
        if mgr is None:
            return "错误: 技能系统未初始化"

        success = mgr.deactivate_skill(name)
        if success:
            return f"技能 '{name}' 已停用"
        else:
            return f"技能 '{name}' 未激活或不存在"

    @classmethod
    def list_skills(cls, detailed: bool = False) -> str:
        """列出所有技能"""
        mgr = cls.get_skill_manager()
        if mgr is None:
            return "错误: 技能系统未初始化"

        return mgr.list_skills(detailed=detailed)

    @classmethod
    def get_active_skills(cls) -> List[str]:
        """获取已激活的技能列表"""
        mgr = cls.get_skill_manager()
        if mgr is None:
            return []
        return mgr.get_active_skills()

    @classmethod
    def is_initialized(cls) -> bool:
        """检查是否已初始化"""
        return cls.get_skill_manager() is not None


# 全局实例（保持向后兼容；单例仅用于 AgentLoop 未显式区分的场景，
# 真正的技能管理器状态已下沉到线程局部 _tls）
skill_context = SkillContext()
