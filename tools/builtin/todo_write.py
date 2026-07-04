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
TodoWrite 工具 - 会话级任务进度跟踪

参考 TodoWriteTool 设计：
- 维护会话级任务列表（内存存储）
- 支持创建、更新、完成、删除任务
- LLM 主动使用以展示任务进度
- 每次调用传入完整任务列表（替换模式）
"""

import time
import json
import threading
from typing import List, Dict, Any, Optional
from tools.registry import register_tool


# ── 全局任务列表（会话级） ────────────────────────────────────────────────────────

_todos: List[Dict[str, Any]] = []
_todos_lock = threading.Lock()


def _get_todos() -> List[Dict]:
    with _todos_lock:
        return list(_todos)


def _set_todos(new_todos: List[Dict]):
    with _todos_lock:
        global _todos
        _todos = new_todos


def _format_todo(todo: Dict, index: int) -> str:
    """格式化单个任务为显示字符串"""
    status = todo.get("status", "pending")
    content = todo.get("content", "")
    active_form = todo.get("activeForm", "")

    status_icons = {
        "pending": "⬚",
        "in_progress": "▶",
        "completed": "✓",
    }
    icon = status_icons.get(status, "?")

    line = f"  {icon} [{index}] {content}"
    if status == "in_progress" and active_form:
        line += f"  ({active_form})"
    return line


def _format_todos(todos: List[Dict]) -> str:
    """格式化任务列表"""
    if not todos:
        return "(任务列表为空)"

    lines = []
    pending = sum(1 for t in todos if t.get("status") == "pending")
    in_progress = sum(1 for t in todos if t.get("status") == "in_progress")
    completed = sum(1 for t in todos if t.get("status") == "completed")

    lines.append(f"任务列表 [{completed}✓ / {in_progress}▶ / {pending}⬚]:\n")

    for i, todo in enumerate(todos, 1):
        lines.append(_format_todo(todo, i))

    return "\n".join(lines)


# ── 主处理函数 ──────────────────────────────────────────────────────────────────

def todo_write_handler(
    action: str = "replace",
    todos: Optional[List[Dict]] = None,
    index: Optional[int] = None,
    content: Optional[str] = None,
    activeForm: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    """
    管理会话级任务列表，用于跟踪复杂多步骤任务的进度。

    操作模式：
    - replace: 用新的完整列表替换（默认，todos 参数为完整列表）
    - add: 添加单个任务
    - update: 更新指定索引的任务状态
    - remove: 删除指定索引的任务
    - list: 显示当前任务列表

    Args:
        action: 操作类型（replace/add/update/remove/list）
        todos: 完整任务列表（replace 模式），每项含:
            - content: 任务描述（祈使句，如 "修复登录 Bug"）
            - status: pending/in_progress/completed
            - activeForm: 进行中时的显示文本（如 "修复登录 Bug 中"）
        index: 任务索引（update/remove 模式，1-based）
        content: 任务内容（add 模式）
        activeForm: 进行中文本（add/update 模式）
        status: 新状态（update 模式）

    Returns:
        更新后的任务列表
    """
    current = _get_todos()

    if action == "list":
        return _format_todos(current)

    elif action == "replace":
        if todos is None:
            return "错误: replace 模式需要提供 todos 参数（完整任务列表）"

        # 验证格式
        valid_statuses = {"pending", "in_progress", "completed"}
        new_todos = []
        for i, t in enumerate(todos):
            if not isinstance(t, dict):
                return f"错误: todos[{i}] 必须是字典"
            c = t.get("content", "").strip()
            if not c:
                return f"错误: todos[{i}].content 不能为空"
            s = t.get("status", "pending")
            if s not in valid_statuses:
                return f"错误: todos[{i}].status 必须是 {valid_statuses} 之一，实际: {s}"
            new_todos.append({
                "content": c,
                "status": s,
                "activeForm": t.get("activeForm", ""),
            })

        # 检查：同时只能有一个 in_progress
        in_progress_count = sum(1 for t in new_todos if t["status"] == "in_progress")
        if in_progress_count > 1:
            return (
                f"警告: 同时只能有 1 个任务处于 in_progress 状态，"
                f"当前有 {in_progress_count} 个。请只保留一个 in_progress。"
            )

        _set_todos(new_todos)
        return _format_todos(new_todos)

    elif action == "add":
        if not content:
            return "错误: add 模式需要提供 content 参数"
        new_todo = {
            "content": content,
            "status": status or "pending",
            "activeForm": activeForm or "",
        }
        current.append(new_todo)
        _set_todos(current)
        return f"已添加任务: {content}\n\n{_format_todos(current)}"

    elif action == "update":
        if index is None:
            return "错误: update 模式需要提供 index 参数（1-based）"
        if not current:
            return "错误: 任务列表为空，无法更新"
        if index < 1 or index > len(current):
            return f"错误: index 越界（1-{len(current)}），实际: {index}"

        todo = current[index - 1]
        if content is not None:
            todo["content"] = content
        if activeForm is not None:
            todo["activeForm"] = activeForm
        if status is not None:
            if status not in {"pending", "in_progress", "completed"}:
                return f"错误: status 必须是 pending/in_progress/completed，实际: {status}"
            todo["status"] = status

        _set_todos(current)
        return f"已更新任务 #{index}\n\n{_format_todos(current)}"

    elif action == "remove":
        if index is None:
            return "错误: remove 模式需要提供 index 参数（1-based）"
        if not current:
            return "错误: 任务列表为空，无法删除"
        if index < 1 or index > len(current):
            return f"错误: index 越界（1-{len(current)}），实际: {index}"

        removed = current.pop(index - 1)
        _set_todos(current)
        return f"已删除任务 #{index}: {removed.get('content', '')}\n\n{_format_todos(current)}"

    else:
        return f"错误: 未知操作 '{action}'，支持: replace/add/update/remove/list"


register_tool("todo_write", {
    "description": (
        "Create and manage a session-level task list for tracking complex multi-step work. "
        "Use for tasks with 3+ steps, multiple user requests, or when you need to show progress. "
        "Each call replaces the full list (replace mode). "
        "Requires subject (imperative form) and activeForm (present tense). "
        "Only one task should be in_progress at a time."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["replace", "add", "update", "remove", "list"],
                "description": (
                    "操作类型：\n"
                    "replace - 替换完整列表（传入 todos）\n"
                    "add - 添加单个任务（传入 content）\n"
                    "update - 更新指定任务（传入 index + status）\n"
                    "remove - 删除指定任务（传入 index）\n"
                    "list - 显示当前列表"
                ),
                "default": "replace"
            },
            "todos": {
                "type": "array",
                "description": "完整任务列表（replace 模式）",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "任务描述（祈使句，如 '修复登录 Bug'）"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "任务状态"
                        },
                        "activeForm": {
                            "type": "string",
                            "description": "进行中时的显示文本（如 '修复登录 Bug 中'）"
                        }
                    },
                    "required": ["content", "status"]
                }
            },
            "index": {
                "type": "integer",
                "description": "任务索引（update/remove 模式，1-based）"
            },
            "content": {
                "type": "string",
                "description": "任务内容（add 模式）"
            },
            "activeForm": {
                "type": "string",
                "description": "进行中文本（add/update 模式）"
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed"],
                "description": "新状态（update/add 模式）"
            }
        },
        "required": []
    },
    "handler": todo_write_handler,
    "permission_level": "read"
})
