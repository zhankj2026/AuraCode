"""
PlanMode 工具 - 计划模式状态管理

参考 Claude Code EnterPlanModeTool / ExitPlanModeTool 设计：
- 进入计划模式：限制为只读工具，专注代码探索和方案设计
- 退出计划模式：用户审批后，恢复正常执行模式
- 全局状态标志，AgentLoop 检查此标志过滤工具
"""

import threading
import logging
from tools.registry import register_tool

logger = logging.getLogger(__name__)

# ── 全局计划模式状态 ──────────────────────────────────────────────────────────────

_plan_mode_lock = threading.Lock()
_plan_mode_active: bool = False
_plan_mode_reason: str = ""


def is_plan_mode_active() -> bool:
    with _plan_mode_lock:
        return _plan_mode_active


def set_plan_mode(active: bool, reason: str = ""):
    global _plan_mode_active, _plan_mode_reason
    with _plan_mode_lock:
        _plan_mode_active = active
        _plan_mode_reason = reason


def get_plan_mode_reason() -> str:
    with _plan_mode_lock:
        return _plan_mode_reason


# ── 计划模式下允许使用的工具（只读） ──────────────────────────────────────────────

PLAN_MODE_ALLOWED_TOOLS = frozenset({
    # 读取类工具
    "read_file",
    "list_directory",
    "find",
    "glob",
    "grep",
    "analyze_file",
    "lint",
    # 网络读取
    "web_fetch",
    "web_search",
    # 任务管理（允许在计划模式中更新任务列表）
    "todo_write",
    # 交互（允许向用户提问）
    "ask_user",
    # 子代理（探索/规划类）
    "spawn_subagent",
    "join_subagent",
    "list_subagents",
    "subagent_stats",
    "list_agent_types",
    "plan_agent",
    # 计划模式自身
    "exit_plan_mode",
    # 技能（只读操作）
    "list_skills",
    "show_available_skills",
    "get_active_skills",
    # 记忆（读取）
    "list_memories",
    "search_memory",
})


def is_tool_allowed_in_plan_mode(tool_name: str) -> bool:
    """检查工具在计划模式下是否允许使用"""
    return tool_name in PLAN_MODE_ALLOWED_TOOLS


# ── 工具处理器 ──────────────────────────────────────────────────────────────────

def enter_plan_mode_handler(reason: str = "") -> str:
    """
    进入计划模式。

    在计划模式下，只能使用只读工具（read_file、grep、find、glob 等），
    不能使用写入或执行工具（write_file、replace_in_file、run_command 等）。

    适用于：
    - 新功能实现前的代码探索
    - 多种方案对比分析
    - 重构方案设计
    - 需要用户审批的架构决策

    Args:
        reason: 进入计划模式的原因（可选）

    Returns:
        模式切换确认
    """
    if is_plan_mode_active():
        return "ℹ️ 当前已处于计划模式，无需重复进入。"

    set_plan_mode(True, reason)
    logger.info(f"进入计划模式: {reason}")

    msg = "📋 已进入计划模式\n\n"
    msg += "当前只能使用只读工具进行代码探索和方案设计：\n"
    msg += "  ✅ read_file, grep, find, glob, list_directory, analyze_file\n"
    msg += "  ✅ web_fetch, web_search（网络查询）\n"
    msg += "  ✅ ask_user（向用户提问）\n"
    msg += "  ✅ spawn_subagent（启动探索子代理）\n"
    msg += "  ❌ write_file, replace_in_file, run_command（写入/执行被禁止）\n\n"

    if reason:
        msg += f"原因: {reason}\n\n"

    msg += "完成方案设计后，使用 exit_plan_mode 退出计划模式。\n"
    return msg


def exit_plan_mode_handler(approved: bool = True, plan_summary: str = "") -> str:
    """
    退出计划模式，恢复正常执行。

    Args:
        approved: 用户是否批准了方案（默认 true）
        plan_summary: 方案摘要（可选，记录设计决策）

    Returns:
        模式切换确认
    """
    if not is_plan_mode_active():
        return "ℹ️ 当前不处于计划模式，无需退出。"

    set_plan_mode(False)
    logger.info(f"退出计划模式: approved={approved}, summary={plan_summary[:100]}")

    if approved:
        msg = "✅ 已退出计划模式，恢复正常执行\n"
        if plan_summary:
            msg += f"\n方案摘要: {plan_summary}\n"
        msg += "\n现在开始实施！可以使用所有工具（write_file、replace_in_file、run_command 等）。"
    else:
        msg = "⚠️ 方案未被批准，已退出计划模式\n"
        msg += "请根据反馈调整方案，或重新使用 enter_plan_mode 进入规划。"

    return msg


# ── 注册工具 ──────────────────────────────────────────────────────────────────────

register_tool("enter_plan_mode", {
    "description": (
        "进入计划模式（只读探索 + 方案设计）。\n"
        "在计划模式下只能使用只读工具，不能修改文件。\n"
        "适用于：\n"
        "1. 新功能实现前需要探索代码库\n"
        "2. 多种实现方案的对比分析\n"
        "3. 需要用户审批的架构决策\n"
        "4. 大规模重构的方案设计\n"
        "不适用于：简单任务、明确指令的任务。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "进入计划模式的原因",
                "default": ""
            }
        },
        "required": []
    },
    "handler": enter_plan_mode_handler,
    "permission_level": "read"
})

register_tool("exit_plan_mode", {
    "description": (
        "退出计划模式，恢复正常执行。\n"
        "完成方案设计后调用此工具。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "approved": {
                "type": "boolean",
                "description": "用户是否批准了设计方案",
                "default": True
            },
            "plan_summary": {
                "type": "string",
                "description": "方案摘要（记录设计决策）",
                "default": ""
            }
        },
        "required": []
    },
    "handler": exit_plan_mode_handler,
    "permission_level": "read"
})
