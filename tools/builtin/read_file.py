"""读取文件工具"""
import os
from tools.registry import register_tool


def read_file_handler(path: str) -> str:
    """读取文件内容"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    if not os.path.isfile(path):
        raise IsADirectoryError(f"路径是目录: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 限制文件大小
    max_size = 100 * 1024  # 100KB
    if len(content) > max_size:
        content = content[:max_size] + "\n\n... (文件过大,已截断)"
    
    return content


register_tool("read_file", {
    "description": "读取指定路径的文件内容",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"}
        },
        "required": ["path"]
    },
    "handler": read_file_handler,
    "permission_level": "read"
})
