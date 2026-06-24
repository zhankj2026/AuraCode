"""
Phase 3 测试 - 工具集成

测试 Dynamic Workflows 的 4 个核心工具。
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.builtin.workflow_tools import (
    dynamic_workflow_handler,
    workflow_status_handler,
    save_workflow_handler,
    execute_saved_workflow_handler,
)
from core.coordinator import coordinator
from core.workflow_types import create_simple_workflow


def test_dynamic_workflow_preview():
    """测试 dynamic_workflow 预览模式"""
    print("=" * 60)
    print("测试 1: dynamic_workflow 预览模式")
    print("=" * 60)

    # 不自动审批，查看脚本预览
    result = dynamic_workflow_handler(
        task="审计 API endpoint 的认证检查",
        auto_approve=False,
        save_script=False
    )

    print(f"结果:\n{result}")

    # 验证返回预览
    assert "工作流脚本已生成" in result, "未显示脚本预览"
    assert "审批脚本" in result, "未提示审批"

    print(f"\n✅ 预览模式正常")
    return True


def test_dynamic_workflow_auto_approve():
    """测试 dynamic_workflow 自动审批"""
    print("\n" + "=" * 60)
    print("测试 2: dynamic_workflow 自动审批")
    print("=" * 60)

    # 自动审批并保存
    result = dynamic_workflow_handler(
        task="审计 API endpoint 的认证检查",
        auto_approve=True,
        save_script=True
    )

    print(f"结果:\n{result}")

    # 验证执行
    assert "已加载并准备执行" in result, "未加载工作流"
    assert "已保存" in result, "未保存脚本"

    print(f"\n✅ 自动审批正常")
    return True


def test_workflow_status():
    """测试 workflow_status"""
    print("\n" + "=" * 60)
    print("测试 3: workflow_status")
    print("=" * 60)

    # 查看状态
    result = workflow_status_handler()

    print(f"结果:\n{result}")

    # 验证显示状态
    assert "工作流进度" in result or "已保存的工作流脚本" in result, "未显示状态"

    print(f"\n✅ 状态查看正常")
    return True


def test_workflow_status_with_id():
    """测试 workflow_status 指定 ID"""
    print("\n" + "=" * 60)
    print("测试 4: workflow_status 指定 ID")
    print("=" * 60)

    # 先加载一个工作流
    workflow = create_simple_workflow(
        name="status-test",
        description="测试状态查询",
        stages=[
            {"name": "stage1", "agents": [{"prompt": "任务", "agent_type": "explore"}]}
        ]
    )

    coordinator.load_workflow_script(workflow)

    # 查看指定 ID
    result = workflow_status_handler(workflow_id="status-test")

    print(f"结果:\n{result}")

    # 验证显示指定工作流
    assert "status-test" in result or "工作流进度" in result, "未显示指定工作流"

    print(f"\n✅ 指定 ID 查询正常")
    return True


def test_save_workflow():
    """测试 save_workflow"""
    print("\n" + "=" * 60)
    print("测试 5: save_workflow")
    print("=" * 60)

    # 先加载一个工作流
    workflow = create_simple_workflow(
        name="save-test-workflow",
        description="测试保存工具",
        stages=[
            {"name": "stage1", "agents": [{"prompt": "任务", "agent_type": "explore"}]}
        ]
    )

    coordinator.load_workflow_script(workflow)

    # 保存工作流
    result = save_workflow_handler(
        name="test-save",
        description="测试保存工具"
    )

    print(f"结果:\n{result}")

    # 验证保存
    assert "已保存" in result, "未保存成功"
    assert "test-save" in result, "名称不匹配"

    # 验证文件存在
    script_file = os.path.join(".opencode", "workflows", "test-save.json")
    assert os.path.exists(script_file), f"脚本文件未保存: {script_file}"

    print(f"\n✅ 保存正常")
    return True


def test_execute_saved_workflow():
    """测试 execute_saved_workflow"""
    print("\n" + "=" * 60)
    print("测试 6: execute_saved_workflow")
    print("=" * 60)

    # 先保存一个工作流
    workflow = create_simple_workflow(
        name="execute-test",
        description="测试执行工具",
        stages=[
            {"name": "stage1", "agents": [{"prompt": "任务", "agent_type": "explore"}]}
        ]
    )

    coordinator.load_workflow_script(workflow)
    coordinator.save_workflow_script("execute-test", "测试执行工具")

    # 执行已保存的工作流
    result = execute_saved_workflow_handler(name="execute-test")

    print(f"结果:\n{result}")

    # 验证执行
    assert "已加载并准备执行" in result or "加载成功" in result, "未加载成功"

    print(f"\n✅ 执行已保存工作流正常")
    return True


def test_execute_saved_workflow_not_found():
    """测试 execute_saved_workflow 找不到脚本"""
    print("\n" + "=" * 60)
    print("测试 7: execute_saved_workflow 找不到脚本")
    print("=" * 60)

    # 尝试执行不存在的工作流
    result = execute_saved_workflow_handler(name="nonexistent-workflow")

    print(f"结果:\n{result}")

    # 验证错误提示
    assert "未找到" in result or "❌" in result, "未显示错误"

    print(f"\n✅ 错误处理正常")
    return True


def test_workflow_tools_integration():
    """测试工具集成工作流"""
    print("\n" + "=" * 60)
    print("测试 8: 工具集成工作流")
    print("=" * 60)

    # 1. 创建并预览工作流
    print("1. 预览工作流...")
    preview = dynamic_workflow_handler(
        task="集成测试工作流",
        auto_approve=False
    )
    assert "脚本已生成" in preview, "预览失败"
    print("   ✅ 预览成功")

    # 2. 自动审批并执行
    print("2. 执行工作流...")
    result = dynamic_workflow_handler(
        task="集成测试工作流",
        auto_approve=True,
        save_script=True
    )
    assert "准备执行" in result, "执行失败"
    print("   ✅ 执行成功")

    # 3. 查看状态
    print("3. 查看状态...")
    status = workflow_status_handler()
    assert "工作流" in status, "状态查询失败"
    print("   ✅ 状态查询成功")

    # 4. 保存工作流
    print("4. 保存工作流...")
    save_result = save_workflow_handler(
        name="integration-test",
        description="集成测试"
    )
    assert "已保存" in save_result, "保存失败"
    print("   ✅ 保存成功")

    # 5. 执行已保存的工作流
    print("5. 执行已保存的工作流...")
    exec_result = execute_saved_workflow_handler(name="integration-test")
    assert "加载" in exec_result, "执行已保存工作流失败"
    print("   ✅ 执行已保存工作流成功")

    print(f"\n🎉 工具集成工作流测试通过")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Phase 3 测试套件 - 工具集成")
    print("=" * 60 + "\n")

    tests = [
        ("dynamic_workflow 预览模式", test_dynamic_workflow_preview),
        ("dynamic_workflow 自动审批", test_dynamic_workflow_auto_approve),
        ("workflow_status", test_workflow_status),
        ("workflow_status 指定 ID", test_workflow_status_with_id),
        ("save_workflow", test_save_workflow),
        ("execute_saved_workflow", test_execute_saved_workflow),
        ("execute_saved_workflow 找不到脚本", test_execute_saved_workflow_not_found),
        ("工具集成工作流", test_workflow_tools_integration),
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
        print("\n🎉 所有测试通过！Phase 3 完成 - Dynamic Workflows 工具集成已就绪。")
        print("\n🎊🎊🎊 全部 3 个 Phase 完成！Dynamic Workflows 渐进增强方案已完整实施！🎊🎊🎊")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息。")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
