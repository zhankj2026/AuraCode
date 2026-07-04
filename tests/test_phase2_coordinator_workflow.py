#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
Phase 2 测试 - CoordinatorMode 工作流支持

测试 CoordinatorMode 增强的工作流脚本加载、执行、进度跟踪和保存功能。
"""
import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.coordinator import coordinator
from core.workflow_types import create_simple_workflow


def test_load_workflow_script():
    """测试加载工作流脚本"""
    print("=" * 60)
    print("测试 1: 加载工作流脚本")
    print("=" * 60)

    # 创建工作流
    workflow = create_simple_workflow(
        name="test-workflow",
        description="测试工作流加载",
        stages=[
            {
                "name": "research",
                "agents": [
                    {"prompt": "研究主题", "agent_type": "explore"},
                ],
            },
            {
                "name": "implement",
                "agents": [
                    {"prompt": "实现功能", "agent_type": "general"},
                ],
                "depends": ["research"],
            }
        ]
    )

    # 测试 Coordinator 加载
    coordinator.activate()
    result = coordinator.load_workflow_script(workflow)

    print(f"加载结果:\n{result}")

    # 验证内部状态
    assert coordinator._workflow_script is not None, "工作流脚本未加载"
    assert coordinator._workflow_script.name == "test-workflow", "工作流名称不匹配"
    assert coordinator._workflow_progress["status"] == "loaded", "进度状态不正确"
    assert coordinator._workflow_progress["stages_total"] == 2, "阶段总数不正确"

    print(f"\n✅ 加载成功")
    print(f"  脚本名称: {coordinator._workflow_script.name}")
    print(f"  阶段数: {coordinator._workflow_progress['stages_total']}")
    print(f"  进度状态: {coordinator._workflow_progress['status']}")

    return True


def test_load_workflow_from_dict():
    """测试从字典加载工作流"""
    print("\n" + "=" * 60)
    print("测试 2: 从字典加载工作流")
    print("=" * 60)

    workflow_dict = {
        "name": "dict-workflow",
        "description": "从字典加载",
        "stages": [
            {
                "name": "stage1",
                "agents": [
                    {"prompt": "任务 1", "agent_type": "explore"}
                ],
                "depends": [],
                "synthesize": True
            }
        ]
    }

    # 加载字典
    result = coordinator.load_workflow_script(workflow_dict)

    print(f"加载结果:\n{result}")

    # 验证
    assert coordinator._workflow_script.name == "dict-workflow", "名称不匹配"
    assert len(coordinator._workflow_script.stages) == 1, "阶段数不匹配"

    print(f"\n✅ 从字典加载成功")
    return True


def test_workflow_progress():
    """测试进度跟踪"""
    print("\n" + "=" * 60)
    print("测试 3: 进度跟踪")
    print("=" * 60)

    # 加载工作流
    workflow = create_simple_workflow(
        name="progress-test",
        description="测试进度跟踪",
        stages=[
            {"name": "s1", "agents": [{"prompt": "任务", "agent_type": "explore"}]},
            {"name": "s2", "agents": [{"prompt": "任务", "agent_type": "general"}], "depends": ["s1"]},
        ]
    )

    coordinator.load_workflow_script(workflow)

    # 获取进度
    progress = coordinator.get_workflow_progress()

    print(f"进度信息:")
    for key, value in progress.items():
        print(f"  {key}: {value}")

    # 验证进度字段
    assert "workflow_name" in progress, "缺少 workflow_name"
    assert "status" in progress, "缺少 status"
    assert "stages_completed" in progress, "缺少 stages_completed"
    assert "stages_total" in progress, "缺少 stages_total"

    print(f"\n✅ 进度跟踪正常")
    return True


def test_save_workflow_script():
    """测试保存工作流脚本"""
    print("\n" + "=" * 60)
    print("测试 4: 保存工作流脚本")
    print("=" * 60)

    # 加载工作流
    workflow = create_simple_workflow(
        name="save-test",
        description="测试保存功能",
        stages=[
            {"name": "stage1", "agents": [{"prompt": "任务", "agent_type": "explore"}]}
        ]
    )

    coordinator.load_workflow_script(workflow)

    # 保存脚本
    result = coordinator.save_workflow_script("test-workflow", "测试保存")

    print(f"保存结果:\n{result}")

    # 验证文件存在
    script_file = os.path.join(".auracode", "workflows", "test-workflow.json")
    assert os.path.exists(script_file), f"脚本文件未保存: {script_file}"

    # 验证文件内容
    with open(script_file, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)

    assert saved_data["name"] == "save-test", "保存的名称不匹配"
    assert len(saved_data["stages"]) == 1, "保存的阶段数不匹配"

    print(f"\n✅ 保存成功")
    print(f"  文件路径: {script_file}")
    print(f"  文件大小: {os.path.getsize(script_file)} 字节")

    return True


def test_workflow_execution_simulation():
    """测试工作流执行（模拟）"""
    print("\n" + "=" * 60)
    print("测试 5: 工作流执行（模拟）")
    print("=" * 60)

    # 加载工作流
    workflow = create_simple_workflow(
        name="execution-test",
        description="测试执行流程",
        stages=[
            {"name": "research", "agents": [{"prompt": "研究", "agent_type": "explore"}]},
            {"name": "implement", "agents": [{"prompt": "实现", "agent_type": "general"}], "depends": ["research"]},
        ]
    )

    coordinator.load_workflow_script(workflow)

    # 注意：实际执行需要 LLM API，这里只验证流程
    print(f"⚠️  实际执行需要 LLM API 配置")
    print(f"  当前跳过执行，仅验证流程")

    # 验证 execute_workflow 方法存在
    assert hasattr(coordinator, 'execute_workflow'), "缺少 execute_workflow 方法"

    # 验证进度更新
    progress_before = coordinator.get_workflow_progress()
    assert progress_before["status"] == "loaded", "执行前状态应为 loaded"

    print(f"\n✅ 执行流程验证通过")
    return True


def test_integration_workflow_lifecycle():
    """测试完整工作流生命周期"""
    print("\n" + "=" * 60)
    print("测试 6: 完整工作流生命周期")
    print("=" * 60)

    # 1. 创建工作流
    workflow = create_simple_workflow(
        name="lifecycle-test",
        description="完整生命周期测试",
        stages=[
            {
                "name": "scan",
                "agents": [
                    {"prompt": "扫描代码", "agent_type": "explore"},
                ],
            },
            {
                "name": "analyze",
                "agents": [
                    {"prompt": "分析结果", "agent_type": "review"},
                ],
                "depends": ["scan"],
                "synthesize": True,
            },
            {
                "name": "report",
                "agents": [
                    {"prompt": "生成报告", "agent_type": "general"},
                ],
                "depends": ["analyze"],
                "synthesize": False,
            }
        ]
    )

    print(f"1. 创建工作流 ✅")
    print(f"   名称: {workflow.name}")
    print(f"   阶段: {len(workflow.stages)}")

    # 2. 加载到 Coordinator
    result = coordinator.load_workflow_script(workflow)
    assert "加载成功" in result, "加载失败"
    print(f"2. 加载到 Coordinator ✅")

    # 3. 检查进度
    progress = coordinator.get_workflow_progress()
    assert progress["status"] == "loaded", "进度状态错误"
    print(f"3. 检查进度 ✅")
    print(f"   状态: {progress['status']}")
    print(f"   阶段: {progress['stages_completed']}/{progress['stages_total']}")

    # 4. 保存脚本
    save_result = coordinator.save_workflow_script("lifecycle-test", "生命周期测试")
    assert "已保存" in save_result, "保存失败"
    print(f"4. 保存脚本 ✅")

    # 5. 从文件重新加载
    script_file = os.path.join(".auracode", "workflows", "lifecycle-test.json")
    with open(script_file, 'r', encoding='utf-8') as f:
        loaded_dict = json.load(f)

    coordinator.load_workflow_script(loaded_dict)
    assert coordinator._workflow_script.name == "lifecycle-test", "重新加载失败"
    print(f"5. 从文件重新加载 ✅")

    print(f"\n🎉 完整生命周期测试通过")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Phase 2 测试套件 - CoordinatorMode 工作流支持")
    print("=" * 60 + "\n")

    tests = [
        ("加载工作流脚本", test_load_workflow_script),
        ("从字典加载工作流", test_load_workflow_from_dict),
        ("进度跟踪", test_workflow_progress),
        ("保存工作流脚本", test_save_workflow_script),
        ("工作流执行（模拟）", test_workflow_execution_simulation),
        ("完整工作流生命周期", test_integration_workflow_lifecycle),
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
        print("\n🎉 所有测试通过！Phase 2 完成 - CoordinatorMode 工作流支持已就绪。")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息。")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
