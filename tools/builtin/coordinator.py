"""
Coordinator 工具 - 协调者模式工具集（P0 核心功能）

提供:
1. coordinator_activate - 激活协调者模式
2. coordinator_synthesize - 综合 Worker 发现
3. coordinator_decide - Continue vs Spawn 决策
4. coordinator_status - 查看协调者状态
"""
from core.coordinator import coordinator, WorkerResult, get_coordinator_system_prompt
from tools.registry import register_tool


def coordinator_activate_handler() -> str:
    """
    激活 Coordinator 模式
    
    Returns:
        激活结果和系统提示词
    """
    coordinator.activate()
    
    return (
        "✅ Coordinator mode activated\n\n"
        "You are now a coordinator. Your role:\n"
        "- Decompose complex tasks into worker assignments\n"
        "- Launch workers in parallel for research/implementation/verification\n"
        "- Synthesize worker findings into specific implementation specs\n"
        "- Decide whether to continue workers (send_message) or spawn fresh ones\n"
        "\n"
        "**System Prompt**:\n"
        "\n"
        + get_coordinator_system_prompt()
    )


def coordinator_deactivate_handler() -> str:
    """
    停用 Coordinator 模式
    
    Returns:
        停用结果
    """
    coordinator.deactivate()
    return "✅ Coordinator mode deactivated"


def coordinator_synthesize_handler(
    worker_ids: str
) -> str:
    """
    综合多个 Worker 的发现（Coordinator 的核心职责！）
    
    **关键原则**:
    - 禁止懒惰委托（"based on your findings"）
    - 必须阅读并理解所有发现
    - 必须生成具体的实施规范（含文件路径、行号）
    
    Args:
        worker_ids: Worker ID 列表（逗号分隔）
    
    Returns:
        综合报告
    """
    # 解析 Worker IDs
    ids = [wid.strip() for wid in worker_ids.split(",") if wid.strip()]
    
    if not ids:
        return "❌ Error: No worker IDs provided"
    
    # 收集 Worker 结果
    worker_results = []
    for agent_id in ids:
        if agent_id in coordinator.workers:
            worker_results.append(coordinator.workers[agent_id])
        else:
            # 尝试从 subagent_manager 获取
            from core.subagent import subagent_manager
            try:
                status_info = subagent_manager.get_agent_status(agent_id)
                # 创建临时 WorkerResult
                temp_worker = WorkerResult(
                    agent_id=agent_id,
                    description=status_info.get("task", "Unknown task"),
                    status=status_info.get("status", "unknown"),
                    result=status_info.get("result_preview", ""),
                    summary=""
                )
                worker_results.append(temp_worker)
            except KeyError:
                return f"❌ Error: Worker '{agent_id}' not found"
    
    # 执行综合
    synthesis = coordinator.synthesize_findings(worker_results)
    
    return synthesis


def coordinator_decide_handler(
    worker_id: str,
    next_task: str
) -> str:
    """
    决策：Continue（SendMessage）还是 Spawn（新 Agent）
    
    Args:
        worker_id: Worker ID
        next_task: 下一步任务描述
    
    Returns:
        决策结果和原因
    """
    # 查找 Worker
    if worker_id not in coordinator.workers:
        return f"❌ Error: Worker '{worker_id}' not found"
    
    worker = coordinator.workers[worker_id]
    
    # 执行决策
    decision = coordinator.decide_continue_vs_spawn(worker, next_task)
    
    # 格式化输出
    decision_emoji = "🔄" if decision["decision"] == "continue" else "🆕"
    
    output_lines = [
        f"{decision_emoji} Decision: {decision['decision'].upper()}",
        f"",
        f"**Worker**: {worker_id}",
        f"**Context Overlap**: {decision['context_overlap']:.0%}",
        f"**Reason**: {decision['reason']}",
        f"",
    ]
    
    if decision["decision"] == "continue":
        output_lines.extend([
            "**Recommended Action**:",
            f"```",
            f"send_message(",
            f"  to=\"{worker_id}\",",
            f"  message=\"{next_task}\"",
            f")",
            f"```",
            f"",
            f"**Why Continue?**",
            f"The worker already has relevant context from its previous work.",
            f"Continuing allows it to leverage loaded files and understanding.",
        ])
    else:
        output_lines.extend([
            "**Recommended Action**:",
            f"```",
            f"spawn_subagent(",
            f"  task=\"{next_task}\"",
            f")",
            f"```",
            f"",
            f"**Why Spawn Fresh?**",
            f"The worker's context has low overlap with the new task.",
            f"Spawning fresh avoids carrying unnecessary context noise.",
        ])
    
    return "\n".join(output_lines)


def coordinator_status_handler() -> str:
    """
    查看 Coordinator 状态
    
    Returns:
        状态报告
    """
    if not coordinator.is_active:
        return "⚪ Coordinator mode is not active.\n\nUse `coordinator_activate()` to activate."
    
    status = coordinator.get_status()
    
    lines = [
        "🎯 Coordinator Status",
        f"",
        f"**Mode**: Active",
        f"**Total Workers**: {status['total_workers']}",
        f"**Pending Notifications**: {status['pending_notifications']}",
        f"**Synthesis Count**: {status['synthesis_count']}",
        f"",
        f"**Workers by Status**:",
        f"  - Running: {status['workers_by_status']['running']}",
        f"  - Completed: {status['workers_by_status']['completed']}",
        f"  - Failed: {status['workers_by_status']['failed']}",
        f"  - Killed: {status['workers_by_status']['killed']}",
    ]
    
    # 列出 Worker 详情
    if coordinator.workers:
        lines.extend([
            f"",
            f"**Worker Details**:",
            f"",
        ])
        
        for agent_id, worker in coordinator.workers.items():
            status_emoji = {
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
                "killed": "🛑"
            }.get(worker.status, "⚪")
            
            lines.append(
                f"  {status_emoji} [{agent_id}] {worker.description[:60]}...\n"
                f"     Status: {worker.status}"
            )
    
    return "\n".join(lines)


# ── 注册工具 ──

register_tool("coordinator_activate", {
    "description": (
        "Activate coordinator mode. Transforms the agent into a task coordinator "
        "that can decompose work, spawn workers, synthesize findings, and direct "
        "implementation and verification."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
    "handler": coordinator_activate_handler,
    "permission_level": "read",
})

register_tool("coordinator_deactivate", {
    "description": (
        "Deactivate coordinator mode and return to normal agent behavior."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
    "handler": coordinator_deactivate_handler,
    "permission_level": "read",
})

register_tool("coordinator_synthesize", {
    "description": (
        "Synthesize findings from multiple workers. This is the coordinator's most "
        "important job — you must read and understand worker findings before directing "
        "follow-up work. Generates specific implementation specs with file paths and "
        "line numbers. Never delegates understanding to workers."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "worker_ids": {
                "type": "string",
                "description": "Comma-separated list of worker IDs to synthesize",
            },
        },
        "required": ["worker_ids"],
    },
    "handler": coordinator_synthesize_handler,
    "permission_level": "read",
})

register_tool("coordinator_decide", {
    "description": (
        "Decide whether to continue a worker (send_message) or spawn a fresh agent "
        "for the next task. Analyzes context overlap between worker's previous work "
        "and the new task. Returns decision with reasoning."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "worker_id": {
                "type": "string",
                "description": "Worker ID to evaluate for continuation",
            },
            "next_task": {
                "type": "string",
                "description": "Description of the next task to be performed",
            },
        },
        "required": ["worker_id", "next_task"],
    },
    "handler": coordinator_decide_handler,
    "permission_level": "read",
})

register_tool("coordinator_status", {
    "description": (
        "Get coordinator status including worker count, status breakdown, "
        "pending notifications, and synthesis history."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
    "handler": coordinator_status_handler,
    "permission_level": "read",
})
