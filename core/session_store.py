"""
会话持久化存储

参考 Claude Code 的 conversationRecovery.ts + history.ts 设计，
实现会话消息的 JSON 持久化、列表、搜索和恢复。

每个会话保存为独立 JSON 文件，包含元数据和完整消息历史。
存储目录: ~/.opencode/sessions/
"""

import json
import os
import uuid
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# 默认存储目录
def _default_sessions_dir() -> str:
    """获取默认会话存储目录"""
    home = os.path.expanduser("~")
    return os.path.join(home, ".opencode", "sessions")


@dataclass
class SessionMeta:
    """会话元数据"""
    session_id: str                     # UUID
    created_at: str                     # ISO 8601
    updated_at: str                     # ISO 8601
    model: str = ""                     # 使用的模型
    message_count: int = 0              # 消息数
    turn_count: int = 0                 # 对话轮次
    total_tokens: int = 0               # 总 token
    total_cost_usd: float = 0.0         # 总费用
    first_prompt: str = ""              # 第一条用户输入（摘要）
    last_prompt: str = ""               # 最后一条用户输入（摘要）
    status: str = "active"              # active / completed / aborted / error
    tags: List[str] = field(default_factory=list)  # 用户标签

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMeta":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class SessionRecord:
    """完整会话记录（元数据 + 消息历史）"""
    meta: SessionMeta
    messages: List[Dict[str, Any]] = field(default_factory=list)
    state_snapshot: Optional[Dict[str, Any]] = None  # SessionState 快照

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "messages": self.messages,
            "state_snapshot": self.state_snapshot,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionRecord":
        meta = SessionMeta.from_dict(data.get("meta", {}))
        messages = data.get("messages", [])
        state_snapshot = data.get("state_snapshot")
        return cls(meta=meta, messages=messages, state_snapshot=state_snapshot)


class SessionStore:
    """
    会话持久化存储管理器

    功能:
    - save_session: 保存当前会话到 JSON 文件
    - load_session: 按 ID 加载会话
    - list_sessions: 列出所有会话（按时间倒序）
    - search_sessions: 按关键词搜索会话
    - delete_session: 删除指定会话
    - get_latest_session: 获取最近一次会话
    """

    def __init__(self, sessions_dir: Optional[str] = None):
        """
        Args:
            sessions_dir: 会话存储目录，默认 ~/.opencode/sessions/
        """
        self.sessions_dir = sessions_dir or _default_sessions_dir()
        os.makedirs(self.sessions_dir, exist_ok=True)
        logger.debug(f"SessionStore initialized: {self.sessions_dir}")

    def _session_path(self, session_id: str) -> str:
        """获取会话文件路径"""
        # 安全: 防止路径遍历
        safe_id = session_id.replace("/", "").replace("\\", "").replace("..", "")
        return os.path.join(self.sessions_dir, f"{safe_id}.json")

    def save_session(
        self,
        messages: List[Dict[str, Any]],
        model: str = "",
        turn_count: int = 0,
        total_tokens: int = 0,
        total_cost_usd: float = 0.0,
        status: str = "active",
        session_id: Optional[str] = None,
        state_snapshot: Optional[Dict[str, Any]] = None,
        existing_meta: Optional[SessionMeta] = None,
    ) -> SessionMeta:
        """
        保存会话到 JSON 文件

        Args:
            messages: 消息历史列表
            model: 使用的模型名
            turn_count: 对话轮次
            total_tokens: 总 token 数
            total_cost_usd: 总费用
            status: 会话状态
            session_id: 会话 ID（None 则自动生成）
            state_snapshot: SessionState 快照
            existing_meta: 已有的元数据（用于更新而非创建新会话）

        Returns:
            SessionMeta 元数据
        """
        now = datetime.now().isoformat()

        if existing_meta:
            meta = existing_meta
            meta.updated_at = now
            meta.message_count = len(messages)
            meta.turn_count = turn_count
            meta.total_tokens = total_tokens
            meta.total_cost_usd = total_cost_usd
            meta.status = status
        else:
            sid = session_id or str(uuid.uuid4())[:12]
            # 提取首条用户消息
            first_prompt = ""
            last_prompt = ""
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str) and content and not content.startswith("["):
                        if not first_prompt:
                            first_prompt = content[:200]
                        last_prompt = content[:200]

            meta = SessionMeta(
                session_id=sid,
                created_at=now,
                updated_at=now,
                model=model,
                message_count=len(messages),
                turn_count=turn_count,
                total_tokens=total_tokens,
                total_cost_usd=total_cost_usd,
                first_prompt=first_prompt,
                last_prompt=last_prompt,
                status=status,
            )

        record = SessionRecord(
            meta=meta,
            messages=messages,
            state_snapshot=state_snapshot,
        )

        path = self._session_path(meta.session_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"Session saved: {meta.session_id} ({meta.message_count} msgs, {path})")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

        return meta

    def load_session(self, session_id: str) -> Optional[SessionRecord]:
        """
        加载指定会话

        Args:
            session_id: 会话 ID

        Returns:
            SessionRecord 或 None（不存在时）
        """
        path = self._session_path(session_id)
        if not os.path.exists(path):
            # 尝试前缀匹配
            matches = self._find_by_prefix(session_id)
            if len(matches) == 1:
                path = self._session_path(matches[0].session_id)
            elif len(matches) > 1:
                logger.warning(f"Ambiguous session ID prefix: {session_id} ({len(matches)} matches)")
                return None
            else:
                logger.warning(f"Session not found: {session_id}")
                return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            record = SessionRecord.from_dict(data)
            logger.info(f"Session loaded: {record.meta.session_id}")
            return record
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def list_sessions(self, limit: int = 20) -> List[SessionMeta]:
        """
        列出所有会话（按更新时间倒序）

        Args:
            limit: 最大返回数

        Returns:
            SessionMeta 列表
        """
        sessions = []
        try:
            for filename in os.listdir(self.sessions_dir):
                if not filename.endswith(".json"):
                    continue
                path = os.path.join(self.sessions_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    meta = SessionMeta.from_dict(data.get("meta", {}))
                    sessions.append(meta)
                except Exception as e:
                    logger.debug(f"Skipping invalid session file {filename}: {e}")
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")

        # 按更新时间倒序
        sessions.sort(key=lambda m: m.updated_at, reverse=True)
        return sessions[:limit]

    def search_sessions(self, keyword: str, limit: int = 20) -> List[SessionMeta]:
        """
        按关键词搜索会话（搜索 first_prompt、last_prompt、tags）

        Args:
            keyword: 搜索关键词
            limit: 最大返回数

        Returns:
            匹配的 SessionMeta 列表
        """
        keyword_lower = keyword.lower()
        results = []

        all_sessions = self.list_sessions(limit=1000)
        for meta in all_sessions:
            searchable = " ".join([
                meta.first_prompt,
                meta.last_prompt,
                meta.model,
                " ".join(meta.tags),
                meta.status,
            ]).lower()
            if keyword_lower in searchable:
                results.append(meta)
                if len(results) >= limit:
                    break

        return results

    def delete_session(self, session_id: str) -> bool:
        """
        删除指定会话

        Args:
            session_id: 会话 ID

        Returns:
            True 如果成功删除
        """
        path = self._session_path(session_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Session deleted: {session_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete session {session_id}: {e}")
                return False

        # 尝试前缀匹配
        matches = self._find_by_prefix(session_id)
        if len(matches) == 1:
            path = self._session_path(matches[0].session_id)
            try:
                os.remove(path)
                logger.info(f"Session deleted (prefix match): {matches[0].session_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete session: {e}")
                return False

        return False

    def get_latest_session(self) -> Optional[SessionRecord]:
        """获取最近一次会话"""
        sessions = self.list_sessions(limit=1)
        if not sessions:
            return None
        return self.load_session(sessions[0].session_id)

    def _find_by_prefix(self, prefix: str) -> List[SessionMeta]:
        """按 ID 前缀匹配会话"""
        all_sessions = self.list_sessions(limit=1000)
        return [s for s in all_sessions if s.session_id.startswith(prefix)]

    def get_session_count(self) -> int:
        """获取总会话数"""
        try:
            return len([f for f in os.listdir(self.sessions_dir) if f.endswith(".json")])
        except Exception:
            return 0

    def get_storage_size_bytes(self) -> int:
        """获取存储总大小（字节）"""
        total = 0
        try:
            for filename in os.listdir(self.sessions_dir):
                if filename.endswith(".json"):
                    path = os.path.join(self.sessions_dir, filename)
                    total += os.path.getsize(path)
        except Exception:
            pass
        return total


# ========== AgentLoop 集成辅助函数 ==========

def auto_save_session(
    store: SessionStore,
    messages: List[Dict[str, Any]],
    model: str = "",
    turn_count: int = 0,
    total_tokens: int = 0,
    total_cost_usd: float = 0.0,
    status: str = "completed",
    session_id: Optional[str] = None,
    existing_meta: Optional[SessionMeta] = None,
) -> Optional[SessionMeta]:
    """
    便捷函数：自动保存当前会话状态。

    供 AgentLoop.run() 末尾或 ChatMode 退出时调用。

    Returns:
        SessionMeta 或 None（保存失败时）
    """
    try:
        meta = store.save_session(
            messages=messages,
            model=model,
            turn_count=turn_count,
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            status=status,
            session_id=session_id,
            existing_meta=existing_meta,
        )
        return meta
    except Exception as e:
        logger.error(f"Auto-save session failed: {e}")
        return None


def restore_session_to_loop(
    loop,
    record: SessionRecord,
) -> bool:
    """
    将保存的会话恢复到 AgentLoop 中。

    恢复消息历史和关键状态。

    Args:
        loop: AgentLoop 实例
        record: 会话记录

    Returns:
        True 如果恢复成功
    """
    try:
        # 恢复消息历史（跳过 system prompt，因为 run() 会重新构建）
        msgs = record.messages
        if msgs and msgs[0].get("role") == "system":
            # 保留非 system 消息
            user_msgs = [m for m in msgs if m.get("role") != "system"]
            loop.state.messages = user_msgs
        else:
            loop.state.messages = list(msgs)

        # 恢复 token 统计
        if record.state_snapshot:
            snap = record.state_snapshot
            loop.state.total_usage.prompt_tokens = snap.get("prompt_tokens", 0)
            loop.state.total_usage.completion_tokens = snap.get("completion_tokens", 0)
            loop.state.total_usage.total_tokens = snap.get("total_tokens", 0)
            loop.state.total_cost_usd = snap.get("total_cost_usd", 0.0)
            loop.state.turn_count = snap.get("turn_count", 0)

        logger.info(
            f"Session restored: {record.meta.session_id} "
            f"({len(loop.state.messages)} messages, "
            f"{loop.state.total_usage.total_tokens} tokens)"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to restore session: {e}")
        return False
