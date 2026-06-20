"""列出目录工具 — 精简返回值"""
import os
from tools.registry import register_tool


def list_directory_handler(path: str = ".") -> str:
    """列出目录内容，返回精简格式"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Directory not found: {path}")
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Path is not a directory: {path}")

    items = os.listdir(path)
    dirs = sorted([i + "/" for i in items if os.path.isdir(os.path.join(path, i))])
    files = sorted([i for i in items if not os.path.isdir(os.path.join(path, i))])

    parts = []
    if dirs:
        parts.extend(dirs)
    if files:
        parts.extend(files)

    max_items = 100
    result = "\n".join(parts[:max_items])
    if len(parts) > max_items:
        result += f"\n... ({len(parts)} total, showing first {max_items})"

    return result


register_tool("list_directory", {
    "description": "List directory contents with compact format (dirs first, then files)",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path (default: current directory)",
                "default": "."
            }
        },
        "required": []
    },
    "handler": list_directory_handler,
    "permission_level": "read"
})
