"""读取文件工具（含 ContextCollapse 行范围支持）"""
import os
from tools.registry import register_tool


# ── 文件缓存：供 ContextCollapse 使用 ──
_FILE_READ_REGISTRY: dict = {}  # {file_path: {"size": int, "lines": int, "last_read_turn": int}}


def get_file_read_registry() -> dict:
    """供 agent_loop 读取文件访问历史"""
    return _FILE_READ_REGISTRY


def read_file_handler(
    path: str,
    start_line: int = 0,
    end_line: int = 0,
) -> str:
    """
    读取文件内容，支持行范围选择（ContextCollapse 基础）。

    Args:
        path: 文件路径
        start_line: 起始行号（1-based，0 表示从头开始）
        end_line: 结束行号（1-based 含尾，0 表示到文件末尾）

    Returns:
        文件内容（带行号前缀，便于后续折叠引用）
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    if not os.path.isfile(path):
        raise IsADirectoryError(f"路径是目录: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()

    total_lines = len(all_lines)

    # 解析行范围
    s = max(1, start_line) if start_line > 0 else 1
    e = min(total_lines, end_line) if end_line > 0 else total_lines
    if s > e:
        return f"错误: start_line({s}) > end_line({e})"

    selected = all_lines[s - 1: e]
    content = "".join(selected)

    # 限制输出大小
    max_chars = 100 * 1024  # 100KB
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n... (内容过大已截断, 共 {total_lines} 行)"

    # 带行号输出（大文件或指定范围时自动启用）
    use_line_numbers = total_lines > 200 or start_line > 0 or end_line > 0
    if use_line_numbers:
        numbered = []
        for i, line in enumerate(selected, start=s):
            numbered.append(f"{i:>5}\t{line.rstrip()}")
        content = "\n".join(numbered)

    # 注册文件读取记录（供 ContextCollapse 使用）
    _FILE_READ_REGISTRY[os.path.abspath(path)] = {
        "size": os.path.getsize(path),
        "lines": total_lines,
        "read_range": (s, e),
    }

    # 添加元信息头
    header = f"[文件: {path} | 总行数: {total_lines}"
    if start_line > 0 or end_line > 0:
        header += f" | 显示: {s}-{e}"
    header += "]\n"

    return header + content


register_tool("read_file", {
    "description": "读取文件内容（支持行范围选择，大文件自动带行号）",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "start_line": {
                "type": "integer",
                "description": "起始行号（1-based，0=从头开始）",
                "default": 0,
            },
            "end_line": {
                "type": "integer",
                "description": "结束行号（1-based 含尾，0=到末尾）",
                "default": 0,
            },
        },
        "required": ["path"]
    },
    "handler": read_file_handler,
    "permission_level": "read"
})
