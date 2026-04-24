"""
Analyze 命令 - 代码分析
"""

from commands.registry import register_command
import os


def analyze_handler(args: list) -> str:
    """分析命令处理函数"""
    if not args:
        return "错误: 请指定要分析的文件或目录\n用法: analyze <path>"

    path = args[0]

    if not os.path.exists(path):
        return f"错误: 路径不存在: {path}"

    lines = []
    lines.append(f"🔍 分析: {path}")
    lines.append("-" * 60)

    # 使用工具进行分析
    from tools.builtin.analyze_file import analyze_file_handler
    from tools.builtin.find import find_handler

    if os.path.isfile(path):
        result = analyze_file_handler(path)
        lines.append(result)
    elif os.path.isdir(path):
        # 查找 Python 文件
        files = find_handler(path, "*.py", max_depth=3)
        lines.append(files)

    return "\n".join(lines)


register_command("analyze", {
    "description": "分析代码文件或目录",
    "handler": analyze_handler,
    "category": "analysis",
    "args_help": "<path>"
})
