#!/usr/bin/env python3
"""
工具功能演示 - 直接测试内置工具
不需要 API Key
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# 导入工具注册表和内置工具
from tools.registry import TOOL_REGISTRY, get_tool_handler, get_tool_schemas
import tools.builtin

print("="*60)
print("Claude Code Python MVP - 工具功能演示")
print("="*60)
print()

# 演示 1: list_directory
print("演示 1: 列出当前目录")
print("-" * 60)
try:
    handler = get_tool_handler("list_directory")
    result = handler(path=".")
    print(result)
except Exception as e:
    print(f"❌ 错误: {e}")

print()

# 演示 2: read_file
print("演示 2: 读取 README.md")
print("-" * 60)
try:
    handler = get_tool_handler("read_file")
    if os.path.exists("README.md"):
        result = handler(path="README.md")
        # 只显示前500字符
        preview = result[:500] + "..." if len(result) > 500 else result
        print(preview)
    else:
        print("⚠️  README.md 不存在,跳过此演示")
except Exception as e:
    print(f"❌ 错误: {e}")

print()

# 演示 3: write_file (需要确认)
print("演示 3: 写入测试文件")
print("-" * 60)
try:
    handler = get_tool_handler("write_file")
    test_file = "test_output.txt"
    result = handler(path=test_file, content="这是 Claude Code Python MVP 的测试输出!\n生成时间: 2026-04-05")
    print(result)
    
    # 验证写入
    if os.path.exists(test_file):
        print(f"✅ 文件已创建: {test_file}")
        with open(test_file, "r", encoding="utf-8") as f:
            print(f"   内容预览: {f.read()[:50]}...")
        
        # 清理测试文件
        os.remove(test_file)
        print(f"✅ 测试文件已清理")
except Exception as e:
    print(f"❌ 错误: {e}")

print()

# 演示 4: run_command
print("演示 4: 执行命令 (python --version)")
print("-" * 60)
try:
    handler = get_tool_handler("run_command")
    result = handler(command="python --version")
    print(result.strip())
except Exception as e:
    print(f"❌ 错误: {e}")

print()

# 显示工具统计
print("="*60)
print("工具系统统计")
print("="*60)
print(f"已注册工具数: {len(TOOL_REGISTRY)}")
print(f"工具列表: {', '.join(TOOL_REGISTRY.keys())}")
print()

schemas = get_tool_schemas()
print(f"生成的 Schema 数量: {len(schemas)}")
for schema in schemas:
    func = schema["function"]
    print(f"  - {func['name']}: {func['description']}")

print()
print("🎉 工具演示完成!")
print()
print("下一步:")
print("  - 设置 API Key 后运行完整 Agent Loop")
print("  - 阅读 docs/03-tools-and-permissions.md 了解如何扩展工具")
