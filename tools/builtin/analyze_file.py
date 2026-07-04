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
analyze_file 工具 - 分析 Python 文件结构

基于 code.md Phase 1 实现
参考: 第 3.2 节
"""

import ast
import json
from tools.registry import register_tool


def analyze_file_handler(path: str) -> str:
    """分析 Python 文件结构(类/函数/导入/全局变量)"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return f"错误: 文件语法错误\n{str(e)}"
        
        analysis = {
            "file": path,
            "line_count": len(source.splitlines()),
            "char_count": len(source),
            "classes": [],
            "functions": [],
            "imports": [],
            "global_vars": []
        }
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "line": node.lineno,
                    "methods": [],
                    "docstring": ast.get_docstring(node)
                }
                
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_info = {
                            "name": item.name,
                            "line": item.lineno,
                            "args": [arg.arg for arg in item.args.args]
                        }
                        class_info["methods"].append(method_info)
                
                analysis["classes"].append(class_info)
            
            elif isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "line": node.lineno,
                    "args": [arg.arg for arg in node.args.args],
                    "docstring": ast.get_docstring(node)
                }
                analysis["functions"].append(func_info)
            
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    analysis["imports"].append({
                        "type": "import",
                        "module": alias.name,
                        "line": node.lineno
                    })
            
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    analysis["imports"].append({
                        "type": "from_import",
                        "module": node.module,
                        "name": alias.name,
                        "line": node.lineno
                    })
            
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        analysis["global_vars"].append({
                            "name": target.id,
                            "line": node.lineno
                        })
        
        analysis["stats"] = {
            "class_count": len(analysis["classes"]),
            "function_count": len(analysis["functions"]),
            "import_count": len(analysis["imports"]),
            "method_count": sum(len(c["methods"]) for c in analysis["classes"])
        }
        
        return json.dumps(analysis, indent=2, ensure_ascii=False)
    
    except FileNotFoundError:
        return f"错误: 文件不存在: {path}"
    
    except Exception as e:
        return f"错误: {str(e)}"


register_tool("analyze_file", {
    "description": "分析 Python 文件结构(类/函数/导入/全局变量)",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Python 文件路径"
            }
        },
        "required": ["path"]
    },
    "handler": analyze_file_handler,
    "permission_level": "read"
})
