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
    
    所有插件必须继承此类并实现抽象方法
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
    
    def __repr__(self) -> str:
        return f"<Plugin {self.name} v{self.version}>"
