#!/usr/bin/env python3
"""
快速测试脚本 - 验证模块导入和基本功能
不需要 API Key
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

print("="*60)
print("Claude Code Python MVP - 模块测试")
print("="*60)
print()

# 测试 1: 导入核心模块
print("测试 1: 导入核心模块...")
try:
    from core.message import create_user_message, validate_message_sequence
    print("✅ core.message 导入成功")
except Exception as e:
    print(f"❌ core.message 导入失败: {e}")
    sys.exit(1)

try:
    from core.context import load_project_context, detect_tech_stack
    print("✅ core.context 导入成功")
except Exception as e:
    print(f"❌ core.context 导入失败: {e}")
    sys.exit(1)

try:
    from tools.registry import TOOL_REGISTRY, get_tool_schemas, register_tool
    print("✅ tools.registry 导入成功")
except Exception as e:
    print(f"❌ tools.registry 导入失败: {e}")
    sys.exit(1)

try:
    from permissions.manager import PermissionManager
    print("✅ permissions.manager 导入成功")
except Exception as e:
    print(f"❌ permissions.manager 导入失败: {e}")
    sys.exit(1)

print()

# 测试 2: 消息管理
print("测试 2: 消息管理系统...")
try:
    msg = create_user_message("你好")
    assert msg["role"] == "user"
    assert msg["content"] == "你好"
    print("✅ 消息创建成功")
    
    messages = [
        {"role": "system", "content": "test"},
        {"role": "user", "content": "hello"}
    ]
    assert validate_message_sequence(messages) == True
    print("✅ 消息验证成功")
except Exception as e:
    print(f"❌ 消息管理测试失败: {e}")
    sys.exit(1)

print()

# 测试 3: 工具注册表
print("测试 3: 工具注册表...")
try:
    # 导入内置工具以触发注册
    import tools.builtin
    
    # 检查是否有工具注册
    assert len(TOOL_REGISTRY) > 0, "没有工具被注册"
    print(f"✅ 已注册 {len(TOOL_REGISTRY)} 个工具: {list(TOOL_REGISTRY.keys())}")
    
    # 获取工具 Schema
    schemas = get_tool_schemas()
    assert len(schemas) > 0
    print(f"✅ 生成 {len(schemas)} 个工具 Schema")
except Exception as e:
    print(f"❌ 工具注册表测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 测试 4: 权限管理器
print("测试 4: 权限管理器...")
try:
    pm = PermissionManager(mode="bypass")
    assert pm.check_permission("read_file", {"path": "test.txt"}) == True
    print("✅ Bypass 模式测试通过")
    
    pm_normal = PermissionManager(mode="plan")
    assert pm_normal.check_permission("write_file", {}) == False
    print("✅ Plan 模式拦截测试通过")
    
    # 黑名单测试
    result = pm.check_permission("run_command", {"command": "rm -rf /"})
    assert result == False
    print("✅ 黑名单检查测试通过")
except Exception as e:
    print(f"❌ 权限管理器测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 测试 5: 上下文加载
print("测试 5: 上下文加载...")
try:
    context = load_project_context(".")
    if context:
        print(f"✅ 上下文加载成功 (长度: {len(context)} 字符)")
    else:
        print("⚠️  未找到 CLAUDE.md (这是正常的)")
    
    tech_stack = detect_tech_stack(".")
    if tech_stack:
        print(f"✅ 技术栈检测: {tech_stack[:50]}...")
    else:
        print("⚠️  未检测到特定技术栈 (这是正常的)")
except Exception as e:
    print(f"❌ 上下文加载测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("="*60)
print("🎉 所有测试通过!")
print("="*60)
print()
print("下一步:")
print("1. 设置 API Key: $env:OPENAI_API_KEY='your-key'")
print("2. 运行 CLI: python cli.py --mode bypass '列出当前目录'")
print()
