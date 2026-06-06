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
