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
PowerShell 工具 - Windows PowerShell 命令执行

专为 Windows 环境设计：
- 使用 powershell.exe（Windows PowerShell 5.x）
- 支持超时控制
- 破坏性命令检测与警告
- 路径验证
- 输出格式化（含编码处理）
"""

import os
import re
import subprocess
import platform
import threading
import logging
from typing import Optional, Dict
from tools.registry import register_tool

logger = logging.getLogger(__name__)

# ── 全局工作目录（会话级持久化） ────────────────────────────────────────────────

_cwd_lock = threading.Lock()
_cwd: str = os.getcwd()


def _get_cwd() -> str:
    with _cwd_lock:
        return _cwd


def _set_cwd(path: str):
    global _cwd
    with _cwd_lock:
        _cwd = path


# ── 危险命令检测 ────────────────────────────────────────────────────────────────

DANGEROUS_PATTERNS = [
    r'Remove-Item\s+.*-Recurse',
    r'Remove-Item\s+.*-Force',
    r'Clear-Content',
    r'Clear-RecycleBin',
    r'Format-[VD]',  # Format-Volume, Format-Disk
    r'Stop-Process\s+.*-Force',
    r'Uninstall-',
    r'Register-ScheduledTask',
    r'Set-ExecutionPolicy',
    r'New-ItemProperty.*-Force',
    r'git\s+push\s+--force',
    r'git\s+reset\s+--hard',
]


def _is_dangerous(command: str) -> Optional[str]:
    """检测命令是否包含危险操作，返回警告文本或 None"""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return f"⚠️ 检测到潜在危险操作: 匹配模式 '{pattern}'"
    return None


# ── 主处理函数 ──────────────────────────────────────────────────────────────────

def run_powershell_handler(
    command: str,
    timeout: int = 60,
    working_directory: Optional[str] = None,
    ignore_danger_warning: bool = False,
    run_in_background: bool = False,
) -> str:
    """
    在 Windows PowerShell 中执行命令。

    特性：
    - 工作目录会话级持久化（cd 效果跨命令保留）
    - 超时控制（默认 60 秒）
    - 危险命令警告
    - 编码自动处理（UTF-8）

    Args:
        command: PowerShell 命令
        timeout: 超时时间（秒，默认 60，最大 600）
        working_directory: 指定工作目录（留空使用上次目录）
        ignore_danger_warning: 忽略危险命令警告强制执行

    Returns:
        命令输出（stdout + stderr）
    """
    if not command or not command.strip():
        return "错误: command 不能为空"

    if platform.system() != "Windows":
        return "错误: run_powershell 工具仅支持 Windows 系统，请使用 run_command"

    # 后台执行（简单实现，不支持复杂的后台任务管理）
    if run_in_background:
        return "警告: run_powershell 不支持后台执行，请使用 run_command 工具进行后台操作"

    # 超时限制
    timeout = min(max(timeout, 1), 600)

    # 工作目录
    cwd = working_directory or _get_cwd()
    if not os.path.isdir(cwd):
        cwd = os.getcwd()
        _set_cwd(cwd)

    # 危险命令检测
    warning = _is_dangerous(command)
    if warning and not ignore_danger_warning:
        return (
            f"{warning}\n\n"
            f"命令: {command}\n\n"
            f"如果确认要执行此操作，请设置 ignore_danger_warning=true 重试。"
        )

    # 执行命令
    try:
        # 使用 -Command 参数，设置 UTF-8 输出
        ps_command = (
            f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
            f'Set-Location -LiteralPath "{cwd}"; '
            f'{command}; '
            f'Write-Output "\\n__PWD__:$PWD"'
        )

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command", ps_command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        # 提取更新后的工作目录
        pwd_match = re.search(r'__PWD__:(.+?)$', stdout, re.MULTILINE)
        if pwd_match:
            new_cwd = pwd_match.group(1).strip()
            if os.path.isdir(new_cwd):
                _set_cwd(new_cwd)
            stdout = re.sub(r'\n?__PWD__:.+$', '', stdout, flags=re.MULTILINE)

        # 格式化输出
        output_parts = []

        if stdout.strip():
            output_parts.append(stdout.rstrip())

        if stderr.strip():
            output_parts.append(f"--- STDERR ---\n{stderr.rstrip()}")

        if result.returncode != 0:
            output_parts.append(f"--- EXIT CODE: {result.returncode} ---")

        if not output_parts:
            output_parts.append("(命令执行成功，无输出)")

        output_parts.append(f"\n工作目录: {_get_cwd()}")

        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"命令超时（{timeout}秒）: {command}"
    except FileNotFoundError:
        return "错误: 未找到 powershell.exe，请确认系统为 Windows"
    except Exception as e:
        return f"执行失败: {str(e)}"


register_tool("run_powershell", {
    "description": (
        "在 Windows PowerShell 中执行命令。\n"
        "专为 Windows 优化，支持：\n"
        "- 工作目录会话级持久化（cd 效果保留）\n"
        "- 超时控制（默认 60 秒）\n"
        "- 危险命令自动警告\n"
        "- UTF-8 编码输出\n"
        "注意：仅支持 Windows 系统，Linux/macOS 请使用 run_command。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "PowerShell 命令（如 Get-Process, Invoke-WebRequest 等）"
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间（秒，默认 60，最大 600）",
                "default": 60
            },
            "working_directory": {
                "type": "string",
                "description": "工作目录（留空使用上次的工作目录）",
                "default": None
            },
            "ignore_danger_warning": {
                "type": "boolean",
                "description": "忽略危险命令警告，强制执行",
                "default": False
            },
            "run_in_background": {
                "type": "boolean",
                "description": "后台执行（不支持，请使用 run_command）",
                "default": False
            }
        },
        "required": ["command"]
    },
    "handler": run_powershell_handler,
    "permission_level": "execute"
})
