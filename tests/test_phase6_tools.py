"""
Phase 6 测试: Subagent(并行任务)

测试内容:
1. Subagent 创建和执行
2. 并发控制
3. 结果获取
4. 状态管理
5. 统计信息
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.subagent import SubagentManager, subagent_manager


def test_spawn_subagent():
    """测试 1: 创建 Subagent"""
    print("=" * 60)
    print("测试 1: 创建 Subagent")
    print("=" * 60)
    
    # 创建一个测试管理器
    manager = SubagentManager(max_concurrent=3)
    
    # 创建 Subagent(后台运行)
    handle = manager.spawn_subagent(
        task="分析代码库结构",
        model="glm-4-plus",
        run_in_background=True
    )
    
    print(f"✅ Subagent 创建成功")
    print(f"   Agent ID: {handle.agent_id}")
    print(f"   任务: {handle.task}")
    print(f"   状态: {handle.status}")
    print()
    
    # 等待完成
    result = manager.join_subagent(handle.agent_id, timeout=30)
    print(f"✅ Subagent 执行完成")
    print(f"   结果长度: {len(result)} 字符")
    print()
    
    assert handle.status == "completed", "状态应该是 completed"
    assert handle.result is not None, "结果不应为空"
    print("✅ 测试 1 通过\n")


def test_synchronous_execution():
    """测试 2: 同步执行"""
    print("=" * 60)
    print("测试 2: 同步执行")
    print("=" * 60)
    
    manager = SubagentManager(max_concurrent=3)
    
    # 同步执行(等待完成)
    handle = manager.spawn_subagent(
        task="生成测试报告",
        model="glm-4-plus",
        run_in_background=False
    )
    
    print(f"✅ Subagent 同步执行完成")
    print(f"   Agent ID: {handle.agent_id}")
    print(f"   状态: {handle.status}")
    print()
    
    assert handle.status == "completed", "状态应该是 completed"
    assert handle.result is not None, "结果不应为空"
    print("✅ 测试 2 通过\n")


def test_concurrent_control():
    """测试 3: 并发控制"""
    print("=" * 60)
    print("测试 3: 并发控制")
    print("=" * 60)
    
    manager = SubagentManager(max_concurrent=2)
    
    # 创建 2 个 Subagent(达到限制)
    handle1 = manager.spawn_subagent(task="任务 1", run_in_background=True)
    handle2 = manager.spawn_subagent(task="任务 2", run_in_background=True)
    
    print(f"✅ 创建 2 个 Subagent")
    print(f"   Agent 1: {handle1.agent_id}")
    print(f"   Agent 2: {handle2.agent_id}")
    
    # 尝试创建第 3 个(应该失败)
    try:
        handle3 = manager.spawn_subagent(task="任务 3", run_in_background=True)
        print("❌ 应该抛出并发数限制错误")
        assert False, "应该抛出异常"
    except RuntimeError as e:
        print(f"✅ 正确触发并发数限制: {str(e)[:50]}...")
    
    print()
    
    # 等待前两个完成
    manager.join_subagent(handle1.agent_id, timeout=30)
    manager.join_subagent(handle2.agent_id, timeout=30)
    
    # 现在应该可以创建新的
    handle3 = manager.spawn_subagent(task="任务 3", run_in_background=True)
    print(f"✅ 等待完成后成功创建第 3 个 Subagent")
    
    manager.join_subagent(handle3.agent_id, timeout=30)
    print("✅ 测试 3 通过\n")


def test_list_agents():
    """测试 4: 列出所有 Agent"""
    print("=" * 60)
    print("测试 4: 列出所有 Agent")
    print("=" * 60)
    
    manager = SubagentManager(max_concurrent=5)
    
    # 创建 3 个 Subagent
    handles = []
    for i in range(3):
        handle = manager.spawn_subagent(
            task=f"任务 {i+1}",
            run_in_background=True
        )
        handles.append(handle)
        print(f"   创建 Agent {i+1}: {handle.agent_id}")
    
    # 列出所有
    agents = manager.list_agents()
    print(f"\n✅ 当前共有 {len(agents)} 个 Subagent")
    
    # 等待所有完成
    for handle in handles:
        manager.join_subagent(handle.agent_id, timeout=30)
    
    # 再次列出
    agents = manager.list_agents()
    print(f"✅ 所有任务完成后仍有 {len(agents)} 个记录")
    
    # 获取运行中的
    running = manager.get_running_agents()
    print(f"✅ 运行中的 Subagent: {len(running)}")
    
    assert len(agents) == 3, "应该有 3 个记录"
    assert len(running) == 0, "应该没有运行中的"
    print("✅ 测试 4 通过\n")


def test_stats():
    """测试 5: 统计信息"""
    print("=" * 60)
    print("测试 5: 统计信息")
    print("=" * 60)
    
    manager = SubagentManager(max_concurrent=5)
    
    # 创建并完成任务
    handle1 = manager.spawn_subagent(task="任务 1", run_in_background=False)
    handle2 = manager.spawn_subagent(task="任务 2", run_in_background=False)
    
    # 获取统计
    stats = manager.get_stats()
    print(f"✅ 统计信息:")
    print(f"   总计: {stats['total']}")
    print(f"   运行中: {stats['running']}")
    print(f"   已完成: {stats['completed']}")
    print(f"   失败: {stats['failed']}")
    
    assert stats['total'] == 2, "总计应该是 2"
    assert stats['completed'] == 2, "已完成应该是 2"
    assert stats['running'] == 0, "运行中应该是 0"
    print("✅ 测试 5 通过\n")


def test_agent_status():
    """测试 6: 获取单个 Agent 状态"""
    print("=" * 60)
    print("测试 6: 获取单个 Agent 状态")
    print("=" * 60)
    
    manager = SubagentManager(max_concurrent=5)
    
    handle = manager.spawn_subagent(task="状态测试", run_in_background=True)
    
    # 获取状态
    status = manager.get_agent_status(handle.agent_id)
    print(f"✅ Agent 状态:")
    print(f"   ID: {status['agent_id']}")
    print(f"   任务: {status['task']}")
    print(f"   状态: {status['status']}")
    
    # 等待完成
    manager.join_subagent(handle.agent_id, timeout=30)
    
    # 再次获取
    status = manager.get_agent_status(handle.agent_id)
    print(f"✅ 完成后状态: {status['status']}")
    
    assert status['status'] == 'completed', "状态应该是 completed"
    print("✅ 测试 6 通过\n")


def test_error_handling():
    """测试 7: 错误处理"""
    print("=" * 60)
    print("测试 7: 错误处理")
    print("=" * 60)
    
    manager = SubagentManager(max_concurrent=5)
    
    # 尝试获取不存在的 Agent
    try:
        manager.get_agent_status("nonexistent")
        assert False, "应该抛出 KeyError"
    except KeyError as e:
        print(f"✅ 正确捕获不存在 Agent 错误")
    
    try:
        manager.join_subagent("nonexistent")
        assert False, "应该抛出 KeyError"
    except KeyError as e:
        print(f"✅ 正确捕获 join 不存在 Agent 错误")
    
    print("✅ 测试 7 通过\n")


def test_global_manager():
    """测试 8: 全局管理器"""
    print("=" * 60)
    print("测试 8: 全局管理器")
    print("=" * 60)
    
    # 使用全局管理器
    handle = subagent_manager.spawn_subagent(
        task="全局管理器测试",
        run_in_background=False
    )
    
    print(f"✅ 全局管理器创建 Subagent: {handle.agent_id}")
    print(f"   状态: {handle.status}")
    
    assert handle.status == "completed"
    print("✅ 测试 8 通过\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Phase 6: Subagent 测试")
    print("=" * 60 + "\n")
    
    tests = [
        test_spawn_subagent,
        test_synchronous_execution,
        test_concurrent_control,
        test_list_agents,
        test_stats,
        test_agent_status,
        test_error_handling,
        test_global_manager,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ 测试失败: {test_func.__name__}")
            print(f"   错误: {str(e)}")
            import traceback
            traceback.print_exc()
            print()
            failed += 1
    
    # 总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"总测试数: {len(tests)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    
    if failed == 0:
        print("\n✅ 所有测试通过!")
        return 0
    else:
        print(f"\n❌ {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
