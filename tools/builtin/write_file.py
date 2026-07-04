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


def write_file_handler(path: str, content: str) -> str:
    """写入内容到文件，返回精简信息"""
    # 验证参数
    if not path:
        raise ValueError("文件路径不能为空")
    if content is None:
        raise ValueError("文件内容不能为 None")
    
    logger.info(f"write_file: path={path}, content_len={len(content)}")
    
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        # 写入前备份已有文件（支持 undo_edit）
        backup_path = None
        if os.path.exists(path):
            try:
                backup_path = _create_backup(path)
                record_edit(path, backup_path, open(path, 'r', encoding='utf-8').read())
            except Exception as e:
                logger.warning(f"备份文件失败: {e}")

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        lines = content.count('\n') + (0 if content.endswith('\n') else 1)
        result = f"Wrote {len(content)} chars ({lines} lines) to {path}"
        logger.info(f"write_file success: {result}")
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
