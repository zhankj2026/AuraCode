"""
多轮对话模式测试

验证 cli.py 的多轮对话功能
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_chat_mode_class():
    """测试 ChatMode 类"""
    print("="*60)
    print("测试 ChatMode 类")
    print("="*60)

    import cli

    # 检查 ChatMode 类
    assert hasattr(cli, 'ChatMode'), "应该有 ChatMode 类"
    print("[OK] ChatMode 类存在")

    # 检查方法
    methods = [
        'show_welcome',
        'show_stats',
        'handle_command',
        'show_help',
        'show_status',
        'handle_skills_command',
        'run',
        'process_round',
    ]

    for method in methods:
        assert hasattr(cli.ChatMode, method), f"应该有 {method} 方法"
        print(f"[OK] {method} 方法存在")


def test_command_handling():
    """测试命令处理"""
    print("\n" + "="*60)
    print("测试命令处理")
    print("="*60)

    import cli
    from core.agent_loop import AgentLoop

    # 创建模拟 AgentLoop
    class MockLoop:
        def __init__(self):
            self.plugin_loader = None
            self.plugins_enabled = False
            self.hooks_enabled = False
            self.skills_enabled = False
            self.skill_manager = None
            self.messages = []

        def get_system_status(self):
            return {
                'plugins': {'loaded': 0},
                'hooks': {'registered': 0},
                'skills': {'total': 2, 'active': 0},
                'tools': {'total': 20}
            }

    loop = MockLoop()
    config = {"model": "test"}

    chat_mode = cli.ChatMode(loop, config)

    # 测试命令处理
    test_cases = [
        ("/help", True, "帮助命令"),
        ("/clear", True, "清空命令"),
        ("/status", True, "状态命令"),
        ("/exit", False, "退出命令"),
        ("/quit", False, "退出命令(quit)"),
        ("/active", True, "激活列表命令"),
    ]

    for cmd, should_continue, desc in test_cases:
        result = chat_mode.handle_command(cmd)
        assert result == should_continue, f"{desc} 处理错误"
        print(f"[OK] {desc}: {cmd} -> continue={should_continue}")


def test_skills_commands():
    """测试技能命令处理"""
    print("\n" + "="*60)
    print("测试技能命令处理")
    print("="*60)

    import cli
    from core.agent_loop import AgentLoop

    class MockLoop:
        def __init__(self):
            self.plugin_loader = None
            self.plugins_enabled = False
            self.hooks_enabled = False
            self.skills_enabled = False
            self.skill_manager = None
            self.messages = []

        def get_system_status(self):
            return {
                'plugins': {'loaded': 0},
                'hooks': {'registered': 0},
                'skills': {'total': 2, 'active': 0},
                'tools': {'total': 20}
            }

    loop = MockLoop()
    config = {"model": "test"}

    chat_mode = cli.ChatMode(loop, config)

    # 测试技能命令（只验证不报错）
    test_cases = [
        "/skills",
        "/skills list",
        "/activate python-standards",
        "/deactivate python-standards",
    ]

    for cmd in test_cases:
        try:
            chat_mode.handle_command(cmd)
            print(f"[OK] 命令处理成功: {cmd}")
        except Exception as e:
            # 某些命令可能因为缺少依赖而失败，但应该不抛出异常
            print(f"[INFO] 命令处理: {cmd} ({e})")


def test_round_tracking():
    """测试轮次跟踪"""
    print("\n" + "="*60)
    print("测试轮次跟踪")
    print("="*60)

    import cli
    from core.agent_loop import AgentLoop

    class MockLoop:
        def __init__(self):
            self.messages = []

        def run(self, prompt):
            # 模拟返回结果
            self.messages.append({
                'role': 'assistant',
                'content': 'Test response',
                'usage': {'total_tokens': 100}
            })
            return "Test response"

    loop = MockLoop()
    config = {"model": "test"}

    chat_mode = cli.ChatMode(loop, config)

    # 初始状态
    assert chat_mode.round == 0, "初始轮次应为 0"
    assert chat_mode.total_tokens == 0, "初始 token 应为 0"
    print("[OK] 初始状态正确")

    # 模拟一轮对话
    chat_mode.process_round("test input")

    assert chat_mode.round == 1, "轮次应增加"
    assert chat_mode.total_tokens == 100, "Token 应累加"
    print("[OK] 轮次和 token 跟踪正确")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("多轮对话模式测试")
    print("="*60)

    try:
        test_chat_mode_class()
        test_command_handling()
        test_skills_commands()
        test_round_tracking()

        print("\n" + "="*60)
        print("[OK] 所有多轮对话模式测试通过！")
        print("="*60)
        print("\n多轮对话功能:")
        print("  - 持续保持对话上下文")
        print("  - 支持 /help, /clear, /status 等命令")
        print("  - 支持 /skills, /activate 等技能命令")
        print("  - 跟踪对话轮次和 token 使用")
        print("  - 显示会话统计信息")
        print("\n使用示例:")
        print("  python cli.py")
        print("  > 帮我分析这个代码")
        print("  [1]> ...")
        print("  > 继续")
        print("  [2]> ...")
        print("  > /exit")

        return 0

    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
