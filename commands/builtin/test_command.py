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
Test 命令 - 运行测试
"""

from commands.registry import register_command


def test_handler(args: list) -> str:
    """测试命令处理函数"""
    from tools.builtin.run_tests import run_tests_handler

    test_path = args[0] if args else "."

    lines = []
    lines.append("🧪 运行测试")
    lines.append("-" * 60)

    result = run_tests_handler(path=test_path)
    lines.append(result)

    return "\n".join(lines)


register_command("test", {
    "description": "运行测试",
    "handler": test_handler,
    "category": "tools",
    "args_help": "[path]"
})
