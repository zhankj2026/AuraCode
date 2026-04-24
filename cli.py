#!/usr/bin/env python3
"""
Claude Code Python MVP - CLI 入口

支持两种模式:
1. 对话模式: 与 AI 进行多轮自然语言交互
2. 命令模式: 直接执行预定义命令
"""

import argparse
import os
import sys
import logging
import json
from datetime import datetime

# Windows 控制台编码修复
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from core.agent_loop import AgentLoop
from tools.builtin import skill_tools
from core.subagent import subagent_manager

# 配置日志
logging.basicConfig(
    level=logging.WARNING,  # 减少日志输出
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class CommandMode:
    """命令模式处理器"""

    def __init__(self, loop: AgentLoop):
        self.loop = loop

    def execute(self, command: str, args: list):
        """执行命令"""
        command_map = {
            'analyze': self.cmd_analyze,
            'test': self.cmd_test,
            'lint': self.cmd_lint,
            'skills': self.cmd_skills,
            'plugins': self.cmd_plugins,
            'status': self.cmd_status,
            'subagents': self.cmd_subagents,
            'help': self.cmd_help,
        }

        if command not in command_map:
            print(f"❌ 未知命令: {command}")
            print(f"使用 'python cli.py --command help' 查看可用命令")
            return False

        try:
            command_map[command](args)
            return True
        except Exception as e:
            print(f"❌ 命令执行失败: {e}")
            return False

    def cmd_analyze(self, args):
        """分析代码"""
        if not args:
            print("❌ 请指定要分析的文件或目录")
            print("用法: python cli.py --command analyze <path>")
            return

        path = args[0]
        print(f"🔍 分析: {path}")
        print("-" * 60)

        # 使用 AgentLoop 的分析工具
        from tools.builtin.analyze_file import analyze_file_handler
        from tools.builtin.find import find_handler

        if os.path.isfile(path):
            result = analyze_file_handler(path)
            print(result)
        elif os.path.isdir(path):
            # 查找 Python 文件
            files = find_handler(path, "*.py", max_depth=3)
            print(f"找到 {len(files.splitlines())} 个 Python 文件\n")

            # 分析每个文件
            for line in files.splitlines()[:10]:  # 限制数量
                if line.strip() and not line.startswith('找到'):
                    file_path = line.strip()
                    if os.path.isfile(file_path):
                        print(f"\n📄 {file_path}")
                        try:
                            result = analyze_file_handler(file_path)
                            if result and len(result) < 500:
                                print(result)
                        except:
                            pass
        else:
            print(f"❌ 路径不存在: {path}")

    def cmd_test(self, args):
        """运行测试"""
        print("🧪 运行测试")
        print("-" * 60)

        from tools.builtin.run_tests import run_tests_handler

        # 支持指定测试路径
        test_path = args[0] if args else "."
        result = run_tests_handler(path=test_path)

        print(result)

    def cmd_lint(self, args):
        """代码检查"""
        print("🔍 代码检查")
        print("-" * 60)

        from tools.builtin.lint import lint_handler

        # 支持指定路径
        path = args[0] if args else "."
        result = lint_handler(path=path)

        print(result)

    def cmd_skills(self, args):
        """技能管理"""
        if not args:
            self.skills_list()
            return

        subcommand = args[0]

        if subcommand == 'list':
            self.skills_list()
        elif subcommand == 'activate':
            if len(args) < 2:
                print("❌ 请指定技能名称")
                return
            self.skills_activate(args[1])
        elif subcommand == 'deactivate':
            if len(args) < 2:
                print("❌ 请指定技能名称")
                return
            self.skills_deactivate(args[1])
        elif subcommand == 'active':
            self.skills_active()
        else:
            print(f"❌ 未知子命令: {subcommand}")
            print("可用子命令: list, activate, deactivate, active")

    def skills_list(self):
        """列出所有技能"""
        result = skill_tools.show_available_skills_handler()
        print(result)

    def skills_activate(self, name: str):
        """激活技能"""
        result = skill_tools.activate_skill_handler(name)
        print(result)

    def skills_deactivate(self, name: str):
        """停用技能"""
        result = skill_tools.deactivate_skill_handler(name)
        print(result)

    def skills_active(self):
        """显示已激活的技能"""
        result = skill_tools.get_active_skills_handler()
        print(result)

    def cmd_plugins(self, args):
        """插件管理"""
        print("🔌 插件系统")
        print("-" * 60)

        if self.loop.plugin_loader:
            result = self.loop.list_plugins()
            print(result)

            # 显示钩子
            hooks = self.loop.list_hooks()
            if hooks:
                print("\n📌 已注册的钩子:")
                print(hooks)
        else:
            print("插件系统未启用")

    def cmd_status(self, args):
        """显示系统状态"""
        print("📊 系统状态")
        print("=" * 60)

        status = self.loop.get_system_status()

        print(f"插件系统: {'✅ 启用' if self.loop.plugins_enabled else '❌ 禁用'}")
        print(f"  已加载: {status['plugins']['loaded']} 个")

        print(f"\n钩子系统: {'✅ 启用' if self.loop.hooks_enabled else '❌ 禁用'}")
        print(f"  已注册: {status['hooks']['registered']} 个")

        print(f"\n技能系统: {'✅ 启用' if self.loop.skills_enabled else '❌ 禁用'}")
        print(f"  总数: {status['skills']['total']} 个")
        print(f"  已激活: {status['skills']['active']} 个")

        print(f"\n工具总数: {status['tools']['total']} 个")

        # 显示 Subagent 状态
        subagent_stats = subagent_manager.get_stats()
        print(f"\nSubagent:")
        print(f"  总数: {subagent_stats['total']} 个")
        print(f"  运行中: {subagent_stats['running']} 个")
        print(f"  已完成: {subagent_stats['completed']} 个")

    def cmd_subagents(self, args):
        """Subagent 管理"""
        print("🤖 Subagent 管理")
        print("-" * 60)

        if not args:
            # 列出所有 Subagent
            result = skill_tools.subagent_stats_handler()
            print(result)

            subagents = subagent_manager.list_agents()
            if subagents:
                print("\nSubagent 列表:")
                for agent in subagents:
                    status_icon = {
                        'running': '🔄',
                        'completed': '✅',
                        'failed': '❌',
                    }.get(agent['status'], '❓')

                    print(f"  {status_icon} {agent['agent_id']}")
                    print(f"     任务: {agent['task']}")
                    print()
        else:
            subcommand = args[0]

            if subcommand == 'list':
                result = skill_tools.list_subagents_handler()
                print(result)
            elif subcommand == 'stats':
                result = skill_tools.subagent_stats_handler()
                print(result)

    def cmd_help(self, args):
        """显示帮助"""
        print("📖 命令帮助")
        print("=" * 60)
        print()
        print("可用命令:")
        print()
        print("  analyze <path>      分析代码文件或目录")
        print("  test [path]         运行测试")
        print("  lint [path]         代码检查")
        print()
        print("  skills list         列出所有技能")
        print("  skills activate <name>  激活技能")
        print("  skills deactivate <name> 停用技能")
        print("  skills active       显示已激活的技能")
        print()
        print("  plugins             显示插件信息")
        print("  status              显示系统状态")
        print("  subagents           管理 Subagent")
        print()
        print("示例:")
        print()
        print("  python cli.py --command analyze .")
        print("  python cli.py --command test")
        print("  python cli.py --command skills activate python-standards")
        print("  python cli.py --command status")
        print()


class ChatMode:
    """多轮对话模式处理器"""

    def __init__(self, loop: AgentLoop, config: dict):
        self.loop = loop
        self.config = config
        self.round = 0
        self.total_tokens = 0
        self.start_time = datetime.now()

    def show_welcome(self):
        """显示欢迎信息"""
        print("=" * 60)
        print("🚀 Claude Code Python MVP - 多轮对话模式")
        print("=" * 60)
        print(f"   Model: {self.config['model']}")
        print(f"   Permission Mode: {self.config['permission_mode']}")
        print(f"   Max Iterations: {self.config['max_iterations']}")
        print()
        print("💡 提示:")
        print("   - 输入你的问题或指令")
        print("   - 输入 /help 查看可用命令")
        print("   - 输入 /clear 清空对话历史")
        print("   - 输入 /exit 或 /quit 退出")
        print("   - 按 Ctrl+C 退出")
        print()
        print("=" * 60)

    def show_stats(self):
        """显示会话统计"""
        duration = (datetime.now() - self.start_time).total_seconds()

        print()
        print("=" * 60)
        print("📊 会话统计")
        print("=" * 60)
        print(f"   对话轮次: {self.round}")
        print(f"   总 Token: {self.total_tokens}")
        print(f"   会话时长: {duration:.1f} 秒")
        if self.round > 0:
            print(f"   平均 Token/轮: {self.total_tokens // self.round}")
        print("=" * 60)

    def handle_command(self, user_input: str) -> bool:
        """处理特殊命令"""
        input_stripped = user_input.strip()

        # 空输入
        if not input_stripped:
            return True

        # 退出命令
        if input_stripped in ['/exit', '/quit', ':q', 'exit', 'quit']:
            return False

        # 帮助命令
        if input_stripped in ['/help', 'help', '?']:
            self.show_help()
            return True

        # 清空历史命令
        if input_stripped in ['/clear', 'clear']:
            self.loop.messages = []
            self.round = 0
            print("✅ 对话历史已清空")
            return True

        # 状态命令
        if input_stripped in ['/status', 'status']:
            self.show_status()
            return True

        # 技能命令
        if input_stripped.startswith('/skills'):
            self.handle_skills_command(input_stripped)
            return True

        # 激活技能快捷方式
        if input_stripped.startswith('/activate'):
            parts = input_stripped.split()
            if len(parts) >= 2:
                skill_name = parts[1]
                result = skill_tools.activate_skill_handler(skill_name)
                print(result)
            else:
                print("用法: /activate <skill_name>")
            return True

        # 停用技能快捷方式
        if input_stripped.startswith('/deactivate'):
            parts = input_stripped.split()
            if len(parts) >= 2:
                skill_name = parts[1]
                result = skill_tools.deactivate_skill_handler(skill_name)
                print(result)
            else:
                print("用法: /deactivate <skill_name>")
            return True

        # 显示激活的技能
        if input_stripped in ['/active', 'active']:
            result = skill_tools.get_active_skills_handler()
            print(result)
            return True

        return False  # 不是特殊命令，需要 AI 处理

    def show_help(self):
        """显示帮助"""
        print()
        print("=" * 60)
        print("📖 可用命令")
        print("=" * 60)
        print()
        print("对话控制:")
        print("  /help          - 显示此帮助")
        print("  /clear         - 清空对话历史")
        print("  /status        - 显示系统状态")
        print("  /exit, /quit   - 退出对话")
        print()
        print("技能管理:")
        print("  /skills        - 列出所有技能")
        print("  /activate <name>  - 激活技能")
        print("  /deactivate <name> - 停用技能")
        print("  /active        - 显示已激活的技能")
        print()
        print("其他:")
        print("  直接输入问题或指令与 AI 对话")
        print()
        print("=" * 60)

    def show_status(self):
        """显示状态"""
        print()
        print("=" * 60)
        print("📊 当前状态")
        print("=" * 60)

        status = self.loop.get_system_status()

        print(f"插件: {status['plugins']['loaded']} 个")
        print(f"钩子: {status['hooks']['registered']} 个")
        print(f"技能: {status['skills']['active']}/{status['skills']['total']} 个激活")
        print(f"工具: {status['tools']['total']} 个")
        print(f"对话轮次: {self.round}")
        print(f"使用 Token: {self.total_tokens}")

        print("=" * 60)

    def handle_skills_command(self, input_cmd: str):
        """处理技能命令"""
        parts = input_cmd.split()

        if len(parts) == 1:
            # /skills
            result = skill_tools.show_available_skills_handler()
            print(result)
        elif len(parts) >= 2:
            action = parts[1]

            if action == 'list':
                result = skill_tools.show_available_skills_handler()
                print(result)
            elif action == 'activate' and len(parts) >= 3:
                result = skill_tools.activate_skill_handler(parts[2])
                print(result)
            elif action == 'deactivate' and len(parts) >= 3:
                result = skill_tools.deactivate_skill_handler(parts[2])
                print(result)
            else:
                print("用法:")
                print("  /skills                - 列出所有技能")
                print("  /skills activate <name> - 激活技能")
                print("  /skills deactivate <name> - 停用技能")

    def run(self, initial_input: str = None):
        """运行多轮对话"""
        self.show_welcome()

        # 如果有初始输入，先处理
        if initial_input:
            self.process_round(initial_input)

        # 多轮对话循环
        while True:
            try:
                # 获取用户输入
                user_input = input(f"[{self.round}]> ").strip()

                # 处理空输入
                if not user_input:
                    continue

                # 处理特殊命令
                should_continue = self.handle_command(user_input)
                if not should_continue:
                    break

                # 处理普通对话
                self.process_round(user_input)

            except KeyboardInterrupt:
                print("\n\n👋 用户中断")
                break
            except EOFError:
                print("\n\n👋 输入结束")
                break

        # 显示会话统计
        self.show_stats()
        print("\n✅ 感谢使用！再见！")

    def process_round(self, user_input: str):
        """处理一轮对话"""
        self.round += 1

        print()
        print(f"🔄 第 {self.round} 轮")
        print("-" * 60)

        try:
            # 执行对话
            result = self.loop.run(user_input)

            # 统计 token 使用
            if self.loop.messages:
                # 从最后一条助手消息中获取 token 使用情况
                for msg in reversed(self.loop.messages):
                    if msg.get('role') == 'assistant' and 'usage' in msg:
                        usage = msg['usage']
                        if usage:
                            tokens = usage.get('total_tokens', 0)
                            self.total_tokens += tokens
                            print(f"\n💰 本轮 Token: {tokens}")
                            break

            if result:
                print(f"\n✅ 完成")
            else:
                print(f"\n⚠️  未获得响应")

        except Exception as e:
            print(f"\n❌ 错误: {e}")

        print()


def check_api_key():
    """检查 API 密钥"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ 错误: 未设置 OPENAI_API_KEY 环境变量")
        print("\n配置方法:")
        print("  智谱 GLM:")
        print("    Windows: $env:OPENAI_API_KEY=\"your-key\"")
        print("    Windows: $env:OPENAI_BASE_URL=\"https://open.bigmodel.cn/api/paas/v4\"")
        print("    Linux/Mac: export OPENAI_API_KEY=\"your-key\"")
        print("    Linux/Mac: export OPENAI_BASE_URL=\"https://open.bigmodel.cn/api/paas/v4\"")
        print("\n获取 GLM API Key: https://open.bigmodel.cn/")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Python MVP - AI 编程助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 多轮对话模式
  python cli.py
  python cli.py "帮我分析这个项目"

  # 命令模式
  python cli.py --command analyze .
  python cli.py --command test
  python cli.py --command skills activate python-standards
  python cli.py --command status

  # 指定模型
  python cli.py "重构代码" --model glm-4-plus

  # 权限模式
  python cli.py "执行命令" --mode auto
        """
    )

    parser.add_argument(
        "prompt",
        nargs="*",
        help="用户指令（对话模式的初始输入）"
    )
    parser.add_argument(
        "--mode",
        choices=["normal", "auto", "plan", "bypass"],
        default="normal",
        help="权限模式 (默认: normal)"
    )
    parser.add_argument(
        "--model",
        default="glm-4.5-flash",
        help="LLM 模型 (默认: glm-4.5-flash, 可选: glm-4.7, glm-4.5-air)"
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="API Base URL (默认从环境变量 OPENAI_BASE_URL 读取)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="最大迭代次数 (默认: 20)"
    )
    parser.add_argument(
        "--command", "-c",
        nargs="+",
        help="命令模式: 直接执行预定义命令",
        metavar=("COMMAND", "ARGS")
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志"
    )

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 检查 API 密钥
    if not check_api_key():
        sys.exit(1)

    # 构建配置
    config = {
        "api_key": os.environ.get("OPENAI_API_KEY"),
        "base_url": args.base_url or os.environ.get("OPENAI_BASE_URL"),
        "model": args.model,
        "max_iterations": args.max_iterations,
        "permission_mode": args.mode,
        # 启用扩展系统
        "enable_plugins": True,
        "enable_hooks": True,
        "enable_skills": True,
        "active_skills": []
    }

    # 命令模式
    if args.command:
        command = args.command[0]
        command_args = args.command[1:] if len(args.command) > 1 else []

        # 初始化 AgentLoop
        try:
            loop = AgentLoop(config)
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            sys.exit(1)

        # 执行命令
        cmd_mode = CommandMode(loop)
        success = cmd_mode.execute(command, command_args)
        sys.exit(0 if success else 1)

    # 对话模式（多轮）
    # 初始化 Agent Loop
    try:
        loop = AgentLoop(config)
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)

    # 获取初始输入
    initial_input = None
    if args.prompt:
        initial_input = " ".join(args.prompt)

    # 运行多轮对话
    try:
        chat_mode = ChatMode(loop, config)
        chat_mode.run(initial_input)
    except KeyboardInterrupt:
        print("\n\n👋 用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
