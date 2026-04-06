"""写入文件工具"""
import os
from tools.registry import register_tool


def write_file_handler(path: str, content: str) -> str:
    """写入内容到文件"""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return f"✅ 成功写入 {path} ({len(content)} 字符)"


register_tool("write_file", {
    "description": "写入内容到指定文件",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "要写入的内容"}
        },
        "required": ["path", "content"]
    },
    "handler": write_file_handler,
    "permission_level": "write"
})
