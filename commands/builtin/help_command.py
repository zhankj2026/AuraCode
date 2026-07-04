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
Help 命令 - 显示帮助信息
"""

from commands.registry import register_command, COMMAND_REGISTRY, get_commands_by_category


def help_handler(args: list) -> str:
    """帮助命令处理函数"""
    lines = []
    lines.append("=" * 60)
    lines.append("📖 可用命令")
    lines.append("=" * 60)
    lines.append("")

    # 按分类显示命令
    categories = {
        "system": "系统命令",
        "skills": "技能管理",
        "tools": "工具命令",
        "analysis": "代码分析"
    }

    for cat_key, cat_name in categories.items():
        commands = get_commands_by_category(cat_key)
        if commands:
            lines.append(f"{cat_name}:")
            for cmd_name in commands:
                cmd = COMMAND_REGISTRY[cmd_name]
                args_help = cmd.get("args_help", "")
                if args_help:
                    lines.append(f"  {cmd_name:15} {args_help}")
                else:
                    lines.append(f"  {cmd_name}")
                lines.append(f"    {cmd['description']}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


# 注册命令
register_command("help", {
    "description": "显示帮助信息",
    "handler": help_handler,
    "category": "system",
    "args_help": ""
})

# 同时注册为 ?
register_command("?", {
    "description": "显示帮助信息 (别名)",
    "handler": help_handler,
    "category": "system",
    "args_help": ""
})
