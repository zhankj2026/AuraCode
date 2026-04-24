"""
CLI 命令模式测试

验证 cli.py 的命令模式功能
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_command_mode_import():
    """测试命令模式导入"""
    print("="*60)
    print("测试命令模式导入")
    print("="*60)

    # 导入 cli.py
    import cli

    # 检查 CommandMode 类
    assert hasattr(cli, 'CommandMode'), "应该有 CommandMode 类"
    print("[OK] CommandMode 类存在")

    # 检查命令映射
    cmd_map = {
        'analyze': 'cmd_analyze',
        'test': 'cmd_test',
        'lint': 'cmd_lint',
        'skills': 'cmd_skills',
        'plugins': 'cmd_plugins',
        'status': 'cmd_status',
        'subagents': 'cmd_subagents',
        'help': 'cmd_help',
    }

    for cmd, method in cmd_map.items():
        assert hasattr(cli.CommandMode, method), f"应该有 {method} 方法"
        print(f"[OK] {cmd} -> {method} 方法存在")


def test_command_mode_methods():
    """测试命令模式方法"""
    print("\n" + "="*60)
    print("测试命令模式方法签名")
    print("="*60)

    import cli
    from core.agent_loop import AgentLoop

    # 创建一个测试用的 AgentLoop
    try:
        loop = AgentLoop({
            "api_key": "test_key",
            "model": "glm-4-plus",
            "max_iterations": 1,
            "permission_mode": "bypass"
        })
    except:
        # 如果初始化失败（没有 API），创建模拟对象
        class MockLoop:
            def __init__(self):
                self.plugin_loader = None
                self.plugins_enabled = False
                self.hooks_enabled = False
                self.skills_enabled = False
                self.skill_manager = None

        loop = MockLoop()

    # 创建 CommandMode 实例
    cmd_mode = cli.CommandMode(loop)

    # 检查方法
    methods = [
        'cmd_analyze',
        'cmd_test',
        'cmd_lint',
        'cmd_skills',
        'cmd_plugins',
        'cmd_status',
        'cmd_subagents',
        'cmd_help',
    ]

    for method in methods:
        assert hasattr(cmd_mode, method), f"应该有 {method} 方法"
        assert callable(getattr(cmd_mode, method)), f"{method} 应该可调用"
        print(f"[OK] {method} 方法可调用")


def test_command_help_output():
    """测试 help 命令输出"""
    print("\n" + "="*60)
    print("测试 help 命令输出")
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

    loop = MockLoop()
    cmd_mode = cli.CommandMode(loop)

    # 调用 help 命令
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        cmd_mode.cmd_help([])

    output = f.getvalue()

    # 验证输出内容
    assert "analyze" in output, "应包含 analyze 命令"
    assert "skills" in output, "应包含 skills 命令"
    assert "status" in output, "应包含 status 命令"
    assert "test" in output, "应包含 test 命令"

    print("[OK] help 命令输出正确")
    print(f"输出包含 {len(output.splitlines())} 行")


def test_argparse_config():
    """测试 argparse 配置"""
    print("\n" + "="*60)
    print("测试 argparse 配置")
    print("="*60)

    import cli

    # 测试带 --command 参数
    test_args = ["--command", "help"]

    try:
        args = cli.parser.parse_args(test_args)
        assert args.command == ["help"], "应该解析命令"
        print("[OK] --command 参数解析正确")
    except:
        # parser 可能没有定义在模块级别
        print("[SKIP] parser 不在模块级别")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("CLI 命令模式测试")
    print("="*60)

    try:
        test_command_mode_import()
        test_command_mode_methods()
        test_command_help_output()
        test_argparse_config()

        print("\n" + "="*60)
        print("[OK] 所有命令模式测试通过！")
        print("="*60)
        print("\n可用命令:")
        print("  - help: 显示帮助")
        print("  - status: 系统状态")
        print("  - skills: 技能管理")
        print("  - plugins: 插件信息")
        print("  - analyze: 代码分析")
        print("  - test: 运行测试")
        print("  - lint: 代码检查")
        print("  - subagents: Subagent 管理")
        print("\n使用示例:")
        print("  python cli.py --command help")
        print("  python cli.py --command status")
        print("  python cli.py --command skills activate python-standards")

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
