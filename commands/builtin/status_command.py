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
Status 命令 - 显示系统状态
"""

from commands.registry import register_command


def status_handler(args: list, loop=None) -> str:
    """状态命令处理函数"""
    if not loop:
        return "错误: AgentLoop 未初始化"

    lines = []
    lines.append("=" * 60)
    lines.append("📊 系统状态")
    lines.append("=" * 60)

    status = loop.get_system_status()

    lines.append(f"插件系统: {'✅ 启用' if loop.plugins_enabled else '❌ 禁用'}")
    lines.append(f"  已加载: {status['plugins']['loaded']} 个")

    lines.append(f"\n钩子系统: {'✅ 启用' if loop.hooks_enabled else '❌ 禁用'}")
    lines.append(f"  已注册: {status['hooks']['registered']} 个")

    lines.append(f"\n技能系统: {'✅ 启用' if loop.skills_enabled else '❌ 禁用'}")
    lines.append(f"  总数: {status['skills']['total']} 个")
    lines.append(f"  已激活: {status['skills']['active']} 个")

    lines.append(f"\n工具总数: {status['tools']['total']} 个")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("status", {
    "description": "显示系统状态",
    "handler": status_handler,
    "category": "system",
    "args_help": ""
})
