"""
SendMessage 工具 - 继续已存在的 Subagent 对话（P0 核心功能）

参考标准实现 SendMessageTool，允许 Coordinator 向已完成的 Subagent
发送后续指令，利用其已有的上下文继续工作。

核心能力:
1. 重新激活已完成的 Subagent
2. 追加消息到 Subagent 的对话历史
3. 支持任务通知机制
4. 与 SubagentManager 集成
"""
import time
import uuid
import threading
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.subagent import subagent_manager, SubagentHandle
from tools.registry import register_tool

logger = logging.getLogger(__name__)


# ── Subagent 对话历史存储 ──
# agent_id -> 对话历史列表
_AGENT_CONVERSATIONS: Dict[str, List[Dict[str, str]]] = {}

# ── 任务通知队列 ──
# 存储 Subagent 完成/状态变更通知
_TASK_NOTIFICATIONS: List[Dict[str, Any]] = []


def _get_conversation_history(agent_id: str) -> List[Dict[str, str]]:
    """获取 Subagent 的对话历史"""
    if agent_id not in _AGENT_CONVERSATIONS:
        _AGENT_CONVERSATIONS[agent_id] = []
    return _AGENT_CONVERSATIONS[agent_id]


def _add_to_conversation(agent_id: str, role: str, content: str):
    """添加消息到对话历史"""
    history = _get_conversation_history(agent_id)
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })


def _create_task_notification(
    agent_id: str,
    status: str,
    summary: str,
    result: str = "",
    usage: Dict[str, int] = None
) -> Dict[str, Any]:
    """创建任务通知（参考标准实现 <task-notification> XML）"""
    notification = {
        "task_id": agent_id,
        "status": status,
        "summary": summary,
        "result": result,
        "usage": usage or {},
        "timestamp": datetime.now().isoformat()
    }
    _TASK_NOTIFICATIONS.append(notification)
    return notification


def send_message_handler(
    to: str,
    message: str,
    summary: str = ""
) -> str:
    """
    向已存在的 Subagent 发送消息，继续其对话（参考标准SendMessageTool）
    
    使用场景:
    1. Subagent 完成研究后，继续指示其实施修复
    2. Subagent 报告失败后，发送修正指令
    3. 需要利用 Subagent 已有上下文进行后续工作
    
    Args:
        to: 目标 Subagent ID（支持前缀匹配）
        message: 消息内容（必须自包含，Subagent 无法看到 Coordinator 的其他对话）
        summary: 简短摘要（5-10 词，用于 UI 显示）
    
    Returns:
        发送结果
    """
    # 解析 Subagent ID
    resolved_id = _resolve_agent_id(to)
    if not resolved_id:
        return f"❌ Error: Subagent '{to}' not found\n\n使用 list_subagents() 查看可用的 Subagent"
    
    # 检查 Subagent 是否存在
    try:
        status_info = subagent_manager.get_agent_status(resolved_id)
    except KeyError:
        return f"❌ Error: Subagent '{resolved_id}' does not exist"
    
    # 获取对话历史
    history = _get_conversation_history(resolved_id)
    
    # 如果 Subagent 已完成，重新激活
    handle = subagent_manager.agents.get(resolved_id)
    if handle and handle.status in ("completed", "failed", "cancelled"):
        logger.info(f"Reactivating Subagent {resolved_id} (was {handle.status})")
        
        # 创建新线程继续对话
        new_thread = threading.Thread(
            target=_continue_subagent_task,
            args=(resolved_id, message),
            daemon=True
        )
        
        # 更新状态
        handle.status = "running"
        handle.result = None
        handle.error = None
        handle.thread = new_thread
        
        # 启动
        new_thread.start()
        
        # 添加到对话历史
        _add_to_conversation(resolved_id, "user", message)
        
        response = (
            f"✅ Message sent to Subagent [{resolved_id}]\n\n"
            f"**Status**: Reactivated ({handle.status} → running)\n"
            f"**Summary**: {summary or message[:100]}\n\n"
            f"Subagent will process your message and notify when complete.\n"
            f"Use `get_task_notifications()` to check for completion."
        )
        return response
    
    # 如果 Subagent 正在运行，追加消息到队列
    elif handle and handle.status == "running":
        _add_to_conversation(resolved_id, "user", message)
        
        response = (
            f"✅ Message queued for Subagent [{resolved_id}]\n\n"
            f"**Status**: Running (message will be processed)\n"
            f"**Summary**: {summary or message[:100]}\n\n"
            f"Note: Subagent is currently running. Your message has been added to its queue."
        )
        return response
    
    else:
        return f"❌ Error: Subagent [{resolved_id}] has unknown status: {handle.status if handle else 'None'}"


def _continue_subagent_task(agent_id: str, new_message: str):
    """
    继续 Subagent 任务（在独立线程中运行）
    
    流程:
    1. 获取对话历史
    2. 调用 LLM 继续对话
    3. 更新结果
    4. 发送任务通知
    """
    try:
        logger.info(f"Subagent {agent_id} continuing task")
        
        # 获取 LLM 客户端
        client = subagent_manager._get_llm_client()
        
        if not client:
            raise RuntimeError("LLM client not available")
        
        # 构建消息历史
        history = _get_conversation_history(agent_id)
        messages = [msg for msg in history if msg["role"] in ("system", "user", "assistant")]
        
        # 调用 LLM
        response = client.chat.completions.create(
            model=handle.model if (handle := subagent_manager.agents.get(agent_id)) else "glm-4-plus",
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        result = response.choices[0].message.content or "No response"
        
        # 添加到对话历史
        _add_to_conversation(agent_id, "assistant", result)
        
        # 更新 Subagent 状态
        with subagent_manager._lock:
            if agent_id in subagent_manager.agents:
                subagent_manager.agents[agent_id].result = result
                subagent_manager.agents[agent_id].status = "completed"
                subagent_manager.agents[agent_id].completed_at = datetime.now().isoformat()
        
        # 创建任务通知
        _create_task_notification(
            agent_id=agent_id,
            status="completed",
            summary=f"Subagent [{agent_id}] completed continuation",
            result=result[:500],
            usage={
                "total_tokens": response.usage.total_tokens if response.usage else 0,
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            }
        )
        
        logger.info(f"Subagent {agent_id} continuation completed")
        
    except Exception as e:
        error_msg = f"Subagent {agent_id} continuation failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # 更新状态
        with subagent_manager._lock:
            if agent_id in subagent_manager.agents:
                subagent_manager.agents[agent_id].error = str(e)
                subagent_manager.agents[agent_id].status = "failed"
                subagent_manager.agents[agent_id].completed_at = datetime.now().isoformat()
        
        # 创建失败通知
        _create_task_notification(
            agent_id=agent_id,
            status="failed",
            summary=f"Subagent [{agent_id}] failed: {str(e)[:100]}",
            result=str(e)
        )


def _resolve_agent_id(agent_id: str) -> Optional[str]:
    """解析 Subagent ID（精确匹配 + 前缀模糊匹配）"""
    if agent_id in subagent_manager.agents:
        return agent_id
    
    # 前缀匹配
    matches = [
        aid for aid in subagent_manager.agents.keys()
        if agent_id in aid or aid.startswith(agent_id)
    ]
    
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        logger.warning(f"Ambiguous agent ID '{agent_id}': {matches}")
        return None
    else:
        return None


def get_task_notifications_handler(
    clear: bool = True
) -> str:
    """
    获取所有待处理的任务通知（参考标准实现 <task-notification>）
    
    Args:
        clear: 是否清空已读取的通知（默认 True）
    
    Returns:
        格式化的任务通知列表
    """
    if not _TASK_NOTIFICATIONS:
        return "📭 No pending task notifications"
    
    lines = ["📬 Task Notifications:\n"]
    
    for i, notif in enumerate(_TASK_NOTIFICATIONS, 1):
        status_emoji = {
            "completed": "✅",
            "failed": "❌",
            "killed": "🛑",
            "running": "🔄"
        }.get(notif["status"], "⚪")
        
        lines.append(f"{i}. {status_emoji} [{notif['task_id']}] {notif['summary']}")
        
        if notif.get("result"):
            result_preview = notif["result"][:200]
            lines.append(f"   Result: {result_preview}{'...' if len(notif['result']) > 200 else ''}")
        
        if notif.get("usage"):
            usage = notif["usage"]
            lines.append(f"   Tokens: {usage.get('total_tokens', 0)} total")
        
        lines.append(f"   Time: {notif['timestamp']}")
        lines.append("")
    
    # 清空通知
    if clear:
        count = len(_TASK_NOTIFICATIONS)
        _TASK_NOTIFICATIONS.clear()
        lines.append(f"({count} notifications cleared)")
    
    return "\n".join(lines)


def list_active_agents_handler() -> str:
    """
    列出所有活跃的 Subagent（包括已完成的，可用于 SendMessage）
    
    Returns:
        Subagent 列表
    """
    agents = subagent_manager.list_agents()
    
    if not agents:
        return "📭 No active Subagents"
    
    lines = ["🤖 Active Subagents:\n"]
    
    for agent in agents:
        status_emoji = {
            "running": "🔄",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "🛑"
        }.get(agent["status"], "⚪")
        
        can_continue = agent["status"] in ("completed", "failed", "cancelled")
        continue_hint = " [✅ Can continue with SendMessage]" if can_continue else ""
        
        lines.append(
            f"{status_emoji} [{agent['agent_id']}] {agent['agent_type']}\n"
            f"   Task: {agent['task'][:80]}{'...' if len(agent['task']) > 80 else ''}\n"
            f"   Status: {agent['status']}{continue_hint}\n"
            f"   Created: {agent['created_at']}\n"
        )
    
    return "\n".join(lines)


# ── 注册工具 ──

register_tool("send_message", {
    "description": (
        "Send a message to an existing Subagent to continue its conversation. "
        "Use this after a Subagent completes research to give it implementation instructions, "
        "or to correct a failed Subagent with new instructions. "
        "The Subagent retains its full context from previous work."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Target Subagent ID (supports prefix matching)",
            },
            "message": {
                "type": "string",
                "description": (
                    "Message content. Must be self-contained — Subagents cannot see your "
                    "conversation with the user. Include file paths, line numbers, and "
                    "specific instructions. Example: 'Fix the null pointer in src/auth/validate.ts:42...'"
                ),
            },
            "summary": {
                "type": "string",
                "description": "Brief summary (5-10 words) for UI display",
                "default": "",
            },
        },
        "required": ["to", "message"],
    },
    "handler": send_message_handler,
    "permission_level": "read",
})

register_tool("get_task_notifications", {
    "description": (
        "Get all pending task notifications from Subagents. "
        "Notifications arrive when Subagents complete, fail, or change status. "
        "Format matches Claude Code's <task-notification> XML structure."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "clear": {
                "type": "boolean",
                "description": "Clear notifications after reading (default: true)",
                "default": True,
            },
        },
    },
    "handler": get_task_notifications_handler,
    "permission_level": "read",
})

register_tool("list_active_agents", {
    "description": (
        "List all Subagents including completed ones that can be continued with SendMessage. "
        "Shows agent ID, type, task, status, and whether continuation is possible."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
    "handler": list_active_agents_handler,
    "permission_level": "read",
})
