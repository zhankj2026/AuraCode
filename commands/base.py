"""
命令基类 - 定义命令接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class Command(ABC):
    """
    命令基类

    所有命令应该继承此类并实现抽象方法
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """命令名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """命令描述"""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """命令分类 (system/skills/tools/analysis)"""
        pass

    @abstractmethod
    def execute(self, args: List[str]) -> str:
        """
        执行命令

        Args:
            args: 命令参数列表

        Returns:
            执行结果字符串
        """
        pass

    @property
    def args_help(self) -> Optional[str]:
        """参数帮助信息"""
        return None

    def get_help(self) -> str:
        """获取命令帮助信息"""
        help_text = f"{self.name}: {self.description}\n"
        if self.args_help:
            help_text += f"用法: {self.name} {self.args_help}\n"
        return help_text

    def __repr__(self) -> str:
        return f"<Command {self.name}>"
