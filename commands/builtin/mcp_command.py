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
MCP 命令 - MCP 服务器管理

功能:
- 查看 MCP 服务器状态
- 添加/移除/重启 MCP 服务器
- 刷新工具列表
- 查看/清理缓存

用法:
  /mcp              查看所有服务器状态
  /mcp status       同上
  /mcp add <name> <command> [args...]   添加 stdio 服务器
  /mcp add <name> --url <url>           添加 SSE 服务器
  /mcp remove <name>   移除服务器
  /mcp restart <name>  重启服务器
  /mcp tools [name]    查看工具列表
  /mcp cache           查看缓存统计
  /mcp cache clear     清空缓存
"""

import asyncio
from commands.registry import register_command


def _get_mcp_manager(loop=None):
    """获取 AgentLoop 上的 McpManager 实例"""
    if loop is None:
        return None
    return getattr(loop, 'mcp_manager', None)


def mcp_handler(args: list, loop=None) -> str:
    """mcp 命令处理函数"""
    mgr = _get_mcp_manager(loop)

    if not args or args[0].lower() in ('status', 'list', ''):
        return _show_status(mgr)

    action = args[0].lower()

    if action == 'add':
        return _add_server(mgr, args[1:], loop)
    elif action in ('remove', 'rm', 'delete'):
        return _remove_server(mgr, args[1:])
    elif action == 'restart':
        return _restart_server(mgr, args[1:])
    elif action == 'tools':
        return _show_tools(mgr, args[1:])
    elif action == 'cache':
        return _show_cache(mgr, args[1:])
    elif action == 'refresh':
        return _refresh_tools(mgr)
    else:
        return f"❌ 未知操作: {action}\n用法: /mcp [status|add|remove|restart|tools|cache|refresh]"


def _show_status(mgr) -> str:
    if mgr is None:
        return "ℹ️  MCP 管理器未初始化（AgentLoop 未启动或 MCP 未配置）"

    servers = mgr.get_status()
    lines = ["🔌 MCP 服务器状态", "=" * 60]

    if not servers:
        lines.append("  ℹ️  无已配置的 MCP 服务器")
        lines.append("  使用 /mcp add <name> <command> 添加服务器")
        lines.append("=" * 60)
        return "\n".join(lines)

    connected = sum(1 for s in servers if s['connected'])
    total_tools = sum(s['tools'] for s in servers)
    total_calls = sum(s['calls'] for s in servers)

    lines.append(f"  服务器: {len(servers)} 个 ({connected} 已连接)")
    lines.append(f"  总工具: {total_tools} 个")
    lines.append(f"  总调用: {total_calls} 次")
    lines.append("")

    lines.append(f"  {'名称':<20} {'状态':>6} {'工具':>4} {'调用':>6} {'错误':>4} {'运行':>8}")
    lines.append(f"  {'-' * 54}")
    for s in servers:
        icon = "🟢" if s['connected'] else "🔴"
        lines.append(
            f"  {icon} {s['name']:<18} "
            f"{'在线' if s['connected'] else '离线':>4} "
            f"{s['tools']:>4} "
            f"{s['calls']:>6} "
            f"{s['errors']:>4} "
            f"{s['uptime']:>8}"
        )
        if s['error']:
            lines.append(f"     ⚠️  {s['error'][:60]}")

    # 缓存统计
    cache = mgr.get_cache_stats()
    lines.append(f"\n  缓存: {cache['active_entries']}/{cache['max_size']} (TTL={cache['default_ttl']}s)")

    lines.append("=" * 60)
    return "\n".join(lines)


def _add_server(mgr, args, loop) -> str:
    if not args or len(args) < 2:
        return "❌ 用法: /mcp add <name> <command> [args...]\n   或: /mcp add <name> --url <url>"

    if mgr is None:
        return "❌ MCP 管理器未初始化"

    name = args[0]

    # 解析配置
    if len(args) >= 3 and args[1] == '--url':
        # SSE 服务器
        from mcp.config.types import McpSSEServerConfig
        config = McpSSEServerConfig(url=args[2])
        lines = [f"🔌 添加 SSE 服务器: {name} → {args[2]}"]
    else:
        # stdio 服务器
        from mcp.config.types import McpStdioServerConfig
        command = args[1]
        cmd_args = args[2:] if len(args) > 2 else []
        config = McpStdioServerConfig(command=command, args=cmd_args)
        lines = [f"🔌 添加 stdio 服务器: {name} → {command} {' '.join(cmd_args)}"]

    try:
        loop_async = asyncio.new_event_loop()
        state = loop_async.run_until_complete(mgr.add_server(name, config))
        loop_async.close()

        if state.connected:
            lines.append(f"  ✅ 已连接，发现 {len(state.tools)} 个工具")
            # 注册到全局
            mgr.register_tools_to_registry()
            for tn in state.tool_adapters:
                lines.append(f"     • {tn}")
        else:
            lines.append(f"  ❌ 连接失败: {state.error}")

    except Exception as e:
        lines.append(f"  ❌ 添加失败: {e}")

    return "\n".join(lines)


def _remove_server(mgr, args) -> str:
    if not args:
        return "❌ 用法: /mcp remove <name>"
    if mgr is None:
        return "❌ MCP 管理器未初始化"

    name = args[0]
    try:
        loop_async = asyncio.new_event_loop()
        ok = loop_async.run_until_complete(mgr.remove_server(name))
        loop_async.close()
        if ok:
            return f"✅ 已移除 MCP 服务器: {name}"
        return f"❌ 未找到服务器: {name}"
    except Exception as e:
        return f"❌ 移除失败: {e}"


def _restart_server(mgr, args) -> str:
    if not args:
        return "❌ 用法: /mcp restart <name>"
    if mgr is None:
        return "❌ MCP 管理器未初始化"

    name = args[0]
    try:
        loop_async = asyncio.new_event_loop()
        state = loop_async.run_until_complete(mgr.restart_server(name))
        loop_async.close()
        if state is None:
            return f"❌ 未找到服务器: {name}"
        if state.connected:
            mgr.register_tools_to_registry()
            return f"✅ 已重启 MCP 服务器: {name} ({len(state.tools)} 工具)"
        return f"❌ 重启失败: {state.error}"
    except Exception as e:
        return f"❌ 重启失败: {e}"


def _show_tools(mgr, args) -> str:
    if mgr is None:
        return "❌ MCP 管理器未初始化"

    target = args[0] if args else None
    lines = ["🔧 MCP 工具列表", "=" * 60]

    for name, state in mgr.servers.items():
        if target and name != target:
            continue
        status = "🟢" if state.connected else "🔴"
        lines.append(f"\n  {status} {name} ({len(state.tools)} 工具)")
        for tool_def in state.tools:
            tn = tool_def.get("name", "?")
            desc = tool_def.get("description", "")[:60]
            lines.append(f"    • {tn}: {desc}")

    lines.append("=" * 60)
    return "\n".join(lines)


def _show_cache(mgr, args) -> str:
    if mgr is None:
        return "❌ MCP 管理器未初始化"

    if args and args[0].lower() == 'clear':
        mgr.clear_cache()
        return "✅ MCP 工具缓存已清空"

    stats = mgr.get_cache_stats()
    lines = ["📦 MCP 工具缓存", "=" * 60]
    lines.append(f"  活跃条目: {stats['active_entries']}")
    lines.append(f"  过期条目: {stats['expired_entries']}")
    lines.append(f"  最大容量: {stats['max_size']}")
    lines.append(f"  默认 TTL:  {stats['default_ttl']}s")
    lines.append("")
    lines.append("  使用 /mcp cache clear 清空缓存")
    lines.append("=" * 60)
    return "\n".join(lines)


def _refresh_tools(mgr) -> str:
    if mgr is None:
        return "❌ MCP 管理器未初始化"

    total = 0
    lines = ["🔄 刷新 MCP 工具", "=" * 60]
    for name, state in mgr.servers.items():
        if not state.connected or not state.client:
            lines.append(f"  ⏭️  {name}: 未连接，跳过")
            continue
        try:
            loop_async = asyncio.new_event_loop()
            tools = loop_async.run_until_complete(state.client.list_tools())
            loop_async.close()
            state.tools = tools
            total += len(tools)
            lines.append(f"  ✅ {name}: {len(tools)} 工具")
        except Exception as e:
            lines.append(f"  ❌ {name}: {e}")

    mgr.register_tools_to_registry()
    lines.append(f"\n  总计: {total} 工具已刷新")
    lines.append("=" * 60)
    return "\n".join(lines)


register_command("mcp", {
    "description": "MCP 服务器管理 - 查看/添加/移除/重启/工具/缓存",
    "handler": mcp_handler,
    "category": "system",
    "args_help": "[status|add|remove|restart|tools|cache|refresh]"
})
