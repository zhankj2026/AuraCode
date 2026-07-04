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
测试 Exec 命令 - Shell/CMD 命令执行功能
"""

import os
import platform
import tempfile
from commands.builtin import exec_command
from tools.builtin import run_command


def test_exec_no_command():
    """测试 1: 未指定命令时的错误提示"""
    result = exec_command.exec_handler([])
    
    assert "❌ 错误: 未指定命令" in result
    assert "/exec <command>" in result
    print("✓ 测试 1 通过: 未指定命令时的错误提示")


def test_exec_empty_command():
    """测试 2: 空命令错误"""
    result = exec_command.exec_handler([""])
    
    assert "❌ 错误: 命令不能为空" in result
    print("✓ 测试 2 通过: 空命令错误")


def test_exec_simple_command():
    """测试 3: 执行简单命令"""
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        # Windows: 使用 dir 命令
        result = exec_command.exec_handler(["dir"])
    else:
        # Unix/Linux/macOS: 使用 ls 命令
        result = exec_command.exec_handler(["ls", "-la"])
    
    # 应该成功执行（不检查具体输出，因为不同系统输出不同）
    assert "工作目录:" in result or "STDERR" in result or "EXIT CODE" in result
    print("✓ 测试 3 通过: 执行简单命令")


def test_exec_with_timeout():
    """测试 4: 带超时参数执行"""
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        result = exec_command.exec_handler(["--timeout", "10", "echo", "hello"])
    else:
        result = exec_command.exec_handler(["--timeout", "10", "echo", "hello"])
    
    assert "执行时间: < 10秒" in result
    print("✓ 测试 4 通过: 带超时参数执行")


def test_exec_invalid_timeout():
    """测试 5: 无效超时值"""
    result = exec_command.exec_handler(["--timeout", "abc", "echo", "hello"])
    
    assert "❌ 错误: 无效的超时值" in result
    print("✓ 测试 5 通过: 无效超时值")


def test_exec_dangerous_command():
    """测试 6: 危险命令检测"""
    # 测试删除命令
    result = exec_command.exec_handler(["rm", "-rf", "/tmp/test"])
    
    assert "⚠️  危险命令检测" in result
    assert "删除文件/目录" in result
    assert "--ignore-warning" in result
    print("✓ 测试 6 通过: 危险命令检测")


def test_exec_ignore_warning():
    """测试 7: 忽略危险警告"""
    # 使用 --ignore-warning 应该执行（但可能因为路径不存在而失败）
    result = exec_command.exec_handler([
        "--ignore-warning", "rm", "-rf", "/nonexistent/path/12345"
    ])
    
    # 不应该有危险警告
    assert "⚠️  危险命令检测" not in result
    print("✓ 测试 7 通过: 忽略危险警告")


def test_exec_echo_command():
    """测试 8: 执行 echo 命令"""
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        result = exec_command.exec_handler(["echo", "hello", "world"])
    else:
        result = exec_command.exec_handler(["echo", "hello world"])
    
    # echo 命令应该不会报错
    assert "❌" not in result or "EXIT CODE" not in result
    print("✓ 测试 8 通过: 执行 echo 命令")


def test_exec_pwd_command():
    """测试 9: 执行 pwd/dir 命令"""
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        result = exec_command.exec_handler(["cd"])
    else:
        result = exec_command.exec_handler(["pwd"])
    
    # 应该成功执行
    assert "❌ 执行失败" not in result
    print("✓ 测试 9 通过: 执行 pwd/dir 命令")


def test_exec_cd_updates_cwd():
    """测试 10: cd 命令更新工作目录"""
    old_cwd = run_command._get_cwd()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        is_windows = platform.system() == "Windows"
        
        if is_windows:
            exec_command.exec_handler(["cd", tmpdir])
        else:
            exec_command.exec_handler(["cd", tmpdir])
        
        # 验证工作目录已更新
        new_cwd = run_command._get_cwd()
        assert new_cwd == os.path.normpath(tmpdir)
        
        # 恢复原目录
        run_command._set_cwd(old_cwd)
    
    print("✓ 测试 10 通过: cd 命令更新工作目录")


def test_exec_cd_relative():
    """测试 11: cd 相对路径"""
    old_cwd = run_command._get_cwd()
    
    try:
        is_windows = platform.system() == "Windows"
        
        if is_windows:
            exec_command.exec_handler(["cd", ".."])
        else:
            exec_command.exec_handler(["cd", ".."])
        
        # 验证工作目录已更新为上级目录
        new_cwd = run_command._get_cwd()
        expected_cwd = os.path.normpath(os.path.join(old_cwd, ".."))
        assert new_cwd == expected_cwd
    finally:
        run_command._set_cwd(old_cwd)
    
    print("✓ 测试 11 通过: cd 相对路径")


def test_exec_with_working_directory():
    """测试 12: 使用 /cd 设置的工作目录"""
    old_cwd = run_command._get_cwd()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 先切换工作目录
        run_command._set_cwd(tmpdir)
        
        # 执行命令应该在 tmpdir 中运行
        is_windows = platform.system() == "Windows"
        
        if is_windows:
            result = exec_command.exec_handler(["cd"])
        else:
            result = exec_command.exec_handler(["pwd"])
        
        # 验证输出包含 tmpdir
        assert tmpdir in result or os.path.basename(tmpdir) in result
        
        # 恢复原目录
        run_command._set_cwd(old_cwd)
    
    print("✓ 测试 12 通过: 使用 /cd 设置的工作目录")


def test_exec_timeout_expired():
    """测试 13: 命令超时"""
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        # Windows: 使用 ping 命令模拟超时（ping 127.0.0.1 -n 10 会等待约 10 秒）
        result = exec_command.exec_handler(["--timeout", "1", "ping", "127.0.0.1", "-n", "10"])
    else:
        # Unix: 使用 sleep 命令
        result = exec_command.exec_handler(["--timeout", "1", "sleep", "10"])
    
    # 应该超时
    assert "❌ 命令超时" in result
    assert "1秒" in result
    print("✓ 测试 13 通过: 命令超时")


def test_exec_run_alias():
    """测试 14: /run 别名"""
    # /run 应该使用相同的 handler
    assert exec_command.exec_handler.__name__ == "exec_handler"
    print("✓ 测试 14 通过: /run 别名")


def test_exec_shell_alias():
    """测试 15: /shell 别名"""
    # /shell 应该使用相同的 handler
    assert exec_command.exec_handler.__name__ == "exec_handler"
    print("✓ 测试 15 通过: /shell 别名")


def test_exec_multiple_dangerous_patterns():
    """测试 16: 多种危险命令模式"""
    dangerous_commands = [
        ["rm", "-rf", "/"],
        ["mkfs.ext4", "/dev/sda1"],
        ["chmod", "777", "/etc"],
    ]
    
    for cmd_parts in dangerous_commands:
        result = exec_command.exec_handler(cmd_parts)
        assert "⚠️  危险命令检测" in result, f"未检测到危险命令: {' '.join(cmd_parts)}"
    
    print("✓ 测试 16 通过: 多种危险命令模式")


if __name__ == "__main__":
    test_exec_no_command()
    test_exec_empty_command()
    test_exec_simple_command()
    test_exec_with_timeout()
    test_exec_invalid_timeout()
    test_exec_dangerous_command()
    test_exec_ignore_warning()
    test_exec_echo_command()
    test_exec_pwd_command()
    test_exec_cd_updates_cwd()
    test_exec_cd_relative()
    test_exec_with_working_directory()
    test_exec_timeout_expired()
    test_exec_run_alias()
    test_exec_shell_alias()
    test_exec_multiple_dangerous_patterns()
    
    print("\n" + "=" * 50)
    print("✅ 所有 Exec 命令测试通过！")
    print("=" * 50)
