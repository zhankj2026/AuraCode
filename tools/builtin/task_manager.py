"""
TaskManager — 结构化任务管理三件套

提供 task_create / task_update / task_list 三个工具，
支持层级任务、依赖关系、进度追踪。
参考 Claude Code 的 Task 系统 (TaskCreate/Get/List)。
"""
import time
import uuid
from typing import Dict, List, Optional, Any
from tools.registry import register_tool


# ── 全局任务存储 ──
_TASKS: Dict[str, Dict[str, Any]] = {}


def _short_id() -> str:
    """生成简短任务 ID"""
    return uuid.uuid4().hex[:8]


def task_create_handler(
    title: str,
    description: str = "",
    parent_id: str = "",
    priority: str = "medium",
    tags: str = "",
) -> str:
    """
    创建新任务。

    Args:
        title: 任务标题
        description: 任务描述
        parent_id: 父任务 ID（创建子任务时使用）
        priority: 优先级（high/medium/low）
        tags: 标签（逗号分隔）

    Returns:
        任务创建结果
    """
    task_id = _short_id()

    # 验证父任务
    if parent_id and parent_id not in _TASKS:
        return f"错误: 父任务 {parent_id} 不存在"

    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "parent_id": parent_id,
        "priority": priority if priority in ("high", "medium", "low") else "medium",
        "status": "pending",
        "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
        "subtasks": [],
        "created_at": time.time(),
        "updated_at": time.time(),
        "progress": 0,  # 0-100
    }

    _TASKS[task_id] = task

    # 注册到父任务
    if parent_id and parent_id in _TASKS:
        _TASKS[parent_id]["subtasks"].append(task_id)

    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(task["priority"], "⚪")
    result = f"✅ 任务已创建: {priority_emoji} [{task_id}] {title}"
    if parent_id:
        result += f" (子任务 → {parent_id})"
    return result


def task_update_handler(
    task_id: str,
    status: str = "",
    progress: int = -1,
    note: str = "",
    add_tag: str = "",
) -> str:
    """
    更新任务状态。

    Args:
        task_id: 任务 ID
        status: 新状态（pending/in_progress/done/cancelled）
        progress: 进度百分比（0-100）
        note: 追加备注
        add_tag: 追加标签

    Returns:
        更新结果
    """
    if task_id not in _TASKS:
        # 模糊匹配
        matches = [t for t in _TASKS if task_id in t or t.startswith(task_id)]
        if len(matches) == 1:
            task_id = matches[0]
        elif len(matches) > 1:
            return f"错误: 任务 ID '{task_id}' 模糊匹配到多个: {matches}"
        else:
            return f"错误: 任务 {task_id} 不存在"

    task = _TASKS[task_id]
    changes = []

    if status and status in ("pending", "in_progress", "done", "cancelled"):
        old_status = task["status"]
        task["status"] = status
        changes.append(f"状态: {old_status} → {status}")

        # 完成时自动设置 100% 进度
        if status == "done":
            task["progress"] = 100
            changes.append("进度: → 100%")

            # 检查父任务是否所有子任务已完成
            if task.get("parent_id") and task["parent_id"] in _TASKS:
                parent = _TASKS[task["parent_id"]]
                all_done = all(
                    _TASKS.get(st, {}).get("status") == "done"
                    for st in parent.get("subtasks", [])
                )
                if all_done and parent.get("subtasks"):
                    parent["status"] = "done"
                    parent["progress"] = 100
                    changes.append(f"父任务 [{task['parent_id']}] 自动完成")

    if progress >= 0:
        task["progress"] = max(0, min(100, progress))
        changes.append(f"进度: → {task['progress']}%")

    if note:
        task.setdefault("notes", []).append({
            "text": note,
            "time": time.time(),
        })
        changes.append(f"备注: {note[:50]}")

    if add_tag:
        if add_tag not in task["tags"]:
            task["tags"].append(add_tag)
            changes.append(f"标签: +{add_tag}")

    task["updated_at"] = time.time()

    if not changes:
        return f"任务 [{task_id}] {task['title']} — 无变更"

    status_emoji = {
        "pending": "⏳", "in_progress": "🔄", "done": "✅", "cancelled": "❌"
    }.get(task["status"], "⚪")

    return f"{status_emoji} 任务 [{task_id}] 已更新:\n" + "\n".join(f"  • {c}" for c in changes)


def task_list_handler(
    filter_status: str = "",
    filter_priority: str = "",
    filter_tag: str = "",
    show_tree: bool = True,
) -> str:
    """
    列出所有任务。

    Args:
        filter_status: 按状态过滤（pending/in_progress/done/cancelled）
        filter_priority: 按优先级过滤（high/medium/low）
        filter_tag: 按标签过滤
        show_tree: 是否以树形结构显示

    Returns:
        任务列表
    """
    if not _TASKS:
        return "📋 暂无任务。使用 task_create 创建新任务。"

    # 过滤
    tasks = list(_TASKS.values())
    if filter_status:
        tasks = [t for t in tasks if t["status"] == filter_status]
    if filter_priority:
        tasks = [t for t in tasks if t["priority"] == filter_priority]
    if filter_tag:
        tasks = [t for t in tasks if filter_tag in t.get("tags", [])]

    if not tasks:
        return f"📋 无匹配任务（过滤条件: {filter_status or 'any'} / {filter_priority or 'any'}）"

    # 统计
    total = len(_TASKS)
    by_status = {}
    for t in _TASKS.values():
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
    stats = " | ".join(f"{k}: {v}" for k, v in sorted(by_status.items()))

    # 格式化
    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    status_emoji = {"pending": "⏳", "in_progress": "🔄", "done": "✅", "cancelled": "❌"}

    lines = [f"📋 任务列表（{len(tasks)}/{total} 显示）[统计: {stats}]\n"]

    if show_tree:
        # 树形显示：先显示根任务，再递归子任务
        root_tasks = [t for t in tasks if not t.get("parent_id")]
        _render_tree(lines, root_tasks, 0)

        # 显示被过滤掉的子任务中匹配的部分
        orphan_shown = set()
        for t in tasks:
            if t.get("parent_id") and t["id"] not in orphan_shown:
                parent = _TASKS.get(t["parent_id"], {})
                if not parent or parent["id"] not in [r["id"] for r in root_tasks]:
                    _render_tree(lines, [t], 0)
                    orphan_shown.add(t["id"])
    else:
        # 平面显示
        for t in sorted(tasks, key=lambda x: (
            {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 3),
            x["created_at"],
        )):
            pe = priority_emoji.get(t["priority"], "⚪")
            se = status_emoji.get(t["status"], "⚪")
            progress = f" [{t['progress']}%]" if t["progress"] > 0 else ""
            tags_str = f" ({', '.join(t['tags'])})" if t.get("tags") else ""
            lines.append(f"  {se}{pe} [{t['id']}] {t['title']}{progress}{tags_str}")

    return "\n".join(lines)


def _render_tree(lines: List[str], tasks: List[Dict], depth: int):
    """递归渲染任务树"""
    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    status_emoji = {"pending": "⏳", "in_progress": "🔄", "done": "✅", "cancelled": "❌"}
    indent = "  " * (depth + 1)

    for t in tasks:
        pe = priority_emoji.get(t["priority"], "⚪")
        se = status_emoji.get(t["status"], "⚪")
        progress = f" [{t['progress']}%]" if t["progress"] > 0 else ""
        sub_count = len(t.get("subtasks", []))
        sub_info = f" ({sub_count} 子任务)" if sub_count else ""
        lines.append(f"{indent}{se}{pe} [{t['id']}] {t['title']}{progress}{sub_info}")

        # 渲染子任务
        if t.get("subtasks"):
            child_tasks = [_TASKS[st] for st in t["subtasks"] if st in _TASKS]
            _render_tree(lines, child_tasks, depth + 1)


register_tool("task_create", {
    "description": "创建新任务（支持层级、优先级、标签）",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "任务标题"},
            "description": {"type": "string", "description": "任务详细描述", "default": ""},
            "parent_id": {"type": "string", "description": "父任务 ID（子任务时使用）", "default": ""},
            "priority": {
                "type": "string",
                "description": "优先级: high/medium/low",
                "default": "medium",
            },
            "tags": {"type": "string", "description": "标签（逗号分隔）", "default": ""},
        },
        "required": ["title"],
    },
    "handler": task_create_handler,
    "permission_level": "read",
})

register_tool("task_update", {
    "description": "更新任务状态/进度/备注",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "任务 ID"},
            "status": {
                "type": "string",
                "description": "新状态: pending/in_progress/done/cancelled",
                "default": "",
            },
            "progress": {
                "type": "integer",
                "description": "进度百分比（0-100）",
                "default": -1,
            },
            "note": {"type": "string", "description": "追加备注", "default": ""},
            "add_tag": {"type": "string", "description": "追加标签", "default": ""},
        },
        "required": ["task_id"],
    },
    "handler": task_update_handler,
    "permission_level": "read",
})

register_tool("task_list", {
    "description": "列出所有任务（支持过滤和树形显示）",
    "parameters": {
        "type": "object",
        "properties": {
            "filter_status": {
                "type": "string",
                "description": "按状态过滤: pending/in_progress/done/cancelled",
                "default": "",
            },
            "filter_priority": {
                "type": "string",
                "description": "按优先级过滤: high/medium/low",
                "default": "",
            },
            "filter_tag": {"type": "string", "description": "按标签过滤", "default": ""},
            "show_tree": {
                "type": "boolean",
                "description": "是否树形显示",
                "default": True,
            },
        },
    },
    "handler": task_list_handler,
    "permission_level": "read",
})
