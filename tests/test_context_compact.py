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
ContextManager / 压缩触发 测试 — token 触发 / 读取占位 / 压后目标 / 开关

背景（demo8 会话日志 llm_25911457）: T41 压缩把早期 read_file 读入的
设计文档内容无差别吞进摘要（每条截 800 字符），T43 被迫重读同一文件；
条数阈值（假设每条消息 800 token）对大工具结果会话严重失真。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name, cond, err=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {err}")


# ============================================================
# 测试用 FakeLoop / FakeState
# ============================================================

class FakeState:
    def __init__(self, msgs):
        self.messages = msgs
        self.auto_compact_enabled = True
        self.last_main_prompt_tokens = 0

    def get_active_model(self, default=None):
        return "glm-4.7"


class FakeEvents:
    def status(self, *a, **k):
        pass

    def emit(self, *a, **k):
        pass

    def fire_lifecycle_hook(self, *a, **k):
        pass


class FakeLLM:
    """模拟压缩摘要 LLM 调用（非流式）"""

    summary_text = "摘要：完成了游戏核心模块开发。"

    class _Completions:
        def create(self, **kw):
            class R:
                pass
            r = R()
            r.choices = [type("C", (), {"message": type(
                "M", (), {"content": FakeLLM.summary_text})()})()]
            r.usage = None
            return r

    def __init__(self):
        chat = type("Chat", (), {})()
        chat.completions = self._Completions()
        self.chat = chat


class FakeLoop:
    def __init__(self, msgs):
        self.state = FakeState(msgs)
        self.events = FakeEvents()
        self.model = "glm-4.7"
        self.hooks_enabled = False
        self._cc_file_ops = []
        self.context_compact_threshold = 80
        self.client = FakeLLM()


def make_history():
    """构造含 read_file 长结果的会话历史"""
    doc = "游戏设计正文行。\n" * 300
    msgs = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "开发游戏"},
        {"role": "assistant", "content": "先读设计文档", "tool_calls": [
            {"id": "tc1", "type": "function", "function": {
                "name": "read_file",
                "arguments": '{"path": "GAME_DESIGN.md"}'}}]},
        {"role": "tool", "tool_call_id": "tc1",
         "content": "[GAME_DESIGN.md: lines 1-300 of 617]\n" + doc},
        {"role": "assistant", "content": "开始写代码"},
        {"role": "user", "content": "继续"},
        {"role": "assistant", "content": "好的"},
    ]
    return msgs


print("=" * 60)
print("ContextManager: token 触发 / 读取占位 / 压后目标 / 开关")
print("=" * 60)

from core.loop.context_manager import ContextManager, _READ_RANGE_RE  # noqa: E402
from core.loop.orchestrator import LoopOrchestrator  # noqa: E402

# ------------------------------------------------------------
# 1. 行范围头解析（原 "总行数:" 解析错配 bug 的修复）
# ------------------------------------------------------------
m = _READ_RANGE_RE.search("[F:\\demo\\GAME_DESIGN.md: lines 120-300 of 617]")
check("行范围头解析 s-e/total",
      m and (m.group(1), m.group(2), m.group(3)) == ("120", "300", "617"))
check("无范围头时不匹配", _READ_RANGE_RE.search("普通内容无头") is None)

# ------------------------------------------------------------
# 2. _shadow_old_reads：占位替换（原消息不被修改）
# ------------------------------------------------------------
loop = FakeLoop(make_history())
cm = ContextManager(loop)
old = loop.state.messages[1:-3]
shadow = cm._shadow_old_reads(old)

tc = [x for x in shadow if x.get("tool_call_id") == "tc1"][0]
check("read_file 长结果替换为占位", "已读取 GAME_DESIGN.md" in tc["content"])
check("占位含行段指针（第 1-300/617 行）", "第 1-300/617 行" in tc["content"])
check("占位含重读指引", "read_file 重新读取" in tc["content"])

orig = loop.state.messages[3]["content"]
check("原消息未被修改（摘要失败可回退）",
      orig.startswith("[GAME_DESIGN.md") and len(orig) > 2000)

# 全文读取（无范围头）→ 行数估算
loop_full = FakeLoop(make_history())
loop_full.state.messages[3]["content"] = "纯正文\n" * 400
cm_full = ContextManager(loop_full)
shadow_full = cm_full._shadow_old_reads(loop_full.state.messages[1:-3])
tc_full = [x for x in shadow_full if x.get("tool_call_id") == "tc1"][0]
check("全文读取占位含行数估算", "约 400 行" in tc_full["content"])

# 小读取 + 非 read_file 结果不占位
loop_small = FakeLoop(make_history())
loop_small.state.messages[3]["content"] = "短内容"
shadow_small = ContextManager(loop_small)._shadow_old_reads(
    loop_small.state.messages[1:-3])
tc_small = [x for x in shadow_small if x.get("tool_call_id") == "tc1"][0]
check("小读取不占位", tc_small["content"] == "短内容")

# ------------------------------------------------------------
# 3. compact: auto_compact_enabled=False 跳过
# ------------------------------------------------------------
loop_off = FakeLoop(make_history())
loop_off.state.auto_compact_enabled = False
loop_off.state.messages += [{"role": "user", "content": "x"}] * 200
ContextManager(loop_off).compact()
check("auto_compact_enabled=False 时跳过压缩",
      len(loop_off.state.messages) > 200)

# ------------------------------------------------------------
# 4. compact 端到端：摘要 + 重建 + 压后目标
# ------------------------------------------------------------
loop_c = FakeLoop(make_history())
for i in range(100):
    loop_c.state.messages.append({"role": "user", "content": f"m{i}"})
    loop_c.state.messages.append({"role": "assistant", "content": f"r{i}"})
before = len(loop_c.state.messages)
ContextManager(loop_c).compact()
after = len(loop_c.state.messages)
check("compact 压缩消息数", after < before, f"{before} → {after}")
check("保留 system + 摘要对 + 最近消息", after >= 8)
check("摘要消息进入历史",
      any("压缩摘要" in str(m.get("content", "")) for m in loop_c.state.messages))

# 压后目标：巨大 recent 消息时 keep 收缩（不高于估算目标线）
loop_big = FakeLoop(make_history())
big_blob = "巨大工具结果内容。" * 200_000  # ~1.6M chars
for i in range(60):
    loop_big.state.messages.append(
        {"role": "tool", "tool_call_id": f"t{i}", "content": big_blob})
for i in range(10):
    loop_big.state.messages.append({"role": "user", "content": "x"})
    loop_big.state.messages.append({"role": "assistant", "content": "y"})
before_big = len(loop_big.state.messages)
ContextManager(loop_big).compact()
after_big = len(loop_big.state.messages)
kept_chars = sum(len(str(m.get("content", ""))) for m in loop_big.state.messages)
check("巨大 recent 时 keep 收缩（消息数大幅下降）",
      after_big < before_big * 0.5, f"{before_big} → {after_big}")
check("压后字符量低于目标线（窗口50%当量）",
      kept_chars < 200_000 * 0.5 * 2.5 + 50_000,
      f"kept {kept_chars} chars")

# ------------------------------------------------------------
# 5. token 触发（orchestrator._run_context_maintenance）
# ------------------------------------------------------------
class RecordingCM:
    def __init__(self):
        self.compact_calls = 0

    def compact(self):
        self.compact_calls += 1

    def microcompact(self):
        return 0

    def context_collapse(self):
        return 0


# 5a. prompt_tokens 超过 窗口×阈值(0.7) → 触发
loop_tok = FakeLoop([{"role": "system", "content": "SYS"}] * 10)
loop_tok.state.last_main_prompt_tokens = 150_000  # 200k × 0.7 = 140k
loop_tok.context_manager = RecordingCM()
orch = LoopOrchestrator(loop_tok)
orch._run_context_maintenance()
check("token 超阈值触发压缩", loop_tok.context_manager.compact_calls == 1)

# 5b. 未超 → 不触发（走轻量路径）
loop_tok2 = FakeLoop([{"role": "system", "content": "SYS"}] * 10)
loop_tok2.state.last_main_prompt_tokens = 50_000
loop_tok2.context_manager = RecordingCM()
orch2 = LoopOrchestrator(loop_tok2)
orch2._run_context_maintenance()
check("token 未超阈值不压缩", loop_tok2.context_manager.compact_calls == 0)

# 5c. 无 usage（0）时走条数 fallback
loop_cnt = FakeLoop([{"role": "system", "content": "SYS"}] +
                    [{"role": "user", "content": "x"}] * 100)
loop_cnt.state.last_main_prompt_tokens = 0  # 无 usage 信息
loop_cnt.context_manager = RecordingCM()
orch3 = LoopOrchestrator(loop_cnt)
orch3._run_context_maintenance()
check("无 usage 时条数阈值 fallback 触发",
      loop_cnt.context_manager.compact_calls == 1)

# 5d. 两个阈值都未达 → 不压缩
loop_idle = FakeLoop([{"role": "system", "content": "SYS"}] +
                     [{"role": "user", "content": "x"}] * 10)
loop_idle.state.last_main_prompt_tokens = 10_000
loop_idle.context_manager = RecordingCM()
orch4 = LoopOrchestrator(loop_idle)
orch4._run_context_maintenance()
check("两个阈值均未达时不压缩", loop_idle.context_manager.compact_calls == 0)

# 5e. 阈值百分比读取（settings auto_compact_threshold 默认 0.7）
pct = orch4._auto_compact_threshold_pct()
check("auto_compact_threshold 读取正常（0.5~0.9 区间）", 0.5 <= pct <= 0.9,
      f"pct={pct}")

# ------------------------------------------------------------
# 6. Microcompact 活跃/热点文件保护（demo10 读→清→重读循环）
# ------------------------------------------------------------
class FakeOpsLoop(FakeLoop):
    def __init__(self, msgs, ops):
        super().__init__(msgs)
        self._cc_file_ops = ops


def _mk(msgs, role, **kw):
    msgs.append({**{"role": role}, **kw})


# 6a. 写活跃: 窗口内被写过的文件，其读取不被清理
msgs_a = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "t"}]
ops_a = []
_mk(msgs_a, "assistant", tool_calls=[
    {"id": "tcE", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/enemy.js"}'}}])
_mk(msgs_a, "tool", tool_call_id="tcE", content="enemy 全文\n" * 200)
ops_a.append((2, "read", "F:\\proj\\js\\enemy.js"))
_mk(msgs_a, "assistant", tool_calls=[
    {"id": "tcW", "type": "function", "function": {"name": "write_file",
     "arguments": '{"file_path": "F:/proj/js/enemy.js"}'}}])
_mk(msgs_a, "tool", tool_call_id="tcW", content="Wrote")
ops_a.append((4, "write", "F:\\proj\\js\\enemy.js"))
_mk(msgs_a, "assistant", tool_calls=[
    {"id": "tcP", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/player.js"}'}}])
_mk(msgs_a, "tool", tool_call_id="tcP", content="player 全文\n" * 200)
ops_a.append((6, "read", "F:\\proj\\js\\player.js"))
for i in range(12):
    _mk(msgs_a, "assistant", tool_calls=[
        {"id": f"n{i}", "type": "function",
         "function": {"name": "run_command", "arguments": '{"command":"x"}'}}])
    _mk(msgs_a, "tool", tool_call_id=f"n{i}", content="out")
ContextManager(FakeOpsLoop(msgs_a, ops_a)).microcompact()
get = lambda k: [x for x in msgs_a if x.get("tool_call_id") == k][0]
check("写活跃文件读取不被清理", "enemy 全文" in get("tcE")["content"])
check("非活跃文件正常清理", "[已读取" in get("tcP")["content"])

# 6b. 热点: 同文件窗口内读 ≥2 次 → 仅最近一次保留
msgs_b = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "t"}]
ops_b = []
_mk(msgs_b, "assistant", tool_calls=[
    {"id": "tC1", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/config.js"}'}}])
_mk(msgs_b, "tool", tool_call_id="tC1", content="config 旧内容\n" * 100)
ops_b.append((2, "read", "F:\\proj\\js\\config.js"))
for i in range(6):
    _mk(msgs_b, "assistant", tool_calls=[
        {"id": f"o{i}", "type": "function", "function": {
            "name": "read_file",
            "arguments": '{"path": "F:/proj/js/o%d.js"}' % i}}])
    _mk(msgs_b, "tool", tool_call_id=f"o{i}", content="x\n" * 100)
    ops_b.append((len(msgs_b) - 1, "read", "F:\\proj\\js\\o%d.js" % i))
_mk(msgs_b, "assistant", tool_calls=[
    {"id": "tC2", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/config.js"}'}}])
_mk(msgs_b, "tool", tool_call_id="tC2", content="config 最新内容\n" * 100)
ops_b.append((len(msgs_b) - 1, "read", "F:\\proj\\js\\config.js"))
for i in range(6):
    _mk(msgs_b, "assistant", tool_calls=[
        {"id": f"n{i}", "type": "function",
         "function": {"name": "run_command", "arguments": '{"command":"x"}'}}])
    _mk(msgs_b, "tool", tool_call_id=f"n{i}", content="out")
ContextManager(FakeOpsLoop(msgs_b, ops_b)).microcompact()
get_b = lambda k: [x for x in msgs_b if x.get("tool_call_id") == k][0]
check("热点文件最近一次读取保留", "config 最新内容" in get_b("tC2")["content"])
check("热点文件旧读取正常清理", "[已读取" in get_b("tC1")["content"])

# 6c. 窗口外写操作不保护
msgs_c = [{"role": "system", "content": "SYS"}]
ops_c = [(1, "write", "F:\\proj\\js\\old.js")]
_mk(msgs_c, "assistant", tool_calls=[
    {"id": "tcO", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/old.js"}'}}])
_mk(msgs_c, "tool", tool_call_id="tcO", content="old 全文\n" * 200)
ops_c.append((2, "read", "F:\\proj\\js\\old.js"))
msgs_c += [{"role": "user", "content": "m%d" % i} for i in range(45)]
for i in range(12):
    _mk(msgs_c, "assistant", tool_calls=[
        {"id": f"q{i}", "type": "function",
         "function": {"name": "run_command", "arguments": '{"command":"x"}'}}])
    _mk(msgs_c, "tool", tool_call_id=f"q{i}", content="out")
ContextManager(FakeOpsLoop(msgs_c, ops_c)).microcompact()
get_c = lambda k: [x for x in msgs_c if x.get("tool_call_id") == k][0]
check("窗口外写操作不再保护", "[已读取" in get_c("tcO")["content"])

check("MICROCOMPACT_KEEP_RECENT 提升至 10",
      ContextManager.MICROCOMPACT_KEEP_RECENT == 10)

# ------------------------------------------------------------
# 7. context_collapse: 读后被写 → 折叠（含行段信息）
# ------------------------------------------------------------
loop_cc = FakeLoop(make_history())
loop_cc.state.messages.append(
    {"role": "assistant", "content": "写文件", "tool_calls": [
        {"id": "tc2", "type": "function", "function": {
            "name": "write_file",
            "arguments": '{"path": "GAME_DESIGN.md"}'}}]})
loop_cc.state.messages.append(
    {"role": "tool", "tool_call_id": "tc2", "content": "Wrote 10 chars"})
loop_cc._cc_file_ops = [
    (3, "read", "F:\\demo\\GAME_DESIGN.md"),
    (8, "write", "F:\\demo\\GAME_DESIGN.md"),
]
folded = ContextManager(loop_cc).context_collapse()
content_after = loop_cc.state.messages[3]["content"]
check("读后被写 → 折叠", folded == 1)
check("折叠摘要含行段信息（解析修复后）",
      "第 1-300/617 行" in content_after, content_after[:80])

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"测试完成: {PASS}/{total} 通过, {FAIL} 失败")
if FAIL > 0:
    print("⚠️ 有测试失败!")
    sys.exit(1)
print("🎉 全部通过!")
sys.exit(0)
