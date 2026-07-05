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
TeamManager — 团队管理模式（P1 核心功能）

参考标准实现 TeamCreate/TeamDelete/Teammate 系统，实现：
1. 创建和管理团队（Team）
2. 启动队友（Teammate）
3. 团队配置持久化
4. 队友间协作机制

核心概念:
- Team: 团队，包含多个 Teammate
- Teammate: 队友，有独立的 agent_id 和角色
- TeamLead: 团队领导者，创建团队的 Agent
- TaskList: 任务列表，与 Team 1:1 对应
"""
import json
import os
import time
import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 数据模型 ──

@dataclass
class Teammate:
    """队友信息"""
    agent_id: str                    # Agent ID
    name: str                        # 队友名称（用于通信）
    agent_type: str                  # Agent 类型（explore/general等）
    role: str = ""                   # 角色描述（researcher/implementer/tester）
    status: str = "idle"             # idle/running/completed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())
    current_task: str = ""           # 当前任务 ID
    model: str = "glm-4-plus"        # 使用的模型
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TeamConfig:
    """团队配置"""
    team_name: str                   # 团队名称
    description: str = ""            # 团队描述
    lead_agent_id: str = ""          # 团队领导者 ID
    members: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    task_list_id: str = ""           # 对应的 TaskList ID
    allowed_paths: List[Dict] = field(default_factory=list)  # 允许的路径
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 全局存储 ──

# team_name -> TeamConfig
_TEAMS: Dict[str, TeamConfig] = {}

# team_name -> List[Teammate]
_TEAMMATES: Dict[str, List[Teammate]] = {}

# 团队配置持久化目录
_TEAMS_DIR = Path.home() / ".auracode" / "teams"
_TASKS_DIR = Path.home() / ".auracode" / "tasks"


def _ensure_dirs():
    """确保目录存在"""
    _TEAMS_DIR.mkdir(parents=True, exist_ok=True)
    _TASKS_DIR.mkdir(parents=True, exist_ok=True)


def _save_team_config(team_name: str):
    """保存团队配置到文件系统"""
    _ensure_dirs()
    team_file = _TEAMS_DIR / f"{team_name}.json"
    
    if team_name in _TEAMS:
        config = _TEAMS[team_name]
        with open(team_file, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"Saved team config: {team_file}")


def _load_team_config(team_name: str) -> Optional[TeamConfig]:
    """从文件系统加载团队配置"""
    team_file = _TEAMS_DIR / f"{team_name}.json"
    
    if not team_file.exists():
        return None
    
    try:
        with open(team_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        config = TeamConfig(**data)
        _TEAMS[team_name] = config
        return config
    except Exception as e:
        logger.error(f"Failed to load team config: {e}")
        return None


def _resolve_teammate_name(team_name: str, name_or_id: str) -> Optional[str]:
    """
    解析队友名称或 ID
    
    Args:
        team_name: 团队名称
        name_or_id: 队友名称或 agent_id
    
    Returns:
        队友的 agent_id
    """
    if team_name not in _TEAMMATES:
        return None
    
    for teammate in _TEAMMATES[team_name]:
        if teammate.name == name_or_id or teammate.agent_id == name_or_id:
            return teammate.agent_id
    
    return None


# ── 核心功能 ──

def team_create_handler(
    team_name: str,
    description: str = "",
    lead_agent_type: str = "general"
) -> str:
    """
    创建新团队（参考标准TeamCreateTool）
    
    流程:
    1. 创建团队配置
    2. 创建对应的 TaskList 目录
    3. 保存配置到文件系统
    4. 注册团队领导者
    
    Args:
        team_name: 团队名称
        description: 团队描述
        lead_agent_type: 领导者 Agent 类型
    
    Returns:
        创建结果
    """
    # 验证团队名称
    if not team_name or not team_name.strip():
        return "❌ Error: team_name is required"
    
    team_name = team_name.strip().lower().replace(" ", "-")
    
    # 检查是否已存在
    if team_name in _TEAMS:
        return f"⚠️ Team '{team_name}' already exists"
    
    # 生成 TaskList ID
    task_list_id = f"team-{team_name}"
    
    # 创建团队配置
    lead_agent_id = f"lead-{uuid.uuid4().hex[:8]}"
    config = TeamConfig(
        team_name=team_name,
        description=description,
        lead_agent_id=lead_agent_id,
        task_list_id=task_list_id,
        members=[{
            "agent_id": lead_agent_id,
            "name": "team-lead",
            "agent_type": lead_agent_type,
            "role": "leader"
        }]
    )
    
    # 存储
    _TEAMS[team_name] = config
    _TEAMMATES[team_name] = [
        Teammate(
            agent_id=lead_agent_id,
            name="team-lead",
            agent_type=lead_agent_type,
            role="leader"
        )
    ]
    
    # 保存到文件系统
    _save_team_config(team_name)
    
    # 创建 TaskList 目录
    task_dir = _TASKS_DIR / task_list_id
    task_dir.mkdir(parents=True, exist_ok=True)
    
    return (
        f"✅ Team created: {team_name}\n\n"
        f"**Team Name**: {team_name}\n"
        f"**Description**: {description or 'N/A'}\n"
        f"**Team Lead**: team-lead ({lead_agent_id})\n"
        f"**Task List**: {task_list_id}\n"
        f"**Config File**: {_TEAMS_DIR / f'{team_name}.json'}\n"
        f"\n"
        f"Next steps:\n"
        f"1. Use `team_spawn` to add teammates\n"
        f"2. Use `task_create` to create tasks\n"
        f"3. Use `team_list` to view team status"
    )


def team_delete_handler(team_name: str) -> str:
    """
    删除团队（参考标准TeamDeleteTool）
    
    Args:
        team_name: 团队名称
    
    Returns:
        删除结果
    """
    if team_name not in _TEAMS:
        return f"❌ Error: Team '{team_name}' not found"
    
    # 获取团队成员
    teammates = _TEAMMATES.get(team_name, [])
    teammate_count = len(teammates)
    
    # 从内存中删除
    del _TEAMS[team_name]
    if team_name in _TEAMMATES:
        del _TEAMMATES[team_name]
    
    # 删除配置文件
    team_file = _TEAMS_DIR / f"{team_name}.json"
    if team_file.exists():
        team_file.unlink()
    
    return (
        f"✅ Team deleted: {team_name}\n\n"
        f"Removed {teammate_count} teammate(s)\n"
        f"Config file deleted: {team_file}"
    )


def team_spawn_handler(
    team_name: str,
    name: str,
    agent_type: str = "general",
    role: str = "",
    model: str = "glm-4-plus",
    initial_prompt: str = ""
) -> str:
    """
    启动队友加入团队（参考标准Agent tool with team_name）
    
    Args:
        team_name: 团队名称
        name: 队友名称（用于通信，如 "researcher", "implementer"）
        agent_type: Agent 类型
        role: 角色描述
        model: 使用的模型
        initial_prompt: 初始任务 prompt
    
    Returns:
        启动结果
    """
    # 验证团队存在
    if team_name not in _TEAMS:
        return f"❌ Error: Team '{team_name}' not found. Use `team_create` first."
    
    # 检查名称是否重复
    for teammate in _TEAMMATES.get(team_name, []):
        if teammate.name == name:
            return f"❌ Error: Teammate name '{name}' already exists in team '{team_name}'"
    
    # 创建队友
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    teammate = Teammate(
        agent_id=agent_id,
        name=name,
        agent_type=agent_type,
        role=role or name,
        model=model
    )
    
    # 添加到团队
    _TEAMMATES.setdefault(team_name, []).append(teammate)
    
    # 更新团队配置
    config = _TEAMS[team_name]
    config.members.append({
        "agent_id": agent_id,
        "name": name,
        "agent_type": agent_type,
        "role": role or name,
        "model": model
    })
    
    # 保存配置
    _save_team_config(team_name)
    
    # 如果有初始 prompt，启动 Subagent
    spawn_result = ""
    if initial_prompt:
        from core.subagent import subagent_manager
        try:
            handle = subagent_manager.spawn_subagent(
                task=initial_prompt,
                model=model,
                agent_type=agent_type,
                run_in_background=True
            )
            spawn_result = f"\n\n**Subagent Started**: {handle.agent_id}"
        except Exception as e:
            spawn_result = f"\n\n⚠️ Failed to start subagent: {str(e)}"
    
    return (
        f"✅ Teammate spawned: {name}\n\n"
        f"**Team**: {team_name}\n"
        f"**Name**: {name}\n"
        f"**Agent ID**: {agent_id}\n"
        f"**Type**: {agent_type}\n"
        f"**Role**: {role or name}\n"
        f"**Model**: {model}\n"
        f"**Status**: idle{spawn_result}"
    )


def team_list_handler(team_name: str = "") -> str:
    """
    列出团队信息
    
    Args:
        team_name: 团队名称（可选，为空时列出所有团队）
    
    Returns:
        团队列表
    """
    if not _TEAMS:
        return "📭 No teams created yet. Use `team_create` to create a team."
    
    if team_name:
        # 列出指定团队
        if team_name not in _TEAMS:
            return f"❌ Error: Team '{team_name}' not found"
        
        config = _TEAMS[team_name]
        teammates = _TEAMMATES.get(team_name, [])
        
        lines = [
            f"👥 Team: {config.team_name}",
            f"",
            f"**Description**: {config.description or 'N/A'}",
            f"**Created**: {config.created_at}",
            f"**Task List**: {config.task_list_id}",
            f"**Members**: {len(teammates)}",
            f"",
            f"**Team Members**:",
            f"",
        ]
        
        for tm in teammates:
            status_emoji = {
                "idle": "⏸️",
                "running": "🔄",
                "completed": "✅"
            }.get(tm.status, "⚪")
            
            lines.append(
                f"  {status_emoji} **{tm.name}** ({tm.role})\n"
                f"     Agent ID: {tm.agent_id}\n"
                f"     Type: {tm.agent_type}\n"
                f"     Status: {tm.status}\n"
                f"     Current Task: {tm.current_task or 'None'}"
            )
        
        return "\n".join(lines)
    
    else:
        # 列出所有团队
        lines = ["📋 All Teams:\n"]
        
        for name, config in _TEAMS.items():
            teammate_count = len(_TEAMMATES.get(name, []))
            lines.append(
                f"👥 **{name}**\n"
                f"   Description: {config.description or 'N/A'}\n"
                f"   Members: {teammate_count}\n"
                f"   Created: {config.created_at}\n"
            )
        
        return "\n".join(lines)


def team_discover_handler(team_name: str) -> str:
    """
    发现团队成员（队友用于读取团队配置）
    
    Args:
        team_name: 团队名称
    
    Returns:
        团队配置信息（包括所有成员）
    """
    # 尝试从内存或文件系统加载
    config = _TEAMS.get(team_name) or _load_team_config(team_name)
    
    if not config:
        return f"❌ Error: Team '{team_name}' not found"
    
    lines = [
        f"🔍 Team Discovery: {team_name}",
        f"",
        f"**Team Lead**: {config.lead_agent_id}",
        f"**Task List**: {config.task_list_id}",
        f"**Members**: {len(config.members)}",
        f"",
        f"**Member List**:",
        f"",
    ]
    
    for member in config.members:
        lines.append(
            f"  - **Name**: {member['name']}\n"
            f"    Agent ID: {member['agent_id']}\n"
            f"    Type: {member['agent_type']}\n"
            f"    Role: {member.get('role', 'N/A')}"
        )
    
    lines.extend([
        f"",
        f"**Usage**:",
        f"- Use names (not agent IDs) for communication",
        f"- Example: `send_message(to='researcher', message='...')`",
        f"- Check task list for available work",
    ])
    
    return "\n".join(lines)


def team_notify_idle_handler(
    team_name: str,
    teammate_name: str,
    message: str = ""
) -> str:
    """
    队友空闲通知（系统自动调用）
    
    Args:
        team_name: 团队名称
        teammate_name: 队友名称
        message: 空闲消息（可选）
    
    Returns:
        通知结果
    """
    agent_id = _resolve_teammate_name(team_name, teammate_name)
    if not agent_id:
        return f"❌ Error: Teammate '{teammate_name}' not found in team '{team_name}'"
    
    # 更新状态
    for teammate in _TEAMMATES.get(team_name, []):
        if teammate.agent_id == agent_id:
            teammate.status = "idle"
            teammate.last_active = datetime.now().isoformat()
            break
    
    return (
        f"⏸️ Teammate '{teammate_name}' is now idle\n\n"
        f"Team lead can assign new work via `task_update` or `send_message`"
    )


# ── 注册工具 ──

from tools.registry import register_tool

register_tool("team_create", {
    "description": (
        "Create a new team to coordinate multiple agents working on a project. "
        "Teams have a 1:1 correspondence with task lists (Team = TaskList). "
        "Use when the user explicitly asks to use a team, or when a task is complex "
        "enough to benefit from parallel work by multiple agents."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {
                "type": "string",
                "description": "Name for the new team (required)",
            },
            "description": {
                "type": "string",
                "description": "Team description/purpose",
                "default": "",
            },
            "lead_agent_type": {
                "type": "string",
                "description": "Agent type for the team lead",
                "default": "general",
            },
        },
        "required": ["team_name"],
    },
    "handler": team_create_handler,
    "permission_level": "read",
})

register_tool("team_delete", {
    "description": (
        "Delete a team and remove all teammates. Use when the project is completed "
        "or the team is no longer needed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {
                "type": "string",
                "description": "Name of the team to delete",
            },
        },
        "required": ["team_name"],
    },
    "handler": team_delete_handler,
    "permission_level": "read",
})

register_tool("team_spawn", {
    "description": (
        "Spawn a new teammate to join an existing team. The teammate can receive "
        "messages, claim tasks, and collaborate with other team members. "
        "Use names (not agent IDs) for communication."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {
                "type": "string",
                "description": "Team name to join",
            },
            "name": {
                "type": "string",
                "description": "Teammate name for communication (e.g., 'researcher', 'implementer')",
            },
            "agent_type": {
                "type": "string",
                "description": "Agent type (explore/plan/review/general)",
                "default": "general",
            },
            "role": {
                "type": "string",
                "description": "Role description",
                "default": "",
            },
            "model": {
                "type": "string",
                "description": "Model to use",
                "default": "glm-4-plus",
            },
            "initial_prompt": {
                "type": "string",
                "description": "Initial task prompt for the teammate",
                "default": "",
            },
        },
        "required": ["team_name", "name"],
    },
    "handler": team_spawn_handler,
    "permission_level": "read",
})

register_tool("team_list", {
    "description": (
        "List team information. Without team_name, lists all teams. "
        "With team_name, shows detailed member list and status."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {
                "type": "string",
                "description": "Team name (optional, lists all if empty)",
                "default": "",
            },
        },
    },
    "handler": team_list_handler,
    "permission_level": "read",
})

register_tool("team_discover", {
    "description": (
        "Discover team members and configuration. Teammates use this to read "
        "the team config file and find other members' names for communication."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {
                "type": "string",
                "description": "Team name to discover",
            },
        },
        "required": ["team_name"],
    },
    "handler": team_discover_handler,
    "permission_level": "read",
})

register_tool("team_notify_idle", {
    "description": (
        "Mark a teammate as idle. Called automatically when a teammate finishes "
        "their turn. Team lead can then assign new work."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {
                "type": "string",
                "description": "Team name",
            },
            "teammate_name": {
                "type": "string",
                "description": "Teammate name",
            },
            "message": {
                "type": "string",
                "description": "Idle message (optional)",
                "default": "",
            },
        },
        "required": ["team_name", "teammate_name"],
    },
    "handler": team_notify_idle_handler,
    "permission_level": "read",
})


# ── 队友通信工具（增强团队协作） ──

def teammate_send_handler(
    team_name: str,
    from_name: str,
    to_name: str,
    message: str,
    msg_type: str = "info"
) -> str:
    """
    队友间发送消息（参考标准 SendMessageTool）
    
    Args:
        team_name: 团队名称
        from_name: 发送者名称
        to_name: 接收者名称（"*" 表示广播）
        message: 消息内容
        msg_type: 消息类型（info/request/response）
    
    Returns:
        发送结果
    """
    from core.subagent import subagent_manager
    
    # 验证团队存在
    if team_name not in _TEAMS:
        return f"❌ Error: Team '{team_name}' not found"
    
    # 查找发送者 agent_id
    from_id = _resolve_teammate_name(team_name, from_name)
    if not from_id:
        return f"❌ Error: Teammate '{from_name}' not found in team '{team_name}'"
    
    # 查找接收者 agent_id
    if to_name == "*":
        to_id = "*"  # 广播
    else:
        to_id = _resolve_teammate_name(team_name, to_name)
        if not to_id:
            return f"❌ Error: Teammate '{to_name}' not found in team '{team_name}'"
    
    # 发送消息
    msg_id = subagent_manager.mailbox.send(
        sender=from_id,
        receiver=to_id,
        content=f"[{from_name} → {to_name}] {message}",
        msg_type=msg_type
    )
    
    return f"✅ Message sent: {msg_id}\nFrom: {from_name}\nTo: {to_name}\nType: {msg_type}"


def teammate_receive_handler(
    team_name: str,
    name: str,
    msg_type: str = ""
) -> str:
    """
    接收队友消息（参考标准 CheckMailboxTool）
    
    Args:
        team_name: 团队名称
        name: 接收者名称
        msg_type: 过滤消息类型（可选）
    
    Returns:
        消息列表
    """
    from core.subagent import subagent_manager
    
    # 验证团队存在
    if team_name not in _TEAMS:
        return f"❌ Error: Team '{team_name}' not found"
    
    # 查找接收者 agent_id
    agent_id = _resolve_teammate_name(team_name, name)
    if not agent_id:
        return f"❌ Error: Teammate '{name}' not found in team '{team_name}'"
    
    # 接收消息
    messages = subagent_manager.mailbox.receive(
        agent_id=agent_id,
        msg_type=msg_type if msg_type else None
    )
    
    if not messages:
        return f"📭 No messages for {name}"
    
    lines = [f"📬 Messages for {name}:\n"]
    for msg in messages:
        lines.append(f"- [{msg.msg_type}] From: {msg.sender}")
        lines.append(f"  {msg.content}")
        lines.append(f"  Time: {msg.timestamp}\n")
    
    return "\n".join(lines)


def team_assign_task_handler(
    team_name: str,
    teammate_name: str,
    task_description: str,
    create_task_list_entry: bool = True
) -> str:
    """
    分配任务给特定队友（参考标准 TaskAssign）
    
    Args:
        team_name: 团队名称
        teammate_name: 队友名称
        task_description: 任务描述
        create_task_list_entry: 是否同时创建 TaskList 条目
    
    Returns:
        分配结果
    """
    from core.subagent import subagent_manager
    
    # 验证团队存在
    if team_name not in _TEAMS:
        return f"❌ Error: Team '{team_name}' not found"
    
    # 查找队友
    agent_id = _resolve_teammate_name(team_name, teammate_name)
    if not agent_id:
        return f"❌ Error: Teammate '{teammate_name}' not found in team '{team_name}'"
    
    # 发送任务请求
    msg_id = subagent_manager.mailbox.send(
        sender="team-lead",
        receiver=agent_id,
        content=f"[Task Assignment]\n\n{task_description}",
        msg_type="request"
    )
    
    # 可选：创建 TaskList 条目
    task_id = None
    if create_task_list_entry:
        from tools.builtin.task_manager import _TASKS, _short_id
        task_id = _short_id()
        _TASKS[task_id] = {
            "id": task_id,
            "title": f"[{teammate_name}] {task_description[:50]}...",
            "description": task_description,
            "status": "pending",
            "owner": agent_id,
            "team": team_name,
            "created_at": time.time(),
        }
    
    result = f"✅ Task assigned to {teammate_name}\n"
    result += f"Message ID: {msg_id}\n"
    if task_id:
        result += f"Task ID: {task_id}\n"
    result += f"\nTask Description:\n{task_description}"
    
    return result


register_tool("teammate_send", {
    "description": "Send a message to a teammate (use '*' for broadcast)",
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {"type": "string", "description": "Team name"},
            "from_name": {"type": "string", "description": "Sender name"},
            "to_name": {"type": "string", "description": "Receiver name (or '*' for broadcast)"},
            "message": {"type": "string", "description": "Message content"},
            "msg_type": {"type": "string", "enum": ["info", "request", "response"], "description": "Message type"},
        },
        "required": ["team_name", "from_name", "to_name", "message"],
    },
    "handler": teammate_send_handler,
    "permission_level": "read",
})

register_tool("teammate_receive", {
    "description": "Check mailbox for messages from teammates",
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {"type": "string", "description": "Team name"},
            "name": {"type": "string", "description": "Your name"},
            "msg_type": {"type": "string", "description": "Filter by message type (optional)"},
        },
        "required": ["team_name", "name"],
    },
    "handler": teammate_receive_handler,
    "permission_level": "read",
})

register_tool("team_assign_task", {
    "description": "Assign a task to a specific teammate",
    "parameters": {
        "type": "object",
        "properties": {
            "team_name": {"type": "string", "description": "Team name"},
            "teammate_name": {"type": "string", "description": "Teammate name"},
            "task_description": {"type": "string", "description": "Task description"},
            "create_task_list_entry": {"type": "boolean", "description": "Also create task list entry"},
        },
        "required": ["team_name", "teammate_name", "task_description"],
    },
    "handler": team_assign_task_handler,
    "permission_level": "read",
})
