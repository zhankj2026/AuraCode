"""列出目录工具"""
import os
from tools.registry import register_tool


def list_directory_handler(path: str = ".") -> str:
    """列出目录内容"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"目录不存在: {path}")
    if not os.path.isdir(path):
        raise NotADirectoryError(f"路径不是目录: {path}")
    
    items = os.listdir(path)
    files = []
    dirs = []
    
    for item in items:
        full_path = os.path.join(path, item)
        if os.path.isdir(full_path):
            dirs.append(item + "/")
        else:
            files.append(item)
    
    files.sort()
    dirs.sort()
    
    output = f"目录: {os.path.abspath(path)}\n\n"
    
    if dirs:
        output += "📁 子目录:\n"
        for d in dirs:
            output += f"  {d}\n"
        output += "\n"
    
    if files:
        output += "📄 文件:\n"
        for f in files:
            output += f"  {f}\n"
    
    max_items = 50
    if len(items) > max_items:
        output += f"\n... (共 {len(items)} 项,显示前 {max_items} 项)"
    
    return output


register_tool("list_directory", {
    "description": "列出目录内容",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "目录路径,默认为当前目录",
                "default": "."
            }
        },
        "required": []
    },
    "handler": list_directory_handler,
    "permission_level": "read"
})
