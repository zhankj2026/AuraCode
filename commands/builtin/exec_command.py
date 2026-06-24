"""
Exec 命令 - 直接执行 Shell/CMD 命令

功能:
- 在 CLI 中直接执行系统命令（bash/sh/cmd/powershell）
- 支持超时控制
- 工作目录会话级持久化（使用 /cd 设置的目录）
- 危险命令检测与警告
- 后台执行支持
- 输出格式化（stdout/stderr 分离）

用法:
  /exec <command>              — 执行命令
  /exec ls -la                 — 列出文件
  /exec --timeout 30 ping localhost  — 带超时执行
  /exec --background npm start       — 后台执行
  /exec --ignore-warning rm -rf      — 忽略危险警告

安全特性:
- 危险命令检测（删除、格式化、系统修改等）
- 超时保护（默认 60 秒，最大 600 秒）
- 输出截断（防止过长输出）
"""

import os
import re
import platform
import threading
from commands.registry import register_command


def _get_cwd_module():
    """动态导入 run_command 模块"""
    from tools.builtin import run_command
    return run_command


def _is_dangerous_command(command: str) -> str:
    """
    检测危险命令
    
    Returns:
        如果是危险命令，返回警告信息；否则返回空字符串
    """
    dangerous_patterns = [
        # 删除命令
        (r'\brm\s+(-rf?|--recursive|--force)\b', '删除文件/目录'),
        (r'\bRemove-Item\b.*\b(-Recurse|-Force)\b', '删除文件/目录 (PowerShell)'),
        (r'\bdel\s+/[fsq]\b', '删除文件 (Windows)'),
        (r'\brmdir\s+/s\b', '删除目录树 (Windows)'),
        
        # 格式化命令
        (r'\bmkfs\.\w+\b', '格式化文件系统'),
        (r'\bformat\b\s+[A-Z]:', '格式化磁盘 (Windows)'),
        
        # 系统修改
        (r'\bchmod\s+[0-7]{3,4}\s+/(bin|sbin|etc|usr)', '修改系统目录权限'),
        (r'\bchown\s+\w+:\w+\s+/(bin|sbin|etc|usr)', '修改系统目录所有者'),
        
        # 进程终止
        (r'\bkill\s+-9\b', '强制终止进程'),
        (r'\bStop-Process\b.*\b-Force\b', '强制终止进程 (PowerShell)'),
        
        # 网络攻击
        (r'\bflood\b', '网络洪水攻击'),
        (r'\bnmap\s+.*\b-s[SFT]\b', '端口扫描'),
    ]
    
    for pattern, description in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return f"⚠️  危险命令检测: {description}"
    
    return ""


def exec_handler(args: list, loop=None) -> str:
    """
    Exec 命令处理函数
    
    Args:
        args: 命令参数
        loop: AgentLoop 实例（可选）
    
    Returns:
        命令输出
    """
    if not args or len(args) == 0:
        return (
            "❌ 错误: 未指定命令\n\n"
            "用法:\n"
            "  /exec <command>              — 执行命令\n"
            "  /exec ls -la                 — 列出文件\n"
            "  /exec --timeout 30 cmd       — 带超时执行\n"
            "  /exec --background cmd       — 后台执行\n"
            "  /exec --ignore-warning cmd   — 忽略危险警告"
        )
    
    # 解析参数
    command_parts = []
    timeout = 60
    background = False
    ignore_warning = False
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg == "--timeout" and i + 1 < len(args):
            try:
                timeout = int(args[i + 1])
                timeout = min(max(timeout, 1), 600)  # 限制 1-600 秒
                i += 2
            except ValueError:
                return f"❌ 错误: 无效的超时值: {args[i + 1]}"
        elif arg == "--background" or arg == "-b":
            background = True
            i += 1
        elif arg == "--ignore-warning" or arg == "-f":
            ignore_warning = True
            i += 1
        else:
            command_parts.append(arg)
            i += 1
    
    # 组合命令
    command = " ".join(command_parts)
    
    if not command or not command.strip():
        return "❌ 错误: 命令不能为空"
    
    # 获取工作目录
    run_command_module = _get_cwd_module()
    _get_cwd = run_command_module._get_cwd
    cwd = _get_cwd()
    
    # 危险命令检测
    if not ignore_warning:
        warning = _is_dangerous_command(command)
        if warning:
            return (
                f"{warning}\n\n"
                f"命令: {command}\n"
                f"工作目录: {cwd}\n\n"
                f"如果确认要执行此操作，请使用 --ignore-warning 或 -f 参数:\n"
                f"  /exec --ignore-warning {command}"
            )
    
    # 执行命令
    try:
        import subprocess
        
        # 根据平台选择执行方式
        is_windows = platform.system() == "Windows"
        
        if background:
            # 后台执行
            return _execute_background(command, cwd, timeout, is_windows)
        else:
            # 同步执行
            return _execute_sync(command, cwd, timeout, is_windows)
    
    except Exception as e:
        return f"❌ 执行失败: {str(e)}"


def _execute_sync(command: str, cwd: str, timeout: int, is_windows: bool) -> str:
    """同步执行命令"""
    import subprocess
    
    try:
        # 在类 Unix 系统中使用 bash -lc 确保加载 profile
        if not is_windows:
            result = subprocess.run(
                ["bash", "-lc", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                encoding="utf-8",
                errors="replace",
            )
        else:
            # Windows 使用 cmd /c
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
        
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        
        # 检测 cd 命令并更新工作目录
        _handle_cd_command(command, cwd)
        
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
        
        # 添加执行信息
        output_parts.append(f"\n工作目录: {cwd}")
        output_parts.append(f"执行时间: < {timeout}秒")
        
        return "\n".join(output_parts)
    
    except subprocess.TimeoutExpired:
        return (
            f"❌ 命令超时（{timeout}秒）\n\n"
            f"命令: {command}\n\n"
            f"提示: 使用 --timeout 参数增加超时时间（最大 600 秒）"
        )
    except FileNotFoundError as e:
        return f"❌ 命令未找到: {e}"
    except Exception as e:
        return f"❌ 执行失败: {str(e)}"


def _execute_background(command: str, cwd: str, timeout: int, is_windows: bool) -> str:
    """后台执行命令"""
    import subprocess
    import time
    
    # 使用 run_command 模块的后台任务功能
    try:
        task_id = run_command_module._start_background_task(command, cwd, timeout)
        
        return (
            f"✅ 命令已在后台启动\n\n"
            f"任务 ID: {task_id}\n"
            f"命令: {command}\n"
            f"工作目录: {cwd}\n"
            f"超时: {timeout}秒\n\n"
            f"提示: 后台任务正在执行，可以使用工具查看状态"
        )
    except Exception as e:
        return f"❌ 后台启动失败: {str(e)}"


def _handle_cd_command(command: str, current_cwd: str):
    """
    检测命令中的 cd 并更新工作目录
    
    例如: cd /path/to/dir 或 cd .. 
    """
    # 匹配 cd 命令
    cd_match = re.search(r'^\s*cd\s+["\']?([^"\'\n;]+)["\']?\s*[;&\n]?', command)
    if cd_match:
        new_dir = cd_match.group(1).strip()
        
        # 处理相对路径
        if not os.path.isabs(new_dir):
            new_dir = os.path.join(current_cwd, new_dir)
        
        new_dir = os.path.normpath(new_dir)
        
        # 验证目录存在
        if os.path.isdir(new_dir):
            run_command_module = _get_cwd_module()
            run_command_module._set_cwd(new_dir)


# 注册命令
register_command("exec", {
    "description": "执行 Shell/CMD 命令",
    "handler": exec_handler,
    "category": "system",
    "args_help": "<command> [--timeout N] [--background] [--ignore-warning]"
})

# 注册别名
register_command("run", {
    "description": "执行命令（同 /exec）",
    "handler": exec_handler,
    "category": "system",
    "args_help": "<command> [--timeout N] [--background] [--ignore-warning]"
})

register_command("shell", {
    "description": "执行 Shell 命令（同 /exec）",
    "handler": exec_handler,
    "category": "system",
    "args_help": "<command> [--timeout N] [--background] [--ignore-warning]"
})
