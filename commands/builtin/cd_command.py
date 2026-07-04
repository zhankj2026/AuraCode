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
CD 命令 - 改变工作目录

功能:
- 改变当前工作目录（会话级持久化）
- 支持绝对路径和相对路径
- 显示当前目录（无参数时）
- 路径验证和错误处理
- 支持 `cd -` 返回上一个目录

用法:
  /cd              — 显示当前工作目录
  /cd <path>       — 切换到指定目录
  /cd -            — 返回上一个目录
  /cd ..           — 返回上级目录
  /cd ~            — 切换到用户主目录
"""

import os
import threading
from commands.registry import register_command

# 上一个目录（用于 cd -）
_previous_cwd_lock = threading.Lock()
_previous_cwd: str = None


def _get_previous_cwd() -> str:
    """获取上一个目录"""
    global _previous_cwd
    with _previous_cwd_lock:
        return _previous_cwd


def _set_previous_cwd(path: str):
    """设置上一个目录"""
    global _previous_cwd
    with _previous_cwd_lock:
        _previous_cwd = path


def _get_cwd_module():
    """动态导入 run_command 模块以获取工作目录函数"""
    from tools.builtin import run_command
    return run_command


def cd_handler(args: list, loop=None) -> str:
    """
    CD 命令处理函数
    
    Args:
        args: 命令参数（目录路径）
        loop: AgentLoop 实例（可选）
    
    Returns:
        命令输出
    """
    run_command_module = _get_cwd_module()
    _get_cwd = run_command_module._get_cwd
    _set_cwd = run_command_module._set_cwd
    
    # 无参数：显示当前目录
    if not args or len(args) == 0:
        current_cwd = _get_cwd()
        return (
            f"📁 当前工作目录:\n"
            f"  {current_cwd}"
        )
    
    # 获取目标路径
    target_path = args[0].strip()
    
    # 特殊路径处理
    if target_path == "-":
        # cd - 返回上一个目录
        previous = _get_previous_cwd()
        if previous and os.path.isdir(previous):
            target_path = previous
        else:
            return "ℹ️ 没有上一个目录可返回"
    elif target_path.startswith("~"):
        # 展开用户主目录
        target_path = os.path.expanduser(target_path)
    else:
        # 相对路径转换为绝对路径
        if not os.path.isabs(target_path):
            current_cwd = _get_cwd()
            target_path = os.path.join(current_cwd, target_path)
    
    # 规范化路径
    target_path = os.path.normpath(target_path)
    
    # 验证目录是否存在
    if not os.path.exists(target_path):
        return f"❌ 目录不存在: {target_path}"
    
    if not os.path.isdir(target_path):
        return f"❌ 不是目录: {target_path}"
    
    # 验证权限
    if not os.access(target_path, os.R_OK):
        return f"❌ 没有访问权限: {target_path}"
    
    # 切换工作目录
    old_cwd = _get_cwd()
    _set_previous_cwd(old_cwd)  # 保存当前目录为上一个目录
    _set_cwd(target_path)
    
    # 计算相对路径（用于显示）
    try:
        rel_path = os.path.relpath(target_path, old_cwd)
        path_info = f" ({rel_path})"
    except ValueError:
        path_info = ""
    
    return (
        f"✅ 工作目录已切换:\n"
        f"  {old_cwd}\n"
        f"  → {target_path}{path_info}"
    )


register_command("cd", {
    "description": "改变工作目录（会话级持久化）",
    "handler": cd_handler,
    "category": "system",
    "args_help": "[path] - 目标目录路径（留空显示当前目录）"
})

# 注册别名
register_command("pwd", {
    "description": "显示当前工作目录",
    "handler": cd_handler,
    "category": "system",
    "args_help": ""
})

register_command("workdir", {
    "description": "改变工作目录（同 /cd）",
    "handler": cd_handler,
    "category": "system",
    "args_help": "[path] - 目标目录路径（留空显示当前目录）"
})
