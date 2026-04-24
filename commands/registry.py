"""
命令注册表

集中管理所有可用命令的定义、参数说明和处理函数。
支持动态注册新命令，生成帮助信息。
"""

from typing import Dict, Callable, Any, List, Optional

# 命令定义类型
CommandDefinition = Dict[str, Any]

# 命令注册表(全局单例)
COMMAND_REGISTRY: Dict[str, CommandDefinition] = {}


def register_command(name: str, definition: CommandDefinition):
    """
    注册命令到全局注册表

    Args:
        name: 命令名称(唯一标识)
        definition: 命令定义,包含:
            - description: 命令描述
            - handler: 执行函数
            - args_help: 参数帮助信息
            - category: 命令分类

    Raises:
        ValueError: 命令已存在或缺少必需字段
    """
    if name in COMMAND_REGISTRY:
        raise ValueError(f"命令 '{name}' 已存在")

    # 验证必需字段
    required_fields = ["description", "handler", "category"]
    for field in required_fields:
        if field not in definition:
            raise ValueError(f"命令 '{name}' 缺少必需字段: {field}")

    COMMAND_REGISTRY[name] = definition


def get_command_list() -> List[str]:
    """获取所有命令名称列表"""
    return list(COMMAND_REGISTRY.keys())


def get_commands_by_category(category: str) -> List[str]:
    """获取指定分类的命令列表"""
    return [
        name for name, cmd in COMMAND_REGISTRY.items()
        if cmd.get("category") == category
    ]


def get_command_handler(command_name: str) -> Callable:
    """
    获取命令的执行函数

    Args:
        command_name: 命令名称

    Returns:
        命令 handler 函数

    Raises:
        KeyError: 命令不存在
    """
    if command_name not in COMMAND_REGISTRY:
        raise KeyError(f"未知命令: {command_name}")

    return COMMAND_REGISTRY[command_name]["handler"]
