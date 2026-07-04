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
AuraCode Bridge - 多会话远程控制系统

提供 REST API + WebSocket 接口，支持：
- 多会话并行管理
- 实时事件推送
- 远程权限审批
- 线程安全的消息传递
"""

from bridge.types import (
    SessionState,
    BridgeEventType,
    BridgeEvent,
    SessionActivity,
    PermissionRequest,
    PermissionResponse,
    SessionConfig,
    SessionInfo,
)
from bridge.config import BridgeServerConfig
from bridge.auth import SimpleTokenAuth
from bridge.session import BridgeSession, BridgePermissionManager
from bridge.manager import BridgeSessionManager
from bridge.server import create_app, start_bridge_server

__all__ = [
    # Types
    "SessionState",
    "BridgeEventType",
    "BridgeEvent",
    "SessionActivity",
    "PermissionRequest",
    "PermissionResponse",
    "SessionConfig",
    "SessionInfo",
    # Config
    "BridgeServerConfig",
    # Auth
    "SimpleTokenAuth",
    # Session
    "BridgeSession",
    "BridgePermissionManager",
    # Manager
    "BridgeSessionManager",
    # Server
    "create_app",
    "start_bridge_server",
]
