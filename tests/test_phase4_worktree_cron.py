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
Phase 4 测试 — Worktree + Cron 定时任务

覆盖:
  1. WorktreeManager (创建/退出/状态/列表)
  2. CronExpression (cron 解析/验证/匹配)
  3. CronScheduler (创建/删除/列表/调度/持久化)
  4. /worktree 命令
  5. /cron 命令
  6. 工具注册验证
"""
import json
import os
import sys
import tempfile
import time
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0
errors = []


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  ❌ {name}: {detail}")


# ═══════════════════════════════════════════════════════════
# 1. Worktree 模块
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("1. Worktree 模块测试")
print("=" * 60)

from tools.builtin.worktree_tool import (
    WorktreeManager, WorktreeSession, WorktreeInfo,
    _validate_worktree_name, _generate_random_name,
    _find_git_root, _get_head_commit, get_worktree_manager,
    worktree_handler, get_current_worktree_session,
    enter_worktree, exit_worktree,
    _current_session,
)

# 1.1 名称验证
check("validate_worktree_name('test-1')", _validate_worktree_name("test-1"))
check("validate_worktree_name('my.wt')", _validate_worktree_name("my.wt"))
check("validate_worktree_name('abc123')", _validate_worktree_name("abc123"))
check("reject 'a b c'", not _validate_worktree_name("a b c"))
check("reject 'a/b'", not _validate_worktree_name("a/b"))
check("reject ''", not _validate_worktree_name(""))
check("reject too long", not _validate_worktree_name("a" * 65))

# 1.2 随机名称
name1 = _generate_random_name()
check("random name starts with 'wt-'", name1.startswith("wt-"))
check("random name length", len(name1) <= 15)
name2 = _generate_random_name()
check("random names unique", name1 != name2)

# 1.3 WorktreeSession dataclass
session = WorktreeSession(
    original_cwd="/tmp/test",
    worktree_path="/tmp/wt/test",
    worktree_branch="worktree/test",
    worktree_name="test",
    original_head="abc123",
    created_at=time.time(),
)
check("WorktreeSession fields", session.worktree_name == "test")
check("WorktreeSession branch", session.worktree_branch == "worktree/test")

# 1.4 WorktreeManager 实例
manager = get_worktree_manager()
check("WorktreeManager instance", isinstance(manager, WorktreeManager))
manager2 = get_worktree_manager()
check("WorktreeManager singleton", manager is manager2)

# 1.5 WorktreeManager status (不在 worktree)
status = manager.get_status()
check("status not in worktree", not status["in_worktree"])

# 1.6 list_worktrees (可能在非 git 环境)
worktrees = manager.list_worktrees()
check("list_worktrees returns list", isinstance(worktrees, list))

# 1.7 Git root detection
git_root = _find_git_root()
check("find_git_root returns str or None", git_root is None or isinstance(git_root, str))

# 1.8 /worktree 命令 - status
result = worktree_handler(["status"])
check("/worktree status", "不在 worktree" in result or "status" in result.lower() or "不在" in result)

# 1.9 /worktree 命令 - list
result = worktree_handler(["list"])
check("/worktree list", isinstance(result, str))

# 1.10 /worktree 无参数 = status
result = worktree_handler([])
check("/worktree default=status", isinstance(result, str))

# 1.11 工具注册
from tools.registry import TOOL_REGISTRY
check("enter_worktree registered", "enter_worktree" in TOOL_REGISTRY)
check("exit_worktree registered", "exit_worktree" in TOOL_REGISTRY)
check("enter_worktree has description", bool(TOOL_REGISTRY["enter_worktree"]["description"]))
check("exit_worktree has description", bool(TOOL_REGISTRY["exit_worktree"]["description"]))

# 1.12 命令注册
from commands.registry import COMMAND_REGISTRY
check("/worktree command registered", "worktree" in COMMAND_REGISTRY)
check("/worktree has handler", "handler" in COMMAND_REGISTRY["worktree"])


# ═══════════════════════════════════════════════════════════
# 2. CronExpression 模块
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("2. CronExpression 模块测试")
print("=" * 60)

from tools.builtin.cron_tool import (
    CronExpression, CronJob, CronStore, CronScheduler,
    cron_create, cron_delete, cron_list, cron_handler,
    get_cron_scheduler,
)

# 2.1 基础解析
ce = CronExpression("* * * * *")
check("parse '* * * * *'", len(ce.fields["minute"]) == 60)
check("all hours", len(ce.fields["hour"]) == 24)

ce2 = CronExpression("0 9 * * *")
check("parse '0 9 * * *'", ce2.fields["minute"] == {0})
check("hour = 9", ce2.fields["hour"] == {9})

# 2.2 步长
ce3 = CronExpression("*/5 * * * *")
check("*/5 minutes", 0 in ce3.fields["minute"] and 5 in ce3.fields["minute"] and 55 in ce3.fields["minute"])
check("*/5 count", len(ce3.fields["minute"]) == 12)

ce4 = CronExpression("0 */2 * * *")
check("*/2 hours", 0 in ce4.fields["hour"] and 2 in ce4.fields["hour"] and 22 in ce4.fields["hour"])

# 2.3 范围
ce5 = CronExpression("0 9-17 * * 1-5")
check("range 9-17 hours", set(range(9, 18)) == ce5.fields["hour"])
check("range 1-5 dow", {1, 2, 3, 4, 5} == ce5.fields["day_of_week"])

# 2.4 多值
ce6 = CronExpression("0,30 * * * *")
check("multi 0,30", ce6.fields["minute"] == {0, 30})

# 2.5 匹配
from datetime import datetime
dt_9am = datetime(2026, 1, 5, 9, 0, 0)  # Monday
ce_9am = CronExpression("0 9 * * *")
check("matches 9am", ce_9am.matches(dt_9am))
check("not matches 10am", not ce_9am.matches(datetime(2026, 1, 5, 10, 0, 0)))

# 工作日匹配
ce_weekday = CronExpression("0 9 * * 1-5")
check("weekday Mon", ce_weekday.matches(datetime(2026, 1, 5, 9, 0, 0)))  # Monday
check("weekday not Sat", not ce_weekday.matches(datetime(2026, 1, 3, 9, 0, 0)))  # Saturday

# 2.6 next_fire_time
ce_next = CronExpression("0 9 * * *")
from datetime import timedelta
before_9am = datetime(2026, 1, 5, 8, 0, 0)
next_fire = ce_next.next_fire_time(before_9am)
check("next fire is 9:00", next_fire.hour == 9 and next_fire.minute == 0)
check("next fire same day", next_fire.day == 5)

after_9am = datetime(2026, 1, 5, 10, 0, 0)
next_fire2 = ce_next.next_fire_time(after_9am)
check("next fire next day", next_fire2.day == 6 and next_fire2.hour == 9)

# 2.7 period_minutes
ce_5min = CronExpression("*/5 * * * *")
period = ce_5min.period_minutes()
check("period ~5 min", 4 < period < 6)

ce_hourly = CronExpression("0 * * * *")
period_h = ce_hourly.period_minutes()
check("period ~60 min", 55 < period_h < 65)

# 2.8 验证
check("validate('* * * * *')", CronExpression.validate("* * * * *"))
check("validate('0 9 * * 1-5')", CronExpression.validate("0 9 * * 1-5"))
check("reject('invalid')", not CronExpression.validate("invalid"))
check("reject('* * *')", not CronExpression.validate("* * *"))
check("reject('60 * * * *')", not CronExpression.validate("60 * * * *"))


# ═══════════════════════════════════════════════════════════
# 3. CronJob + CronStore
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("3. CronJob + CronStore 测试")
print("=" * 60)

# 3.1 CronJob dataclass
job = CronJob(
    job_id="test123",
    cron="*/5 * * * *",
    prompt="check status",
    recurring=True,
    durable=False,
    created_at=time.time(),
    next_fire_at=time.time() + 300,
)
check("CronJob fields", job.job_id == "test123" and job.cron == "*/5 * * * *")
check("CronJob recurring", job.recurring is True)

# 3.2 to_dict / from_dict
d = job.to_dict()
check("to_dict has job_id", d["job_id"] == "test123")
job2 = CronJob.from_dict(d)
check("from_dict roundtrip", job2.job_id == "test123" and job2.cron == "*/5 * * * *")

# 3.3 CronStore
tmpdir = tempfile.mkdtemp()
store_path = os.path.join(tmpdir, "test_tasks.json")
store = CronStore(store_path)

job_durable = CronJob(
    job_id="dur1",
    cron="0 9 * * *",
    prompt="morning task",
    recurring=True,
    durable=True,
    created_at=time.time(),
    next_fire_at=time.time() + 3600,
    status="active",
)
job_session = CronJob(
    job_id="sess1",
    cron="0 10 * * *",
    prompt="session task",
    recurring=False,
    durable=False,
    created_at=time.time(),
    next_fire_at=time.time() + 3600,
    status="active",
)

store.save_jobs({"dur1": job_durable, "sess1": job_session})
check("store file exists", os.path.exists(store_path))

# 验证只保存 durable 任务
with open(store_path, "r") as f:
    saved = json.load(f)
check("only durable saved", "dur1" in saved and "sess1" not in saved)

# 加载
loaded = store.load_jobs()
check("load durable job", "dur1" in loaded)
check("load job cron", loaded["dur1"].cron == "0 9 * * *")

# 清空
store.clear()
check("store cleared", not os.path.exists(store_path))

shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════
# 4. CronScheduler
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("4. CronScheduler 测试")
print("=" * 60)

tmpdir = tempfile.mkdtemp()
store = CronStore(os.path.join(tmpdir, "scheduler_test.json"))
scheduler = CronScheduler(store=store)

# 4.1 create_job
job1 = scheduler.create_job(
    cron="*/10 * * * *",
    prompt="check logs",
    recurring=True,
    label="log checker",
)
check("create job", job1.job_id is not None)
check("job cron", job1.cron == "*/10 * * * *")
check("job recurring", job1.recurring is True)
check("job label", job1.label == "log checker")
check("job status active", job1.status == "active")
check("job next_fire set", job1.next_fire_at > time.time() - 60)

# 4.2 list_jobs
job2 = scheduler.create_job(cron="0 9 * * *", prompt="morning report")
jobs = scheduler.list_jobs()
check("list jobs count", len(jobs) >= 2)

# 4.3 get_job
retrieved = scheduler.get_job(job1.job_id)
check("get_job found", retrieved is not None)
check("get_job id match", retrieved.job_id == job1.job_id)
check("get_job nonexistent", scheduler.get_job("nonexistent") is None)

# 4.4 delete_job
deleted = scheduler.delete_job(job2.job_id)
check("delete_job success", deleted is True)
check("delete_job nonexistent", scheduler.delete_job("nonexistent") is False)
remaining = scheduler.list_jobs()
check("after delete count", len(remaining) == len(jobs) - 1)

# 4.5 invalid cron
try:
    scheduler.create_job(cron="invalid", prompt="bad")
    check("invalid cron raises", False, "should have raised")
except ValueError:
    check("invalid cron raises", True)

# 4.6 durable create + persistence
durable_job = scheduler.create_job(
    cron="0 12 * * *",
    prompt="noon task",
    durable=True,
)
check("durable file exists", os.path.exists(os.path.join(tmpdir, "scheduler_test.json")))

# 4.7 callback
callback_called = []
scheduler.register_callback(lambda j: callback_called.append(j.job_id))

# 4.8 execution log
log = scheduler.get_execution_log()
check("initial log empty", len(log) == 0)

shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════
# 5. 工具函数 + /cron 命令
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("5. 工具函数 + /cron 命令测试")
print("=" * 60)

# 5.1 cron_create 工具
result = cron_create(
    cron="*/15 * * * *",
    prompt="check server status",
    recurring=True,
    label="status check",
)
check("cron_create returns job_id", "job_id" in result)
check("cron_create has next_fire", "next_fire" in result)
check("cron_create message", "Scheduled" in result["message"])
job_id = result["job_id"]

# 5.2 cron_list 工具
result = cron_list()
check("cron_list total", result["total"] >= 1)
check("cron_list jobs", len(result["jobs"]) >= 1)
check("cron_list message", "Found" in result["message"])

# 5.3 cron_delete 工具
result = cron_delete(job_id)
check("cron_delete success", "Cancelled" in result["message"])

result = cron_delete("nonexistent")
check("cron_delete not found", "not found" in result["message"])

# 5.4 /cron 命令
# list
result = cron_handler(["list"])
check("/cron list", isinstance(result, str))

# create
result = cron_handler(["create", "*/30 * * * *", "test prompt", "--label", "test"])
check("/cron create", "已创建" in result)

# log
result = cron_handler(["log"])
check("/cron log", isinstance(result, str))

# 无参数
result = cron_handler([])
check("/cron default=list", isinstance(result, str))

# 错误用法
result = cron_handler(["create"])
check("/cron create missing args", "用法" in result)

result = cron_handler(["delete"])
check("/cron delete missing id", "用法" in result)

result = cron_handler(["unknown"])
check("/cron unknown action", "用法" in result)

# 5.5 工具注册
check("cron_create tool registered", "cron_create" in TOOL_REGISTRY)
check("cron_delete tool registered", "cron_delete" in TOOL_REGISTRY)
check("cron_list tool registered", "cron_list" in TOOL_REGISTRY)
check("cron_create has params", "cron" in TOOL_REGISTRY["cron_create"]["parameters"])
check("cron_delete has params", "job_id" in TOOL_REGISTRY["cron_delete"]["parameters"])

# 5.6 命令注册
check("/cron command registered", "cron" in COMMAND_REGISTRY)
check("/cron has handler", "handler" in COMMAND_REGISTRY["cron"])
check("/cron has description", "定时任务" in COMMAND_REGISTRY["cron"]["description"])


# ═══════════════════════════════════════════════════════════
# 6. 集成验证
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("6. 集成验证")
print("=" * 60)

# 全量加载
from tools.builtin import worktree_tool as wt, cron_tool as ct
tool_count = len(TOOL_REGISTRY)
cmd_count = len(COMMAND_REGISTRY)
check(f"工具总数 >= 53 (actual: {tool_count})", tool_count >= 53)
check(f"命令总数 >= 45 (actual: {cmd_count})", cmd_count >= 45)

# worktree + cron 工具都在
wt_tools = ["enter_worktree", "exit_worktree"]
cron_tools = ["cron_create", "cron_delete", "cron_list"]
for t in wt_tools + cron_tools:
    check(f"tool '{t}' in registry", t in TOOL_REGISTRY)

# 命令
for c in ["worktree", "cron"]:
    check(f"command '/{c}' in registry", c in COMMAND_REGISTRY)

# 工具 schema 格式
for tool_name in wt_tools + cron_tools:
    defn = TOOL_REGISTRY[tool_name]
    check(f"{tool_name} has description", isinstance(defn["description"], str) and len(defn["description"]) > 5)
    check(f"{tool_name} has handler", callable(defn["handler"]))
    check(f"{tool_name} has parameters", isinstance(defn["parameters"], dict))
    check(f"{tool_name} has permission_level", defn.get("permission_level") in ("read", "write", "execute"))


# ═══════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
total = passed + failed
print(f"Phase 4 测试结果: {passed}/{total} 通过")
if errors:
    print(f"\n失败项:")
    for e in errors:
        print(f"  - {e}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
