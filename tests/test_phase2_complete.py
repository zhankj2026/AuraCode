"""Phase 2 完整测试 - 包括撤销功能"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools.builtin
from tools.registry import TOOL_REGISTRY
from tools.builtin import replace_in_file, undo_edit

print("="*60)
print("Phase 2 完整测试 (包括撤销)")
print("="*60)

# 清理旧的编辑历史
if os.path.exists(".backup/edit_history.json"):
    os.remove(".backup/edit_history.json")

# 创建测试文件
test_file = "test_undo_temp.txt"
with open(test_file, 'w', encoding='utf-8') as f:
    f.write("Original Content\n")
    f.write("Line 2\n")
    f.write("Line 3\n")

print(f"\n[测试 1] 创建测试文件")
print("原始内容:")
with open(test_file, 'r') as f:
    print(f.read())

# 测试第一次替换
print("\n[测试 2] 第一次替换")
result = replace_in_file.replace_in_file_handler(
    test_file,
    "Original Content",
    "Modified Content V1",
    show_diff=False
)
print(result)
assert "成功替换" in result
print("✅ 第一次替换成功")

# 测试第二次替换
print("\n[测试 3] 第二次替换")
result = replace_in_file.replace_in_file_handler(
    test_file,
    "Line 2",
    "Modified Line 2",
    show_diff=False
)
print(result)
assert "成功替换" in result
print("✅ 第二次替换成功")

# 查看编辑历史
print("\n[测试 4] 查看编辑历史")
result = undo_edit.edit_history_handler(limit=5)
print(result)
assert "编辑历史" in result
print("✅ 历史记录查询成功")

# 测试撤销
print("\n[测试 5] 撤销上次编辑")
result = undo_edit.undo_edit_handler()
print(result)
assert "已撤销" in result
print("✅ 撤销成功")

# 验证撤销后内容
print("\n[测试 6] 验证撤销后内容")
with open(test_file, 'r', encoding='utf-8') as f:
    content = f.read()
    print(content)
    assert "Modified Content V1" in content  # 第一次替换还在
    assert "Line 2" in content  # 第二次替换被撤销
print("✅ 撤销验证通过")

# 测试撤销指定文件
print("\n[测试 7] 撤销指定文件的编辑")
result = undo_edit.undo_edit_handler(path=test_file)
print(result)
assert "已撤销" in result
print("✅ 指定文件撤销成功")

# 验证完全恢复
print("\n[测试 8] 验证完全恢复")
with open(test_file, 'r', encoding='utf-8') as f:
    content = f.read()
    print(content)
    assert "Original Content" in content
    assert "Modified Content V1" not in content
print("✅ 完全恢复验证通过")

# 测试无历史可撤销
print("\n[测试 9] 测试无历史可撤销")
result = undo_edit.undo_edit_handler()
print(result)
assert "没有可撤销的操作" in result or "未找到" in result
print("✅ 空历史处理正确")

# 清理测试文件
if os.path.exists(test_file):
    os.remove(test_file)
print(f"\n[清理] 删除测试文件 {test_file}")

# 测试工具注册
print("\n[测试 10] 工具注册表")
print(f"总工具数: {len(TOOL_REGISTRY)}")
assert "replace_in_file" in TOOL_REGISTRY
assert "undo_edit" in TOOL_REGISTRY
assert "edit_history" in TOOL_REGISTRY
assert TOOL_REGISTRY["undo_edit"]["permission_level"] == "write"
assert TOOL_REGISTRY["edit_history"]["permission_level"] == "read"
print("✅ 工具注册测试通过")

print("\n" + "="*60)
print("✅ 所有 Phase 2 测试通过!")
print("="*60)
print("\nPhase 2 完成工具:")
print("  1. replace_in_file - 精确替换(含 diff)")
print("  2. undo_edit - 撤销编辑")
print("  3. edit_history - 查看历史")
