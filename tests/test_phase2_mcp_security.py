"""
Phase 2 测试 - MCP 企业安全策略

测试允许列表/拒绝列表、命令匹配、URL 模式匹配。
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mcp.security import (
    McpSecurityPolicy,
    AllowedMcpServerEntry,
    DeniedMcpServerEntry,
    load_security_policy,
    is_mcp_server_allowed,
    initialize_security_policy,
    get_security_policy,
)


def test_basic_allowlist():
    """测试 1: 基础允许列表"""
    print("=" * 60)
    print("测试 1: 基础允许列表")
    print("=" * 60)
    
    policy = McpSecurityPolicy(
        allowlist=[
            AllowedMcpServerEntry(server_name="postgres"),
            AllowedMcpServerEntry(server_name="filesystem"),
        ]
    )
    
    # 允许的服务器
    assert policy.is_server_allowed("postgres") == True, "postgres 应该被允许"
    assert policy.is_server_allowed("filesystem") == True, "filesystem 应该被允许"
    
    # 不允许的服务器
    assert policy.is_server_allowed("unknown") == False, "unknown 应该被拒绝"
    
    print("✅ 基础允许列表测试通过")
    return True


def test_denylist_precedence():
    """测试 2: 拒绝列表优先级"""
    print("\n" + "=" * 60)
    print("测试 2: 拒绝列表优先级")
    print("=" * 60)
    
    policy = McpSecurityPolicy(
        allowlist=[
            AllowedMcpServerEntry(server_name="postgres"),
        ],
        denylist=[
            DeniedMcpServerEntry(server_name="postgres"),
        ]
    )
    
    # 拒绝列表优先
    assert policy.is_server_allowed("postgres") == False, "拒绝列表应该优先"
    
    print("✅ 拒绝列表优先级测试通过")
    return True


def test_command_matching():
    """测试 3: 命令精确匹配"""
    print("\n" + "=" * 60)
    print("测试 3: 命令精确匹配")
    print("=" * 60)
    
    policy = McpSecurityPolicy(
        allowlist=[
            AllowedMcpServerEntry(
                server_command=["npx", "-y", "@modelcontextprotocol/server-postgres"]
            ),
        ]
    )
    
    config = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
    }
    
    # 精确匹配
    assert policy.is_server_allowed("postgres", config) == True, "命令应该匹配"
    
    # 不匹配
    config2 = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@other/server"],
    }
    assert policy.is_server_allowed("other", config2) == False, "命令不应该匹配"
    
    print("✅ 命令精确匹配测试通过")
    return True


def test_url_pattern_matching():
    """测试 4: URL 模式匹配"""
    print("\n" + "=" * 60)
    print("测试 4: URL 模式匹配")
    print("=" * 60)
    
    policy = McpSecurityPolicy(
        allowlist=[
            AllowedMcpServerEntry(server_url="https://*.example.com/*"),
            AllowedMcpServerEntry(server_url="http://localhost:*"),
        ]
    )
    
    # 匹配通配符
    config1 = {"type": "sse", "url": "https://api.example.com/mcp"}
    assert policy.is_server_allowed("api", config1) == True, "URL 应该匹配 *.example.com"
    
    config2 = {"type": "sse", "url": "http://localhost:3000"}
    assert policy.is_server_allowed("local", config2) == True, "URL 应该匹配 localhost:*"
    
    # 不匹配
    config3 = {"type": "sse", "url": "https://malicious.com/mcp"}
    assert policy.is_server_allowed("malicious", config3) == False, "URL 不应该匹配"
    
    print("✅ URL 模式匹配测试通过")
    return True


def test_empty_allowlist():
    """测试 5: 空允许列表"""
    print("\n" + "=" * 60)
    print("测试 5: 空允许列表")
    print("=" * 60)
    
    # 空列表 = 全部拒绝
    policy = McpSecurityPolicy(allowlist=[])
    assert policy.is_server_allowed("any") == False, "空允许列表应该拒绝所有"
    
    # 无列表（None）= 全部允许
    policy2 = McpSecurityPolicy(allowlist=None)
    assert policy2.is_server_allowed("any") == True, "无允许列表应该允许所有"
    
    # 默认（None）= 全部允许
    policy3 = McpSecurityPolicy()
    assert policy3.is_server_allowed("any") == True, "默认应该允许所有"
    
    print("✅ 空允许列表测试通过")
    return True


def test_disabled_policy():
    """测试 6: 禁用策略"""
    print("\n" + "=" * 60)
    print("测试 6: 禁用策略")
    print("=" * 60)
    
    policy = McpSecurityPolicy(
        allowlist=[],  # 空列表
        enabled=False  # 禁用
    )
    
    # 禁用后应该允许所有
    assert policy.is_server_allowed("any") == True, "禁用策略应该允许所有"
    
    print("✅ 禁用策略测试通过")
    return True


def test_load_from_config():
    """测试 7: 从配置加载"""
    print("\n" + "=" * 60)
    print("测试 7: 从配置加载")
    print("=" * 60)
    
    config = {
        "mcp": {
            "security": {
                "enabled": True,
                "allowlist": [
                    {"server_name": "postgres"},
                    {"server_command": ["npx", "-y", "@modelcontextprotocol/server-filesystem"]},
                    {"server_url": "https://*.example.com/*"},
                ],
                "denylist": [
                    {"server_name": "dangerous-server"},
                ],
            }
        }
    }
    
    policy = load_security_policy(config)
    
    assert policy.enabled == True, "应该启用"
    assert len(policy.allowlist) == 3, "应该有 3 个允许条目"
    assert len(policy.denylist) == 1, "应该有 1 个拒绝条目"
    
    # 测试允许
    assert policy.is_server_allowed("postgres") == True
    assert policy.is_server_allowed("unknown") == False
    
    # 测试拒绝
    assert policy.is_server_allowed("dangerous-server") == False
    
    print("✅ 从配置加载测试通过")
    return True


def test_global_policy():
    """测试 8: 全局策略"""
    print("\n" + "=" * 60)
    print("测试 8: 全局策略")
    print("=" * 60)
    
    config = {
        "mcp": {
            "security": {
                "allowlist": [
                    {"server_name": "allowed-server"},
                ]
            }
        }
    }
    
    # 初始化全局策略
    initialize_security_policy(config)
    
    # 使用便捷函数
    assert is_mcp_server_allowed("allowed-server") == True, "应该允许"
    assert is_mcp_server_allowed("unknown") == False, "应该拒绝"
    
    print("✅ 全局策略测试通过")
    return True


def test_validation():
    """测试 9: 配置验证"""
    print("\n" + "=" * 60)
    print("测试 9: 配置验证")
    print("=" * 60)
    
    # 无效条目（多个字段）
    entry = AllowedMcpServerEntry(
        server_name="test",
        server_command=["cmd"],  # 两个字段
    )
    errors = entry.validate()
    assert len(errors) > 0, "应该验证失败"
    
    # 无效名称
    entry2 = AllowedMcpServerEntry(server_name="invalid name!")
    errors2 = entry2.validate()
    assert len(errors2) > 0, "名称应该验证失败"
    
    # 空命令 - 需要测试 policy.validate()
    policy = McpSecurityPolicy(
        allowlist=[AllowedMcpServerEntry(server_command=[])]
    )
    errors3 = policy.validate()
    assert len(errors3) > 0, "空命令应该验证失败"
    
    print("✅ 配置验证测试通过")
    return True


def test_integration_with_manager():
    """测试 10: 与 McpManager 集成"""
    print("\n" + "=" * 60)
    print("测试 10: 与 McpManager 集成")
    print("=" * 60)
    
    from mcp.manager import McpManager
    from mcp.config.types import McpStdioServerConfig
    
    # 初始化安全策略
    initialize_security_policy({
        "mcp": {
            "security": {
                "allowlist": [
                    {"server_name": "allowed"},
                ],
                "denylist": [
                    {"server_name": "denied"},
                ],
            }
        }
    })
    
    mgr = McpManager()
    
    # 测试配置转换
    config = McpStdioServerConfig(
        command="echo",
        args=["test"],
        env={"KEY": "value"}
    )
    config_dict = mgr._config_to_dict(config)
    
    assert config_dict["type"] == "stdio"
    assert config_dict["command"] == "echo"
    assert config_dict["args"] == ["test"]
    assert config_dict["env"] == {"KEY": "value"}
    
    print("✅ McpManager 集成测试通过")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Phase 2 测试套件 - MCP 企业安全策略")
    print("=" * 60 + "\n")
    
    tests = [
        ("基础允许列表", test_basic_allowlist),
        ("拒绝列表优先级", test_denylist_precedence),
        ("命令精确匹配", test_command_matching),
        ("URL 模式匹配", test_url_pattern_matching),
        ("空允许列表", test_empty_allowlist),
        ("禁用策略", test_disabled_policy),
        ("从配置加载", test_load_from_config),
        ("全局策略", test_global_policy),
        ("配置验证", test_validation),
        ("与 McpManager 集成", test_integration_with_manager),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {status}: {name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！Phase 2 完成 - MCP 企业安全策略已就绪。")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息。")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
