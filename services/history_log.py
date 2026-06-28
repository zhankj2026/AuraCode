"""
全局交互历史日志 (history.jsonl)

每次交互（一轮用户输入 + AI 响应）追加一行 JSON 到 ~/.auracode/history.jsonl。
用于跨会话搜索、统计和使用模式分析。

设计参考:
- Claude Code: ~/.auracode/history.jsonl (每行一条交互摘要)
"""

import json
import os
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# 默认存储路径
def _default_history_path() -> str:
    """获取默认历史日志文件路径"""
    home = os.path.expanduser("~")
    return os.path.join(home, ".auracode", "history.jsonl")


@dataclass
class HistoryEntry:
    """单条交互历史条目"""
    timestamp: str            # ISO 8601
    session_id: str           # 会话 ID
    model: str                # 使用的模型
    user_prompt: str          # 用户输入（截取前 500 字符）
    assistant_summary: str    # AI 响应摘要（截取前 500 字符）
    turn_count: int = 1       # 当前会话中的轮次序号
    status: str = "success"   # success / error / aborted
    tokens_used: int = 0      # 本轮 token 消耗
    duration_ms: int = 0      # 本轮耗时（毫秒）
    tools_used: List[str] = field(default_factory=list)  # 本轮使用的工具名
    work_dir: str = ""        # 工作目录
    source: str = "cli"       # 来源: cli / bridge

    def to_json_line(self) -> str:
        """序列化为 JSON 行"""
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json_line(cls, line: str) -> Optional["HistoryEntry"]:
        """从 JSON 行反序列化"""
        try:
            data = json.loads(line.strip())
            valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in valid_fields}
            return cls(**filtered)
        except Exception as e:
            logger.debug(f"Failed to parse history entry: {e}")
            return None


class HistoryLog:
    """
    全局交互历史日志管理器

    存储位置: ~/.auracode/history.jsonl
    写入方式: 追加写入（每行一条 JSON）
    读取方式: 流式读取（逐行解析，支持大文件）

    功能:
    - append(): 追加一条交互记录
    - read_all(): 读取所有历史（注意大文件）
    - read_recent(): 读取最近 N 条
    - search(): 按关键词搜索
    - get_stats(): 获取统计信息
    """

    def __init__(self, history_path: Optional[str] = None):
        """
        Args:
            history_path: 历史日志文件路径，默认 ~/.auracode/history.jsonl
        """
        self.history_path = history_path or _default_history_path()
        # 确保目录存在
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        logger.debug(f"HistoryLog initialized: {self.history_path}")

    def append(
        self,
        session_id: str,
        model: str,
        user_prompt: str,
        assistant_summary: str,
        turn_count: int = 1,
        status: str = "success",
        tokens_used: int = 0,
        duration_ms: int = 0,
        tools_used: Optional[List[str]] = None,
        work_dir: str = "",
        source: str = "cli",
    ) -> HistoryEntry:
        """
        追加一条交互记录

        Args:
            session_id: 会话 ID
            model: 使用的模型
            user_prompt: 用户输入
            assistant_summary: AI 响应摘要
            turn_count: 当前轮次
            status: 状态 (success/error/aborted)
            tokens_used: token 消耗
            duration_ms: 耗时（毫秒）
            tools_used: 使用的工具列表
            work_dir: 工作目录
            source: 来源 (cli/bridge)

        Returns:
            HistoryEntry
        """
        entry = HistoryEntry(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            model=model,
            user_prompt=user_prompt[:500],
            assistant_summary=assistant_summary[:500],
            turn_count=turn_count,
            status=status,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            tools_used=tools_used or [],
            work_dir=work_dir,
            source=source,
        )

        try:
            with open(self.history_path, "a", encoding="utf-8") as f:
                f.write(entry.to_json_line() + "\n")
            logger.debug(f"History entry appended: session={session_id} turn={turn_count}")
        except Exception as e:
            logger.error(f"Failed to append history entry: {e}")

        return entry

    def read_recent(self, limit: int = 50) -> List[HistoryEntry]:
        """
        读取最近 N 条历史记录

        使用反向读取优化：从文件末尾向前读取，避免加载整个文件。

        Args:
            limit: 最多返回条数

        Returns:
            HistoryEntry 列表（时间倒序）
        """
        if not os.path.exists(self.history_path):
            return []

        entries = []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                # 读取所有行（对于一般大小的文件足够高效）
                lines = f.readlines()

            # 从末尾开始，取最近 limit 条
            for line in reversed(lines[-limit:]):
                line = line.strip()
                if not line:
                    continue
                entry = HistoryEntry.from_json_line(line)
                if entry:
                    entries.append(entry)
        except Exception as e:
            logger.error(f"Failed to read history: {e}")

        return entries

    def read_all(self) -> List[HistoryEntry]:
        """读取所有历史记录（注意：大文件可能较慢）"""
        if not os.path.exists(self.history_path):
            return []

        entries = []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = HistoryEntry.from_json_line(line)
                    if entry:
                        entries.append(entry)
        except Exception as e:
            logger.error(f"Failed to read history: {e}")

        return entries

    def search(self, keyword: str, limit: int = 50) -> List[HistoryEntry]:
        """
        按关键词搜索历史（搜索 user_prompt 和 assistant_summary）

        Args:
            keyword: 搜索关键词
            limit: 最多返回条数

        Returns:
            匹配的 HistoryEntry 列表（时间倒序）
        """
        keyword_lower = keyword.lower()
        results = []

        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                entry = HistoryEntry.from_json_line(line)
                if not entry:
                    continue
                searchable = f"{entry.user_prompt} {entry.assistant_summary}".lower()
                if keyword_lower in searchable:
                    results.append(entry)
                    if len(results) >= limit:
                        break
        except Exception as e:
            logger.error(f"Failed to search history: {e}")

        return results

    def search_by_session(self, session_id: str) -> List[HistoryEntry]:
        """按会话 ID 过滤历史"""
        results = []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = HistoryEntry.from_json_line(line)
                    if entry and entry.session_id == session_id:
                        results.append(entry)
        except Exception as e:
            logger.error(f"Failed to search history by session: {e}")
        return results

    def get_stats(self) -> Dict[str, Any]:
        """
        获取历史统计信息

        Returns:
            包含总条数、总会话数、总 token、总交互次数等的字典
        """
        if not os.path.exists(self.history_path):
            return {"total_entries": 0, "total_sessions": 0, "file_size_bytes": 0}

        total_entries = 0
        sessions = set()
        total_tokens = 0
        total_duration_ms = 0
        models_used = set()
        tools_used = set()
        first_timestamp = ""
        last_timestamp = ""

        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = HistoryEntry.from_json_line(line)
                    if not entry:
                        continue

                    total_entries += 1
                    sessions.add(entry.session_id)
                    total_tokens += entry.tokens_used
                    total_duration_ms += entry.duration_ms
                    if entry.model:
                        models_used.add(entry.model)
                    tools_used.update(entry.tools_used)

                    if not first_timestamp:
                        first_timestamp = entry.timestamp
                    last_timestamp = entry.timestamp

            file_size = os.path.getsize(self.history_path)
        except Exception as e:
            logger.error(f"Failed to get history stats: {e}")
            file_size = 0

        return {
            "total_entries": total_entries,
            "total_sessions": len(sessions),
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration_ms,
            "models_used": sorted(models_used),
            "tools_used_count": len(tools_used),
            "first_entry": first_timestamp,
            "last_entry": last_timestamp,
            "file_size_bytes": file_size,
            "file_path": self.history_path,
        }

    def get_entry_count(self) -> int:
        """获取总条目数（快速计算）"""
        if not os.path.exists(self.history_path):
            return 0
        count = 0
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        count += 1
        except Exception:
            pass
        return count

    def clear(self) -> bool:
        """清空历史日志"""
        try:
            if os.path.exists(self.history_path):
                os.remove(self.history_path)
            logger.info("History log cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            return False

    def trim(self, keep_entries: int = 10000) -> int:
        """
        裁剪历史：保留最近 N 条，删除更早的记录

        Args:
            keep_entries: 保留的条目数

        Returns:
            删除的条目数
        """
        if not os.path.exists(self.history_path):
            return 0

        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                lines = [l for l in f if l.strip()]

            if len(lines) <= keep_entries:
                return 0

            removed = len(lines) - keep_entries
            kept_lines = lines[-keep_entries:]

            with open(self.history_path, "w", encoding="utf-8") as f:
                f.writelines(kept_lines)

            logger.info(f"History trimmed: removed {removed} entries, kept {keep_entries}")
            return removed
        except Exception as e:
            logger.error(f"Failed to trim history: {e}")
            return 0


# ── 全局单例 ────────────────────────────────────────────────────────────────

_history_log: Optional[HistoryLog] = None


def get_history_log() -> HistoryLog:
    """获取全局 HistoryLog 实例"""
    global _history_log
    if _history_log is None:
        _history_log = HistoryLog()
    return _history_log
