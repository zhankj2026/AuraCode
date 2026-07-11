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

"""
grep 工具 - 递归搜索文件内容(支持正则)

基于 code.md Phase 1 实现
参考: 第 3.1 节
"""

import os
import re
import fnmatch
from typing import Optional
from tools.registry import register_tool


def grep_handler(
    pattern: str,
    path: str = ".",
    file_pattern: str = "*",
    case_sensitive: bool = False,
    max_lines: int = 100,
    **kwargs
) -> str:
    """
    增强版 grep - 支持文件过滤和大小写控制
    
    Args:
        pattern: 搜索模式(支持正则表达式)
        path: 搜索路径,默认为当前目录
        file_pattern: 文件匹配模式(如 *.py),默认为所有文件
        case_sensitive: 是否区分大小写,默认不区分
        max_lines: 最大返回行数,防止上下文溢出
        **kwargs: 兼容 LLM 发送的额外参数
    
    Returns:
        匹配结果,格式为 "文件:行号:内容"
    """
    try:
        matches = []
        path = os.path.abspath(path)
        
        # 编译正则表达式
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"错误: 正则表达式语法错误: {str(e)}"
        
        def search_file(filepath: str):
            """搜索单个文件"""
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            rel_path = os.path.relpath(filepath, path)
                            matches.append(f"{rel_path}:{line_num}:{line.rstrip()}")
                            if len(matches) >= max_lines:
                                return True
            except (PermissionError, OSError):
                pass
            return False
        
        def search_dir(current_path: str):
            """递归搜索目录"""
            try:
                for entry in os.scandir(current_path):
                    if len(matches) >= max_lines:
                        break
                    
                    if entry.is_file():
                        if file_pattern and file_pattern != "*":
                            if not fnmatch.fnmatch(entry.name, file_pattern):
                                continue
                        search_file(entry.path)
                    
                    elif entry.is_dir() and not entry.name.startswith('.'):
                        search_dir(entry.path)
            
            except PermissionError:
                pass
        
        search_dir(path)
        
        total = len(matches)
        if total == 0:
            return f"未找到匹配 '{pattern}' 的内容"
        
        output = "\n".join(matches[:max_lines])
        
        if total > max_lines:
            return (
                f"找到 {total} 个匹配(显示前 {max_lines} 行):\n\n"
                f"{output}\n\n"
                f"... (还有 {total - max_lines} 行未显示)"
            )
        else:
            return f"找到 {total} 个匹配:\n\n{output}"
    
    except Exception as e:
        return f"错误: {str(e)}"


# 注册工具
register_tool("grep", {
    "description": "递归搜索文件内容(支持正则表达式)",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "搜索模式(支持正则表达式),如 'def.*auth'"
            },
            "path": {
                "type": "string",
                "description": "搜索路径",
                "default": "."
            },
            "file_pattern": {
                "type": "string",
                "description": "文件匹配模式,如 '*.py'、'*.js'",
                "default": "*"
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "是否区分大小写",
                "default": False
            },
            "max_lines": {
                "type": "integer",
                "description": "最大返回行数",
                "default": 100
            }
        },
        "required": ["pattern"]
    },
    "handler": grep_handler,
    "permission_level": "read"
})
