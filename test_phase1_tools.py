"""Phase 1 工具测试"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools.builtin
from tools.registry import TOOL_REGISTRY
from tools.builtin import grep, find, analyze_file

print("="*60)
print("Phase 1 工具测试")
print("="*60)

# 测试 1: grep
print("\n[测试 1] grep 工具 - 搜索 'class' 关键字")
result = grep.grep_handler('class', '.', '*.py', max_lines=5)
print(result)
assert '找到' in result
print("✅ grep 测试通过")

# 测试 2: find
print("\n[测试 2] find 工具 - 查找 .py 文件")
result = find.find_handler('.', '*.py', 'file', 2, 5)
print(result)
assert '找到' in result
print("✅ find 测试通过")

# 测试 3: analyze_file
print("\n[测试 3] analyze_file 工具 - 分析 agent_loop.py")
result = analyze_file.analyze_file_handler('core/agent_loop.py')
data = json.loads(result)
print(f"文件: {data['file']}")
print(f"行数: {data['line_count']}")
print(f"类: {[c['name'] for c in data['classes']]}")
print(f"函数: {[f['name'] for f in data['functions']]}")
assert data['stats']['class_count'] >= 1
print("✅ analyze_file 测试通过")

# 测试 4: 工具注册
print("\n[测试 4] 工具注册表")
print(f"总工具数: {len(TOOL_REGISTRY)}")
print(f"Phase 1 工具: {[t for t in ['grep', 'find', 'analyze_file'] if t in TOOL_REGISTRY]}")
assert all(t in TOOL_REGISTRY for t in ['grep', 'find', 'analyze_file'])
print("✅ 工具注册测试通过")

print("\n" + "="*60)
print("✅ 所有测试通过!")
print("="*60)
