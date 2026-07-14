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
Bash / Shell 命令执行工具（增强版）

参考 BashTool 设计，增强功能：
- 可配置超时（默认 60 秒，最大 600 秒）
- 后台执行（run_in_background 模式）
- 工作目录会话级持久化（cd 效果跨命令保留）
- 危险命令检测与警告
- 更好的错误处理和输出格式化
"""

import os
import re
import subprocess
import platform
import threading
import time
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


# ── 后台任务管理 ────────────────────────────────────────────────────────────────

_background_tasks: Dict[int, Dict] = {}
_bg_lock = threading.Lock()
_bg_id_counter = 0


def _start_background_task(command: str, cwd: str, timeout: int) -> int:
    """启动后台任务，返回任务 ID"""
    global _bg_id_counter
    with _bg_lock:
        _bg_id_counter += 1
        task_id = _bg_id_counter

    task_info = {
        "id": task_id,
        "command": command,
        "cwd": cwd,
        "status": "running",
        "stdout": "",
        "stderr": "",
        "returncode": None,
        "start_time": time.time(),
    }

    def _run():
        try:
            shell = platform.system() == "Windows"
            # 在类 Unix 系统中使用 bash -lc 确保加载 profile
            if not shell and platform.system() != "Windows":
                proc = subprocess.run(
                    ["bash", "-lc", command],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                )
            else:
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                )
            task_info["stdout"] = proc.stdout or ""
            task_info["stderr"] = proc.stderr or ""
            task_info["returncode"] = proc.returncode
            task_info["status"] = "completed"
        except subprocess.TimeoutExpired:
            task_info["status"] = "timeout"
            task_info["stderr"] = f"命令超时（{timeout}秒）"
        except Exception as e:
            task_info["status"] = "error"
            task_info["stderr"] = str(e)

    thread = threading.Thread(target=_run, daemon=True, name=f"bg-task-{task_id}")
    thread.start()
    task_info["thread"] = thread

    with _bg_lock:
        _background_tasks[task_id] = task_info

    return task_id


# ── 危险命令检测 ────────────────────────────────────────────────────────────────

DANGEROUS_PATTERNS_UNIX = [
    r'rm\s+-rf\s+/',
    r'rm\s+-rf\s+~',
    r'mkfs\.',
    r'dd\s+if=.*of=/dev/',
    r':\(\)\s*\{\s*:\|:\s*&\s*\}\s*;',  # fork bomb
    r'chmod\s+-R\s+777',
    r'git\s+push\s+--force\s+.*\bmain\b',
    r'git\s+push\s+--force\s+.*\bmaster\b',
    r'git\s+reset\s+--hard',
]

DANGEROUS_PATTERNS_WIN = [
    r'format\s+[a-zA-Z]:',
    r'rd\s+/s\s+/q\s+[a-zA-Z]:\\',
    r'del\s+/s\s+/q',
    r'git\s+push\s+--force',
    r'git\s+reset\s+--hard',
]


def _is_dangerous(command: str) -> Optional[str]:
    patterns = (
        DANGEROUS_PATTERNS_WIN if platform.system() == "Windows"
        else DANGEROUS_PATTERNS_UNIX
    )
    for pattern in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return f"⚠️ 检测到潜在危险操作: 匹配模式 '{pattern}'"
    return None


# ── Windows 命令兼容（防御性修正） ────────────────────────────────────────────

# 匹配 mkdir / md 后紧跟的 Unix 专用标志：-p / --parents / -pv / -fp 等
_MKDIR_FLAG_RE = re.compile(r"\b(?P<tool>mkdir|md)\s+(?P<flag>-{1,2}[A-Za-z][\w-]*)")


def _fix_mkdir_for_windows(command: str) -> str:
    """Windows 兼容：剥离 mkdir/md 的 Unix 专用 -p / --parents 标志。

    Windows 的 mkdir 默认就会创建父目录（等价于 Unix 的 -p），而：
    - cmd.exe 会把 `-p` 当成真实的目录名，建出一个名为 `-p` 的目录（结果错误）；
    - PowerShell 的 mkdir（New-Item 别名）不接受 -p，直接报错。

    因此把 LLM 误写的 `mkdir -p a/b/c` 归一化为 `mkdir a/b/c`，使命令在
    Windows 上正确执行。短标志簇（如 -pv）只去掉其中的 p，保留其余标志；
    --parents 长标志整体删除。仅在 Windows 生效，其它平台原样返回。
    """
    if platform.system() != "Windows":
        return command

    def _strip(m):
        tool, flag = m.group("tool"), m.group("flag")
        body = flag.lstrip("-")
        if body.lower() == "parents":              # --parents → 整体删除
            return tool
        kept = re.sub(r"[pP]", "", body)            # 短标志簇：去掉 p，保留 v/m 等
        return f"{tool} -{kept}" if kept else tool

    fixed = _MKDIR_FLAG_RE.sub(_strip, command)
    if fixed != command:
        logger.info(f"[Windows] mkdir 自动修正: {command!r} -> {fixed!r}")
    return fixed


# ── 主处理函数 ──────────────────────────────────────────────────────────────────

def run_command_handler(
    command: str = "",
    timeout: int = 60,
    run_in_background: bool = False,
    working_directory: Optional[str] = None,
    ignore_danger_warning: bool = False,
    check_task_id: Optional[int] = None,
) -> str:
    """
    执行 Shell 命令（增强版）。

    新功能：
    - 超时控制（默认 60 秒，最大 600 秒）
    - 后台执行（run_in_background=true）
    - 工作目录持久化（cd 效果跨命令保留）
    - 危险命令警告
    - 查看后台任务（check_task_id）

    Args:
        command: Shell 命令
        timeout: 超时时间（秒，默认 60，最大 600）
        run_in_background: 是否后台执行
        working_directory: 工作目录（留空使用上次目录）
        ignore_danger_warning: 忽略危险命令警告
        check_task_id: 查看指定后台任务状态和输出

    Returns:
        命令输出或任务状态
    """
    # 参数验证
    if not command or not str(command).strip():
        return "错误: command 参数不能为空"
    
    # 查看后台任务
    if check_task_id is not None:
        with _bg_lock:
            task = _background_tasks.get(check_task_id)
        if not task:
            return f"错误: 后台任务 #{check_task_id} 不存在"
        status = task["status"]
        elapsed = time.time() - task["start_time"]
        lines = [f"任务 #{check_task_id} [{status}]（已运行 {elapsed:.1f}秒）"]
        lines.append(f"命令: {task['command']}")
        if task["stdout"]:
            lines.append(f"\n输出:\n{task['stdout']}")
        if task["stderr"]:
            lines.append(f"\n错误输出:\n{task['stderr']}")
        if task["returncode"] is not None:
            lines.append(f"\n退出码: {task['returncode']}")
        return "\n".join(lines)

    if not command or not command.strip():
        return "错误: command 不能为空"

    # Windows 兼容：自动剥离 mkdir -p（Windows mkdir 默认建父目录，-p 会出错）
    command = _fix_mkdir_for_windows(command)

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

    # 后台执行
    if run_in_background:
        task_id = _start_background_task(command, cwd, timeout)
        return (
            f"✅ 后台任务已启动 (ID: #{task_id})\n"
            f"命令: {command}\n"
            f"工作目录: {cwd}\n\n"
            f"使用 check_task_id={task_id} 查看任务状态和输出。"
        )

    # 前台执行
    try:
        is_windows = platform.system() == "Windows"

        if is_windows:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                encoding="utf-8",
                errors="replace",
            )
        else:
            result = subprocess.run(
                ["bash", "-lc", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        # 尝试检测 cd 后的工作目录（通过 echo $PWD 或 cd 命令）
        cd_match = re.search(r'^\s*cd\s+["\']?([^"\'\n;]+)["\']?\s*[;&\n]', command)
        if cd_match:
            new_dir = cd_match.group(1).strip()
            if not os.path.isabs(new_dir):
                new_dir = os.path.join(cwd, new_dir)
            new_dir = os.path.normpath(new_dir)
            if os.path.isdir(new_dir):
                _set_cwd(new_dir)

        # 格式化输出（精简：去掉工作目录信息）
        output_parts = []
        if stdout.strip():
            output_parts.append(stdout.rstrip())
        if stderr.strip():
            output_parts.append(f"STDERR:\n{stderr.rstrip()}")
        if result.returncode != 0:
            output_parts.append(f"Exit code: {result.returncode}")
        if not output_parts:
            output_parts.append("(success, no output)")

        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"命令超时（{timeout}秒）: {command}"
    except FileNotFoundError as e:
        return f"错误: 命令未找到: {e}"
    except Exception as e:
        return f"执行失败: {str(e)}"


register_tool("run_command", {
    "description": (
        "Execute shell commands with enhanced features.\n"
        "Supports:\n"
        "- Timeout control (default 60s)\n"
        "- Background execution (non-blocking)\n"
        "- Working directory persistence across commands\n"
        "- Dangerous command warnings\n"
        "- Background task status checking\n"
        "Use run_powershell on Windows instead."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 60, max 600)",
                "default": 60
            },
            "run_in_background": {
                "type": "boolean",
                "description": "Run in background (non-blocking)",
                "default": False
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory (empty = use last working directory)",
                "default": None
            },
            "ignore_danger_warning": {
                "type": "boolean",
                "description": "Suppress danger warnings and force execute",
                "default": False
            },
            "check_task_id": {
                "type": "integer",
                "description": "Check status/output of a background task by task ID",
                "default": None
            }
        },
        "required": ["command"]
    },
    "handler": run_command_handler,
    "permission_level": "execute"
})
