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
PlanMode 工具 - 计划模式状态管理（参考标准EnterPlanMode/ExitPlanMode）

核心机制:
- Plan 文件持久化: 进入计划模式时生成 plan 文件路径，模型用 write_file 写入方案
- ExitPlanMode 读回: 退出时自动读取 plan 文件内容，展示给用户审批
- 用户审批门控: 方案必须经过用户确认才能开始实施
- 周期性提醒: AgentLoop 每 N 轮注入 plan_mode 提醒，防止模型忘记处于计划模式
- EnterPlanMode prompt: 7 类触发条件，参考标准
"""

import os
import threading
import logging
import uuid
from datetime import datetime
from tools.registry import register_tool

logger = logging.getLogger(__name__)

# ── 全局计划模式状态 ──────────────────────────────────────────────────────────────

_plan_mode_lock = threading.Lock()
_plan_mode_active: bool = False
_plan_mode_reason: str = ""
_plan_file_path: str = ""          # plan 文件路径
_plan_turn_count: int = 0          # 进入计划模式后的轮次计数
_plan_mode_entry_time: float = 0   # 进入计划模式的时间戳

# 周期性提醒配置: 每隔 N 轮注入一次提醒
PLAN_REMINDER_INTERVAL = 3

# ── 项目工作目录（由 AgentLoop 注入，替代 os.getcwd()）───────────────────
_project_root: str = ""


def set_project_root(root: str):
    """设置项目工作目录（由 AgentLoop.__init__ 调用）"""
    global _project_root
    _project_root = root


def get_project_root() -> str:
    """获取项目工作目录，未设置时降级为 os.getcwd()"""
    return _project_root or os.getcwd()


def is_plan_mode_active() -> bool:
    with _plan_mode_lock:
        return _plan_mode_active


def set_plan_mode(active: bool, reason: str = "", plan_file: str = ""):
    global _plan_mode_active, _plan_mode_reason, _plan_file_path
    global _plan_turn_count, _plan_mode_entry_time
    with _plan_mode_lock:
        _plan_mode_active = active
        _plan_mode_reason = reason
        if active:
            _plan_file_path = plan_file
            _plan_turn_count = 0
            _plan_mode_entry_time = datetime.now().timestamp()
        else:
            _plan_file_path = ""
            _plan_turn_count = 0


def get_plan_mode_reason() -> str:
    with _plan_mode_lock:
        return _plan_mode_reason


def get_plan_file_path() -> str:
    """获取当前 plan 文件路径（供 AgentLoop 传递给 LLM）"""
    with _plan_mode_lock:
        return _plan_file_path


def get_plan_turn_count() -> int:
    """获取计划模式已持续的轮次数"""
    with _plan_mode_lock:
        return _plan_turn_count


def increment_plan_turn():
    """递增计划模式轮次计数（由 AgentLoop 每轮调用）"""
    with _plan_mode_lock:
        if _plan_mode_active:
            global _plan_turn_count
            _plan_turn_count += 1


def should_inject_reminder() -> bool:
    """判断是否需要注入计划模式提醒（每 PLAN_REMINDER_INTERVAL 轮）"""
    with _plan_mode_lock:
        if not _plan_mode_active:
            return False
        return _plan_turn_count > 0 and _plan_turn_count % PLAN_REMINDER_INTERVAL == 0


def get_plan_content() -> str:
    """读取 plan 文件内容（供 ExitPlanMode 返回给用户审批）"""
    path = get_plan_file_path()
    if not path or not os.path.exists(path):
        return ""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        logger.warning(f"读取 plan 文件失败: {e}")
        return ""


def _generate_plan_file_path(cwd: str = ".") -> str:
    """生成 plan 文件路径: .auracode/plans/{slug}.md"""
    plan_dir = os.path.join(cwd, ".auracode", "plans")
    os.makedirs(plan_dir, exist_ok=True)
    slug = uuid.uuid4().hex[:12]
    return os.path.join(plan_dir, f"plan-{slug}.md")


# ── 计划模式下允许使用的工具（只读） ──────────────────────────────────────────────

PLAN_MODE_ALLOWED_TOOLS = frozenset({
    # 读取类工具
    "read_file",
    "list_directory",
    "find",
    "glob",
    "glob_tool",
    "grep",
    "analyze_file",
    "lint",
    "search_code",
    # 网络读取
    "web_fetch",
    "web_search",
    # 任务管理（允许在计划模式中预建任务骨架 + 规划期间更新进度）
    "todo_write",
    "task_create",
    "task_get",
    "task_update",
    "task_list",
    "task_stop",
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
    # 写入工具 — 仅允许写入 plan 文件（由 _execute_tool 额外检查路径）
    "write_file",
})


def is_tool_allowed_in_plan_mode(tool_name: str) -> bool:
    """检查工具在计划模式下是否允许使用"""
    return tool_name in PLAN_MODE_ALLOWED_TOOLS


def is_write_allowed_for_plan(path: str) -> bool:
    """检查 write_file 是否写入 plan 文件（计划模式下只允许写 plan 文件）"""
    plan_path = get_plan_file_path()
    if not plan_path or not path:
        return False
    return os.path.abspath(path) == os.path.abspath(plan_path)


def build_plan_mode_reminder() -> str:
    """构建计划模式周期性提醒文本（由 AgentLoop 注入系统提示）"""
    plan_path = get_plan_file_path()
    reason = get_plan_mode_reason()
    turn = get_plan_turn_count()

    msg = (
        "\n## ⚠️ 提醒：当前仍处于计划模式\n\n"
        "你只能使用只读工具探索代码库。"
        "请将你的实现方案写入以下 plan 文件：\n"
        f"  plan 文件: `{plan_path}`\n\n"
    )
    if reason:
        msg += f"规划原因: {reason}\n\n"
    msg += (
        f"已在计划模式持续 {turn} 轮。"
        "完成方案后请调用 exit_plan_mode 退出计划模式。\n"
    )
    return msg


# ── 工具处理器 ──────────────────────────────────────────────────────────────────

def enter_plan_mode_handler(reason: str = "") -> str:
    """
    进入计划模式（参考标准EnterPlanMode）。

    在计划模式下，只能使用只读工具探索代码库并设计实现方案，
    方案必须写入指定的 plan 文件，完成后调用 exit_plan_mode 提交给用户审批。

    Args:
        reason: 进入计划模式的原因（可选）

    Returns:
        模式切换确认 + plan 文件路径
    """
    if is_plan_mode_active():
        return "Already in plan mode."

    # 检查是否已有计划文件
    cwd = get_project_root()
    logger.info(f"enter_plan_mode: project_root={cwd}, os.getcwd()={os.getcwd()}")
    
    # 查找最新的计划文件
    plan_dir = os.path.join(cwd, ".auracode", "plans")
    existing_plan_file = None
    if os.path.exists(plan_dir):
        # 查找最新的计划文件（按修改时间排序）
        plan_files = [
            os.path.join(plan_dir, f) 
            for f in os.listdir(plan_dir) 
            if f.startswith("plan-") and f.endswith(".md")
        ]
        if plan_files:
            plan_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            existing_plan_file = plan_files[0]
    
    # 如果找到已有计划文件
    if existing_plan_file and os.path.exists(existing_plan_file):
        # 读取计划内容
        try:
            with open(existing_plan_file, 'r', encoding='utf-8') as f:
                plan_content = f.read().strip()
            
            if plan_content:
                # 计划文件有内容，直接使用
                logger.info(f"发现已有计划文件，跳过新建: {existing_plan_file}")
                set_plan_mode(True, reason=reason, plan_file=existing_plan_file)
                
                msg = (
                    "Found existing plan file. Resuming with it.\n\n"
                    f"**Plan file**: `{existing_plan_file}`\n\n"
                    "Existing plan content:\n"
                    "```\n"
                    f"{plan_content[:500]}...\n"  # 只显示前 500 字符
                    "```\n\n"
                    "You can:\n"
                    "1. Review the existing plan and improve it if needed\n"
                    "2. Call exit_plan_mode to proceed with implementation\n"
                    "3. Or continue exploring and update the plan\n"
                )
                return msg
        except Exception as e:
            logger.warning(f"读取已有计划文件失败: {e}")
    
    # 没有已有计划文件或读取失败，新建计划文件
    plan_file = _generate_plan_file_path(cwd)
    set_plan_mode(True, reason=reason, plan_file=plan_file)
    logger.info(f"进入计划模式: reason={reason}, plan_file={plan_file}")

    # 构建返回消息（参考标准实现 tool_result）
    msg = (
        "Entered plan mode. Focus on exploring the codebase and designing "
        "an implementation approach.\n\n"
        "In plan mode, you should:\n"
        "1. Thoroughly explore the codebase using read_file, grep, find, glob\n"
        "2. Identify existing patterns and architectural approaches\n"
        "3. Consider multiple approaches and their trade-offs\n"
        "4. Use ask_user if you need to clarify the approach\n"
        "5. Write your plan to the plan file below\n"
        "6. When ready, call exit_plan_mode to present for user approval\n\n"
        f"**Plan file**: `{plan_file}`\n"
        "Use write_file to write your implementation plan to this file.\n\n"
        "DO NOT write or edit any project files yet. "
        "This is a read-only exploration and planning phase "
        "(except for writing to the plan file above).\n"
    )
    return msg


def exit_plan_mode_handler(plan_summary: str = "") -> str:
    """
    退出计划模式，提交方案给用户审批（参考标准ExitPlanMode）。

    自动读取 plan 文件内容。如果 plan 文件存在，将完整内容展示给用户；
    如果 plan 文件为空，则使用 plan_summary 参数。

    Args:
        plan_summary: 方案摘要（备选，当 plan 文件为空时使用）

    Returns:
        完整 plan 内容 + 审批指示
    """
    if not is_plan_mode_active():
        return "Not in plan mode."

    # 读取 plan 文件
    plan_content = get_plan_content()
    plan_path = get_plan_file_path()

    # 如果没有 plan 文件内容，使用参数
    if not plan_content and plan_summary:
        plan_content = plan_summary

    # 退出计划模式
    set_plan_mode(False)
    logger.info(f"退出计划模式: plan_path={plan_path}, "
                f"content_len={len(plan_content)}")

    if plan_content:
        # 检查可用的多任务工具
        from tools.registry import TOOL_REGISTRY
        has_team_create = "team_create" in TOOL_REGISTRY
        has_task_create = "task_create" in TOOL_REGISTRY
        has_spawn_subagent = "spawn_subagent" in TOOL_REGISTRY
        
        # 构建自适应多任务引导（根据实际可用工具动态生成）
        task_hint = ""
        if has_team_create or has_task_create or has_spawn_subagent:
            # 1. 推荐工作流（动态适配可用工具）
            task_hint = "\n## 🎯 Recommended Workflow\n\n"
            
            if has_task_create:
                task_hint += "### Step 1: Break Down Work\n"
                task_hint += "Use `task_create` to track progress:\n"
                task_hint += "```\n"
                task_hint += "# Example for a web project:\n"
                task_hint += "task_create('Setup structure', 'Create HTML/CSS skeleton')\n"
                task_hint += "task_create('Core logic', 'Implement main functionality')\n"
                task_hint += "task_create('Testing', 'Write unit tests')\n"
                task_hint += "```\n\n"
            
            # 2. 并行执行（更真实的示例）
            task_hint += "### Step 2: Batch Independent Operations\n"
            task_hint += "When creating multiple independent files, **batch them in one response**:\n"
            task_hint += "```\n"
            task_hint += "# ✅ Good: 3 calls in same response\n"
            task_hint += "write_file('config.js', content1)\n"
            task_hint += "write_file('utils.js', content2)\n"
            task_hint += "write_file('api.js', content3)\n"
            task_hint += "# System parallelizes: ~3s vs sequential 15s\n"
            task_hint += "```\n\n"
            
            # 3. 进度跟踪（更完整的状态）
            if has_task_create:
                task_hint += "### Step 3: Update Progress\n"
                task_hint += "```\n"
                task_hint += "task_update(id=1, status='complete')\n"
                task_hint += "task_update(id=2, status='in_progress')\n"
                task_hint += "task_update(id=3, status='blocked', reason='Waiting for API spec')\n"
                task_hint += "```\n\n"
            
            # 4. 工具选择（根据实际能力动态生成）
            task_hint += "## 🚀 Tool Selection Guide\n\n"
            choices = []
            if has_spawn_subagent:
                choices.append("- **Independent modules?** → `spawn_subagent` (3 subagents for UI/API/tests)")
            if has_task_create:
                choices.append("- **Track multi-step work?** → `task_create` + `task_update`")
            if has_team_create:
                choices.append("- **Complex collaboration?** → `team_create` (multiple agents coordinate)")
            task_hint += "\n".join(choices) + "\n\n"
            
            # 5. 性能提示（更具体）
            task_hint += "**⚡ Performance**: Independent operations are auto-parallelized. "
            task_hint += "Batch them in the same response for best results.\n"

        msg = (
            "✅ Your plan has been approved. Start implementing now!\n\n"
            f"📋 Plan saved to: `{plan_path}`\n"
            "You can refer back to it during implementation.\n\n"
            "---\n\n"
            "## 🎯 Next Steps\n\n"
            "1. **Review** your plan above\n"
            "2. **Create todo list** to track progress (recommended)\n"
            "3. **Start implementing** the first step immediately\n"
            "4. **Use parallel execution** when creating multiple files\n\n"
            f"{task_hint}"
            "---\n\n"
            "## 📋 Approved Plan\n\n"
            f"{plan_content}\n"
        )
    else:
        msg = (
            "⚠️ Plan mode exited. No plan file was written.\n\n"
            "You can now start coding, but consider creating a plan "
            "for complex tasks using `enter_plan_mode`."
        )

    return msg


# ── 注册工具 ──────────────────────────────────────────────────────────────────────

register_tool("enter_plan_mode", {
    "description": (
        "Use this tool proactively when you're about to start a non-trivial "
        "implementation task. Getting user sign-off on your approach before "
        "writing code prevents wasted effort and ensures alignment. This tool "
        "transitions you into plan mode where you can explore the codebase and "
        "design an implementation approach for user approval.\n\n"
        "## When to Use This Tool\n\n"
        "**Prefer using EnterPlanMode** for implementation tasks unless "
        "they're simple. Use it when ANY of these conditions apply:\n\n"
        "1. **New Feature Implementation**: Adding meaningful new functionality\n"
        "   - Example: 'Add a logout button' - where should it go? What should happen on click?\n"
        "   - Example: 'Add form validation' - what rules? What error messages?\n"
        "2. **Multiple Valid Approaches**: The task can be solved in several different ways\n"
        "   - Example: 'Add caching to the API' - could use Redis, in-memory, file-based, etc.\n"
        "   - Example: 'Improve performance' - many optimization strategies possible\n"
        "3. **Code Modifications**: Changes that affect existing behavior or structure\n"
        "   - Example: 'Update the login flow' - what exactly should change?\n"
        "   - Example: 'Refactor this component' - what's the target architecture?\n"
        "4. **Architectural Decisions**: The task requires choosing between patterns or technologies\n"
        "   - Example: 'Add real-time updates' - WebSockets vs SSE vs polling\n"
        "   - Example: 'Implement state management' - Redux vs Context vs custom solution\n"
        "5. **Multi-File Changes**: The task will likely touch more than 2-3 files\n"
        "   - Example: 'Refactor the authentication system'\n"
        "   - Example: 'Add a new API endpoint with tests'\n"
        "6. **Unclear Requirements**: You need to explore before understanding the full scope\n"
        "   - Example: 'Make the app faster' - need to profile and identify bottlenecks\n"
        "   - Example: 'Fix the bug in checkout' - need to investigate root cause\n"
        "7. **User Preferences Matter**: The implementation could reasonably go multiple ways\n"
        "   - If you would use ask_user to clarify the approach, use EnterPlanMode instead\n"
        "   - Plan mode lets you explore first, then present options with context\n\n"
        "## When NOT to Use This Tool\n\n"
        "Only skip EnterPlanMode for simple tasks:\n"
        "- Single-line or few-line fixes (typos, obvious bugs, small tweaks)\n"
        "- Adding a single function with clear requirements\n"
        "- Tasks where the user has given very specific, detailed instructions\n"
        "- Pure research/exploration tasks (use spawn_subagent explore instead)\n\n"
        "## Examples\n\n"
        "### GOOD - Use EnterPlanMode:\n"
        "User: 'Add user authentication to the app'\n"
        "- Requires architectural decisions (session vs JWT, where to store tokens, middleware structure)\n\n"
        "User: 'Optimize the database queries'\n"
        "- Multiple approaches possible, need to profile first, significant impact\n\n"
        "User: 'Implement dark mode'\n"
        "- Architectural decision on theme system, affects many components\n\n"
        "User: 'Build a web game based on the design document'\n"
        "- Complex multi-system architecture (rendering, physics, AI, UI), many design decisions\n\n"
        "### BAD - Don't use EnterPlanMode:\n"
        "User: 'Fix the typo in the README'\n"
        "- Straightforward, no planning needed\n\n"
        "User: 'Add a console.log to debug this function'\n"
        "- Simple, obvious implementation\n\n"
        "User: 'What files handle routing?'\n"
        "- Research task, not implementation planning\n\n"
        "## Important Notes\n\n"
        "- This tool REQUIRES user approval - they must consent to entering plan mode\n"
        "- If unsure whether to use it, err on the side of planning - it's better to get alignment upfront than to redo work\n"
        "- Users appreciate being consulted before significant changes are made to their codebase"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why plan mode is needed for this task",
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
        "Use this tool when you are in plan mode and have finished writing "
        "your plan to the plan file. This signals that you're done planning "
        "and ready for the user to review and approve.\n\n"
        "## ⚠️ CRITICAL WORKFLOW ⚠️\n\n"
        "1. Call this tool to submit your plan for approval\n"
        "2. **STOP and WAIT** for the user to respond\n"
        "3. The user will either:\n"
        "   - Approve your plan (then you can start coding)\n"
        "   - Request changes (then you must revise the plan)\n"
        "   - Reject the plan (then you must propose a different approach)\n\n"
        "**DO NOT** start writing code immediately after calling this tool.\n"
        "**DO NOT** call write_file or edit_file until the user explicitly approves.\n\n"
        "## When to Use This Tool\n\n"
        "- Only when you have written a complete plan to the plan file\n"
        "- Only when you are ready to present the plan for approval\n"
        "- NOT for asking 'Is this plan okay?' - that's what this tool does\n\n"
        "## Example Flow\n\n"
        "1. User: 'Add user authentication'\n"
        "2. You: Call enter_plan_mode\n"
        "3. You: Explore codebase, design plan, write to plan file\n"
        "4. You: Call exit_plan_mode\n"
        "5. **STOP AND WAIT**\n"
        "6. User: 'Approved, go ahead'\n"
        "7. You: Start implementing the plan"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "plan_summary": {
                "type": "string",
                "description": "Brief summary of the plan (fallback if plan file is empty)",
                "default": ""
            }
        },
        "required": []
    },
    "handler": exit_plan_mode_handler,
    "permission_level": "read"
})
