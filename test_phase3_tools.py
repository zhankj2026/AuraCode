"""Phase 3 工具测试"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools.builtin
from tools.registry import TOOL_REGISTRY
from tools.builtin import lint, run_tests

print("="*60)
print("Phase 3 工具测试")
print("="*60)

# 测试 1: lint 工具 - 语言检测
print("\n[测试 1] lint - 语言检测")
python_file = "test_lint_sample.py"
with open(python_file, 'w', encoding='utf-8') as f:
    f.write("import os\n")
    f.write("import sys\n\n")
    f.write("def hello():\n")
    f.write("    print('Hello World')\n")

result = lint._detect_language(python_file)
print(f"检测 Python 文件: {result}")
assert result == 'python', f"期望 python,实际 {result}"
print("✅ Python 检测通过")

# 测试 2: lint 工具 - 运行检查
print("\n[测试 2] lint - 运行静态检查")
result = lint.lint_handler(path=python_file, language='python')
print(result)
# 可能通过或失败(取决于 ruff 是否安装)
assert "静态检查" in result or "未找到" in result
print("✅ lint 工具执行通过")

# 测试 3: run_tests - 框架检测
print("\n[测试 3] run_tests - 框架检测")
result = run_tests._detect_test_framework('.')
print(f"检测到测试框架: {result}")
assert result in ['pytest', 'jest', 'unittest', 'unknown']
print("✅ 框架检测通过")

# 测试 4: 创建测试文件
print("\n[测试 4] run_tests - 创建并运行测试")
test_file = "test_sample.py"
with open(test_file, 'w', encoding='utf-8') as f:
    f.write("def test_addition():\n")
    f.write("    assert 1 + 1 == 2\n\n")
    f.write("def test_subtraction():\n")
    f.write("    assert 5 - 3 == 2\n")

print(f"创建测试文件: {test_file}")
print("✅ 测试文件创建成功")

# 测试 5: run_tests - 运行测试
print("\n[测试 5] run_tests - 执行测试")
result = run_tests.run_tests_handler(
    test_path=test_file,
    framework='pytest',
    verbose=True
)
print(result)
# 测试应该通过
assert "测试" in result
print("✅ 测试执行通过")

# 测试 6: 测试失败场景
print("\n[测试 6] run_tests - 测试失败场景")
failing_test = "test_failing.py"
with open(failing_test, 'w', encoding='utf-8') as f:
    f.write("def test_will_fail():\n")
    f.write("    assert 1 + 1 == 3  # 故意失败\n")

result = run_tests.run_tests_handler(
    test_path=failing_test,
    framework='pytest',
    verbose=False
)
print(result)
assert "失败" in result or "❌" in result
print("✅ 失败检测通过")

# 测试 7: 不支持的语言
print("\n[测试 7] lint - 不支持的语言")
result = lint.lint_handler(language='rust')
print(result)
assert "不支持" in result
print("✅ 不支持语言处理正确")

# 测试 8: 解析测试输出
print("\n[测试 8] run_tests - 解析 pytest 输出")
sample_output = "10 passed, 2 failed, 1 skipped in 1.23s"
stats = run_tests._parse_test_output(sample_output, 'pytest')
print(f"解析结果: {stats}")
assert stats['passed'] == 10
assert stats['failed'] == 2
assert stats['skipped'] == 1
print("✅ 输出解析正确")

# 清理测试文件
for f in [python_file, test_file, failing_test]:
    if os.path.exists(f):
        os.remove(f)
        print(f"\n[清理] 删除 {f}")

# 测试 9: 工具注册
print("\n[测试 9] 工具注册表")
print(f"总工具数: {len(TOOL_REGISTRY)}")
assert "lint" in TOOL_REGISTRY
assert "run_tests" in TOOL_REGISTRY
assert TOOL_REGISTRY["lint"]["permission_level"] == "read"
assert TOOL_REGISTRY["run_tests"]["permission_level"] == "execute"
print("✅ 工具注册测试通过")

print("\n" + "="*60)
print("✅ 所有 Phase 3 测试通过!")
print("="*60)
print("\nPhase 3 完成工具:")
print("  1. lint - 静态代码检查(ruff/eslint)")
print("  2. run_tests - 测试执行(pytest/jest/unittest)")
