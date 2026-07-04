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
Subagents 命令 - Subagent 管理 (完整版)

支持的子命令:
- (无参数)  显示概览
- list      列出所有或按状态过滤
- stats     显示统计信息
- types     列出所有可用的 agent 类型
- get <id>  获取特定 subagent 详情
- cancel <id> 取消运行中的 subagent
- join <id> [timeout] 等待 subagent 完成并获取结果
- cleanup [hours] 清理已完成的记录 (默认24小时)
"""

from commands.registry import register_command
from core.subagent import subagent_manager

# 直接从 subagent 模块导入处理函数
from tools.builtin.subagent import (
    list_subagents_handler,
    subagent_stats_handler,
    list_agent_types_handler
)


def subagents_handler(args: list) -> str:
    """Subagent 命令处理函数"""
    if not args:
        return _show_overview()

    subcommand = args[0]
    subargs = args[1:] if len(args) > 1 else []

    if subcommand == 'list':
        return _cmd_list(subargs)
    elif subcommand == 'stats':
        return subagent_stats_handler()
    elif subcommand == 'types':
        return list_agent_types_handler()
    elif subcommand == 'get':
        return _cmd_get(subargs)
    elif subcommand == 'cancel':
        return _cmd_cancel(subargs)
    elif subcommand == 'join':
        return _cmd_join(subargs)
    elif subcommand == 'cleanup':
        return _cmd_cleanup(subargs)
    else:
        return _show_help(subcommand)


def _show_overview() -> str:
    """显示概览信息"""
    lines = []
    lines.append("🤖 Subagent 管理")
    lines.append("=" * 60)

    # 统计信息
    stats = subagent_manager.get_stats()
    lines.append(f"📊 状态统计:")
    lines.append(f"   总数: {stats['total']}")
    lines.append(f"   🔄 运行中: {stats['running']}")
    lines.append(f"   ✅ 已完成: {stats['completed']}")
    lines.append(f"   ❌ 失败: {stats['failed']}")
    lines.append(f"   ⛔ 已取消: {stats['cancelled']}")

    # 可用的 agent 类型
    available_types = subagent_manager.get_available_agent_types()
    lines.append(f"\n📦 可用的 Agent 类型 ({len(available_types)}):")
    for agent_type in available_types[:6]:  # 只显示前6个
        if agent_type == "general":
            lines.append(f"   {agent_type}: 通用任务")
        else:
            agent_def = subagent_manager.get_agent_definition(agent_type)
            if agent_def:
                desc = agent_def.get('description', '无描述')[:40]
                lines.append(f"   {agent_type}: {desc}...")
            else:
                lines.append(f"   {agent_type}: 未找到定义")

    if len(available_types) > 6:
        lines.append(f"   ... 还有 {len(available_types) - 6} 个类型 (使用 'types' 查看全部)")

    # 子命令帮助
    lines.append("\n📋 子命令:")
    lines.append("   list [status]   列出 subagent (可过滤: running/completed/failed)")
    lines.append("   stats           显示统计信息")
    lines.append("   types           查看所有 agent 类型")
    lines.append("   get <id>        获取特定 subagent 详情")
    lines.append("   cancel <id>     取消运行中的 subagent")
    lines.append("   join <id> [sec] 等待完成并获取结果")
    lines.append("   cleanup [hr]    清理旧记录 (默认24小时)")

    return "\n".join(lines)


def _cmd_list(subargs: list) -> str:
    """列出 subagent，支持状态过滤"""
    status = None
    if subargs:
        status = subargs[0].lower()
        valid_statuses = ['running', 'completed', 'failed', 'cancelled']
        if status not in valid_statuses:
            return f"❌ 无效的状态 '{status}'\n" \
                   f"有效状态: {', '.join(valid_statuses)}"

    return list_subagents_handler(status=status)


def _cmd_get(subargs: list) -> str:
    """获取特定 subagent 详情"""
    if not subargs:
        return "❌ 请提供 agent ID\n用法: /subagents get <agent_id>"

    agent_id = subargs[0]

    try:
        status = subagent_manager.get_agent_status(agent_id)

        lines = []
        lines.append(f"📋 Subagent 详情: {agent_id}")
        lines.append("=" * 60)
        lines.append(f"任务: {status['task']}")
        lines.append(f"类型: {status['agent_type']}")
        lines.append(f"模型: {status['model']}")
        lines.append(f"状态: {status['status']}")
        lines.append(f"模式: {'Fork' if status.get('fork_mode') else 'Fresh'}")
        lines.append(f"创建时间: {status['created_at']}")

        if status.get('completed_at'):
            lines.append(f"完成时间: {status['completed_at']}")

        if status.get('error'):
            lines.append(f"❌ 错误: {status['error']}")

        if status.get('result_preview'):
            lines.append(f"\n结果预览:")
            lines.append(status['result_preview'][:300])
            if len(status['result_preview']) > 300:
                lines.append(f"...")

        return "\n".join(lines)

    except KeyError:
        return f"❌ 未找到 agent: {agent_id}\n" \
               f"使用 '/subagents list' 查看可用的 agent"


def _cmd_cancel(subargs: list) -> str:
    """取消运行中的 subagent"""
    if not subargs:
        return "❌ 请提供 agent ID\n用法: /subagents cancel <agent_id>"

    agent_id = subargs[0]

    success = subagent_manager.cancel_agent(agent_id)

    if success:
        return f"✅ Agent {agent_id} 已标记为取消\n" \
               f"注意: 线程可能仍在后台运行，只是状态被标记为取消"
    else:
        return f"❌ 无法取消 agent {agent_id}\n" \
               f"可能原因: agent 不存在或未在运行中"


def _cmd_join(subargs: list) -> str:
    """等待 subagent 完成并获取结果"""
    if not subargs:
        return "❌ 请提供 agent ID\n用法: /subagents join <agent_id> [timeout]"

    agent_id = subargs[0]
    timeout = None

    if len(subargs) > 1:
        try:
            timeout = int(subargs[1])
        except ValueError:
            return f"❌ 超时时间必须是数字\n用法: /subagents join <agent_id> [timeout]"

    try:
        result = subagent_manager.join_subagent(agent_id, timeout=timeout)

        lines = []
        lines.append(f"✅ Agent {agent_id} 完成")
        lines.append("=" * 60)
        lines.append(result)
        return "\n".join(lines)

    except KeyError:
        return f"❌ 未找到 agent: {agent_id}"
    except TimeoutError:
        return f"⏱️ Agent {agent_id} 未在指定时间内完成\n" \
               f"仍在后台运行，可以稍后再次查询"


def _cmd_cleanup(subargs: list) -> str:
    """清理已完成的记录"""
    max_age_hours = 24  # 默认 24 小时

    if subargs:
        try:
            max_age_hours = float(subargs[0])
        except ValueError:
            return f"❌ 时间必须是数字\n用法: /subagents cleanup [hours]"

    before_count = subagent_manager.get_stats()['total']
    subagent_manager.cleanup_finished(max_age_hours=max_age_hours)
    after_count = subagent_manager.get_stats()['total']

    cleaned = before_count - after_count

    return f"🧹 清理完成\n" \
           f"清理了 {cleaned} 个已完成的 agent 记录 " \
           f"(超过 {max_age_hours} 小时)\n" \
           f"当前剩余: {after_count} 个"


def _show_help(unknown_cmd: str) -> str:
    """显示帮助（针对未知命令）"""
    return f"❌ 未知的子命令: '{unknown_cmd}'\n\n" \
           f"可用子命令:\n" \
           f"  list [status]   列出 subagent\n" \
           f"  stats           显示统计信息\n" \
           f"  types           查看所有 agent 类型\n" \
           f"  get <id>        获取特定 subagent 详情\n" \
           f"  cancel <id>     取消运行中的 subagent\n" \
           f"  join <id> [sec] 等待完成并获取结果\n" \
           f"  cleanup [hr]    清理旧记录\n\n" \
           f"使用 '/subagents' 查看概览"


register_command("subagents", {
    "description": "管理 Subagent - 列表、查询、取消、清理",
    "handler": subagents_handler,
    "category": "system",
    "args_help": "[list|stats|types|get|cancel|join|cleanup] [args...]"
})
