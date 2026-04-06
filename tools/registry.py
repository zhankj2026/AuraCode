"""
工具注册表

集中管理所有可用工具的定义、参数 Schema 和执行 handler。
支持动态注册新工具,生成 OpenAI/Claude API 兼容的工具定义。
"""

from typing import Dict, Callable, Any, List


# 工具定义类型
ToolDefinition = Dict[str, Any]

# 工具注册表(全局单例)
TOOL_REGISTRY: Dict[str, ToolDefinition] = {}


def register_tool(name: str, definition: ToolDefinition):
    """
    注册工具到全局注册表
    
    Args:
        name: 工具名称(唯一标识)
        definition: 工具定义,包含:
            - description: 工具描述
            - parameters: JSON Schema 参数定义
            - handler: 执行函数
            - permission_level: 权限级别(read/write/execute)
            
    Raises:
        ValueError: 工具已存在或缺少必需字段
    """
    if name in TOOL_REGISTRY:
        raise ValueError(f"工具 '{name}' 已存在")
    
    # 验证必需字段
    required_fields = ["description", "parameters", "handler", "permission_level"]
    for field in required_fields:
        if field not in definition:
            raise ValueError(f"工具 '{name}' 缺少必需字段: {field}")
    
    TOOL_REGISTRY[name] = definition


def get_tool_schemas() -> List[Dict]:
    """
    生成 OpenAI 兼容的工具定义列表
    
    Returns:
        OpenAI API 所需的 tools 参数格式
    """
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": info["description"],
                "parameters": info["parameters"]
            }
        }
        for name, info in TOOL_REGISTRY.items()
    ]


def get_tool_handler(tool_name: str) -> Callable:
    """
    获取工具的执行函数
    
    Args:
        tool_name: 工具名称
        
    Returns:
        工具 handler 函数
        
    Raises:
        KeyError: 工具不存在
    """
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"未知工具: {tool_name}")
    
    return TOOL_REGISTRY[tool_name]["handler"]
