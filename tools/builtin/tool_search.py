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
ToolSearch 工具 - 搜索可用的工具

参考 ToolSearchTool 设计，支持按名称/描述/类别搜索工具，
帮助 LLM 在工具较多时发现正确的工具。
"""

from typing import Optional
from tools.registry import register_tool, TOOL_REGISTRY


# 工具类别标签
TOOL_CATEGORIES = {
    # File operations
    "read_file": "file", "write_file": "file", "replace_in_file": "file",
    "list_directory": "file", "find": "file", "glob": "file",
    "undo_edit": "file", "notebook_edit": "file",
    # Code analysis
    "grep": "code", "analyze_file": "code", "lint": "code", "lsp": "code",
    # Execution
    "run_command": "execute", "run_powershell": "execute", "run_tests": "execute",
    "repl": "execute",
    # Web
    "web_fetch": "web", "web_search": "web",
    # Utility
    "todo_write": "aux", "ask_user": "aux", "tool_search": "aux",
    "sleep": "aux", "config": "aux", "brief": "aux",
    # Task management
    "task_create": "task", "task_get": "task", "task_update": "task",
    "task_list": "task", "task_stop": "task",
    # Planning
    "enter_plan_mode": "plan", "exit_plan_mode": "plan",
    "plan_agent": "plan", "subagent": "plan",
    # Memory
    "get_memory": "memory", "save_memory": "memory", "list_memories": "memory",
    "search_memory": "memory",
    # Skills
    "activate_skill": "skill", "deactivate_skill": "skill", "list_skills": "skill",
    # Scheduling
    "cron_create": "scheduling", "cron_delete": "scheduling", "cron_list": "scheduling",
    # Worktree
    "enter_worktree": "worktree", "exit_worktree": "worktree",
}


def tool_search_handler(
    query: str = "",
    category: str = "",
    limit: int = 20,
) -> str:
    """
    搜索可用工具

    Args:
        query: 搜索关键词（匹配工具名或描述）
        category: 按类别过滤 (file/code/execute/web/aux/plan/memory/skill)
        limit: 最大返回数量
    """
    results = []

    for name, info in TOOL_REGISTRY.items():
        # 类别过滤
        if category:
            tool_cat = TOOL_CATEGORIES.get(name, "other")
            if tool_cat != category:
                continue

        # 关键词匹配
        if query:
            q = query.lower()
            name_match = q in name.lower()
            desc_match = q in info.get("description", "").lower()
            if not name_match and not desc_match:
                continue

        results.append({
            "name": name,
            "description": info.get("description", "")[:100],
            "category": TOOL_CATEGORIES.get(name, "other"),
            "permission": info.get("permission_level", "read"),
        })

    if not results:
        # 无匹配时列出所有工具名
        all_names = sorted(TOOL_REGISTRY.keys())
        return f"未找到匹配 '{query}' 的工具。\n\n可用工具 ({len(all_names)}):\n" + \
               ", ".join(all_names)

    # 按名称排序
    results.sort(key=lambda x: x["name"])
    results = results[:limit]

    output = f"找到 {len(results)} 个工具"
    if query:
        output += f" (匹配: '{query}')"
    if category:
        output += f" (类别: {category})"
    output += ":\n\n"

    for r in results:
        output += f"📦 {r['name']} [{r['category']}] ({r['permission']})\n"
        output += f"   {r['description']}\n\n"

    # 附加可用类别列表
    categories = sorted(set(TOOL_CATEGORIES.values()))
    output += f"可用类别: {', '.join(categories)}"

    return output


register_tool("tool_search", {
    "description": (
        "Discover available tools by keyword or category. "
        "Use when unsure which tool to use for a task. "
        "Supports keyword search (query='file') and category filter (category='code'). "
        "Available categories: file, code, execute, web, aux, task, plan, memory, skill, scheduling, worktree."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keyword (matches tool name or description)",
                "default": "",
            },
            "category": {
                "type": "string",
                "description": "Filter by category: file/code/execute/web/aux/task/plan/memory/skill/scheduling/worktree",
                "default": "",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return",
                "default": 20,
            },
        },
        "required": [],
    },
    "handler": tool_search_handler,
    "permission_level": "read",
})
