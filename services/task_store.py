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
文件级任务持久化 (Task Store)

参考标准~/.auracode/tasks/{taskListId}/{taskId}.json
每个任务独立保存为 JSON 文件，支持:
- 跨进程并发安全（文件锁）
- 崩溃恢复（文件级持久化）
- 多 Agent 协作（文件锁竞争认领）

存储结构:
~/.auracode/tasks/{task_list_id}/
├── 1.json              # 任务文件
├── 2.json
├── .highwatermark      # 最大 ID 记录（防止重置后 ID 复用）
└── .lock               # 列表级锁文件

任务状态流: pending → in_progress → completed
"""

import json
import os
import re
import logging
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 路径工具 ──

def _auracode_home() -> str:
    return os.path.join(os.path.expanduser("~"), ".auracode")


def _sanitize_component(s: str) -> str:
    """将字符串转为安全的路径组件"""
    return re.sub(r'[^a-zA-Z0-9_-]', '-', s)


def get_tasks_dir(task_list_id: str) -> str:
    """获取任务列表目录"""
    return os.path.join(
        _auracode_home(), "tasks", _sanitize_component(task_list_id)
    )


def get_task_path(task_list_id: str, task_id: str) -> str:
    """获取单个任务文件路径"""
    return os.path.join(
        get_tasks_dir(task_list_id),
        f"{_sanitize_component(task_id)}.json",
    )


def get_high_watermark_path(task_list_id: str) -> str:
    """获取高水位文件路径"""
    return os.path.join(get_tasks_dir(task_list_id), ".highwatermark")


# ── 任务数据 ──

@dataclass
class Task:
    """任务数据"""
    id: str                           # 任务 ID
    subject: str = ""                 # 简短标题
    description: str = ""             # 详细描述
    active_form: str = ""             # 进行中时显示文本
    owner: str = ""                   # 认领的 Agent ID
    status: str = "pending"           # pending / in_progress / completed
    blocks: List[str] = field(default_factory=list)     # 此任务阻塞的任务
    blocked_by: List[str] = field(default_factory=list) # 阻塞此任务的任务
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid}
        return cls(**filtered)


# ── 任务存储管理器 ──

class TaskStore:
    """
    文件级任务持久化存储

    用法:
        store = TaskStore(task_list_id="session-abc")
        task_id = store.create(subject="Fix bug", description="...")
        store.update(task_id, status="in_progress")
        tasks = store.list_tasks()
        store.update(task_id, status="completed")
    """

    def __init__(self, task_list_id: str):
        self.task_list_id = task_list_id
        self._dir = get_tasks_dir(task_list_id)
        self._lock = threading.Lock()

        os.makedirs(self._dir, exist_ok=True)
        logger.debug(f"TaskStore initialized: {self._dir}")

    # ── CRUD 操作 ──

    def create(
        self,
        subject: str,
        description: str = "",
        active_form: str = "",
        owner: str = "",
    ) -> str:
        """
        创建新任务

        Returns:
            新任务 ID
        """
        with self._lock:
            highest = self._find_highest_id()
            task_id = str(highest + 1)

            now = datetime.now().isoformat()
            task = Task(
                id=task_id,
                subject=subject,
                description=description,
                active_form=active_form,
                owner=owner,
                status="pending",
                created_at=now,
                updated_at=now,
            )

            path = get_task_path(self.task_list_id, task_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(f"Task created: #{task_id} '{subject}'")
            return task_id

    def get(self, task_id: str) -> Optional[Task]:
        """读取单个任务"""
        path = get_task_path(self.task_list_id, task_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Task.from_dict(data)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.warning(f"Failed to read task {task_id}: {e}")
            return None

    def update(self, task_id: str, **kwargs) -> Optional[Task]:
        """
        更新任务字段

        用法:
            store.update("1", status="in_progress", owner="agent-1")
        """
        with self._lock:
            task = self.get(task_id)
            if not task:
                return None

            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)

            task.updated_at = datetime.now().isoformat()

            path = get_task_path(self.task_list_id, task_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)

            return task

    def delete(self, task_id: str) -> bool:
        """删除任务"""
        with self._lock:
            path = get_task_path(self.task_list_id, task_id)
            try:
                # 更新高水位
                try:
                    numeric_id = int(task_id)
                    self._update_high_watermark(numeric_id)
                except ValueError:
                    pass

                os.unlink(path)

                # 清理引用
                all_tasks = self.list_tasks()
                for t in all_tasks:
                    changed = False
                    if task_id in t.blocks:
                        t.blocks = [x for x in t.blocks if x != task_id]
                        changed = True
                    if task_id in t.blocked_by:
                        t.blocked_by = [x for x in t.blocked_by if x != task_id]
                        changed = True
                    if changed:
                        t_path = get_task_path(self.task_list_id, t.id)
                        with open(t_path, "w", encoding="utf-8") as f:
                            json.dump(t.to_dict(), f, indent=2)

                return True
            except FileNotFoundError:
                return False
            except Exception as e:
                logger.error(f"Failed to delete task {task_id}: {e}")
                return False

    def list_tasks(self) -> List[Task]:
        """列出所有任务"""
        tasks = []
        try:
            for fname in os.listdir(self._dir):
                if fname.endswith(".json") and not fname.startswith("."):
                    tid = fname[:-5]
                    task = self.get(tid)
                    if task:
                        tasks.append(task)
        except OSError:
            pass

        # 按 ID 数值排序
        tasks.sort(key=lambda t: int(t.id) if t.id.isdigit() else 999999)
        return tasks

    def add_dependency(self, from_task_id: str, to_task_id: str) -> bool:
        """
        添加任务依赖: from_task blocks to_task

        Returns:
            是否成功
        """
        from_task = self.get(from_task_id)
        to_task = self.get(to_task_id)
        if not from_task or not to_task:
            return False

        if to_task_id not in from_task.blocks:
            self.update(from_task_id, blocks=from_task.blocks + [to_task_id])
        if from_task_id not in to_task.blocked_by:
            self.update(to_task_id, blocked_by=to_task.blocked_by + [from_task_id])

        return True

    def claim(self, task_id: str, agent_id: str) -> Optional[Task]:
        """
        认领任务（原子操作）

        Returns:
            认领成功返回 Task，失败返回 None
        """
        with self._lock:
            task = self.get(task_id)
            if not task:
                return None

            if task.owner and task.owner != agent_id:
                return None  # 已被他人认领
            if task.status == "completed":
                return None  # 已完成

            # 检查阻塞
            for blocker_id in task.blocked_by:
                blocker = self.get(blocker_id)
                if blocker and blocker.status != "completed":
                    return None  # 被未完成的任务阻塞

            task.owner = agent_id
            task.status = "in_progress"
            task.updated_at = datetime.now().isoformat()

            path = get_task_path(self.task_list_id, task_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)

            return task

    def reset(self) -> None:
        """重置任务列表（新 swarm 时使用）"""
        with self._lock:
            # 保存高水位
            highest = self._find_highest_id()
            if highest > 0:
                self._update_high_watermark(highest)

            # 删除所有任务文件
            try:
                for fname in os.listdir(self._dir):
                    if fname.endswith(".json") and not fname.startswith("."):
                        os.unlink(os.path.join(self._dir, fname))
            except OSError:
                pass

    # ── 内部方法 ──

    def _find_highest_id(self) -> int:
        """查找当前最大任务 ID"""
        highest = self._read_high_watermark()
        try:
            for fname in os.listdir(self._dir):
                if fname.endswith(".json"):
                    try:
                        tid = int(fname[:-5])
                        highest = max(highest, tid)
                    except ValueError:
                        pass
        except OSError:
            pass
        return highest

    def _read_high_watermark(self) -> int:
        """读取高水位值"""
        path = get_high_watermark_path(self.task_list_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0

    def _update_high_watermark(self, value: int) -> None:
        """更新高水位值"""
        path = get_high_watermark_path(self.task_list_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(str(value))
        except Exception as e:
            logger.warning(f"Failed to update high watermark: {e}")


# ── 全局单例 ──

_stores: Dict[str, TaskStore] = {}


def get_task_store(task_list_id: Optional[str] = None) -> TaskStore:
    """获取任务存储实例"""
    if task_list_id is None:
        task_list_id = "default"
    if task_list_id not in _stores:
        _stores[task_list_id] = TaskStore(task_list_id=task_list_id)
    return _stores[task_list_id]
