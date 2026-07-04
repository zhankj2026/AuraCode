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
插件基类 - 定义插件接口

基于 code.md Phase 4 实现
参考: 第 6.1 节
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class ToolPlugin(ABC):
    """
    插件基类
    
    所有插件必须继承此类并实现抽象方法。
    
    可选属性（有默认值，子类可按需覆盖）：
    - default_enabled: 默认启用状态（配合 builtin.py 三级回退链）
    - source: 插件来源（builtin/project/user/marketplace）
    - mcp_servers: 携带的 MCP Server 配置
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """插件描述"""
        pass

    # ── 可选属性（子类可覆盖）──────────────────────────────────

    @property
    def default_enabled(self) -> bool:
        """
        默认启用状态（三级回退链的第二级）

        回退优先级: 用户设置 > default_enabled > True
        内置插件设为 False 则默认禁用，需用户手动开启。
        """
        return True

    @property
    def source(self) -> str:
        """
        插件来源标识

        可选值: builtin / project / user / marketplace
        用于生成规范 plugin_id: {name}@{source}
        """
        return "user"

    @property
    def mcp_servers(self) -> List[Dict[str, Any]]:
        """
        插件携带的 MCP Server 配置列表

        格式示例:
        [
            {
                "name": "my-server",
                "command": "node",
                "args": ["server.js"],
                "env": {"KEY": "value"}
            }
        ]
        """
        return []
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        返回工具定义列表
        
        Returns:
            工具定义列表,格式与 tools.registry.register_tool 一致
        """
        pass
    
    @abstractmethod
    def get_hooks(self) -> List[Dict[str, Any]]:
        """
        返回钩子定义列表
        
        Returns:
            钩子定义列表,格式:
            [
                {
                    "event": "PreToolUse",  # 钩子事件
                    "handler": callable,     # 处理函数
                    "matcher": "run_command" # 可选,匹配特定工具
                }
            ]
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        检查插件是否可用
        
        返回 False 时:
        - loader.py: 不加载该插件
        - builtin.py: 完全隐藏（不出现在 enabled/disabled 列表）
        
        Returns:
            True 如果插件可用,False 否则
        """
        pass
    
    def initialize(self) -> bool:
        """
        初始化插件(可选实现)
        
        Returns:
            True 如果初始化成功,False 否则
        """
        return True
    
    def cleanup(self):
        """清理插件资源(可选实现)"""
        pass

    @property
    def plugin_id(self) -> str:
        """规范插件 ID: {name}@{source}"""
        return f"{self.name}@{self.source}"
    
    def __repr__(self) -> str:
        return f"<Plugin {self.plugin_id} v{self.version}>"
