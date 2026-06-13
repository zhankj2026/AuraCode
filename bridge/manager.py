"""
Bridge 多会话管理器

线程安全的会话生命周期管理：创建、列出、停止、删除会话。
"""

import logging
import threading
from typing import Callable, Dict, List, Optional

from bridge.types import (
    BridgeEvent, BridgeEventType, SessionConfig, SessionInfo, SessionState,
)
from bridge.session import BridgeSession

logger = logging.getLogger(__name__)


class BridgeSessionManager:
    """
    多会话管理器。

    管理多个 BridgeSession 的生命周期，提供线程安全的 CRUD 操作。
    每个事件通过 event_callback 广播给外部（WebSocket 客户端）。
    """

    def __init__(
        self,
        max_sessions: int = 5,
        event_callback: Optional[Callable[[BridgeEvent], None]] = None,
    ):
        self.max_sessions = max_sessions
        self._event_callback = event_callback or (lambda e: None)
        self._sessions: Dict[str, BridgeSession] = {}
        self._lock = threading.Lock()

    def set_event_callback(self, callback: Callable[[BridgeEvent], None]):
        """设置/更新全局事件回调"""
        self._event_callback = callback
        # 同步到已有会话
        with self._lock:
            for session in self._sessions.values():
                session._event_callback = callback

    def create_session(self, config: SessionConfig) -> BridgeSession:
        """创建并启动新会话"""
        with self._lock:
            # 容量检查
            active_count = sum(
                1 for s in self._sessions.values()
                if s.state not in (SessionState.COMPLETED, SessionState.FAILED)
            )
            if active_count >= self.max_sessions:
                raise RuntimeError(
                    f"Max sessions reached ({self.max_sessions}). "
                    f"Stop a session before creating a new one."
                )

            if config.session_id in self._sessions:
                raise RuntimeError(f"Session {config.session_id} already exists")

        session = BridgeSession(
            config=config,
            event_callback=self._event_callback,
        )

        with self._lock:
            self._sessions[config.session_id] = session

        session.start()

        # 发射创建事件
        self._event_callback(BridgeEvent(
            type=BridgeEventType.SESSION_CREATED.value,
            session_id=config.session_id,
            data={
                "model": config.model,
                "work_dir": config.work_dir,
                "permission_mode": config.permission_mode,
            },
        ))

        logger.info(f"Session created: {config.session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[BridgeSession]:
        """获取会话"""
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> List[SessionInfo]:
        """列出所有会话"""
        with self._lock:
            return [s.get_info() for s in self._sessions.values()]

    def stop_session(self, session_id: str) -> bool:
        """停止指定会话"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            session.stop()
            logger.info(f"Session stopped: {session_id}")
            return True
        return False

    def remove_session(self, session_id: str) -> bool:
        """移除会话（先停止再删除）"""
        with self._lock:
            session = self._sessions.get(session_id)

        if session:
            if session.is_alive:
                session.stop()
            with self._lock:
                self._sessions.pop(session_id, None)
            logger.info(f"Session removed: {session_id}")
            return True
        return False

    def stop_all(self):
        """停止所有会话"""
        with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            try:
                if session.is_alive:
                    session.stop(timeout=3.0)
            except Exception as e:
                logger.warning(f"Error stopping session {session.session_id}: {e}")
        logger.info("All sessions stopped")

    def get_session_events(
        self, session_id: str, since: int = 0
    ) -> Optional[List[Dict]]:
        """获取会话事件（支持从序列号重放）"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            return session.get_events(since)
        return None

    def replay_session_events(
        self, session_id: str, from_seq: int = 0
    ) -> Optional[List[Dict]]:
        """断线重连后重放缺失事件"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            return session.replay_events(from_seq)
        return None

    def respond_permission(
        self, session_id: str, request_id: str, behavior: str, message: str = ""
    ) -> bool:
        """向会话转发权限响应"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            return session.respond_permission(request_id, behavior, message)
        return False

    def send_message(self, session_id: str, content: str) -> bool:
        """向会话发送消息"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            session.send_message(content)
            return True
        return False

    @property
    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(
                1 for s in self._sessions.values()
                if s.state not in (SessionState.COMPLETED, SessionState.FAILED)
            )

    # ── 会话迁移 ─────────────────────────────────────────────────────

    def migrate_session(
        self,
        session_id: str,
        new_model: str = None,
        new_work_dir: str = None,
    ) -> bool:
        """
        迁移会话配置（停止旧会话并创建新会话）

        Args:
            session_id: 源会话 ID
            new_model: 新模型（None 保持原配置）
            new_work_dir: 新工作目录

        Returns:
            True 如果迁移成功
        """
        with self._lock:
            old_session = self._sessions.get(session_id)

        if not old_session:
            logger.warning(f"Migration failed: session {session_id} not found")
            return False

        old_info = old_session.get_info()
        old_events_count = old_session.get_event_count()

        # 停止旧会话
        if old_session.is_alive:
            old_session.stop(timeout=3.0)

        # 构建新配置
        config = SessionConfig(
            session_id=f"{session_id}-migrated",
            work_dir=new_work_dir or old_info.work_dir,
            model=new_model or old_info.model,
            permission_mode=old_session.config.permission_mode,
            max_iterations=old_session.config.max_iterations,
            base_url=old_session.config.base_url,
            api_key=old_session.config.api_key,
        )

        try:
            new_session = self.create_session(config)
            logger.info(
                f"Session migrated: {session_id} → {config.session_id} "
                f"(old events: {old_events_count})"
            )

            # 发射迁移事件
            self._event_callback(BridgeEvent(
                type="session_migrated",
                session_id=config.session_id,
                data={
                    "from_session": session_id,
                    "old_model": old_info.model,
                    "new_model": config.model,
                    "old_events": old_events_count,
                },
            ))
            return True

        except Exception as e:
            logger.error(f"Session migration failed: {e}")
            return False
