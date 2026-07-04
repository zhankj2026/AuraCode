#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""读取文件工具 — 纯净内容返回，不干扰 LLM 理解"""
import os
from tools.registry import register_tool


# ── 文件缓存：供 ContextCollapse 使用 ──
_FILE_READ_REGISTRY: dict = {}


def get_file_read_registry() -> dict:
    """供 agent_loop 读取文件访问历史"""
    return _FILE_READ_REGISTRY


def read_file_handler(
    path: str,
    start_line: int = 0,
    end_line: int = 0,
) -> str:
    """
    读取文件内容。默认返回纯净内容（无行号前缀），
    避免干扰 LLM 对文件内容的理解（特别是 replace_in_file 的 old_text 匹配）。

    Args:
        path: 文件路径
        start_line: 起始行号（1-based，0 表示从头开始）
        end_line: 结束行号（1-based 含尾，0 表示到文件末尾）
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    if not os.path.isfile(path):
        raise IsADirectoryError(f"Path is a directory: {path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()

    total_lines = len(all_lines)

    # 解析行范围
    s = max(1, start_line) if start_line > 0 else 1
    e = min(total_lines, end_line) if end_line > 0 else total_lines
    if s > e:
        return f"Error: start_line({s}) > end_line({e})"

    selected = all_lines[s - 1: e]
    content = "".join(selected)

    # 限制输出大小
    max_chars = 100 * 1024  # 100KB
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n... (truncated, {total_lines} total lines)"

    # 注册文件读取记录（供 ContextCollapse 使用）
    _FILE_READ_REGISTRY[os.path.abspath(path)] = {
        "size": os.path.getsize(path),
        "lines": total_lines,
        "read_range": (s, e),
    }

    # 仅当指定了行范围时添加简短元信息头
    if start_line > 0 or end_line > 0:
        header = f"[{path}: lines {s}-{e} of {total_lines}]\n"
        return header + content

    return content


register_tool("read_file", {
    "description": (
        "Read file contents. Returns raw content without line numbers "
        "so you can copy exact text for replace_in_file. "
        "Use start_line/end_line for partial reads of large files."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "start_line": {
                "type": "integer",
                "description": "Start line (1-based, 0=from beginning)",
                "default": 0,
            },
            "end_line": {
                "type": "integer",
                "description": "End line (1-based inclusive, 0=to end)",
                "default": 0,
            },
        },
        "required": ["path"]
    },
    "handler": read_file_handler,
    "permission_level": "read"
})
