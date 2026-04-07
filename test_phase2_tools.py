"""Phase 2 工具测试"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools.builtin
from tools.registry import TOOL_REGISTRY
from tools.builtin import replace_in_file

print("="*60)
print("Phase 2 工具测试")
print("="*60)

# 创建测试文件
test_file = "test_replace_temp.txt"
with open(test_file, 'w', encoding='utf-8') as f:
    f.write("Hello World\n")
    f.write("This is a test file\n")
    f.write("Hello World again\n")

print(f"\n[测试 1] 创建测试文件: {test_file}")
print("原始内容:")
with open(test_file, 'r') as f:
    print(f.read())

# 测试替换
print("\n[测试 2] replace_in_file - 替换第一处匹配")
result = replace_in_file.replace_in_file_handler(
    test_file,
    "Hello World",
    "Hi Python",
    replace_all=False,
    show_diff=True
)
print(result)
assert "成功替换 1 处" in result
assert "差异对比" in result
print("✅ 替换测试通过")

# 验证文件内容
print("\n[测试 3] 验证文件内容")
with open(test_file, 'r', encoding='utf-8') as f:
    content = f.read()
    print(content)
    assert "Hi Python" in content
    assert content.count("Hello World") == 1  # 还有一处未替换
print("✅ 内容验证通过")

# 测试全部替换
print("\n[测试 4] replace_in_file - 替换所有匹配")
result = replace_in_file.replace_in_file_handler(
    test_file,
    "Hello World",
    "Hi Python",
    replace_all=True,
    show_diff=True
)
print(result)
assert "成功替换 1 处" in result  # 只剩 1 处
print("✅ 全部替换测试通过")

# 测试未找到匹配
print("\n[测试 5] 测试未找到匹配")
result = replace_in_file.replace_in_file_handler(
    test_file,
    "NOT_EXIST",
    "something",
    show_diff=False
)
print(result)
assert "未找到匹配" in result
print("✅ 错误处理测试通过")

# 测试备份文件
print("\n[测试 6] 验证备份文件")
backup_dir = ".backup"
if os.path.exists(backup_dir):
    backups = os.listdir(backup_dir)
    print(f"备份文件数: {len(backups)}")
    assert len(backups) >= 1  # 至少有 1 个备份
    print("✅ 备份测试通过")

# 清理测试文件
os.remove(test_file)
print(f"\n[清理] 删除测试文件 {test_file}")

# 测试工具注册
print("\n[测试 7] 工具注册表")
print(f"总工具数: {len(TOOL_REGISTRY)}")
assert "replace_in_file" in TOOL_REGISTRY
assert TOOL_REGISTRY["replace_in_file"]["permission_level"] == "write"
print("✅ 工具注册测试通过")

print("\n" + "="*60)
print("✅ 所有测试通过!")
print("="*60)
