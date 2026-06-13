"""P0/P1/P2 功能验证测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("P0: 权限系统深化测试")
print("=" * 60)

from permissions.manager import PermissionManager, PermissionRule, ApprovalRequest

pm = PermissionManager(mode="auto")

# 测试规则匹配
rule = PermissionRule(pattern="run_command:git *", rule_type="allow")
assert rule.matches("run_command", {"command": "git status"}), "Should match git status"
assert not rule.matches("run_command", {"command": "rm -rf"}), "Should not match rm"
print("  [PASS] PermissionRule.matches() 模式匹配")

# 添加规则
pm.add_rule("allow", "read_file:*", source="test")
pm.add_rule("deny", "run_command:rm -rf*", source="test")
assert len(pm.get_rules()) == 2, "Should have 2 rules"
print("  [PASS] add_rule() / get_rules()")

# deny 规则生效 (使用不触发黑名单的命令)
pm.add_rule("deny", "run_command:curl *", source="test")
result = pm.check_permission("run_command", {"command": "curl http://evil.com"})
assert result == False, "Deny rule should block"
print("  [PASS] Deny 规则阻止")

# allow 规则生效
result = pm.check_permission("read_file", {"file_path": "/test.py"})
assert result == True, "Allow rule should pass"
print("  [PASS] Allow 规则放行")

# 统计
stats = pm.get_stats()
assert stats["rule_denied"] >= 1, "Should track rule denials"
print(f"  [PASS] 统计: allowed={stats['allowed']}, denied={stats['denied']}, rule_denied={stats['rule_denied']}")

# 审批队列
req = pm.request_approval("write_file", {"path": "/test.py"}, reason="test")
pm.respond_approval(req.request_id, "allow")
result = pm.wait_approval(req.request_id, timeout=1.0)
assert result == "allow", f"Should be allow, got {result}"
print("  [PASS] 审批队列: request → respond → wait")

# 批量批准
req1 = pm.request_approval("run_command", {"command": "ls"})
req2 = pm.request_approval("run_command", {"command": "pwd"})
count = pm.batch_approve()
assert count == 2, f"Should approve 2, got {count}"
print(f"  [PASS] 批量批准: {count} 个")

print()
print("=" * 60)
print("P1: Hook 系统完善测试")
print("=" * 60)

from hooks.manager import HookManager, HookResult

hm = HookManager()

# 注册中间件
async def test_middleware(event, tool_name, kwargs):
    kwargs["_middleware_ran"] = True
    return kwargs

mw_id = hm.register_middleware("before", test_middleware, priority=5)
assert mw_id >= 0, "Middleware ID should be valid"
print("  [PASS] register_middleware()")

# 健康状态
health = hm.get_health()
assert health["total_hooks"] == 0, "No hooks registered"
assert health["total_middlewares"] == 1, "1 middleware"
assert health["healthy"] == True, "Should be healthy"
print(f"  [PASS] get_health(): {health}")

# 错误隔离
import asyncio
async def failing_hook(**kwargs):
    raise RuntimeError("Hook failed!")

hook_id = hm.register_hook("PreToolUse", failing_hook)
result = asyncio.get_event_loop().run_until_complete(
    hm.execute_hooks("PreToolUse", tool_name="test")
)
assert result.allow == True, "Hook failure should not block"
assert hm._error_count >= 1, "Error should be tracked"
print(f"  [PASS] 错误隔离: Hook 失败不阻止执行, errors={hm._error_count}")

# 热重载 (不实际启动监听，只测试 API)
hm.set_reload_callback(lambda: None)
assert hm._reload_callback is not None
print("  [PASS] set_reload_callback()")

print()
print("=" * 60)
print("P2: Bridge 远程控制增强测试")
print("=" * 60)

from bridge.types import SessionConfig, BridgeEvent
from bridge.session import BridgeSession
from bridge.manager import BridgeSessionManager

# 事件序列号与重放
config = SessionConfig(session_id="test-replay", model="test", permission_mode="bypass")
session = BridgeSession(config=config, event_callback=lambda e: None)

# 模拟发射事件
session._emit(BridgeEvent(type="test_1", session_id="test-replay", data={"v": 1}))
session._emit(BridgeEvent(type="test_2", session_id="test-replay", data={"v": 2}))
session._emit(BridgeEvent(type="test_3", session_id="test-replay", data={"v": 3}))

assert session.get_event_count() == 3, "Should have 3 events"
print("  [PASS] get_event_count()")

# 重放测试
replayed = session.replay_events(from_seq=1)
assert len(replayed) == 2, f"Should replay 2 events, got {len(replayed)}"
print(f"  [PASS] replay_events(from_seq=1): {len(replayed)} events")

# 序列号检查
events = session.get_events()
for i, e in enumerate(events):
    assert "_seq" in e["data"], f"Event {i} should have _seq"
print("  [PASS] 事件序列号 _seq 标记")

# 管理器重放 API
manager = BridgeSessionManager()
manager._sessions["test-replay"] = session
result = manager.replay_session_events("test-replay", from_seq=2)
assert result is not None and len(result) == 1, "Should replay 1 event"
print("  [PASS] manager.replay_session_events()")

print()
print("=" * 60)
print("命令系统集成测试")
print("=" * 60)

from commands.registry import COMMAND_REGISTRY
print(f"  总命令数: {len(COMMAND_REGISTRY)}")
print(f"  包含 tools: {'tools' in COMMAND_REGISTRY}")
print(f"  包含 model: {'model' in COMMAND_REGISTRY}")
print(f"  包含 permissions: {'permissions' in COMMAND_REGISTRY}")
print(f"  包含 hooks: {'hooks' in COMMAND_REGISTRY}")

print()
print("ALL TESTS PASSED!")
