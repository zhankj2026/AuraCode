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
Bridge Remote Control 类型定义

定义多会话远程控制系统所需的所有数据类型。
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SessionState(str, Enum):
    """会话状态"""
    IDLE = "idle"
    RUNNING = "running"
    REQUIRES_ACTION = "requires_action"
    COMPLETED = "completed"
    FAILED = "failed"


class BridgeEventType(str, Enum):
    """事件类型"""
    # 生命周期
    SESSION_CREATED = "session_created"
    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    SESSION_ERROR = "session_error"
    SESSION_ARCHIVED = "session_archived"       # 会话持久化完成
    SERVER_SHUTTING_DOWN = "server_shutting_down"  # 服务器即将关闭
    # 对话
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RESULT = "result"
    INTERRUPTED = "interrupted"                 # 当前 turn 被中断（会话仍存活）
    # 权限
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_RESPONSE = "permission_response"
    # 输出
    OUTPUT = "output"
    # 配置变更
    MODEL_CHANGED = "model_changed"             # 模型热切换
    # AgentLoop 实时事件（由 event_callback 推送）
    TURN_START = "turn_start"
    TURN_COMPLETE = "turn_complete"
    TOOL_EXECUTE = "tool_execute"
    TOOL_COMPLETE = "tool_complete"
    CONTEXT_COMPACTED = "context_compacted"
    FALLBACK_ACTIVATED = "fallback_activated"
    PROMPT_TOO_LONG_RECOVERY = "prompt_too_long_recovery"
    ABORTED = "aborted"
    LLM_CALL = "llm_call"                       # LLM API 调用详情（网络报文）
    TEXT_CHUNK = "text_chunk"                   # Token 级流式文本块（实时打字机效果）


@dataclass
class BridgeEvent:
    """Bridge 事件"""
    type: str
    session_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "session_id": self.session_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class PermissionRequest:
    """权限审批请求"""
    request_id: str
    tool_name: str
    tool_input: Dict[str, Any]
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "description": self.description,
        }


@dataclass
class PermissionResponse:
    """权限审批响应"""
    request_id: str
    behavior: str  # "allow" | "deny"
    message: str = ""


@dataclass
class SessionConfig:
    """会话配置"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    work_dir: str = "."
    model: str = "glm-4-plus"
    permission_mode: str = "auto"
    max_iterations: int = 20
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    session_timeout: int = 3600  # 秒（0=不超时）


@dataclass
class SessionActivity:
    """会话活动记录"""
    type: str           # "tool_start" | "text" | "result" | "error"
    summary: str        # e.g. "Editing src/foo.py", "Running grep"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "summary": self.summary, "timestamp": self.timestamp}


@dataclass
class SessionInfo:
    """会话摘要信息"""
    session_id: str
    state: SessionState = SessionState.IDLE
    work_dir: str = "."
    model: str = ""
    created_at: float = field(default_factory=time.time)
    event_count: int = 0
    last_activity: float = 0.0
    title: str = ""
    current_activity: Optional[Dict[str, Any]] = None  # 当前正在执行的工具摘要
    round_count: int = 0  # 已处理的对话轮次数

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "work_dir": self.work_dir,
            "model": self.model,
            "created_at": self.created_at,
            "event_count": self.event_count,
            "last_activity": self.last_activity,
            "title": self.title,
            "current_activity": self.current_activity,
            "round_count": self.round_count,
        }
