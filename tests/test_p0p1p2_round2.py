"""P0/P1/P2 功能验证测试 — MCP深化 + 子代理协同 + 插件生态"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("P0: MCP 集成深化测试")
print("=" * 60)

from mcp.manager import McpManager

mgr = McpManager()

# 调用链追踪
rec_id = mgr.record_call_start("test-server", "list_files", {"path": "/src"})
mgr.record_call_end(rec_id, success=True)
rec_id2 = mgr.record_call_start("test-server", "read_file", {"file": "/src/main.py"})
mgr.record_call_end(rec_id2, success=True)
rec_id3 = mgr.record_call_start("test-server", "read_file", {"file": "/src/bad.py"})
mgr.record_call_end(rec_id3, success=False, error="file_not_found")

history = mgr.get_call_history()
assert len(history) == 3, f"Should have 3 records, got {len(history)}"
print(f"  [PASS] 调用链记录: {len(history)} 条")

# 统计
stats = mgr.get_call_stats()
assert "test-server::read_file" in stats, "Should have read_file stats"
rs = stats["test-server::read_file"]
assert rs["calls"] == 2, f"Should be 2 calls, got {rs['calls']}"
assert rs["errors"] == 1, f"Should be 1 error, got {rs['errors']}"
print(f"  [PASS] 调用统计: calls={rs['calls']}, errors={rs['errors']}, avg={rs['avg_ms']:.1f}ms")

# 调试报告
report = mgr.get_debug_report()
assert "servers" in report and "call_stats" in report and "cache" in report
print(f"  [PASS] 调试报告: {len(report)} 个字段")

# 自动发现 (不实际连接服务器，只测试解析)
discovered = mgr.discover_servers()
print(f"  [PASS] 自动发现: {len(discovered)} 个服务器 (可能为空，取决于环境)")

# 配置转换
from mcp.config.types import McpStdioServerConfig
cfg = mgr._dict_to_config("test", {"type": "stdio", "command": "node", "args": ["server.js"]})
assert cfg is not None and isinstance(cfg, McpStdioServerConfig), "Should create StdioConfig"
print(f"  [PASS] 配置转换: {type(cfg).__name__}")

print()
print("=" * 60)
print("P1: 子代理协同增强测试")
print("=" * 60)

from core.subagent import SubagentManager, AgentMailbox, SubagentOrchestrator, AgentMessage

# 邮箱测试
mailbox = AgentMailbox()
mailbox.register_agent("agent-a")
mailbox.register_agent("agent-b")

msg_id = mailbox.send("agent-a", "agent-b", "请帮我检查代码", msg_type="request")
assert msg_id.startswith("msg_"), "Should return msg ID"
print(f"  [PASS] 发送消息: {msg_id}")

# 接收
msgs = mailbox.receive("agent-b")
assert len(msgs) == 1, f"Should receive 1 message, got {len(msgs)}"
assert msgs[0].sender == "agent-a"
assert msgs[0].content == "请帮我检查代码"
print(f"  [PASS] 接收消息: sender={msgs[0].sender}, type={msgs[0].msg_type}")

# 广播
mailbox.send("agent-a", "*", "任务完成通知")
msgs_a = mailbox.receive("agent-a")
# agent-a 不应收到自己的广播
broadcast_b = mailbox.receive("agent-b")
assert len(broadcast_b) == 2, f"agent-b should have 2 messages, got {len(broadcast_b)}"
print(f"  [PASS] 广播消息: agent-b 收到 {len(broadcast_b)} 条")

# 对话历史
conv = mailbox.get_conversation("agent-a", "agent-b")
assert len(conv) >= 2, f"Should have 2+ messages in conversation"
print(f"  [PASS] 对话历史: {len(conv)} 条")

# 邮箱统计
m_stats = mailbox.get_stats()
assert m_stats["registered_agents"] == 2
assert m_stats["total_messages"] >= 2
print(f"  [PASS] 邮箱统计: agents={m_stats['registered_agents']}, msgs={m_stats['total_messages']}")

# 编排器 — 结果聚合
orch = SubagentOrchestrator()
orch.set_shared_context("project", "opencode")
assert orch.get_shared_context("project") == "opencode"
print("  [PASS] 共享上下文: 设置和获取")

# 聚合测试 (使用模拟数据)
mock_results = [
    {"agent_id": "a1", "task": "分析代码", "status": "completed",
     "result_preview": "## 发现\n代码结构良好\n**建议**: 添加类型注解"},
    {"agent_id": "a2", "task": "检查安全", "status": "completed",
     "result_preview": "## 发现\n无安全漏洞\nerror: none"},
    {"agent_id": "a3", "task": "性能分析", "status": "failed",
     "result_preview": "执行超时"},
]

agg = orch.aggregate_results(mock_results, strategy="summary")
assert agg["total_tasks"] == 3
assert agg["completed"] == 2
assert agg["failed"] == 1
assert abs(agg["success_rate"] - 2/3) < 0.01
assert "findings" in agg
print(f"  [PASS] 聚合(summary): success_rate={agg['success_rate']:.1%}, findings={len(agg['findings'])}")

agg_merge = orch.aggregate_results(mock_results, strategy="merge")
assert "merged_text" in agg_merge
print(f"  [PASS] 聚合(merge): {len(agg_merge['merged_text'])} 字符")

agg_vote = orch.aggregate_results(mock_results, strategy="vote")
assert "consensus" in agg_vote
print(f"  [PASS] 聚合(vote): agreement_count={agg_vote.get('agreement_count', 0)}")

print()
print("=" * 60)
print("P2: 插件生态建设测试")
print("=" * 60)

from plugins.registry import PluginRegistry, PluginManifest, PluginBus, DependencyResolver

# 插件清单
manifest = PluginManifest(
    name="test-plugin", version="1.0.0",
    description="测试插件",
    dependencies=["base-plugin"],
    provides=["formatting"],
    tags=["dev-tools"],
)
assert manifest.to_dict()["name"] == "test-plugin"
print(f"  [PASS] PluginManifest: {manifest.name} v{manifest.version}")

# 注册中心
reg = PluginRegistry()

# 创建模拟插件
class MockPlugin:
    name = "base-plugin"
    version = "1.0.0"
    description = "基础插件"
    def initialize(self): return True
    def cleanup(self): pass
    def is_available(self): return True
    def get_tools(self): return []
    def get_hooks(self): return []

class MockPlugin2:
    name = "format-plugin"
    version = "2.0.0"
    description = "格式化插件"
    dependencies = ["base-plugin"]
    provides = ["formatting"]
    def initialize(self): return True
    def cleanup(self): pass
    def is_available(self): return True
    def get_tools(self): return [{"name": "format", "description": "格式化代码"}]
    def get_hooks(self): return [{"event": "PostToolUse", "handler": lambda **kw: None}]

base = MockPlugin()
fmt = MockPlugin2()

entry1 = reg.register_plugin(base)
assert entry1.status == "registered"
entry2 = reg.register_plugin(fmt)
print(f"  [PASS] 注册插件: {len(reg._entries)} 个")

# 激活
results = reg.start_all()
assert results.get("base-plugin") == True, "base-plugin should activate"
assert results.get("format-plugin") == True, "format-plugin should activate"
print(f"  [PASS] 启动所有插件: {sum(v for v in results.values() if v)}/{len(results)}")

# 查询
active = reg.get_active_plugins()
assert "base-plugin" in active and "format-plugin" in active
print(f"  [PASS] 活跃插件: {active}")

# 按能力查找
found = reg.find_by_capability("formatting")
assert "format-plugin" in found
print(f"  [PASS] 按能力查找: {found}")

# 统计
p_stats = reg.get_stats()
assert p_stats["total"] == 2 and p_stats["active"] == 2
print(f"  [PASS] 插件统计: {p_stats}")

# 事件总线
bus = PluginBus()
received = []
bus.subscribe("tool.called", lambda event, data: received.append(data))
bus.emit("tool.called", {"tool": "write_file"})
assert len(received) == 1
print(f"  [PASS] 事件总线: emit + subscribe")

# 请求-响应
bus.subscribe("get.version", lambda event, data: "1.0.0")
responses = bus.request("get.version", {})
assert len(responses) == 1 and responses[0] == "1.0.0"
print(f"  [PASS] 请求-响应: {responses}")

# 依赖解析
resolver = DependencyResolver()
resolver.add_plugin("a", [])
resolver.add_plugin("b", ["a"])
resolver.add_plugin("c", ["b"])
resolver.add_plugin("d", ["a", "c"])

order = resolver.resolve_load_order()
assert order.index("a") < order.index("b"), "a should load before b"
assert order.index("b") < order.index("c"), "b should load before c"
print(f"  [PASS] 拓扑排序: {' → '.join(order)}")

# 循环依赖检测
resolver2 = DependencyResolver()
resolver2.add_plugin("x", ["y"])
resolver2.add_plugin("y", ["z"])
resolver2.add_plugin("z", ["x"])
cycles = resolver2.detect_cycles()
assert len(cycles) > 0, "Should detect cycle"
print(f"  [PASS] 循环依赖检测: {cycles}")

# 缺失依赖
missing = resolver.get_missing_dependencies("nonexistent")
assert missing == []
missing_b = resolver.get_missing_dependencies("b")
assert missing_b == []
print(f"  [PASS] 缺失依赖检查: none missing")

# 停用 + 注销
reg.deactivate_plugin("format-plugin")
assert "format-plugin" not in reg.get_active_plugins()
print(f"  [PASS] 停用插件")

reg.unregister_plugin("format-plugin")
assert reg.get_plugin("format-plugin") is None
print(f"  [PASS] 注销插件")

print()
print("=" * 60)
print("命令系统集成测试")
print("=" * 60)

from commands.registry import COMMAND_REGISTRY
print(f"  总命令数: {len(COMMAND_REGISTRY)}")
print(f"  包含 plugins: {'plugins' in COMMAND_REGISTRY}")
print(f"  包含 tools: {'tools' in COMMAND_REGISTRY}")
print(f"  包含 mcp: {'mcp' in COMMAND_REGISTRY}")

print()
print("ALL TESTS PASSED!")
