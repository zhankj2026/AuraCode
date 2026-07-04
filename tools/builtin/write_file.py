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
    """写入内容到文件，返回精简信息"""
    # 验证参数
    if not path:
        raise ValueError("文件路径不能为空")
    if content is None:
        raise ValueError("文件内容不能为 None")
    
    # 详细日志：显示路径解析过程
    cwd = os.getcwd()
    # 如果提供了 project_root，使用它来解析路径；否则使用 cwd
    if project_root and not os.path.isabs(path):
        abs_path = os.path.join(project_root, path)
    else:
        abs_path = os.path.abspath(path)
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
