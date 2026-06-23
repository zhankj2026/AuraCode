"""
Dynamic Workflows 使用示例和测试

演示如何使用增强后的 SubagentOrchestrator 执行阶段化工作流。
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.workflow_types import WorkflowScript, WorkflowStage, AgentTask, AgentType, create_simple_workflow
from core.subagent import SubagentOrchestrator


def test_workflow_types():
    """测试工作流类型定义"""
    print("=" * 60)
    print("测试 1: 工作流类型定义")
    print("=" * 60)

    # 创建简单工作流
    workflow = create_simple_workflow(
        name="api-auth-audit",
        description="审计 API endpoint 的认证检查",
        stages=[
            {
                "name": "scan",
                "agents": [
                    {"prompt": "扫描 src/routes/ 下所有 API endpoint，检查是否有认证检查", "agent_type": "explore"},
                    {"prompt": "分析认证中间件的实现", "agent_type": "explore"},
                ],
                "depends": [],
                "synthesize": True,
                "synthesize_prompt": "汇总扫描结果，列出缺少认证检查的 endpoint"
            },
            {
                "name": "verify",
                "agents": [
                    {"prompt": "验证扫描发现的缺少认证的 endpoint，确认真实性", "agent_type": "review"},
                ],
                "depends": ["scan"],
                "synthesize": True,
            },
            {
                "name": "report",
                "agents": [
                    {"prompt": "生成审计报告，包含 endpoint 列表、风险等级、修复建议", "agent_type": "general"},
                ],
                "depends": ["verify"],
                "synthesize": False,
            }
        ]
    )

    # 验证脚本
    errors = workflow.validate()
    if errors:
        print(f"❌ 脚本验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False

    print(f"✅ 脚本验证通过")
    print(f"  名称: {workflow.name}")
    print(f"  阶段数: {len(workflow.stages)}")
    print(f"  描述: {workflow.description}")

    # 获取执行顺序
    order = workflow.get_execution_order()
    print(f"  执行顺序: {' -> '.join(order)}")

    # 转换为字典
    workflow_dict = workflow.to_dict()
    print(f"  序列化: ✅ (dict with {len(workflow_dict)} keys)")

    # 从字典恢复
    workflow_restored = WorkflowScript.from_dict(workflow_dict)
    print(f"  反序列化: ✅ (name={workflow_restored.name})")

    return True


def test_workflow_execution():
    """测试工作流执行（模拟）"""
    print("\n" + "=" * 60)
    print("测试 2: 工作流执行（模拟）")
    print("=" * 60)

    # 创建工作流
    workflow = create_simple_workflow(
        name="test-workflow",
        description="测试工作流执行",
        stages=[
            {
                "name": "research",
                "agents": [
                    {"prompt": "研究 Python 异步编程最佳实践", "agent_type": "explore"},
                ],
                "synthesize": False,
            },
            {
                "name": "implement",
                "agents": [
                    {"prompt": "基于研究结果，实现异步函数示例", "agent_type": "general"},
                ],
                "depends": ["research"],
                "synthesize": True,
            }
        ]
    )

    # 创建编排器
    orchestrator = SubagentOrchestrator()

    print(f"✅ 工作流创建成功")
    print(f"  阶段: {len(workflow.stages)}")
    print(f"  执行顺序: {' -> '.join(workflow.get_execution_order())}")

    # 注意：实际执行需要 LLM API，这里只验证流程
    print(f"\n⚠️  实际执行需要 LLM API 配置")
    print(f"  当前跳过执行，仅验证流程")

    # 验证中间存储
    orchestrator.clear_intermediate_store()
    print(f"  中间存储: ✅ (已清空)")

    return True


def test_complex_workflow():
    """测试复杂工作流（多依赖）"""
    print("\n" + "=" * 60)
    print("测试 3: 复杂工作流（多依赖）")
    print("=" * 60)

    # 创建复杂工作流
    workflow = create_simple_workflow(
        name="deep-research",
        description="深度研究（交叉验证）",
        stages=[
            {
                "name": "search",
                "agents": [
                    {"prompt": "搜索 Node.js v20 权限模型", "agent_type": "explore"},
                    {"prompt": "搜索 Node.js v22 权限模型", "agent_type": "explore"},
                    {"prompt": "搜索 v20 到 v22 的破坏性变更", "agent_type": "explore"},
                ],
                "depends": [],
                "synthesize": False,
            },
            {
                "name": "fetch",
                "agents": [
                    {"prompt": "获取并提取搜索结果的关键信息（来源 1-5）", "agent_type": "explore"},
                    {"prompt": "获取并提取搜索结果的关键信息（来源 6-10）", "agent_type": "explore"},
                ],
                "depends": ["search"],
                "synthesize": False,
            },
            {
                "name": "cross-check",
                "agents": [
                    {"prompt": "交叉检查不同来源的声明，识别矛盾", "agent_type": "review"},
                    {"prompt": "根据 Node.js 官方文档验证声明", "agent_type": "review"},
                ],
                "depends": ["fetch"],
                "synthesize": True,
                "synthesize_prompt": "综合交叉检查结果，过滤未通过验证的声明，生成可信结论列表"
            },
            {
                "name": "report",
                "agents": [
                    {"prompt": "编写引用报告，仅包含已验证的声明", "agent_type": "general"},
                ],
                "depends": ["cross-check"],
                "synthesize": False,
            }
        ]
    )

    # 验证脚本
    errors = workflow.validate()
    if errors:
        print(f"❌ 脚本验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False

    print(f"✅ 复杂工作流验证通过")
    print(f"  阶段数: {len(workflow.stages)}")
    print(f"  总 Agent 数: {sum(len(s.agents) for s in workflow.stages)}")
    print(f"  执行顺序: {' -> '.join(workflow.get_execution_order())}")

    # 显示阶段依赖
    for stage in workflow.stages:
        deps = f" (依赖: {', '.join(stage.depends)})" if stage.depends else ""
        print(f"  - {stage.name}: {len(stage.agents)} 个 Agent{deps}")

    return True


def test_workflow_serialization():
    """测试工作流序列化"""
    print("\n" + "=" * 60)
    print("测试 4: 工作流序列化")
    print("=" * 60)

    from core.workflow_types import workflow_from_json, workflow_to_json

    # 创建工作流
    workflow = create_simple_workflow(
        name="serialization-test",
        description="测试序列化",
        stages=[
            {
                "name": "stage1",
                "agents": [
                    {"prompt": "测试任务 1", "agent_type": "explore"},
                ],
            },
            {
                "name": "stage2",
                "agents": [
                    {"prompt": "测试任务 2", "agent_type": "general"},
                ],
                "depends": ["stage1"],
            }
        ]
    )

    # 序列化为 JSON
    json_str = workflow_to_json(workflow)
    print(f"✅ 序列化成功 ({len(json_str)} 字符)")
    print(f"  JSON 预览: {json_str[:100]}...")

    # 从 JSON 恢复
    workflow_restored = workflow_from_json(json_str)
    print(f"✅ 反序列化成功")
    print(f"  名称: {workflow_restored.name}")
    print(f"  阶段数: {len(workflow_restored.stages)}")

    # 验证恢复的工作流
    errors = workflow_restored.validate()
    if errors:
        print(f"❌ 恢复的脚本验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False

    print(f"✅ 恢复的脚本验证通过")

    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Dynamic Workflows 测试套件")
    print("=" * 60 + "\n")

    tests = [
        ("工作流类型定义", test_workflow_types),
        ("工作流执行（模拟）", test_workflow_execution),
        ("复杂工作流（多依赖）", test_complex_workflow),
        ("工作流序列化", test_workflow_serialization),
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
        print("\n🎉 所有测试通过！Dynamic Workflows 基础框架已就绪。")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息。")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
