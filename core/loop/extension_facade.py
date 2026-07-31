#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.extension_facade — 扩展系统控制面

从 ``AgentLoop`` 提取的扩展系统查询 / 控制 API（技能 / 钩子 / 插件 / 状态）。
这些方法是对外公共接口（被 commands、tests 等广泛调用），与主循环编排无关，
因此独立成 ``ExtensionFacade`` 协作者。

``AgentLoop`` 保留同名方法作为**转发桩**，保证既有调用方零破坏::

    loop.activate_skill(...)    ->  loop.extensions.activate_skill(...)
    loop.get_system_status()    ->  loop.extensions.get_system_status()
"""

import logging
from typing import Any, Dict, List

from tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)


class ExtensionFacade:
    """扩展系统（技能 / 钩子 / 插件）的统一查询与控制面。"""

    def __init__(self, loop):
        self.loop = loop

    # ========== 技能系统 ==========

    def activate_skill(self, name: str) -> bool:
        """
        激活指定的技能

        Args:
            name: 技能名称

        Returns:
            True 如果成功, False 否则
        """
        loop = self.loop
        if not loop.skill_manager or not loop.skills_enabled:
            logger.warning("技能系统未启用")
            return False

        try:
            loop.skill_manager.activate_skill(name)
            logger.info(f"激活技能: {name}")
            return True
        except ValueError as e:
            logger.warning(f"激活技能失败: {e}")
            return False

    def deactivate_skill(self, name: str) -> bool:
        """
        停用指定的技能

        Args:
            name: 技能名称

        Returns:
            True 如果成功, False 否则
        """
        loop = self.loop
        if not loop.skill_manager or not loop.skills_enabled:
            logger.warning("技能系统未启用")
            return False

        return loop.skill_manager.deactivate_skill(name)

    def list_skills(self) -> str:
        """列出所有可用技能"""
        loop = self.loop
        if not loop.skill_manager or not loop.skills_enabled:
            return "技能系统未启用"

        return loop.skill_manager.list_skills(detailed=True)

    def list_active_skills(self) -> List[str]:
        """获取已激活的技能列表"""
        loop = self.loop
        if not loop.skill_manager or not loop.skills_enabled:
            return []

        return loop.skill_manager.get_active_skills()

    # ========== 钩子系统 ==========

    def register_hook(
        self,
        event: str,
        handler,
        matcher: str = None,
        priority: int = 0,
    ) -> int:
        """
        手动注册钩子

        Args:
            event: 钩子事件类型
            handler: 钩子处理函数
            matcher: 可选, 只匹配特定工具名称
            priority: 优先级, 数字越大越先执行

        Returns:
            钩子 ID, 如果失败返回 -1
        """
        loop = self.loop
        if not loop.hook_manager or not loop.hooks_enabled:
            logger.warning("钩子系统未启用")
            return -1

        try:
            hook_id = loop.hook_manager.register_hook(event, handler, matcher, priority)
            logger.info(f"注册钩子: {event} [ID: {hook_id}]")
            return hook_id
        except ValueError as e:
            logger.warning(f"注册钩子失败: {e}")
            return -1

    def unregister_hook(self, hook_id: int) -> bool:
        """
        删除钩子

        Args:
            hook_id: 钩子 ID

        Returns:
            True 如果成功, False 否则
        """
        loop = self.loop
        if not loop.hook_manager or not loop.hooks_enabled:
            return False

        return loop.hook_manager.unregister_hook(hook_id)

    def list_hooks(self) -> str:
        """列出所有已注册的钩子"""
        loop = self.loop
        if not loop.hook_manager or not loop.hooks_enabled:
            return "钩子系统未启用"

        hooks = loop.hook_manager.list_hooks()
        if not hooks:
            return "没有注册的钩子"

        lines = ["已注册的钩子:", ""]
        for h in hooks:
            lines.append(f"  [ID: {h['id']}] {h['event']}")
            if h['matcher']:
                lines.append(f"    匹配: {h['matcher']}")
            lines.append(f"    优先级: {h['priority']}")
            lines.append("")

        return "\n".join(lines)

    # ========== 插件系统 ==========

    def list_plugins(self) -> str:
        """列出所有已加载的插件"""
        loop = self.loop
        if not loop.plugin_loader or not loop.plugins_enabled:
            return "插件系统未启用"

        plugins = loop.plugin_loader.list_plugins()
        if not plugins:
            return "没有加载的插件"

        lines = [f"已加载的插件 (共 {len(plugins)} 个):", ""]
        for p in plugins:
            status = "✅" if p['available'] else "❌"
            lines.append(f"  {status} {p['name']} v{p['version']}")
            lines.append(f"     {p['description']}")
            lines.append("")

        return "\n".join(lines)

    # ========== 系统状态 ==========

    def get_system_status(self) -> Dict[str, Any]:
        """获取扩展系统状态"""
        loop = self.loop
        return {
            "plugins": {
                "enabled": loop.plugins_enabled,
                "loaded": len(loop.plugin_loader.plugins) if loop.plugin_loader else 0,
            },
            "hooks": {
                "enabled": loop.hooks_enabled,
                "registered": sum(loop.hook_manager.get_hook_stats().values()) if loop.hook_manager else 0,
            },
            "skills": {
                "enabled": loop.skills_enabled,
                "total": len(loop.skill_manager.skills) if loop.skill_manager else 0,
                "active": len(loop.skill_manager.get_active_skills()) if loop.skill_manager else 0,
            },
            "tools": {
                "total": len(TOOL_REGISTRY),
            },
        }
