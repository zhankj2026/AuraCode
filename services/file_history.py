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
文件修改历史 (file-history)

在每次文件编辑前自动创建备份，支持回退到任意时间点。
备份存储在 ~/.auracode/file-history/ 目录下。

设计参考:
- Claude Code: ~/.auracode/file-history/ (按会话组织的文件快照)
- 每次 track_edit 时备份原始文件
- 支持 apply_snapshot 恢复
"""

import hashlib
import os
import shutil
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 路径工具 ────────────────────────────────────────────────────────────────

def _default_history_dir() -> str:
    """获取默认文件历史目录"""
    home = os.path.expanduser("~")
    return os.path.join(home, ".auracode", "file-history")


# ── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class FileBackup:
    """单个文件的备份记录"""
    original_path: str        # 原始文件路径
    backup_path: str          # 备份文件路径
    version: int              # 版本号（同一文件在同一会话中的第 N 次备份）
    session_id: str           # 所属会话 ID
    message_index: int        # 对应的消息索引（用于 rewind 定位）
    file_hash: str            # 文件内容 SHA256
    file_size: int            # 文件大小（字节）
    backup_time: str          # ISO 8601
    existed: bool = True      # False 表示文件原本不存在（新建操作）

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileBackup":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class Snapshot:
    """会话快照：某一轮对话后所有文件的备份状态"""
    snapshot_id: str          # 快照 ID (turn_index)
    session_id: str           # 会话 ID
    message_index: int        # 对应的消息索引
    turn: int                 # 对话轮次
    timestamp: str            # ISO 8601
    file_backups: Dict[str, str] = field(default_factory=dict)
    # key: original_path, value: backup_path (或 "" 表示文件不存在)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


# ── FileHistory ─────────────────────────────────────────────────────────────

class FileHistory:
    """
    文件修改历史管理器

    功能:
    - track_edit(): 在文件编辑前备份
    - get_backups(): 获取指定文件的所有备份
    - restore(): 恢复到指定备份
    - get_snapshots(): 获取会话的所有快照
    - list_tracked_files(): 列出被追踪的文件
    """

    def __init__(self, history_dir: Optional[str] = None):
        """
        Args:
            history_dir: 文件历史目录，默认 ~/.auracode/file-history/
        """
        self.history_dir = history_dir or _default_history_dir()
        os.makedirs(self.history_dir, exist_ok=True)

        # 内存索引: {original_path: [FileBackup, ...]}
        self._backups: Dict[str, List[FileBackup]] = {}

        # 快照列表: [Snapshot, ...]
        self._snapshots: List[Snapshot] = []

        # 追踪的文件集合
        self._tracked_files: set = set()

        # 当前会话 ID（由 agent_loop 设置）
        self._session_id: str = ""

        # 索引文件路径
        self._index_path = os.path.join(self.history_dir, "index.json")

        # 加载已有索引
        self._load_index()

        logger.debug(f"FileHistory initialized: {self.history_dir}")

    def set_session_id(self, session_id: str):
        """设置当前会话 ID"""
        self._session_id = session_id

    def track_edit(self, file_path: str, message_index: int = 0, turn: int = 0) -> Optional[FileBackup]:
        """
        在文件编辑前创建备份

        如果文件在此会话中已被备份过，跳过重复备份（仅首次备份）。
        如果文件不存在（将被创建），记录一个 existed=False 的备份。

        Args:
            file_path: 要备份的文件路径
            message_index: 当前消息索引
            turn: 当前对话轮次

        Returns:
            FileBackup 或 None（文件已在本次会话中备份过）
        """
        abs_path = os.path.abspath(file_path)

        # 检查是否在此会话中已备份过此文件
        if abs_path in self._tracked_files:
            # 检查最新快照是否已包含此文件
            if self._snapshots:
                latest = self._snapshots[-1]
                if abs_path in latest.file_backups:
                    # 已在此快照中跟踪，检查文件是否变化
                    existing_backup = latest.file_backups[abs_path]
                    if existing_backup:  # 有备份文件
                        # 检查文件是否已变化
                        current_hash = self._compute_hash(abs_path)
                        for fb in self._backups.get(abs_path, []):
                            if fb.backup_path == existing_backup:
                                if fb.file_hash == current_hash:
                                    return None  # 文件未变化，无需备份
                                break
                    # 文件已变化，创建新备份

        # 计算版本号
        existing_backups = self._backups.get(abs_path, [])
        version = len(existing_backups) + 1

        # 创建备份
        backup = self._create_backup(abs_path, version, message_index)
        if backup is None:
            return None

        # 更新索引
        if abs_path not in self._backups:
            self._backups[abs_path] = []
        self._backups[abs_path].append(backup)
        self._tracked_files.add(abs_path)

        # 创建/更新快照
        self._update_snapshot(
            abs_path, backup.backup_path if backup.existed else "",
            message_index, turn,
        )

        logger.info(
            f"File tracked: {os.path.basename(file_path)} "
            f"(v{version}, {'new file' if not backup.existed else f'{backup.file_size}B'})"
        )
        return backup

    def _create_backup(
        self, abs_path: str, version: int, message_index: int
    ) -> Optional[FileBackup]:
        """创建文件备份"""
        try:
            # 计算哈希
            file_hash = self._compute_hash(abs_path)
            exists = os.path.exists(abs_path)

            if not exists:
                # 文件不存在（将被创建），记录空备份
                return FileBackup(
                    original_path=abs_path,
                    backup_path="",
                    version=version,
                    session_id=self._session_id,
                    message_index=message_index,
                    file_hash="",
                    file_size=0,
                    backup_time=datetime.now().isoformat(),
                    existed=False,
                )

            # 创建备份目录
            file_hash_short = file_hash[:12] if file_hash else "unknown"
            backup_subdir = os.path.join(
                self.history_dir, self._session_id or "default"
            )
            os.makedirs(backup_subdir, exist_ok=True)

            # 生成备份文件名
            basename = os.path.basename(abs_path)
            backup_name = f"{basename}.v{version}.{file_hash_short}"
            backup_path = os.path.join(backup_subdir, backup_name)

            # 复制文件
            shutil.copy2(abs_path, backup_path)
            file_size = os.path.getsize(abs_path)

            return FileBackup(
                original_path=abs_path,
                backup_path=backup_path,
                version=version,
                session_id=self._session_id,
                message_index=message_index,
                file_hash=file_hash,
                file_size=file_size,
                backup_time=datetime.now().isoformat(),
                existed=True,
            )
        except Exception as e:
            logger.error(f"Failed to create backup for {abs_path}: {e}")
            return None

    def restore(self, file_path: str, version: Optional[int] = None) -> bool:
        """
        恢复文件到指定版本

        Args:
            file_path: 文件路径
            version: 版本号（None = 恢复到第一个版本/原始状态）

        Returns:
            True 如果恢复成功
        """
        abs_path = os.path.abspath(file_path)
        backups = self._backups.get(abs_path, [])
        if not backups:
            logger.warning(f"No backups found for {file_path}")
            return False

        # 选择目标版本
        if version is None:
            target = backups[0]  # 最早版本（原始状态）
        else:
            target = None
            for b in backups:
                if b.version == version:
                    target = b
                    break
            if not target:
                logger.warning(f"Version {version} not found for {file_path}")
                return False

        # 执行恢复
        try:
            if not target.existed:
                # 原始文件不存在 → 删除当前文件
                if os.path.exists(abs_path):
                    os.remove(abs_path)
                    logger.info(f"File deleted (restored to non-existent state): {file_path}")
                return True

            if not target.backup_path or not os.path.exists(target.backup_path):
                logger.error(f"Backup file missing: {target.backup_path}")
                return False

            # 恢复备份
            shutil.copy2(target.backup_path, abs_path)
            logger.info(
                f"File restored: {file_path} → v{target.version} "
                f"({target.file_size}B, hash={target.file_hash[:12]})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to restore {file_path}: {e}")
            return False

    def restore_snapshot(self, snapshot_id: str) -> List[str]:
        """
        恢复到指定快照（所有文件）

        Args:
            snapshot_id: 快照 ID

        Returns:
            被恢复的文件路径列表
        """
        target_snapshot = None
        for snap in self._snapshots:
            if snap.snapshot_id == snapshot_id:
                target_snapshot = snap
                break

        if not target_snapshot:
            logger.warning(f"Snapshot not found: {snapshot_id}")
            return []

        restored_files = []
        for original_path, backup_path in target_snapshot.file_backups.items():
            try:
                if not backup_path:
                    # 文件不存在 → 删除
                    if os.path.exists(original_path):
                        os.remove(original_path)
                        restored_files.append(original_path)
                elif os.path.exists(backup_path):
                    shutil.copy2(backup_path, original_path)
                    restored_files.append(original_path)
            except Exception as e:
                logger.error(f"Failed to restore {original_path} from snapshot: {e}")

        logger.info(f"Snapshot restored: {snapshot_id} ({len(restored_files)} files)")
        return restored_files

    def get_backups(self, file_path: str) -> List[FileBackup]:
        """获取指定文件的所有备份"""
        abs_path = os.path.abspath(file_path)
        return list(self._backups.get(abs_path, []))

    def get_snapshots(self) -> List[Snapshot]:
        """获取所有快照"""
        return list(self._snapshots)

    def list_tracked_files(self) -> List[Dict[str, Any]]:
        """列出所有被追踪的文件及其备份数量"""
        result = []
        for path, backups in self._backups.items():
            result.append({
                "path": path,
                "basename": os.path.basename(path),
                "backup_count": len(backups),
                "first_version": backups[0].backup_time if backups else "",
                "last_version": backups[-1].backup_time if backups else "",
                "current_hash": self._compute_hash(path)[:12] if os.path.exists(path) else "(deleted)",
            })
        return result

    def has_changes(self, file_path: str) -> bool:
        """检查文件是否有未备份的更改"""
        abs_path = os.path.abspath(file_path)
        backups = self._backups.get(abs_path, [])
        if not backups:
            return False

        latest_backup = backups[-1]
        if not os.path.exists(abs_path):
            return latest_backup.existed  # 如果最新备份时文件存在但现在已经删除

        current_hash = self._compute_hash(abs_path)
        return current_hash != latest_backup.file_hash

    # ── 快照管理 ─────────────────────────────────────────────────────────

    def _update_snapshot(
        self, file_path: str, backup_path: str,
        message_index: int, turn: int,
    ):
        """更新或创建快照"""
        snapshot_id = f"turn_{turn}"

        # 查找已有快照
        for snap in self._snapshots:
            if snap.snapshot_id == snapshot_id:
                snap.file_backups[file_path] = backup_path
                snap.message_index = message_index
                return

        # 创建新快照（继承前一个快照的文件状态）
        file_backups = {}
        if self._snapshots:
            file_backups = dict(self._snapshots[-1].file_backups)
        file_backups[file_path] = backup_path

        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            session_id=self._session_id,
            message_index=message_index,
            turn=turn,
            timestamp=datetime.now().isoformat(),
            file_backups=file_backups,
        )
        self._snapshots.append(snapshot)

    # ── 持久化 ────────────────────────────────────────────────────────────

    def _load_index(self):
        """加载索引"""
        if not os.path.exists(self._index_path):
            return
        try:
            import json
            with open(self._index_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 加载备份
            for path, backup_list in data.get("backups", {}).items():
                self._backups[path] = [FileBackup.from_dict(b) for b in backup_list]
                self._tracked_files.add(path)

            # 加载快照
            self._snapshots = [
                Snapshot.from_dict(s) for s in data.get("snapshots", [])
            ]

            logger.debug(
                f"FileHistory index loaded: {len(self._tracked_files)} files, "
                f"{len(self._snapshots)} snapshots"
            )
        except Exception as e:
            logger.warning(f"Failed to load file history index: {e}")

    def save_index(self):
        """保存索引到磁盘"""
        try:
            import json
            data = {
                "backups": {
                    path: [b.to_dict() for b in backups]
                    for path, backups in self._backups.items()
                },
                "snapshots": [s.to_dict() for s in self._snapshots],
                "session_id": self._session_id,
                "saved_at": datetime.now().isoformat(),
            }
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"FileHistory index saved: {self._index_path}")
        except Exception as e:
            logger.error(f"Failed to save file history index: {e}")

    # ── 工具方法 ─────────────────────────────────────────────────────────

    @staticmethod
    def _compute_hash(file_path: str) -> str:
        """计算文件的 SHA256 哈希"""
        if not os.path.exists(file_path):
            return ""
        try:
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def get_stats(self) -> Dict[str, Any]:
        """获取文件历史统计"""
        total_backups = sum(len(b) for b in self._backups.values())
        total_size = 0
        for backups in self._backups.values():
            for b in backups:
                if b.existed and os.path.exists(b.backup_path):
                    try:
                        total_size += os.path.getsize(b.backup_path)
                    except Exception:
                        pass

        return {
            "tracked_files": len(self._tracked_files),
            "total_backups": total_backups,
            "total_snapshots": len(self._snapshots),
            "total_backup_size_bytes": total_size,
            "session_id": self._session_id,
            "history_dir": self.history_dir,
        }

    def clear_session(self, session_id: Optional[str] = None):
        """清除指定会话的文件历史"""
        sid = session_id or self._session_id
        if not sid:
            return

        # 删除备份文件
        backup_dir = os.path.join(self.history_dir, sid)
        if os.path.exists(backup_dir):
            try:
                shutil.rmtree(backup_dir)
                logger.info(f"File history cleared for session {sid}")
            except Exception as e:
                logger.error(f"Failed to clear file history: {e}")

        # 清理内存索引
        to_remove = []
        for path, backups in self._backups.items():
            self._backups[path] = [b for b in backups if b.session_id != sid]
            if not self._backups[path]:
                to_remove.append(path)
        for path in to_remove:
            del self._backups[path]
            self._tracked_files.discard(path)

        self._snapshots = [s for s in self._snapshots if s.session_id != sid]


# ── 全局单例 ────────────────────────────────────────────────────────────────

_file_history: Optional[FileHistory] = None


def get_file_history() -> FileHistory:
    """获取全局 FileHistory 实例"""
    global _file_history
    if _file_history is None:
        _file_history = FileHistory()
    return _file_history
