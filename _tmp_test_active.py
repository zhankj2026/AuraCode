# -*- coding: utf-8 -*-
"""活跃/热点文件保护验证：复现 demo10 读→清→重读场景"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
from core.loop.context_manager import ContextManager


class FakeState:
    def __init__(self, msgs):
        self.messages = msgs

    def get_active_model(self, default=None):
        return "glm-4.7"


class FakeEvents:
    def status(self, *a, **k): pass
    def emit(self, *a, **k): pass
    def fire_lifecycle_hook(self, *a, **k): pass


class FakeLoop:
    def __init__(self, msgs, ops):
        self.state = FakeState(msgs)
        self.events = FakeEvents()
        self.model = "glm-4.7"
        self.hooks_enabled = False
        self._cc_file_ops = ops
        self.context_compact_threshold = 80


def mk(msgs, role, **kw):
    msgs.append({**{"role": role}, **kw})


# ── 场景 1：写活跃保护（demo10: 写入与重读间隔 27+ 条消息）──
msgs = [{"role": "system", "content": "SYS"},
        {"role": "user", "content": "task"}]
ops = []
mk(msgs, "assistant", content="读", tool_calls=[
    {"id": "tcE", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/enemy.js"}'}}])
mk(msgs, "tool", tool_call_id="tcE", content="enemy 全文内容\n" * 200)
ops.append((2, "read", "F:\\proj\\js\\enemy.js"))
mk(msgs, "assistant", content="改", tool_calls=[
    {"id": "tcW", "type": "function", "function": {"name": "write_file",
     "arguments": '{"file_path": "F:/proj/js/enemy.js"}'}}])
mk(msgs, "tool", tool_call_id="tcW", content="Wrote 100 lines")
ops.append((4, "write", "F:\\proj\\js\\enemy.js"))
mk(msgs, "assistant", content="读", tool_calls=[
    {"id": "tcP", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/player.js"}'}}])
mk(msgs, "tool", tool_call_id="tcP", content="player 全文内容\n" * 200)
ops.append((6, "read", "F:\\proj\\js\\player.js"))
for i in range(12):  # 12 个更新的结果挤出 KEEP_RECENT
    mk(msgs, "assistant", content="c", tool_calls=[
        {"id": f"tcN{i}", "type": "function",
         "function": {"name": "run_command", "arguments": '{"command": "x"}'}}])
    mk(msgs, "tool", tool_call_id=f"tcN{i}", content="out")

loop = FakeLoop(msgs, ops)
ContextManager(loop).microcompact()
enemy = [m for m in loop.state.messages if m.get("tool_call_id") == "tcE"][0]
player = [m for m in loop.state.messages if m.get("tool_call_id") == "tcP"][0]
assert "enemy 全文内容" in enemy["content"], "写活跃文件被误清: " + enemy["content"][:60]
assert "[已读取" in player["content"], "非活跃文件未被清理"
print("OK 场景1 写活跃保护: enemy.js(写过) 保留, player.js 正常清理")

# ── 场景 2：热点读取保护（同一文件被读 2 次 → 最近一次不清）──
msgs2 = [{"role": "system", "content": "SYS"},
         {"role": "user", "content": "task"}]
ops2 = []
# 第一次读 config.js（会被清）+ 中间其他读取
mk(msgs2, "assistant", content="读", tool_calls=[
    {"id": "tC1", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/config.js"}'}}])
mk(msgs2, "tool", tool_call_id="tC1", content="config 内容\n" * 100)
ops2.append((2, "read", "F:\\proj\\js\\config.js"))
for i in range(6):
    mk(msgs2, "assistant", content="r", tool_calls=[
        {"id": f"tO{i}", "type": "function", "function": {"name": "read_file",
         "arguments": '{"path": "F:/proj/js/other' + str(i) + '.js"}'}}])
    mk(msgs2, "tool", tool_call_id=f"tO{i}", content="other\n" * 100)
    ops2.append((len(msgs2) - 1, "read", f"F:\\proj\\js\\other{i}.js"))
# 第二次读 config.js（最近）→ hot
mk(msgs2, "assistant", content="再读", tool_calls=[
    {"id": "tC2", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/config.js"}'}}])
mk(msgs2, "tool", tool_call_id="tC2", content="config 最新内容\n" * 100)
ops2.append((len(msgs2) - 1, "read", "F:\\proj\\js\\config.js"))
for i in range(6):  # 再挤 6 个
    mk(msgs2, "assistant", content="c", tool_calls=[
        {"id": f"tN{i}", "type": "function",
         "function": {"name": "run_command", "arguments": '{"command": "x"}'}}])
    mk(msgs2, "tool", tool_call_id=f"tN{i}", content="out")

loop2 = FakeLoop(msgs2, ops2)
ContextManager(loop2).microcompact()
c1 = [m for m in loop2.state.messages if m.get("tool_call_id") == "tC1"][0]
c2 = [m for m in loop2.state.messages if m.get("tool_call_id") == "tC2"][0]
assert "config 最新内容" in c2["content"], "热点文件最近读取被误清: " + c2["content"][:60]
assert "[已读取" in c1["content"] or "[result cleared" in c1["content"]
print("OK 场景2 热点保护: config.js(读2次) 最近一次保留, 旧一次正常清理")

# ── 场景 3：窗口外的写不再保护 ──
msgs3 = [{"role": "system", "content": "SYS"}]
ops3 = [(1, "write", "F:\\proj\\js\\old.js")]
mk(msgs3, "assistant", content="读", tool_calls=[
    {"id": "tcO", "type": "function", "function": {"name": "read_file",
     "arguments": '{"path": "F:/proj/js/old.js"}'}}])
mk(msgs3, "tool", tool_call_id="tcO", content="old 全文\n" * 200)
ops3.append((2, "read", "F:\\proj\\js\\old.js"))
for i in range(45):  # 45 条消息把写操作挤出 40 条窗口
    msgs3.append({"role": "user", "content": f"m{i}"})
for i in range(12):
    mk(msgs3, "assistant", content="c", tool_calls=[
        {"id": f"tM{i}", "type": "function",
         "function": {"name": "run_command", "arguments": '{"command": "x"}'}}])
    mk(msgs3, "tool", tool_call_id=f"tM{i}", content="out")
loop3 = FakeLoop(msgs3, ops3)
ContextManager(loop3).microcompact()
old = [m for m in loop3.state.messages if m.get("tool_call_id") == "tcO"][0]
assert "[已读取" in old["content"] or "[result cleared" in old["content"]
print("OK 场景3 窗口外写操作不保护")

assert ContextManager.MICROCOMPACT_KEEP_RECENT == 10
print("OK KEEP_RECENT = 10")
print("\n全部通过")
