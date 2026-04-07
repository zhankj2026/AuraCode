"""
find 工具 - 查找文件(按名称/类型/深度)

基于 code.md Phase 1 实现
参考: 第 3.1 节
"""

import os
import fnmatch
from typing import Optional
from tools.registry import register_tool


def find_handler(
    path: str = ".",
    name_pattern: Optional[str] = None,
    type: Optional[str] = None,
    max_depth: int = 3,
    max_results: int = 100
) -> str:
    """
    查找文件(按名称/类型/深度)
    
    Args:
        path: 搜索起始路径
        name_pattern: 文件名匹配模式(支持通配符),如 '*.py'
        type: 文件类型过滤,可选 'file'(文件) 或 'dir'(目录)
        max_depth: 最大搜索深度
        max_results: 最大返回结果数
    
    Returns:
        找到的文件/目录列表
    """
    try:
        if not os.path.exists(path):
            return f"错误: 路径不存在: {path}"
        
        results = []
        path = os.path.abspath(path)
        
        def search_dir(current_path: str, current_depth: int):
            if current_depth > max_depth or len(results) >= max_results:
                return
            
            try:
                for entry in os.scandir(current_path):
                    if len(results) >= max_results:
                        break
                    
                    if type == "file" and not entry.is_file():
                        continue
                    if type == "dir" and not entry.is_dir():
                        continue
                    
                    if name_pattern:
                        if not fnmatch.fnmatch(entry.name, name_pattern):
                            continue
                    
                    results.append(entry.path)
                    
                    if entry.is_dir() and current_depth < max_depth:
                        search_dir(entry.path, current_depth + 1)
            
            except PermissionError:
                pass
        
        search_dir(path, 0)
        
        total = len(results)
        if total == 0:
            return "未找到匹配的文件"
        
        output = "\n".join(results[:max_results])
        
        if total > max_results:
            return (
                f"找到 {total} 个结果(显示前 {max_results} 个):\n\n"
                f"{output}\n\n"
                f"... (还有 {total - max_results} 个未显示)"
            )
        else:
            return f"找到 {total} 个结果:\n\n{output}"
    
    except Exception as e:
        return f"错误: {str(e)}"


# 注册工具
register_tool("find", {
    "description": "查找文件(按名称/类型/深度)",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "搜索起始路径",
                "default": "."
            },
            "name_pattern": {
                "type": "string",
                "description": "文件名匹配模式(支持通配符),如 '*.py'",
                "default": None
            },
            "type": {
                "type": "string",
                "description": "文件类型过滤: 'file'(文件) 或 'dir'(目录)",
                "enum": ["file", "dir"],
                "default": None
            },
            "max_depth": {
                "type": "integer",
                "description": "最大搜索深度",
                "default": 3
            },
            "max_results": {
                "type": "integer",
                "description": "最大返回结果数",
                "default": 100
            }
        },
        "required": []
    },
    "handler": find_handler,
    "permission_level": "read"
})
