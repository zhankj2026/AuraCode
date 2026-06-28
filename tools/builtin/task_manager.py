"""
TaskManager — 结构化任务管理六件套（参考标准TaskCreate/Get/List/Update/Stop）

提供 task_create / task_get / task_update / task_list / task_stop 五个工具，
支持层级任务、依赖关系(blocks/blockedBy)、进度追踪、activeForm 进行时描述。
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
    subject: str = "",
    title: str = "",
    description: str = "",
    active_form: str = "",
    parent_id: str = "",
    priority: str = "medium",
    tags: str = "",
) -> str:
    """
    创建新任务（参考标准TaskCreateTool）。

    Args:
        subject: 任务标题（推荐，祈使句式如 'Implement X'）
        title: 任务标题（兼容旧参数，等同 subject）
        description: 任务详细描述
        active_form: 进行时描述（如 'Implementing X'），用于 UI 显示
        parent_id: 父任务 ID（创建子任务时使用）
        priority: 优先级（high/medium/low）
        tags: 标签（逗号分隔）

    Returns:
        任务创建结果
    """
    # 兼容: subject 和 title 二选一
    actual_title = subject or title
    if not actual_title:
        return "Error: subject (or title) is required"

    task_id = _short_id()

    # 验证父任务
    if parent_id and parent_id not in _TASKS:
        return f"Error: parent task {parent_id} not found"

    task = {
        "id": task_id,
        "title": actual_title,
        "description": description,
        "active_form": active_form,
        "parent_id": parent_id,
        "priority": priority if priority in ("high", "medium", "low") else "medium",
        "status": "pending",
        "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
        "subtasks": [],
        "blocks": [],       # tasks this one blocks
        "blocked_by": [],   # tasks that block this one
        "created_at": time.time(),
        "updated_at": time.time(),
        "progress": 0,  # 0-100
    }

    _TASKS[task_id] = task

    # 注册到父任务
    if parent_id and parent_id in _TASKS:
        _TASKS[parent_id]["subtasks"].append(task_id)

    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(task["priority"], "⚪")
    result = f"✅ Created: {priority_emoji} [{task_id}] {actual_title}"
    if active_form:
        result += f" ({active_form})"
    if parent_id:
        result += f" (subtask of {parent_id})"
    return result


def _resolve_task(task_id: str) -> Optional[str]:
    """解析任务 ID（精确匹配 + 前缀模糊匹配）"""
    if task_id in _TASKS:
        return task_id
    matches = [t for t in _TASKS if task_id in t or t.startswith(task_id)]
    if len(matches) == 1:
        return matches[0]
    return None


def task_get_handler(task_id: str) -> str:
    """
    按 ID 获取任务完整详情（参考标准TaskGetTool）。

    Args:
        task_id: 任务 ID（支持前缀匹配）

    Returns:
        任务完整信息
    """
    resolved = _resolve_task(task_id)
    if not resolved:
        return f"Error: task '{task_id}' not found"

    t = _TASKS[resolved]
    se = {"pending": "⏳", "in_progress": "🔄", "done": "✅", "cancelled": "❌"}.get(t["status"], "⚪")
    pe = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "⚪")

    lines = [
        f"{se}{pe} Task [{t['id']}]",
        f"  Title: {t['title']}",
    ]
    if t.get("active_form"):
        lines.append(f"  Active: {t['active_form']}")
    if t.get("description"):
        lines.append(f"  Description: {t['description']}")
    lines.append(f"  Status: {t['status']} ({t['progress']}%)")
    lines.append(f"  Priority: {t['priority']}")
    if t.get("tags"):
        lines.append(f"  Tags: {', '.join(t['tags'])}")
    if t.get("parent_id"):
        lines.append(f"  Parent: {t['parent_id']}")
    if t.get("blocked_by"):
        lines.append(f"  BlockedBy: {', '.join(t['blocked_by'])}")
    if t.get("blocks"):
        lines.append(f"  Blocks: {', '.join(t['blocks'])}")
    if t.get("subtasks"):
        sub_list = [f"{sid} ({_TASKS[sid]['status']})" for sid in t["subtasks"] if sid in _TASKS]
        lines.append(f"  Subtasks: {', '.join(sub_list)}")
    if t.get("notes"):
        for n in t["notes"][-3:]:
            lines.append(f"  Note: {n['text'][:80]}")

    return "\n".join(lines)


def task_update_handler(
    task_id: str,
    status: str = "",
    subject: str = "",
    description: str = "",
    active_form: str = "",
    progress: int = -1,
    note: str = "",
    add_tag: str = "",
    add_blocks: str = "",
    add_blocked_by: str = "",
    owner: str = "",
    team_name: str = "",
) -> str:
    """
    更新任务状态/内容（参考标准TaskUpdateTool）。

    Args:
        task_id: 任务 ID（支持前缀匹配）
        status: 新状态（pending/in_progress/done/cancelled）
        subject: 新标题（替换原 subject）
        description: 新描述（替换原 description）
        active_form: 新进行时描述
        progress: 进度百分比（0-100）
        note: 追加备注
        add_tag: 追加标签
        owner: 任务负责人（队友认领任务时使用）
        team_name: 团队名称

    Returns:
        更新结果
    """
    resolved = _resolve_task(task_id)
    if not resolved:
        return f"Error: task '{task_id}' not found"
    task_id = resolved

    task = _TASKS[task_id]
    changes = []

    # 状态更新
    if status and status in ("pending", "in_progress", "done", "cancelled"):
        old_status = task["status"]
        task["status"] = status
        changes.append(f"status: {old_status} → {status}")

        if status == "done":
            task["progress"] = 100
            changes.append("progress: → 100%")

            # 检查父任务
            if task.get("parent_id") and task["parent_id"] in _TASKS:
                parent = _TASKS[task["parent_id"]]
                all_done = all(
                    _TASKS.get(st, {}).get("status") == "done"
                    for st in parent.get("subtasks", [])
                )
                if all_done and parent.get("subtasks"):
                    parent["status"] = "done"
                    parent["progress"] = 100
                    changes.append(f"parent [{task['parent_id']}] auto-completed")

    # 内容更新（参考标准TaskUpdateTool 的 subject/description 参数）
    if subject:
        old_title = task["title"]
        task["title"] = subject
        changes.append(f"title: {old_title} → {subject}")

    if description:
        task["description"] = description
        changes.append(f"description: updated ({len(description)} chars)")

    if active_form:
        task["active_form"] = active_form
        changes.append(f"active_form: {active_form}")

    if progress >= 0:
        task["progress"] = max(0, min(100, progress))
        changes.append(f"progress: → {task['progress']}%")

    if note:
        task.setdefault("notes", []).append({
            "text": note,
            "time": time.time(),
        })
        changes.append(f"note: {note[:50]}")

    if add_tag:
        if add_tag not in task["tags"]:
            task["tags"].append(add_tag)
            changes.append(f"tag: +{add_tag}")

    # Dependency tracking (blocks / blockedBy)
    if add_blocks:
        resolved_block = _resolve_task(add_blocks)
        if not resolved_block:
            return f"Error: blocks target task '{add_blocks}' not found"
        if resolved_block not in task.get("blocks", []):
            task.setdefault("blocks", []).append(resolved_block)
            _TASKS[resolved_block].setdefault("blocked_by", []).append(task_id)
            changes.append(f"blocks: +{resolved_block}")

    if add_blocked_by:
        resolved_dep = _resolve_task(add_blocked_by)
        if not resolved_dep:
            return f"Error: blockedBy target task '{add_blocked_by}' not found"
        if resolved_dep not in task.get("blocked_by", []):
            task.setdefault("blocked_by", []).append(resolved_dep)
            _TASKS[resolved_dep].setdefault("blocks", []).append(task_id)
            changes.append(f"blocked_by: +{resolved_dep}")

    # 任务认领
    if owner:
        old_owner = task.get("owner", "")
        task["owner"] = owner
        changes.append(f"owner: {old_owner or 'None'} → {owner}")
        
        # 自动设置状态为 in_progress
        if task["status"] == "pending":
            task["status"] = "in_progress"
            changes.append(f"status: pending → in_progress (auto)")
    
    # 团队关联
    if team_name and not task.get("team_name"):
        task["team_name"] = team_name
        changes.append(f"team: {team_name}")

    task["updated_at"] = time.time()

    if not changes:
        return f"Task [{task_id}] {task['title']} — no changes"

    se = {"pending": "⏳", "in_progress": "🔄", "done": "✅", "cancelled": "❌"}.get(task["status"], "⚪")
    return f"{se} Task [{task_id}] updated:\n" + "\n".join(f"  • {c}" for c in changes)


def task_stop_handler(task_id: str) -> str:
    """
    Stop a running task (cancel background work).

    Args:
        task_id: Task ID (supports prefix matching)

    Returns:
        Stop result
    """
    resolved = _resolve_task(task_id)
    if not resolved:
        return f"Error: task '{task_id}' not found"

    task = _TASKS[resolved]
    if task["status"] in ("done", "cancelled"):
        return f"Task [{resolved}] is already {task['status']}."

    old_status = task["status"]
    task["status"] = "cancelled"
    task["updated_at"] = time.time()

    # Cancel subtasks too
    cancelled_subs = []
    for sid in task.get("subtasks", []):
        sub = _TASKS.get(sid)
        if sub and sub["status"] not in ("done", "cancelled"):
            sub["status"] = "cancelled"
            sub["updated_at"] = time.time()
            cancelled_subs.append(sid)

    result = f"❌ Task [{resolved}] stopped ({old_status} → cancelled)"
    if cancelled_subs:
        result += f"\n  Also cancelled {len(cancelled_subs)} subtask(s): {', '.join(cancelled_subs)}"
    return result


def task_list_handler(
    filter_status: str = "",
    filter_priority: str = "",
    filter_tag: str = "",
    show_tree: bool = True,
    team_name: str = "",
    show_available: bool = False,
) -> str:
    """
    列出所有任务。

    Args:
        filter_status: 按状态过滤（pending/in_progress/done/cancelled）
        filter_priority: 按优先级过滤（high/medium/low）
        filter_tag: 按标签过滤
        show_tree: 是否以树形结构显示
        team_name: 团队名称（过滤特定团队的任务）
        show_available: 只显示可认领的任务（pending、无 owner、无阻塞）

    Returns:
        任务列表
    """
    if not _TASKS:
        return "📋 暂无任务。使用 task_create 创建新任务。"

    # 过滤
    tasks = list(_TASKS.values())
    
    # 团队过滤
    if team_name:
        tasks = [t for t in tasks if t.get("team_name") == team_name]
    
    if filter_status:
        tasks = [t for t in tasks if t["status"] == filter_status]
    if filter_priority:
        tasks = [t for t in tasks if t["priority"] == filter_priority]
    if filter_tag:
        tasks = [t for t in tasks if filter_tag in t.get("tags", [])]
    
    # 只显示可认领的任务
    if show_available:
        tasks = [
            t for t in tasks
            if t["status"] == "pending"
            and not t.get("owner")
            and not t.get("blocked_by")
        ]

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
    "description": (
        "Create a new task to track implementation work. "
        "Use subject (imperative form like 'Implement X') and activeForm "
        "(present tense like 'Implementing X') for best results. "
        "Supports hierarchy via parent_id, priorities, tags, and team association."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Task title in imperative form (e.g. 'Implement login flow')",
            },
            "description": {
                "type": "string",
                "description": "Detailed task description",
                "default": "",
            },
            "active_form": {
                "type": "string",
                "description": "Present-tense description for UI (e.g. 'Implementing login flow')",
                "default": "",
            },
            "parent_id": {
                "type": "string",
                "description": "Parent task ID (for subtasks)",
                "default": "",
            },
            "priority": {
                "type": "string",
                "description": "Priority: high/medium/low",
                "default": "medium",
            },
            "tags": {
                "type": "string",
                "description": "Comma-separated tags",
                "default": "",
            },
            "team_name": {
                "type": "string",
                "description": "Associate task with a team",
                "default": "",
            },
        },
        "required": ["subject"],
    },
    "handler": task_create_handler,
    "permission_level": "read",
})

register_tool("task_get", {
    "description": (
        "Get full details of a task by ID. "
        "Use this to review task description and check blockedBy before starting work."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID (supports prefix matching)",
            },
        },
        "required": ["task_id"],
    },
    "handler": task_get_handler,
    "permission_level": "read",
})

register_tool("task_update", {
    "description": (
        "Update task status, content, or progress. "
        "Supports status changes (pending/in_progress/done/cancelled), "
        "subject/description/activeForm updates, notes, and task claiming by teammates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID (supports prefix matching)",
            },
            "status": {
                "type": "string",
                "description": "New status: pending/in_progress/done/cancelled",
                "default": "",
            },
            "subject": {
                "type": "string",
                "description": "New title (replaces current)",
                "default": "",
            },
            "description": {
                "type": "string",
                "description": "New description (replaces current)",
                "default": "",
            },
            "active_form": {
                "type": "string",
                "description": "New present-tense description",
                "default": "",
            },
            "progress": {
                "type": "integer",
                "description": "Progress percentage (0-100)",
                "default": -1,
            },
            "note": {
                "type": "string",
                "description": "Append a note",
                "default": "",
            },
            "add_tag": {
                "type": "string",
                "description": "Append a tag",
                "default": "",
            },
            "add_blocks": {
                "type": "string",
                "description": "Task ID that this task blocks",
                "default": "",
            },
            "add_blocked_by": {
                "type": "string",
                "description": "Task ID that blocks this task",
                "default": "",
            },
            "owner": {
                "type": "string",
                "description": "Claim task by setting owner (teammate name)",
                "default": "",
            },
            "team_name": {
                "type": "string",
                "description": "Associate task with team",
                "default": "",
            },
        },
        "required": ["task_id"],
    },
    "handler": task_update_handler,
    "permission_level": "read",
})

register_tool("task_list", {
    "description": (
        "List all tasks with optional filtering. "
        "Shows id, subject, status, owner, and blockedBy. "
        "Use to see available work, project progress, or team tasks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filter_status": {
                "type": "string",
                "description": "Filter by status: pending/in_progress/done/cancelled",
                "default": "",
            },
            "filter_priority": {
                "type": "string",
                "description": "Filter by priority: high/medium/low",
                "default": "",
            },
            "filter_tag": {
                "type": "string",
                "description": "Filter by tag",
                "default": "",
            },
            "show_tree": {
                "type": "boolean",
                "description": "Show as tree (default: true)",
                "default": True,
            },
            "team_name": {
                "type": "string",
                "description": "Filter by team name",
                "default": "",
            },
            "show_available": {
                "type": "boolean",
                "description": "Show only available tasks (pending, no owner, not blocked)",
                "default": False,
            },
        },
    },
    "handler": task_list_handler,
    "permission_level": "read",
})

register_tool("task_stop", {
    "description": (
        "Stop a running task by ID. "
        "Cancels the task and all in-progress subtasks. "
        "Use when a task is no longer needed or was started by mistake."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID to stop (supports prefix matching)",
            },
        },
        "required": ["task_id"],
    },
    "handler": task_stop_handler,
    "permission_level": "read",
})
