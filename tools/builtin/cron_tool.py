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
Cron Tool — 定时任务管理

创建、管理、删除定时/周期性任务。
参考 ScheduleCronTool (CronCreate/Delete/List)。

功能:
  - CronCreate: 创建定时任务(cron 表达式 + 一次性)
  - CronDelete: 取消定时任务
  - CronList: 列出所有定时任务
  - 后台调度器: 自动执行到期任务
  - 持久化: 支持 durable 任务跨会话恢复
"""
import json
import math
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Callable, Any

from tools.registry import register_tool


# ── 常量 ─────────────────────────────────────────────────

DEFAULT_MAX_AGE_DAYS = 30
RECURRING_MAX_AGE_MS = DEFAULT_MAX_AGE_DAYS * 24 * 60 * 60 * 1000
RECURRING_JITTER_PCT = 0.10      # 周期性任务最多延迟 10%
RECURRING_JITTER_MAX_MIN = 15    # 最大延迟 15 分钟
ONESHOT_JITTER_SEC = 90          # 一次性任务最大抖动 90 秒
CRON_POLL_INTERVAL = 30          # 轮询间隔(秒)
DURABLE_TASKS_FILE = ".auracode/scheduled_tasks.json"


# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class CronJob:
    """定时任务"""
    job_id: str
    cron: str                       # cron 表达式 (5字段)
    prompt: str                     # 要执行的提示词
    recurring: bool = True          # True=周期性, False=一次性
    durable: bool = False           # True=持久化, False=仅会话
    created_at: float = 0.0         # 创建时间戳
    next_fire_at: float = 0.0       # 下次触发时间戳
    last_fire_at: float = 0.0       # 上次触发时间戳
    fire_count: int = 0             # 已触发次数
    expires_at: float = 0.0         # 过期时间(周期性任务)
    status: str = "active"          # active / expired / cancelled / fired
    label: str = ""                 # 用户可读标签

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'CronJob':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CronResult:
    """任务执行结果"""
    job_id: str
    prompt: str
    fired_at: float
    success: bool
    message: str = ""
    duration: float = 0.0


# ── Cron 表达式解析 ──────────────────────────────────────

class CronExpression:
    """标准 5 字段 cron 表达式解析器"""

    FIELD_NAMES = ["minute", "hour", "day_of_month", "month", "day_of_week"]
    FIELD_RANGES = {
        "minute": (0, 59),
        "hour": (0, 23),
        "day_of_month": (1, 31),
        "month": (1, 12),
        "day_of_week": (0, 6),  # 0=Sunday
    }

    def __init__(self, expr: str):
        self.expr = expr.strip()
        self.fields = self._parse(expr)

    def _parse(self, expr: str) -> Dict[str, set]:
        """解析 cron 表达式"""
        parts = expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: '{expr}' (need 5 fields, got {len(parts)})")

        result = {}
        for i, (part, name) in enumerate(zip(parts, self.FIELD_NAMES)):
            result[name] = self._parse_field(part, name)
        return result

    def _parse_field(self, part: str, field_name: str) -> set:
        """解析单个字段"""
        lo, hi = self.FIELD_RANGES[field_name]
        values = set()

        for segment in part.split(","):
            segment = segment.strip()

            # */N (步长)
            if segment.startswith("*/"):
                step = int(segment[2:])
                if step <= 0:
                    raise ValueError(f"Step must be positive: {segment}")
                values.update(range(lo, hi + 1, step))
                continue

            # * (通配)
            if segment == "*":
                values.update(range(lo, hi + 1))
                continue

            # 范围 N-M
            if "-" in segment:
                if "/" in segment:
                    range_part, step = segment.split("/")
                    step = int(step)
                else:
                    range_part = segment
                    step = 1
                start, end = map(int, range_part.split("-"))
                values.update(range(start, end + 1, step))
                continue

            # 固定值
            val = int(segment)
            if val < lo or val > hi:
                raise ValueError(f"Value {val} out of range [{lo}-{hi}] for {field_name}")
            values.add(val)

        return values

    def matches(self, dt: datetime = None) -> bool:
        """检查给定时间是否匹配"""
        if dt is None:
            dt = datetime.now()
        return (
            dt.minute in self.fields["minute"] and
            dt.hour in self.fields["hour"] and
            dt.day in self.fields["day_of_month"] and
            dt.month in self.fields["month"] and
            dt.weekday() in self._convert_dow(self.fields["day_of_week"])
        )

    def next_fire_time(self, after: datetime = None) -> datetime:
        """计算下次触发时间"""
        if after is None:
            after = datetime.now()
        dt = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(525960):  # 最多扫描 1 年
            if self.matches(dt):
                return dt
            dt += timedelta(minutes=1)
        raise RuntimeError(f"Cannot find next fire time within 1 year for: {self.expr}")

    @staticmethod
    def _convert_dow(dow_set: set) -> set:
        """转换 cron 星期(0=Sun) 到 Python weekday(0=Mon)"""
        result = set()
        for d in dow_set:
            if d == 0:
                result.add(6)  # Sunday -> 6
            else:
                result.add(d - 1)  # 1-6 -> 0-5
        return result

    def period_minutes(self) -> float:
        """估算 cron 周期(分钟)，基于1周采样"""
        count = 0
        # 扫描一周(10080分钟)
        base = datetime(2026, 1, 5, 0, 0)  # 某个周一
        for i in range(7 * 24 * 60):
            dt = base + timedelta(minutes=i)
            if self.matches(dt):
                count += 1
        if count > 0:
            return (7 * 24 * 60) / count  # 一周分钟数 / 匹配次数
        return float('inf')

    @staticmethod
    def validate(expr: str) -> bool:
        """验证 cron 表达式是否合法"""
        try:
            CronExpression(expr)
            return True
        except (ValueError, IndexError):
            return False


# ── 持久化 ──────────────────────────────────────────────

class CronStore:
    """持久化存储"""

    def __init__(self, store_path: str = None):
        if store_path is None:
            # 默认存储位置
            home = Path.home()
            store_path = str(home / ".auracode" / "scheduled_tasks.json")
        self._path = store_path
        self._lock = threading.Lock()

    def save_jobs(self, jobs: Dict[str, CronJob]):
        """保存所有持久化任务"""
        with self._lock:
            data = {}
            for job_id, job in jobs.items():
                if job.durable:
                    data[job_id] = job.to_dict()
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def load_jobs(self) -> Dict[str, CronJob]:
        """加载持久化任务"""
        with self._lock:
            if not os.path.exists(self._path):
                return {}
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    job_id: CronJob.from_dict(job_data)
                    for job_id, job_data in data.items()
                }
            except (json.JSONDecodeError, TypeError, KeyError):
                return {}

    def clear(self):
        """清空持久化存储"""
        with self._lock:
            if os.path.exists(self._path):
                os.remove(self._path)


# ── 调度器 ──────────────────────────────────────────────

class CronScheduler:
    """
    定时任务调度器。

    支持:
    - 周期性任务 (recurring=True) — 自动过期(30天)
    - 一次性任务 (recurring=False) — 触发后自动删除
    - 持久化任务 (durable=True) — 跨会话恢复
    - 会话任务 (durable=False) — 仅当前会话存活
    """

    def __init__(self, store: CronStore = None):
        self._store = store or CronStore()
        self._jobs: Dict[str, CronJob] = {}
        self._execution_log: List[CronResult] = []
        self._callbacks: List[Callable] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._load_durable_jobs()

    def _load_durable_jobs(self):
        """从持久化存储恢复任务"""
        loaded = self._store.load_jobs()
        with self._lock:
            for job_id, job in loaded.items():
                if job.status == "active":
                    # 检查是否过期
                    if job.recurring and job.expires_at and time.time() > job.expires_at:
                        job.status = "expired"
                    else:
                        self._jobs[job_id] = job

    def _save(self):
        """持久化到磁盘"""
        self._store.save_jobs(self._jobs)

    # ── 核心操作 ──

    def create_job(self, cron: str, prompt: str,
                   recurring: bool = True,
                   durable: bool = False,
                   label: str = "") -> CronJob:
        """
        创建定时任务。

        Args:
            cron: 标准 5 字段 cron 表达式
            prompt: 要执行的提示词/命令
            recurring: True=周期性, False=一次性
            durable: True=持久化, False=仅会话
            label: 可选标签

        Returns:
            CronJob

        Raises:
            ValueError: cron 表达式无效
        """
        cron_expr = CronExpression(cron)  # 验证

        job_id = str(uuid.uuid4())[:12]
        now = time.time()

        # 计算下次触发
        next_fire = cron_expr.next_fire_time()
        next_fire_ts = next_fire.timestamp()

        # 周期性任务: 计算过期时间 (30天)
        expires_at = 0.0
        if recurring:
            period_min = cron_expr.period_minutes()
            jitter_min = min(period_min * RECURRING_JITTER_PCT, RECURRING_JITTER_MAX_MIN)
            expires_at = now + RECURRING_MAX_AGE_MS / 1000

        job = CronJob(
            job_id=job_id,
            cron=cron,
            prompt=prompt,
            recurring=recurring,
            durable=durable,
            created_at=now,
            next_fire_at=next_fire_ts,
            expires_at=expires_at,
            status="active",
            label=label,
        )

        with self._lock:
            self._jobs[job_id] = job
            if durable:
                self._save()

        return job

    def delete_job(self, job_id: str) -> bool:
        """删除任务"""
        with self._lock:
            if job_id not in self._jobs:
                return False
            job = self._jobs[job_id]
            job.status = "cancelled"
            del self._jobs[job_id]
            if job.durable:
                self._save()
            return True

    def list_jobs(self) -> List[CronJob]:
        """列出所有任务"""
        with self._lock:
            return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[CronJob]:
        """获取任务详情"""
        with self._lock:
            return self._jobs.get(job_id)

    def get_execution_log(self) -> List[CronResult]:
        """获取执行日志"""
        return list(self._execution_log)

    # ── 调度引擎 ──

    def register_callback(self, callback: Callable[[CronJob], Any]):
        """注册任务执行回调"""
        self._callbacks.append(callback)

    def start(self):
        """启动后台调度线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _scheduler_loop(self):
        """后台调度主循环"""
        while self._running:
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(CRON_POLL_INTERVAL)

    def _tick(self):
        """单次调度检查"""
        now = time.time()
        now_dt = datetime.now()
        jobs_to_fire = []

        with self._lock:
            expired_ids = []

            for job_id, job in list(self._jobs.items()):
                if job.status != "active":
                    continue

                # 检查过期
                if job.recurring and job.expires_at and now > job.expires_at:
                    job.status = "expired"
                    expired_ids.append(job_id)
                    if job.durable:
                        self._save()
                    continue

                # 检查是否该触发
                if now >= job.next_fire_at:
                    # 抖动
                    cron_expr = CronExpression(job.cron)
                    jitter = 0
                    if job.recurring:
                        period_min = cron_expr.period_minutes()
                        jitter = min(period_min * RECURRING_JITTER_PCT, RECURRING_JITTER_MAX_MIN) * 60
                    elif not job.recurring:
                        jitter = ONESHOT_JITTER_SEC

                    actual_fire = job.next_fire_at + jitter * random_sign()
                    if now >= actual_fire:
                        jobs_to_fire.append(job)

            # 清理过期任务
            for eid in expired_ids:
                self._jobs.pop(eid, None)

        # 触发任务
        for job in jobs_to_fire:
            self._fire_job(job)

    def _fire_job(self, job: CronJob):
        """触发任务执行"""
        import logging
        logger = logging.getLogger(__name__)
        
        start = time.time()
        success = True
        message = ""

        logger.info(f"[CronScheduler] Firing job {job.job_id}: {job.prompt[:50]}...")

        try:
            for cb in self._callbacks:
                cb(job)
            message = f"Task executed: {job.prompt[:80]}"
        except Exception as e:
            success = False
            message = f"Task failed: {e}"
            logger.error(f"[CronScheduler] Job {job.job_id} failed: {e}")

        duration = time.time() - start

        result = CronResult(
            job_id=job.job_id,
            prompt=job.prompt,
            fired_at=time.time(),
            success=success,
            message=message,
            duration=duration,
        )
        self._execution_log.append(result)

        with self._lock:
            job.last_fire_at = time.time()
            job.fire_count += 1

            if not job.recurring:
                # 一次性任务: 触发后删除
                job.status = "fired"
                self._jobs.pop(job.job_id, None)
                if job.durable:
                    self._save()
            else:
                # 周期性任务: 计算下次触发
                try:
                    cron_expr = CronExpression(job.cron)
                    next_fire = cron_expr.next_fire_time()
                    job.next_fire_at = next_fire.timestamp()
                except Exception:
                    job.status = "expired"
                    self._jobs.pop(job.job_id, None)
                if job.durable:
                    self._save()


def random_sign() -> int:
    """随机正负"""
    import random
    return 1 if random.random() > 0.5 else -1


# ── 工具函数 ──────────────────────────────────────────────

def cron_create(cron: str, prompt: str,
                recurring: bool = True,
                durable: bool = False,
                label: str = "") -> Dict:
    """工具函数: 创建定时任务"""
    scheduler = get_cron_scheduler()
    job = scheduler.create_job(
        cron=cron, prompt=prompt,
        recurring=recurring, durable=durable, label=label,
    )
    next_dt = datetime.fromtimestamp(job.next_fire_at)
    recurring_note = "周期性" if recurring else "一次性"
    durable_note = " (持久化)" if durable else " (仅会话)"

    return {
        "job_id": job.job_id,
        "cron": job.cron,
        "prompt": job.prompt,
        "recurring": recurring,
        "durable": durable,
        "next_fire": next_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "message": f"Scheduled {recurring_note}{durable_note} task [{job.job_id}]. "
                   f"Next fire: {next_dt.strftime('%Y-%m-%d %H:%M:%S')}. "
                   f"Use CronDelete to cancel.",
    }


def cron_delete(job_id: str) -> Dict:
    """工具函数: 删除定时任务"""
    scheduler = get_cron_scheduler()
    success = scheduler.delete_job(job_id)
    if success:
        return {"job_id": job_id, "message": f"Cancelled cron job [{job_id}]"}
    return {"job_id": job_id, "message": f"Job [{job_id}] not found"}


def cron_list() -> Dict:
    """工具函数: 列出定时任务"""
    scheduler = get_cron_scheduler()
    jobs = scheduler.list_jobs()
    log = scheduler.get_execution_log()

    job_summaries = []
    for job in jobs:
        next_dt = datetime.fromtimestamp(job.next_fire_at) if job.next_fire_at else None
        job_summaries.append({
            "job_id": job.job_id,
            "cron": job.cron,
            "prompt": job.prompt[:80],
            "recurring": job.recurring,
            "durable": job.durable,
            "status": job.status,
            "next_fire": next_dt.strftime("%Y-%m-%d %H:%M:%S") if next_dt else "N/A",
            "fire_count": job.fire_count,
        })

    return {
        "total": len(jobs),
        "jobs": job_summaries,
        "total_executions": len(log),
        "message": f"Found {len(jobs)} scheduled job(s), {len(log)} execution(s).",
    }


# ── /cron 命令 ──────────────────────────────────────────

def cron_handler(args: list, loop=None) -> str:
    """
    定时任务管理命令。

    用法:
        /cron list                         — 列出所有任务
        /cron create <cron_expr> <prompt>  — 创建任务
        /cron delete <job_id>              — 删除任务
        /cron log                          — 查看执行日志
    """
    scheduler = get_cron_scheduler()

    if not args:
        args = ["list"]

    action = args[0]

    if action == "list":
        jobs = scheduler.list_jobs()
        if not jobs:
            return "📭 没有定时任务。使用 /cron create 创建。"

        lines = [f"⏰ 定时任务列表 ({len(jobs)}):\n"]
        for job in jobs:
            next_dt = datetime.fromtimestamp(job.next_fire_at) if job.next_fire_at else None
            type_icon = "🔄" if job.recurring else "⏱️"
            dur_icon = "💾" if job.durable else "📝"
            status_icon = {"active": "✅", "expired": "⏰", "cancelled": "❌", "fired": "🔥"}.get(job.status, "❓")
            lines.append(f"  {status_icon} {type_icon}{dur_icon} [{job.job_id}]")
            lines.append(f"     Cron: {job.cron}")
            lines.append(f"     提示: {job.prompt[:60]}{'...' if len(job.prompt) > 60 else ''}")
            lines.append(f"     类型: {'周期性' if job.recurring else '一次性'} | {'持久化' if job.durable else '会话'}")
            lines.append(f"     触发: {job.fire_count} 次 | 下次: {next_dt.strftime('%m-%d %H:%M') if next_dt else 'N/A'}")
            if job.label:
                lines.append(f"     标签: {job.label}")
            lines.append("")
        return "\n".join(lines)

    elif action == "create":
        if len(args) < 3:
            return "用法: /cron create <cron表达式> <提示词> [--once] [--durable] [--label <name>]"

        cron_expr = args[1]
        remaining = args[2:]

        # 解析选项
        recurring = True
        durable = False
        label = ""

        while remaining:
            if remaining[0] == "--once":
                recurring = False
                remaining.pop(0)
            elif remaining[0] == "--durable":
                durable = True
                remaining.pop(0)
            elif remaining[0] == "--label" and len(remaining) > 1:
                label = remaining[1]
                remaining = remaining[2:]
            else:
                break

        prompt = " ".join(remaining)

        try:
            job = scheduler.create_job(
                cron=cron_expr, prompt=prompt,
                recurring=recurring, durable=durable, label=label,
            )
            next_dt = datetime.fromtimestamp(job.next_fire_at)
            return (
                f"✅ 已创建定时任务 [{job.job_id}]\n"
                f"   Cron: {job.cron}\n"
                f"   提示: {job.prompt[:80]}\n"
                f"   类型: {'周期性' if recurring else '一次性'} | {'持久化' if durable else '会话'}\n"
                f"   下次触发: {next_dt.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except ValueError as e:
            return f"❌ 创建失败: {e}"

    elif action == "delete":
        if len(args) < 2:
            return "用法: /cron delete <job_id>"
        job_id = args[1]
        if scheduler.delete_job(job_id):
            return f"✅ 已取消任务 [{job_id}]"
        return f"❌ 任务 [{job_id}] 不存在"

    elif action == "log":
        log = scheduler.get_execution_log()
        if not log:
            return "📭 暂无执行记录。"

        lines = [f"📋 执行日志 (最近 {min(len(log), 20)} 条):\n"]
        for result in log[-20:]:
            status = "✅" if result.success else "❌"
            fired_dt = datetime.fromtimestamp(result.fired_at)
            lines.append(f"  {status} [{result.job_id}] {fired_dt.strftime('%m-%d %H:%M:%S')}")
            lines.append(f"     {result.prompt[:60]}{'...' if len(result.prompt) > 60 else ''}")
            lines.append(f"     耗时: {result.duration:.1f}s")
        return "\n".join(lines)

    else:
        return "用法: /cron [list|create|delete|log] [参数...]"


# ── 注册 ─────────────────────────────────────────────────

register_tool("cron_create", {
    "description": (
        "Schedule a prompt to run at a future time — recurring cron or one-shot. "
        "Supports standard 5-field cron expressions, durable persistence across sessions, "
        "and automatic jitter to avoid thundering herd."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "cron": {
                "type": "string",
                "description": "Standard 5-field cron expression (e.g. '0 9 * * 1' for Mon 9am)",
            },
            "prompt": {
                "type": "string",
                "description": "The prompt/command to execute when triggered",
            },
            "recurring": {
                "type": "boolean",
                "description": "True=recurring (default), False=one-shot",
                "default": True,
            },
            "durable": {
                "type": "boolean",
                "description": "True=persist to disk across sessions, False=session-only",
                "default": False,
            },
            "label": {
                "type": "string",
                "description": "Optional human-readable label",
                "default": "",
            },
        },
        "required": ["cron", "prompt"],
    },
    "handler": cron_create,
    "permission_level": "write",
})

register_tool("cron_delete", {
    "description": "Cancel a scheduled cron job by ID. Removes it from the scheduler.",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "Job ID to cancel",
            },
        },
        "required": ["job_id"],
    },
    "handler": cron_delete,
    "permission_level": "write",
})

register_tool("cron_list", {
    "description": (
        "List all scheduled cron jobs with status, next fire time, and execution count."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
    "handler": cron_list,
    "permission_level": "read",
})

# 注册命令
try:
    from commands.registry import register_command
    register_command("cron", {
        "description": "定时任务管理 — 创建/删除/查看 Cron 任务",
        "handler": cron_handler,
        "category": "scheduling",
        "args_help": "[list|create|delete|log] [参数...]",
    })
except Exception:
    pass


# ── 全局单例 ──────────────────────────────────────────────

_cron_scheduler: Optional[CronScheduler] = None


def get_cron_scheduler() -> CronScheduler:
    """获取全局 CronScheduler 单例（自动启动）"""
    global _cron_scheduler
    if _cron_scheduler is None:
        _cron_scheduler = CronScheduler()
        _cron_scheduler.start()  # 自动启动调度器
    return _cron_scheduler
