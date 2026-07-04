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
最终轮测试 — /rewind + DiagnosticTracker + 集成验证

测试覆盖:
1. /rewind 命令 (CheckpointManager)
2. DiagnosticTracker 诊断追踪
3. agent_loop 检查点集成
4. 跨模块加载验证
"""
import os
import sys
import json
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}: {detail}")


# ============================================================
# P0: /rewind 命令
# ============================================================
print("\n" + "=" * 60)
print("P0: /rewind 命令 — CheckpointManager")
print("=" * 60)

try:
    from commands.builtin.rewind_command import (
        CheckpointManager, get_checkpoint_manager, rewind_handler
    )
    check("/rewind 模块可导入", True)
except Exception as e:
    check("/rewind 模块可导入", False, str(e))
    CheckpointManager = None

# CheckpointManager 基本功能
if CheckpointManager:
    mgr = CheckpointManager()

    # 创建检查点
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Hello, fix the bug"},
    ]
    mgr.create_checkpoint(1, messages)
    check("创建检查点 1", len(mgr.list_checkpoints()) == 1)

    messages2 = messages + [
        {"role": "assistant", "content": "I'll fix it"},
        {"role": "user", "content": "Now add a test"},
    ]
    mgr.create_checkpoint(2, messages2)
    check("创建检查点 2", len(mgr.list_checkpoints()) == 2)

    messages3 = messages2 + [
        {"role": "assistant", "content": "Test added"},
        {"role": "user", "content": "Refactor please"},
    ]
    mgr.create_checkpoint(3, messages3)
    check("创建检查点 3", len(mgr.list_checkpoints()) == 3)

    # 列出检查点
    cps = mgr.list_checkpoints()
    check("检查点列表正确", cps[0]["turn"] == 1 and cps[2]["turn"] == 3)

    # 回退到 turn 2
    result = mgr.rewind_to(2, messages3)
    check("回退到 Turn 2 截断消息", len(result) == len(messages2))

    # 检查点已清除后续的
    remaining = mgr.list_checkpoints()
    check("回退后清除后续检查点", len(remaining) == 2)

    # 获取最后检查点 (回退后返回前一个检查点用于"撤销上一轮")
    last = mgr.get_last_checkpoint()
    check("获取最后检查点", last is not None and last["turn"] == 1)

    # 状态
    status = mgr.get_status()
    check("状态报告正确", status["total_checkpoints"] == 2)

# 全局单例
mgr1 = get_checkpoint_manager()
mgr2 = get_checkpoint_manager()
check("CheckpointManager 全局单例", mgr1 is mgr2)

# rewind_handler 输出
output = rewind_handler(["status"])
check("rewind_handler status 输出", "检查点" in output or "Checkpoint" in output or "=" in output)

output_list = rewind_handler(["list"])
check("rewind_handler list 输出", "=" in output_list)


# ============================================================
# P1: DiagnosticTracker
# ============================================================
print("\n" + "=" * 60)
print("P1: DiagnosticTracker — 诊断追踪")
print("=" * 60)

try:
    from services.diagnostic_tracker import (
        DiagnosticTracker, Diagnostic, get_diagnostic_tracker, FileChangeRecord
    )
    check("DiagnosticTracker 可导入", True)
except Exception as e:
    check("DiagnosticTracker 可导入", False, str(e))
    DiagnosticTracker = None

if DiagnosticTracker:
    tracker = DiagnosticTracker()

    # 设置基线
    baseline_diags = [
        {"message": "Unused import", "severity": 2, "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 10}}},
        {"message": "Missing return", "severity": 1, "range": {"start": {"line": 5, "character": 0}, "end": {"line": 5, "character": 20}}},
    ]
    tracker.set_baseline("test.py", baseline_diags)
    check("设置基线诊断", "test.py" in str(tracker._baseline) or len(tracker._baseline) == 1)

    # 更新诊断 (模拟修改后)
    current_diags = [
        {"message": "Missing return", "severity": 1, "range": {"start": {"line": 5, "character": 0}, "end": {"line": 5, "character": 20}}},
        {"message": "Type error", "severity": 1, "range": {"start": {"line": 10, "character": 0}, "end": {"line": 10, "character": 15}}},
        {"message": "Unused import", "severity": 2, "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 10}}},
    ]
    tracker.update_diagnostics("test.py", current_diags)
    check("更新诊断", True)

    # 追踪变更
    record = tracker.track_file_change("test.py")
    check("变更追踪返回 FileChangeRecord", isinstance(record, FileChangeRecord))
    check("基线错误数=1 (仅 Error)", record.baseline_errors == 1)
    check("当前错误数=2", record.current_errors == 2)
    check("新增错误=1 (Type error)", len(record.new_errors) == 1)
    if record.new_errors:
        check("新增错误信息正确", "Type error" in record.new_errors[0].message)

    # Diagnostic 转换
    d = Diagnostic.from_lsp(baseline_diags[0])
    check("Diagnostic.from_lsp 转换", d.severity == "Warning" and d.line == 1)

    # 报告
    report = tracker.generate_report()
    check("报告包含新增错误", "Type error" in report)
    check("报告包含统计", "新增" in report or "new" in report.lower())

    # 统计
    stats = tracker.get_stats()
    check("统计信息正确", stats["tracked_files"] == 1 and stats["total_new_errors"] == 1)

    # 全局单例
    t1 = get_diagnostic_tracker()
    t2 = get_diagnostic_tracker()
    check("DiagnosticTracker 全局单例", t1 is t2)

    # 重置
    tracker.reset()
    check("重置后清空", len(tracker._baseline) == 0 and len(tracker._changes) == 0)


# ============================================================
# 集成验证
# ============================================================
print("\n" + "=" * 60)
print("集成验证")
print("=" * 60)

# agent_loop.py 集成检查点
try:
    import py_compile
    py_compile.compile(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "core", "agent_loop.py"),
        doraise=True
    )
    check("agent_loop.py 语法正确", True)

    al_source = open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "core", "agent_loop.py"),
        "r", encoding="utf-8"
    ).read()
    check("agent_loop.py 创建检查点", "get_checkpoint_manager" in al_source)
    check("agent_loop.py create_checkpoint 调用", "create_checkpoint" in al_source)
except Exception as e:
    check("agent_loop.py 集成检查", False, str(e))

# 命令注册验证
try:
    from commands.registry import COMMAND_REGISTRY
    check("/rewind 命令已注册", "rewind" in COMMAND_REGISTRY)
except Exception as e:
    check("/rewind 命令注册", False, str(e))

# 所有文件语法检查
for filepath in [
    "commands/builtin/rewind_command.py",
    "services/diagnostic_tracker.py",
    "services/__init__.py",
]:
    full = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filepath)
    try:
        py_compile.compile(full, doraise=True)
        check(f"{os.path.basename(filepath)} 语法正确", True)
    except Exception as e:
        check(f"{os.path.basename(filepath)} 语法正确", False, str(e))


# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"测试完成: {PASS}/{total} 通过, {FAIL} 失败")
if FAIL > 0:
    print("⚠️ 有测试失败!")
    sys.exit(1)
else:
    print("🎉 全部通过!")
    sys.exit(0)
