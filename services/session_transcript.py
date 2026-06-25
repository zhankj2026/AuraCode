"""
JSONL 增量会话转录 (Session Transcript)

对标 Claude Code: ~/.claude/projects/{sanitized-cwd}/{sessionId}.jsonl
每条消息以 JSONL 格式增量写入，一行一条，支持崩溃恢复和高效读取。

存储结构:
~/.auracode/projects/{sanitized-cwd}/{session_id}.jsonl

作用:
1. 增量持久化 — 每条消息产生后立即写入，崩溃不丢失
2. 高效恢复 — /resume 直接读取 JSONL 重建会话
3. 会话列表 — 扫描 projects/ 目录快速获取所有会话
4. 审计追踪 — 完整记录包括 tool_use/tool_result
"""

import json
import os
import time
import logging
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 路径工具 ──

def _auracode_home() -> str:
    """获取 ~/.auracode 目录"""
    return os.path.join(os.path.expanduser("~"), ".auracode")


def _sanitize_path(path: str) -> str:
    """
    将项目路径转为安全的目录名。
    对标 Claude Code sanitizePath(): 非字母数字替换为 '-'
    """
    # 规范化路径
    normalized = os.path.normpath(os.path.abspath(path))
    # Windows: 去掉盘符 (C:\ -> )
    if len(normalized) >= 2 and normalized[1] == ':':
        normalized = normalized[2:]
    # 替换非法字符
    sanitized = re.sub(r'[^a-zA-Z0-9]', '-', normalized)
    # 合并连续 '-'
    sanitized = re.sub(r'-+', '-', sanitized).strip('-')
    # 截断过长路径（保留前200字符 + hash）
    if len(sanitized) > 200:
        h = abs(hash(path)) % (16 ** 8)
        sanitized = f"{sanitized[:200]}-{h:08x}"
    return sanitized


def get_projects_dir() -> str:
    """获取项目目录根: ~/.auracode/projects/"""
    return os.path.join(_auracode_home(), "projects")


def get_project_dir(cwd: str) -> str:
    """获取指定项目的目录: ~/.auracode/projects/{sanitized-cwd}/"""
    return os.path.join(get_projects_dir(), _sanitize_path(cwd))


def get_transcript_path(session_id: str, cwd: str) -> str:
    """获取会话转录文件路径: ~/.auracode/projects/{cwd}/{sessionId}.jsonl"""
    return os.path.join(get_project_dir(cwd), f"{session_id}.jsonl")


# ── 转录条目类型 ──

@dataclass
class TranscriptEntry:
    """单条转录条目"""
    type: str               # message / summary / tag / cost / mode / file-history-snapshot
    timestamp: str          # ISO 8601
    data: Dict[str, Any]    # 条目内容
    uuid: str = ""          # 唯一标识（消息用）
    session_id: str = ""    # 所属会话

    def to_json_line(self) -> str:
        """序列化为 JSONL 行"""
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json_line(cls, line: str) -> Optional["TranscriptEntry"]:
        """从 JSONL 行反序列化"""
        try:
            d = json.loads(line.strip())
            return cls(
                type=d.get("type", "message"),
                timestamp=d.get("timestamp", ""),
                data=d.get("data", {}),
                uuid=d.get("uuid", ""),
                session_id=d.get("session_id", ""),
            )
        except (json.JSONDecodeError, KeyError):
            return None


# ── 转录管理器 ──

class SessionTranscript:
    """
    JSONL 增量转录管理器

    用法:
        transcript = SessionTranscript(session_id="abc123", cwd="/home/user/project")
        transcript.append_message({"role": "user", "content": "hello"})
        transcript.append_message({"role": "assistant", "content": "hi"})
        transcript.append_metadata("tag", {"tag": "feature-work"})
        transcript.flush()

        # 恢复会话
        messages = transcript.read_messages()
    """

    def __init__(self, session_id: str, cwd: str):
        self.session_id = session_id
        self.cwd = cwd
        self._transcript_path = get_transcript_path(session_id, cwd)
        self._buffer: List[str] = []
        self._written_uuids: set = set()
        self._flush_interval = 1.0  # 秒
        self._last_flush = 0.0

        # 确保目录存在
        project_dir = get_project_dir(cwd)
        os.makedirs(project_dir, exist_ok=True)

        # 加载已写入的 UUID 集合（用于去重）
        self._load_existing_uuids()

        logger.debug(f"SessionTranscript initialized: {self._transcript_path}")

    def _load_existing_uuids(self):
        """扫描已有 JSONL 文件，收集已写入的 UUID"""
        if not os.path.exists(self._transcript_path):
            return
        try:
            with open(self._transcript_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = TranscriptEntry.from_json_line(line)
                    if entry and entry.uuid:
                        self._written_uuids.add(entry.uuid)
        except Exception as e:
            logger.warning(f"Failed to load existing UUIDs: {e}")

    # ── 写入接口 ──

    def append_message(
        self,
        message: Dict[str, Any],
        uuid: str = "",
        model: str = "",
        usage: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        追加一条消息到转录。

        Args:
            message: 消息字典 {role, content, ...}
            uuid: 消息唯一标识（用于去重）
            model: 使用的模型名
            usage: token 使用量
        """
        if uuid and uuid in self._written_uuids:
            return  # 去重

        entry = TranscriptEntry(
            type="message",
            timestamp=datetime.now().isoformat(),
            data={
                "message": message,
                "model": model,
                "usage": usage or {},
            },
            uuid=uuid,
            session_id=self.session_id,
        )
        self._buffer.append(entry.to_json_line())

        if uuid:
            self._written_uuids.add(uuid)

        self._auto_flush()

    def append_summary(self, summary: str, message_count: int = 0) -> None:
        """追加会话摘要（compact 时使用）"""
        entry = TranscriptEntry(
            type="summary",
            timestamp=datetime.now().isoformat(),
            data={
                "summary": summary,
                "message_count": message_count,
            },
            session_id=self.session_id,
        )
        self._buffer.append(entry.to_json_line())
        self._auto_flush()

    def append_metadata(self, meta_type: str, data: Dict[str, Any]) -> None:
        """
        追加元数据条目。

        Args:
            meta_type: 元数据类型 (tag / cost / mode / title / file-history-snapshot)
            data: 元数据内容
        """
        entry = TranscriptEntry(
            type=meta_type,
            timestamp=datetime.now().isoformat(),
            data=data,
            session_id=self.session_id,
        )
        self._buffer.append(entry.to_json_line())
        self._auto_flush()

    def append_cost_record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        """追加费用记录"""
        self.append_metadata("cost", {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
        })

    # ── 刷新/关闭 ──

    def _auto_flush(self):
        """定时自动刷新缓冲区"""
        now = time.time()
        if now - self._last_flush >= self._flush_interval:
            self.flush()

    def flush(self):
        """将缓冲区内容写入磁盘"""
        if not self._buffer:
            return

        lines = "\n".join(self._buffer) + "\n"
        self._buffer.clear()
        self._last_flush = time.time()

        try:
            with open(self._transcript_path, "a", encoding="utf-8") as f:
                f.write(lines)
        except Exception as e:
            logger.error(f"Transcript flush failed: {e}")
            # 放回缓冲区以防丢失
            self._buffer.insert(0, lines.rstrip("\n"))

    def close(self):
        """关闭转录，刷新所有缓冲"""
        self.flush()
        logger.debug(f"SessionTranscript closed: {self._transcript_path}")

    # ── 读取接口 ──

    def read_entries(self) -> List[TranscriptEntry]:
        """读取所有转录条目"""
        entries = []
        if not os.path.exists(self._transcript_path):
            return entries

        try:
            with open(self._transcript_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = TranscriptEntry.from_json_line(line)
                    if entry:
                        entries.append(entry)
        except Exception as e:
            logger.error(f"Transcript read failed: {e}")

        return entries

    def read_messages(self) -> List[Dict[str, Any]]:
        """仅读取消息条目（type=message），返回消息列表"""
        messages = []
        for entry in self.read_entries():
            if entry.type == "message":
                msg = entry.data.get("message", {})
                if msg:
                    messages.append(msg)
        return messages

    def read_metadata(self, meta_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """读取元数据条目"""
        results = []
        for entry in self.read_entries():
            if entry.type != "message" and entry.type != "summary":
                if meta_type is None or entry.type == meta_type:
                    results.append({
                        "type": entry.type,
                        "timestamp": entry.timestamp,
                        **entry.data,
                    })
        return results

    def get_file_size(self) -> int:
        """获取转录文件大小（字节）"""
        try:
            return os.path.getsize(self._transcript_path)
        except OSError:
            return 0

    def get_entry_count(self) -> int:
        """获取条目总数"""
        return len(self.read_entries())


# ── 便捷函数 ──

def list_session_transcripts(cwd: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    列出会话转录文件。

    Args:
        cwd: 指定项目目录（None 则扫描所有项目）

    Returns:
        [{"session_id", "cwd", "path", "size", "modified"}]
    """
    results = []
    projects_dir = get_projects_dir()

    if not os.path.exists(projects_dir):
        return results

    if cwd:
        scan_dirs = [get_project_dir(cwd)]
    else:
        try:
            scan_dirs = [
                os.path.join(projects_dir, d)
                for d in os.listdir(projects_dir)
                if os.path.isdir(os.path.join(projects_dir, d))
            ]
        except OSError:
            return results

    for proj_dir in scan_dirs:
        if not os.path.isdir(proj_dir):
            continue
        try:
            for fname in os.listdir(proj_dir):
                if fname.endswith(".jsonl"):
                    fpath = os.path.join(proj_dir, fname)
                    sid = fname[:-6]  # 去掉 .jsonl
                    try:
                        stat = os.stat(fpath)
                        results.append({
                            "session_id": sid,
                            "project_dir": proj_dir,
                            "path": fpath,
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        })
                    except OSError:
                        pass
        except OSError:
            continue

    # 按修改时间倒序
    results.sort(key=lambda x: x["modified"], reverse=True)
    return results


def read_session_messages(session_id: str, cwd: str) -> List[Dict[str, Any]]:
    """快捷读取指定会话的消息列表"""
    transcript = SessionTranscript(session_id=session_id, cwd=cwd)
    return transcript.read_messages()


# ── 全局单例 ──

_current_transcript: Optional[SessionTranscript] = None


def get_transcript() -> Optional[SessionTranscript]:
    """获取当前会话的转录实例"""
    return _current_transcript


def init_transcript(session_id: str, cwd: str) -> SessionTranscript:
    """初始化当前会话转录"""
    global _current_transcript
    if _current_transcript:
        _current_transcript.close()
    _current_transcript = SessionTranscript(session_id=session_id, cwd=cwd)
    return _current_transcript


def close_transcript():
    """关闭当前会话转录"""
    global _current_transcript
    if _current_transcript:
        _current_transcript.close()
        _current_transcript = None
