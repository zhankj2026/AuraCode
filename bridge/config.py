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
Bridge Server 配置管理
"""

import secrets
from dataclasses import dataclass, field


@dataclass
class BridgeServerConfig:
    """Bridge 服务器配置"""
    host: str = "127.0.0.1"
    port: int = 8765
    max_sessions: int = 5
    auth_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    max_history_per_session: int = 500
    session_timeout: int = 3600  # 秒
    default_model: str = "glm-4-plus"
    default_permission_mode: str = "auto"
