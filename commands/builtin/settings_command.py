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
/settings 命令 - 全局用户设置管理

查看、修改、重置 ~/.auracode/settings.json 中的用户偏好。

用法:
    /settings                    — 查看所有设置
    /settings get <key>          — 获取指定设置
    /settings set <key> <value>  — 修改设置
    /settings reset              — 重置为默认值
    /settings backup             — 创建备份
    /settings backups            — 列出备份
"""
import json
from commands.registry import register_command


def settings_handler(args, loop=None):
    action = args[0] if args else "show"

    from services.settings_store import get_settings_store

    project_root = ""
    if loop and hasattr(loop, 'project_root'):
        project_root = loop.project_root

    store = get_settings_store(project_root=project_root or None)

    if action == "show":
        return _show_settings(store)
    elif action == "get" and len(args) >= 2:
        return _get_setting(store, args[1])
    elif action == "set" and len(args) >= 3:
        value = " ".join(args[2:])
        return _set_setting(store, args[1], value)
    elif action == "reset":
        return _reset_settings(store)
    elif action == "backup":
        return _backup_settings(store)
    elif action == "backups":
        return _list_backups(store)
    else:
        return (
            "用法: /settings [show|get|set|reset|backup|backups]\n\n"
            "  show              — 查看所有设置\n"
            "  get <key>         — 获取指定设置\n"
            "  set <key> <value> — 修改设置\n"
            "  reset             — 重置为默认值\n"
            "  backup            — 创建备份\n"
            "  backups           — 列出备份"
        )


def _show_settings(store) -> str:
    display = store.to_display_dict()
    lines = ["=" * 60, "全局用户设置 (~/.auracode/settings.json)", "=" * 60]

    categories = {
        "模型偏好": ["preferred_model", "fallback_model"],
        "权限": ["default_permission_mode"],
        "显示": ["theme", "language", "verbose", "show_token_count", "show_cost"],
        "Agent 行为": ["max_iterations", "auto_compact_threshold", "streaming_enabled"],
        "持久化": ["auto_save_sessions", "file_history_enabled", "history_log_enabled"],
        "安全": ["trusted_paths", "blocked_commands"],
        "其他": ["custom_instructions", "disabled_tools", "preferred_shell"],
    }

    for cat_name, keys in categories.items():
        lines.append(f"\n  [{cat_name}]")
        for key in keys:
            value = display.get(key, "(未设置)")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value) if value else "(空)"
            elif isinstance(value, bool):
                value = "✓ 启用" if value else "✗ 禁用"
            elif isinstance(value, dict):
                value = f"{len(value)} 项"
            elif not value:
                value = "(未设置)"
            lines.append(f"    {key:30} = {value}")

    # MCP 服务器
    mcp = display.get("mcp_servers", {})
    if mcp:
        lines.append(f"\n  [MCP 服务器]")
        for name, config in mcp.items():
            lines.append(f"    {name}: {json.dumps(config, ensure_ascii=False)[:80]}")

    lines.append(f"\n  元数据")
    lines.append(f"    _version       = {display.get('_version', 1)}")
    lines.append(f"    _last_modified = {display.get('_last_modified', '(never)')}")
    lines.append("")
    return "\n".join(lines)


def _get_setting(store, key: str) -> str:
    value = store.get(key)
    if value is None:
        return f"设置 '{key}' 未设置"
    if isinstance(value, (dict, list)):
        return f"{key} = {json.dumps(value, ensure_ascii=False, indent=2)}"
    return f"{key} = {value}"


def _set_setting(store, key: str, value: str) -> str:
    # 智能类型转换
    if value.lower() in ("true", "yes", "on", "1"):
        parsed_value = True
    elif value.lower() in ("false", "no", "off", "0"):
        parsed_value = False
    else:
        try:
            parsed_value = int(value)
        except ValueError:
            try:
                parsed_value = float(value)
            except ValueError:
                # 尝试解析 JSON（列表/对象）
                try:
                    parsed_value = json.loads(value)
                except json.JSONDecodeError:
                    parsed_value = value

    success = store.set(key, parsed_value)
    if success:
        return f"✓ 已设置 {key} = {parsed_value}"
    return f"✗ 设置失败: {key}"


def _reset_settings(store) -> str:
    store.backup("global")
    success = store.reset("global")
    if success:
        return "✓ 设置已重置为默认值（已自动创建备份）"
    return "✗ 重置失败"


def _backup_settings(store) -> str:
    path = store.backup("global")
    if path:
        return f"✓ 设置已备份到: {path}"
    return "✗ 备份失败（可能没有设置文件）"


def _list_backups(store) -> str:
    backups = store.list_backups()
    if not backups:
        return "没有找到备份文件"
    lines = [f"找到 {len(backups)} 个备份:"]
    for b in backups:
        lines.append(f"  {b['filename']}  ({b['size_bytes']}B, {b['modified']})")
    return "\n".join(lines)


register_command("settings", {
    "description": "全局用户设置管理 (~/.auracode/settings.json)",
    "handler": settings_handler,
    "category": "system",
})
