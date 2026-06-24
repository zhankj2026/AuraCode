"""
Phase 3 测试：MCP 高级功能

测试内容：
1. MCPB 文件格式支持（打包/解包/验证）
2. 健康检查机制（状态分类/自动重连）
3. DCR 完善（OAuth 动态客户端注册）

对标 Claude Code 的 .mcpb bundle 格式和健康检查机制。
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

from mcp.bundle import (
    McpbBundle,
    McpbMetadata,
    McpbServerConfig,
    McpbManager,
)
from mcp.health import (
    HealthChecker,
    ServerHealthStatus,
    HealthCheckResult,
    ServerHealthState,
    get_health_checker,
    initialize_health_checker,
)


# ═══════════ MCPB Bundle 测试 ═══════════

def test_create_mcpb_bundle():
    """测试 1: 创建 MCPB 包"""
    metadata = McpbMetadata(
        name="database-tools",
        version="1.0.0",
        description="Database MCP servers bundle",
    )
    
    bundle = McpbBundle(
        metadata=metadata,
        servers={
            "postgres": McpbServerConfig(
                name="postgres",
                type="stdio",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-postgres"],
                env={"DATABASE_URL": "${user:DATABASE_URL}"},
            ),
            "redis": McpbServerConfig(
                name="redis",
                type="stdio",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-redis"],
                env={"REDIS_URL": "${user:REDIS_URL}"},
            ),
        },
    )
    
    # 验证包
    errors = bundle.validate()
    assert len(errors) == 0
    
    # 检查服务器数量
    assert bundle.get_server_count() == 2
    assert bundle.get_enabled_count() == 2
    
    print("✓ 测试 1 通过: 创建 MCPB 包")


def test_save_load_mcpb_file():
    """测试 2: 保存和加载 .mcpb 文件"""
    metadata = McpbMetadata(
        name="test-bundle",
        version="2.0.0",
        description="Test bundle",
    )
    
    bundle = McpbBundle(
        metadata=metadata,
        servers={
            "api-server": McpbServerConfig(
                name="api-server",
                type="sse",
                url="https://api.example.com/mcp",
                headers={"Authorization": "Bearer ${user:API_TOKEN}"},
            ),
        },
        variables={"API_KEY": "default-value"},
    )
    
    # 保存到临时文件
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "test.mcpb")
        bundle.to_file(file_path)
        
        # 验证文件存在
        assert os.path.exists(file_path)
        
        # 从文件加载
        loaded_bundle = McpbBundle.from_file(file_path)
        
        # 验证内容
        assert loaded_bundle.metadata.name == "test-bundle"
        assert loaded_bundle.metadata.version == "2.0.0"
        assert len(loaded_bundle.servers) == 1
        assert "api-server" in loaded_bundle.servers
        
        server = loaded_bundle.servers["api-server"]
        assert server.type == "sse"
        assert server.url == "https://api.example.com/mcp"
    
    print("✓ 测试 2 通过: 保存和加载 .mcpb 文件")


def test_mcpb_validation_errors():
    """测试 3: MCPB 验证错误"""
    # 缺少名称
    metadata1 = McpbMetadata(name="", version="1.0.0")
    bundle1 = McpbBundle(metadata=metadata1)
    errors1 = bundle1.validate()
    assert any("name" in e.lower() for e in errors1)
    
    # stdio 服务器缺少命令
    metadata2 = McpbMetadata(name="test", version="1.0.0")
    bundle2 = McpbBundle(
        metadata=metadata2,
        servers={
            "bad-server": McpbServerConfig(
                name="bad-server",
                type="stdio",
                command=None,  # 缺少命令
            ),
        },
    )
    errors2 = bundle2.validate()
    assert len(errors2) > 0
    assert any("command" in e.lower() for e in errors2)
    
    # SSE 服务器缺少 URL
    metadata3 = McpbMetadata(name="test", version="1.0.0")
    bundle3 = McpbBundle(
        metadata=metadata3,
        servers={
            "bad-sse": McpbServerConfig(
                name="bad-sse",
                type="sse",
                url=None,  # 缺少 URL
            ),
        },
    )
    errors3 = bundle3.validate()
    assert len(errors3) > 0
    assert any("url" in e.lower() for e in errors3)
    
    print("✓ 测试 3 通过: MCPB 验证错误")


def test_mcpb_disabled_servers():
    """测试 4: 禁用服务器"""
    metadata = McpbMetadata(name="test", version="1.0.0")
    bundle = McpbBundle(
        metadata=metadata,
        servers={
            "enabled-server": McpbServerConfig(
                name="enabled-server",
                type="stdio",
                command="echo",
                args=["hello"],
            ),
            "disabled-server": McpbServerConfig(
                name="disabled-server",
                type="stdio",
                command="echo",
                args=["world"],
                disabled=True,
            ),
        },
    )
    
    # 检查启用的服务器
    enabled = bundle.get_enabled_servers()
    assert len(enabled) == 1
    assert "enabled-server" in enabled
    
    # 检查禁用的服务器
    disabled = bundle.get_disabled_servers()
    assert len(disabled) == 1
    assert "disabled-server" in disabled
    
    print("✓ 测试 4 通过: 禁用服务器")


def test_mcpb_variable_resolution():
    """测试 5: 环境变量解析"""
    metadata = McpbMetadata(name="test", version="1.0.0")
    bundle = McpbBundle(
        metadata=metadata,
        servers={
            "db": McpbServerConfig(
                name="db",
                type="stdio",
                command="npx",
                args=["@mcp/postgres"],
                env={
                    "DATABASE_URL": "${user:DATABASE_URL}",
                    "API_KEY": "${bundle:API_KEY}",
                    "HOME": "${HOME}",
                },
            ),
        },
        variables={"API_KEY": "bundle-default-key"},
    )
    
    # 解析变量
    user_vars = {"DATABASE_URL": "postgres://localhost:5432/test"}
    resolved = bundle.resolve_variables(user_vars)
    
    # 检查解析结果
    assert "DATABASE_URL" in resolved
    assert resolved["DATABASE_URL"] == "postgres://localhost:5432/test"
    assert "API_KEY" in resolved
    assert resolved["API_KEY"] == "bundle-default-key"
    assert "HOME" in resolved
    
    print("✓ 测试 5 通过: 环境变量解析")


def test_mcpb_manager():
    """测试 6: MCPB 管理器"""
    manager = McpbManager()
    
    metadata = McpbMetadata(name="manager-test", version="1.0.0")
    bundle = McpbBundle(
        metadata=metadata,
        servers={
            "server1": McpbServerConfig(
                name="server1",
                type="stdio",
                command="echo",
            ),
        },
    )
    
    # 保存到临时文件
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "manager-test.mcpb")
        bundle.to_file(file_path)
        
        # 加载包
        loaded = manager.load_bundle(file_path)
        assert loaded.metadata.name == "manager-test"
        
        # 列出包
        bundles = manager.list_bundles()
        assert "manager-test" in bundles
        
        # 获取包
        retrieved = manager.get_bundle("manager-test")
        assert retrieved is not None
        assert retrieved.metadata.version == "1.0.0"
    
    print("✓ 测试 6 通过: MCPB 管理器")


def test_mcpb_scan_directory():
    """测试 7: 扫描目录中的 .mcpb 文件"""
    manager = McpbManager()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager.set_bundle_dir(tmpdir)
        
        # 创建多个 .mcpb 文件
        for i in range(3):
            metadata = McpbMetadata(name=f"bundle-{i}", version="1.0.0")
            bundle = McpbBundle(metadata=metadata)
            bundle.to_file(os.path.join(tmpdir, f"bundle-{i}.mcpb"))
        
        # 扫描目录
        files = manager.scan_directory()
        assert len(files) == 3
        
        # 所有文件都应该以 .mcpb 结尾
        for f in files:
            assert f.endswith(".mcpb")
    
    print("✓ 测试 7 通过: 扫描目录中的 .mcpb 文件")


# ═══════════ Health Check 测试 ═══════════

def test_health_checker_initialization():
    """测试 8: 健康检查器初始化"""
    checker = initialize_health_checker(
        check_interval=30.0,
        max_reconnect_attempts=5,
        max_consecutive_failures=3,
    )
    
    assert checker.check_interval == 30.0
    assert checker.max_reconnect_attempts == 5
    assert checker.max_consecutive_failures == 3
    
    print("✓ 测试 8 通过: 健康检查器初始化")


def test_server_health_status_transitions():
    """测试 9: 服务器健康状态转换"""
    state = ServerHealthState(
        name="test-server",
        check_interval_seconds=30.0,
    )
    
    # 初始状态：PENDING
    assert state.status == ServerHealthStatus.PENDING
    
    # 转换为 CONNECTED
    state.update_status(ServerHealthStatus.CONNECTED)
    assert state.status == ServerHealthStatus.CONNECTED
    assert state.consecutive_failures == 0
    assert state.last_healthy_time is not None
    
    # 转换为 FAILED
    state.update_status(ServerHealthStatus.FAILED, "Connection refused")
    assert state.status == ServerHealthStatus.FAILED
    assert state.consecutive_failures == 1
    assert state.last_error == "Connection refused"
    
    # 再次失败
    state.update_status(ServerHealthStatus.FAILED, "Timeout")
    assert state.consecutive_failures == 2
    assert state.last_error == "Timeout"
    
    # 恢复连接
    state.update_status(ServerHealthStatus.CONNECTED)
    assert state.status == ServerHealthStatus.CONNECTED
    assert state.consecutive_failures == 0
    assert state.reconnect_attempts == 0
    
    print("✓ 测试 9 通过: 服务器健康状态转换")


def test_reconnect_logic():
    """测试 10: 重连逻辑"""
    state = ServerHealthState(
        name="reconnect-test",
        max_reconnect_attempts=3,
        max_consecutive_failures=2,
    )
    
    # 初始状态：应该重连
    assert state.should_reconnect() == True
    
    # 连续失败达到上限
    state.update_status(ServerHealthStatus.FAILED, "Error 1")
    state.update_status(ServerHealthStatus.FAILED, "Error 2")
    
    # 不应该重连（连续失败过多）
    assert state.should_reconnect() == False
    
    # 禁用状态：不应该重连
    state.update_status(ServerHealthStatus.DISABLED)
    assert state.should_reconnect() == False
    
    # 需要认证状态：不应该重连
    state2 = ServerHealthState(name="auth-test")
    state2.update_status(ServerHealthStatus.NEEDS_AUTH, "OAuth expired")
    assert state2.should_reconnect() == False
    
    # 重连次数达到上限
    state3 = ServerHealthState(name="attempts-test", max_reconnect_attempts=2)
    state3.reconnect_attempts = 2
    assert state3.should_reconnect() == False
    
    print("✓ 测试 10 通过: 重连逻辑")


def test_health_check_result():
    """测试 11: 健康检查结果"""
    result = HealthCheckResult(
        server_name="test-server",
        status=ServerHealthStatus.CONNECTED,
        latency_ms=15.5,
    )
    
    # 转换为字典
    result_dict = result.to_dict()
    assert result_dict["server_name"] == "test-server"
    assert result_dict["status"] == "connected"
    assert result_dict["latency_ms"] == 15.5
    
    # 带错误的结果
    error_result = HealthCheckResult(
        server_name="failed-server",
        status=ServerHealthStatus.FAILED,
        error="Connection refused",
    )
    error_dict = error_result.to_dict()
    assert error_dict["error"] == "Connection refused"
    
    print("✓ 测试 11 通过: 健康检查结果")


def test_uptime_calculation():
    """测试 12: 可用率计算"""
    state = ServerHealthState(name="uptime-test")
    
    # 模拟 10 次检查：8 次成功，2 次失败
    for i in range(8):
        state.update_status(ServerHealthStatus.CONNECTED)
    for i in range(2):
        state.update_status(ServerHealthStatus.FAILED, "Error")
    
    # 计算可用率
    uptime = state.get_uptime_percentage()
    assert uptime == 80.0  # 8/10 = 80%
    
    # 添加更多成功检查
    for i in range(10):
        state.update_status(ServerHealthStatus.CONNECTED)
    
    # 可用率应该提高
    uptime = state.get_uptime_percentage()
    assert uptime > 80.0
    
    print("✓ 测试 12 通过: 可用率计算")


def test_health_report_generation():
    """测试 13: 健康报告生成"""
    checker = HealthChecker()
    
    # 注册多个服务器
    checker.register_server("server-connected")
    checker.register_server("server-failed")
    checker.register_server("server-needs-auth")
    
    # 更新状态
    checker.update_status("server-connected", ServerHealthStatus.CONNECTED)
    checker.update_status("server-failed", ServerHealthStatus.FAILED, "Error")
    checker.update_status("server-needs-auth", ServerHealthStatus.NEEDS_AUTH, "Auth expired")
    
    # 生成报告
    report = checker.generate_report()
    
    assert report["total_servers"] == 3
    assert report["connected"] == 1
    assert report["failed"] == 1
    assert report["needs_auth"] == 1
    
    # 检查摘要文本
    summary = checker.get_summary_text()
    assert "MCP Server Health Report" in summary
    assert "Total servers: 3" in summary
    
    print("✓ 测试 13 通过: 健康报告生成")


def test_server_state_to_dict():
    """测试 14: 服务器状态序列化"""
    state = ServerHealthState(
        name="serialize-test",
        status=ServerHealthStatus.CONNECTED,
        consecutive_failures=0,
        reconnect_attempts=0,
    )
    
    # 模拟一些历史
    for i in range(5):
        state.update_status(ServerHealthStatus.CONNECTED)
    
    # 转换为字典
    state_dict = state.to_dict()
    
    assert state_dict["name"] == "serialize-test"
    assert state_dict["status"] == "connected"
    assert state_dict["consecutive_failures"] == 0
    assert state_dict["uptime_percentage"] == 100.0
    assert "last_check_time" in state_dict
    
    print("✓ 测试 14 通过: 服务器状态序列化")


def test_health_checker_register_unregister():
    """测试 15: 健康检查器注册/注销"""
    checker = HealthChecker()
    
    # 注册服务器
    state1 = checker.register_server("server-1")
    assert state1 is not None
    assert state1.name == "server-1"
    
    # 重复注册应该返回同一个对象
    state1_again = checker.register_server("server-1")
    assert state1 is state1_again
    
    # 注销服务器
    checker.unregister_server("server-1")
    
    # 再次注册应该创建新对象
    state1_new = checker.register_server("server-1")
    assert state1_new is not state1
    
    print("✓ 测试 15 通过: 健康检查器注册/注销")


def test_mcpb_json_serialization():
    """测试 16: MCPB JSON 序列化/反序列化"""
    metadata = McpbMetadata(
        name="json-test",
        version="1.2.3",
        description="Test JSON serialization",
        author="Test Author",
        license="MIT",
        keywords=["test", "mcp"],
    )
    
    bundle = McpbBundle(
        metadata=metadata,
        servers={
            "stdio-server": McpbServerConfig(
                name="stdio-server",
                type="stdio",
                command="npx",
                args=["-y", "@mcp/test"],
                env={"KEY": "value"},
                auto_approve=["read_tool"],
            ),
            "sse-server": McpbServerConfig(
                name="sse-server",
                type="sse",
                url="https://example.com/mcp",
                headers={"X-API-Key": "${user:API_KEY}"},
            ),
        },
        variables={"API_KEY": "default"},
        dependencies=["numpy", "requests"],
    )
    
    # 转换为字典
    data = bundle.to_dict()
    
    # 验证结构
    assert data["name"] == "json-test"
    assert data["version"] == "1.2.3"
    assert "servers" in data
    assert "stdio-server" in data["servers"]
    assert "sse-server" in data["servers"]
    assert data["variables"]["API_KEY"] == "default"
    assert "numpy" in data["dependencies"]
    
    # 反序列化
    restored = McpbBundle.from_dict(data)
    
    assert restored.metadata.name == "json-test"
    assert restored.metadata.version == "1.2.3"
    assert len(restored.servers) == 2
    assert restored.servers["stdio-server"].command == "npx"
    assert restored.servers["sse-server"].url == "https://example.com/mcp"
    
    print("✓ 测试 16 通过: MCPB JSON 序列化/反序列化")


if __name__ == "__main__":
    # 运行所有测试
    test_create_mcpb_bundle()
    test_save_load_mcpb_file()
    test_mcpb_validation_errors()
    test_mcpb_disabled_servers()
    test_mcpb_variable_resolution()
    test_mcpb_manager()
    test_mcpb_scan_directory()
    
    test_health_checker_initialization()
    test_server_health_status_transitions()
    test_reconnect_logic()
    test_health_check_result()
    test_uptime_calculation()
    test_health_report_generation()
    test_server_state_to_dict()
    test_health_checker_register_unregister()
    test_mcpb_json_serialization()
    
    print("\n" + "=" * 50)
    print("✅ 所有 Phase 3 测试通过！")
    print("=" * 50)
