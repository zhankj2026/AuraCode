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
Bridge 多会话管理器

线程安全的会话生命周期管理：创建、列出、停止、删除会话。
"""

import logging
import threading
import time
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
        """列出所有会话（仅活跃会话；归档在专门的归档管理页展示）。

        历史会话退出时持久化到 ~/.auracode/sessions/*.json。曾把归档合并
        进本列表（混排），但用户交互反馈：归档与活跃会话混在一起容易误点、
        归档不可直接交互也易困惑——现归档独立入口 list_archives()。
        """
        with self._lock:
            return [s.get_info() for s in self._sessions.values()]

    def list_archives(self, limit: int = 200) -> List[SessionInfo]:
        """列出磁盘归档会话（专门的归档管理页数据源）。

        与 list_sessions 分离：归档不占活跃会话位，按 updated_at 倒序。
        """
        try:
            from core.session_store import SessionStore
            from datetime import datetime
            store = SessionStore()
            out = []
            for meta in store.list_sessions(limit=limit):
                try:
                    updated = datetime.fromisoformat(meta.updated_at).timestamp()
                    created = datetime.fromisoformat(meta.created_at).timestamp()
                except (ValueError, TypeError):
                    updated = created = 0.0
                out.append(SessionInfo(
                    session_id=meta.session_id,
                    state=SessionState.COMPLETED,
                    work_dir=meta.work_dir or ".",
                    model=meta.model or "",
                    created_at=created,
                    event_count=meta.message_count,
                    last_activity=updated,
                    title=meta.last_prompt or meta.first_prompt or "",
                    round_count=meta.turn_count,
                    archived=True,
                ))
            return out
        except Exception as e:
            logger.warning(f"list_archives failed: {e}")
            return []

    def get_archive_messages(self, session_id: str, limit: int = 500) -> List[Dict]:
        """读取归档会话的消息历史（归档页「查看内容」用，只读）。"""
        from core.session_store import SessionStore
        store = SessionStore()
        record = store.load_session(session_id)
        if record is None:
            raise KeyError(f"archived session not found: {session_id}")
        msgs = []
        for m in (record.messages or [])[-limit:]:
            role = m.get("role", "")
            content = m.get("content")
            if role not in ("user", "assistant"):
                continue
            if isinstance(content, list):
                # 多段内容（图片等）拼接文本段
                content = " ".join(
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                )
            if not content:
                continue
            msgs.append({"role": role, "content": str(content)})
        return msgs

    def archive_session(self, session_id: str) -> bool:
        """手动归档：停止会话（退出钩子会把消息写盘归档）并从活跃列表移除。"""
        with self._lock:
            session = self._sessions.get(session_id)
        if not session:
            return False
        # stop() 会触发 _save_session_on_exit → ~/.auracode/sessions/*.json
        session.stop()
        with self._lock:
            self._sessions.pop(session_id, None)
        logger.info(f"Session archived (manual): {session_id}")
        return True

    def resume_session(self, session_id: str, permission_mode: str = "auto") -> BridgeSession:
        """从磁盘归档恢复会话为活跃会话。

        恢复 = 以归档的 work_dir/model 新建会话 + 回放归档消息历史。
        - 复用 create_session 的容量/生命周期管理
        - 归档文件保留（resume 不等于移动；新会话退出时会再写一份新归档）
        """
        from core.session_store import SessionStore
        store = SessionStore()
        record = store.load_session(session_id)
        if record is None:
            raise KeyError(f"archived session not found: {session_id}")
        if not record.messages:
            raise ValueError(f"archived session has no messages: {session_id}")

        meta = record.meta
        config = SessionConfig(
            work_dir=meta.work_dir or ".",
            model=meta.model or "glm-4-flash",
            permission_mode=permission_mode,
            restore_history=False,  # 历史由下面显式回放，不走 work_dir 自动匹配
        )
        session = self.create_session(config)

        # 显式回放归档消息（绕过 find_latest_by_workdir 的自动恢复，
        # 精确恢复这份档案且不叠加别的归档）。restore_record 内部等待
        # loop 就绪后回放；这里再等回放事件落库（最多 10s），保证 HTTP
        # 返回时前端拉事件已能拿到完整历史。
        restored = session.restore_record(record)
        if not restored:
            # 消息全被清洗（如全是残缺 tool_calls）：撤销创建，报明确错误
            self.remove_session(session.session_id)
            raise ValueError(f"archived session has no restorable messages: {session_id}")
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if session.replayed_message_count() >= restored:
                break
            time.sleep(0.1)
        return session

    def delete_session_full(self, session_id: str) -> bool:
        """删除会话：内存活跃会话（停+移除）与磁盘归档文件一并清理。"""
        removed = self.remove_session(session_id)
        archived_deleted = False
        try:
            from core.session_store import SessionStore
            store = SessionStore()
            archived_deleted = store.delete_session(session_id)
        except Exception as e:
            logger.warning(f"delete archive failed for {session_id}: {e}")
        return removed or archived_deleted

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

    def send_message(self, session_id: str, content: str, attachments: list = None) -> bool:
        """向会话发送消息（支持附件）"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            try:
                session.send_message(content, attachments=attachments)
                return True
            except RuntimeError:
                # 会话已停止（_stop_flag 已设置）
                return False
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

    # ── 会话中断 ─────────────────────────────────────────────

    def interrupt_session(self, session_id: str) -> bool:
        """
        中断会话当前正在执行的 turn（不终止会话）。

        参考标准实现 interrupt control_request。
        """
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            return session.interrupt()
        return False

    # ── 模型热切换 ─────────────────────────────────────────────

    def switch_model(
        self,
        session_id: str,
        new_model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> bool:
        """
        热切换会话模型（仅在空闲时生效）。

        参考标准实现 set_model control_request。
        base_url / api_key 为可选：自定义模型可携带独立接口地址与密钥。
        """
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            return session.switch_model(new_model, base_url=base_url, api_key=api_key)
        return False

    def set_permission_mode(self, session_id: str, mode: str) -> bool:
        """
        运行时切换会话的权限模式（normal/auto/plan/bypass）。

        让顶部模式选择器对「已运行」的会话即时生效，而非仅作用于新建会话。
        """
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            session.set_permission_mode(mode)
            return True
        return False

    def clear_context(self, session_id: str) -> bool:
        """清空指定会话的对话上下文（消息历史）。"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session:
            return session.clear_context()
        return False

    # ── 过期会话清理 ─────────────────────────────────────────────

    def cleanup_stale_sessions(self, max_idle_seconds: int = 7200) -> int:
        """
        清理过期会话（由 lifespan 定时任务调用）。

        - 已完成的会话直接移除
        - 空闲超过 max_idle_seconds 的会话自动停止

        Returns:
            清理的会话数量
        """
        cleaned = 0
        now = time.time()
        stale: List[tuple] = []  # (session_id, reason)

        with self._lock:
            for sid, session in self._sessions.items():
                # 已完成/失败的会话
                if session.state in (SessionState.COMPLETED, SessionState.FAILED):
                    stale.append((sid, session.state.value))
                    continue
                # 长时间空闲的会话
                if session.state == SessionState.IDLE:
                    idle = now - session.last_activity
                    if idle > max_idle_seconds:
                        stale.append((sid, "idle_timeout"))

        for sid, reason in stale:
            self.remove_session(sid)
            cleaned += 1
            logger.info(f"Stale session cleaned up: {sid} ({reason})")
            # 广播过期事件：前端据此移除侧栏幽灵条目。此前清理是静默的，
            # 前端列表不刷新，会话消失后 UI 仍显示 idle 状态的旧会话。
            try:
                self._event_callback(BridgeEvent(
                    type=BridgeEventType.SESSION_EXPIRED,
                    session_id=sid,
                    data={"reason": reason},
                ))
            except Exception as e:
                logger.warning(f"Emit session_expired failed for {sid}: {e}")

        return cleaned

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
