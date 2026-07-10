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

"""写入文件工具 — 精简返回值"""
import os
import logging
from datetime import datetime
from tools.registry import register_tool
from .undo_edit import record_edit

logger = logging.getLogger(__name__)


def write_file_handler(path: str, content: str, project_root: str = None) -> str:
    """
    写入内容到文件，返回精简信息。
    
    注意：AgentLoop 已将相对路径转换为绝对路径（基于 project_root），
    所以这里收到的 path 通常是绝对路径。project_root 参数作为后备机制。
    """
    # 验证参数
    if not path:
        raise ValueError("文件路径不能为空")
    if content is None:
        raise ValueError("文件内容不能为 None")
    
    # 详细日志：显示路径解析过程
    cwd = os.getcwd()
    # 路径解析：支持相对路径和绝对路径
    # - 绝对路径：直接使用
    # - 相对路径：基于 project_root 或 cwd 解析
    if os.path.isabs(path):
        abs_path = path
        logger.info(f"write_file: absolute path, use directly")
    elif project_root:
        abs_path = os.path.abspath(os.path.join(project_root, path))
        logger.info(f"write_file: relative path, resolve against project_root")
    else:
        abs_path = os.path.abspath(path)
        logger.info(f"write_file: relative path, resolve against cwd")
    logger.info(f"write_file: original_path={path}")
    logger.info(f"write_file: project_root={project_root}")
    logger.info(f"write_file: cwd={cwd}")
    logger.info(f"write_file: abs_path={abs_path}")
    logger.info(f"write_file: content_len={len(content)}")
    
    try:
        directory = os.path.dirname(abs_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"write_file: created directory {directory}")

        # 写入前备份已有文件（支持 undo_edit）
        backup_path = None
        if os.path.exists(abs_path):
            try:
                backup_path = _create_backup(abs_path)
                record_edit(abs_path, backup_path, open(abs_path, 'r', encoding='utf-8').read())
            except Exception as e:
                logger.warning(f"备份文件失败: {e}")

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        lines = content.count('\n') + (0 if content.endswith('\n') else 1)
        result = f"Wrote {len(content)} chars ({lines} lines) to {abs_path}"
        logger.info(f"write_file success: {result}")
        
        # 验证文件确实写入成功
        if os.path.exists(abs_path):
            actual_size = os.path.getsize(abs_path)
            logger.info(f"write_file verified: file exists, size={actual_size} bytes")
        else:
            logger.error(f"write_file ERROR: file does not exist after write: {abs_path}")
        
        # 自动语法检查（参考 Claude 架构验证机制）
        syntax_check_result = _auto_syntax_check(abs_path)
        if syntax_check_result:
            result += f"\n\n⚠️ 语法检查发现错误:\n{syntax_check_result}"
            result += "\n建议立即修复。"
        
        return result
    except Exception as e:
        logger.error(f"write_file failed: {e}", exc_info=True)
        raise


def _create_backup(path: str) -> str:
    """创建文件备份"""
    backup_dir = os.path.join(os.path.dirname(path) or '.', '.backup')
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = os.path.basename(path)
    backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")
    with open(path, 'r', encoding='utf-8') as src:
        with open(backup_path, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    return backup_path


def _auto_syntax_check(file_path: str) -> str:
    """
    自动语法检查（参考 Claude 架构验证机制）
    
    对于代码文件，在创建后立即进行语法检查，
    发现错误时立即返回给 LLM，让 LLM 自动修复。
    
    Args:
        file_path: 文件绝对路径
    
    Returns:
        错误信息字符串，如果没有错误则返回空字符串
    """
    import subprocess
    import platform
    
    # 根据文件扩展名选择语法检查命令
    ext = os.path.splitext(file_path)[1].lower()
    
    # Python 文件
    if ext == '.py':
        cmd = ['python', '-m', 'py_compile', file_path]
    # JavaScript 文件
    elif ext == '.js':
        cmd = ['node', '--check', file_path]
    # TypeScript 文件
    elif ext == '.ts':
        cmd = ['tsc', '--noEmit', file_path]
    # JSON 文件
    elif ext == '.json':
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            return ""  # JSON 有效
        except json.JSONDecodeError as e:
            return f"JSON 解析错误: {e}"
    # 其他文件类型不检查
    else:
        return ""
    
    # 执行语法检查
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10  # 10秒超时
        )
        
        # 如果返回码非零，表示有错误
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            # 限制错误信息长度
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "\n... (错误信息过长，已截断)"
            return error_msg
        
        return ""  # 语法正确
    
    except subprocess.TimeoutExpired:
        logger.warning(f"Syntax check timeout for {file_path}")
        return ""  # 超时不报错
    except FileNotFoundError as e:
        # 检查工具不存在（如 node, tsc）
        logger.debug(f"Syntax checker not found: {e}")
        return ""  # 工具不存在不报错
    except Exception as e:
        logger.debug(f"Syntax check failed: {e}")
        return ""  # 其他错误不报错


register_tool("write_file", {
    "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "Content to write"}
        },
        "required": ["path", "content"]
    },
    "handler": write_file_handler,
    "permission_level": "write"
})
