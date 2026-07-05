#!/usr/bin/env python3
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
AuraCode - CLI 入口

支持两种模式:
1. 对话模式: 与 AI 进行多轮自然语言交互
2. 命令模式: 直接执行预定义命令
"""

import argparse
import os
import sys
import logging
from datetime import datetime

# Windows 控制台编码修复（带超时保护）
if sys.platform == "win32":
    import io
    try:
        # 尝试包装 stdout/stderr，但设置超时避免卡住
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, 
            encoding='utf-8',
            errors='replace',  # 替换无效字符而不是阻塞
            line_buffering=True  # 启用行缓冲
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, 
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )
    except Exception as e:
        # 如果包装失败，继续使用原始流
        print(f"Warning: Failed to wrap stdout/stderr: {e}", file=sys.__stderr__)

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from core.agent_loop import AgentLoop
from commands.registry import COMMAND_REGISTRY, get_command_list, get_commands_by_category
from core.session_store import SessionStore, auto_save_session
from config import config_manager

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class CommandExecutor:
    """命令执行器"""

    def __init__(self, loop: AgentLoop = None):
        self.loop = loop

    def execute(self, command_name: str, args: list) -> bool:
        """
        执行命令

        Args:
            command_name: 命令名称
            args: 命令参数

        Returns:
            True 表示成功，False 表示失败
        """
        # 处理别名
        aliases = {
            '?': 'help',
            'h': 'help',
            'ls': 'list',
        }
        command_name = aliases.get(command_name, command_name)

        # 查找命令
        cmd_def = COMMAND_REGISTRY.get(command_name)
        if not cmd_def:
            print(f"❌ 未知命令: {command_name}")
            print(f"使用 'help' 查看可用命令")
            return False

        try:
            handler = cmd_def["handler"]

            # 根据处理函数类型调用
            if callable(handler):
                # 检查是否是 Command 类实例
                if hasattr(handler, 'execute'):
                    # Command 类
                    if hasattr(handler, 'set_loop') and self.loop:
                        handler.set_loop(self.loop)
                    result = handler.execute(args)
                else:
                    # 普通函数
                    if hasattr(handler, '__code__'):
                        # 检查函数签名
                        import inspect
                        sig = inspect.signature(handler)
                        if 'loop' in sig.parameters:
                            result = handler(args, loop=self.loop)
                        else:
                            result = handler(args)
                    else:
                        result = handler(args)
                print(result)
            else:
                print(f"❌ 命令处理函数无效")
                return False

            return True

        except Exception as e:
            print(f"❌ 命令执行失败: {e}")
            logger.error(f"Command {command_name} failed: {e}", exc_info=True)
            return False


class ChatMode:
    """多轮对话模式处理器"""

    def __init__(self, loop: AgentLoop, config: dict, executor: CommandExecutor):
        self.loop = loop
        self.config = config
        self.executor = executor
        self.round = 0
        self.start_time = datetime.now()
        # 会话持久化
        self._session_store = SessionStore()
        self._session_meta = None  # 当前会话元数据（用于增量更新）

    def show_welcome(self):
        """显示欢迎信息"""
        print("=" * 60)
        print("🚀 AuraCode - 多轮对话模式")
        print("=" * 60)
        print(f"   Model: {self.config['model']}")
        print(f"   Permission Mode: {self.config['permission_mode']}")
        print()
        print("💡 提示:")
        print("   - 输入你的问题或指令")
        print("   - 输入 'help' 查看可用命令")
        print("   - 输入 'clear' 清空对话历史")
        print("   - 输入 'exit' 或 'quit' 退出")
        print("   - 按 Ctrl+C 退出")
        print()
        print("=" * 60)

    def show_stats(self):
        """显示会话统计（基于 SessionState 集中数据）"""
        duration = (datetime.now() - self.start_time).total_seconds()
        state = self.loop.state

        print()
        print("=" * 60)
        print("📊 会话统计")
        print("=" * 60)
        print(f"   对话轮次: {self.round}")
        print(f"   总 Token: {state.total_usage.total_tokens}"
              f" (输入={state.total_usage.prompt_tokens},"
              f" 输出={state.total_usage.completion_tokens})")
        if state.total_cost_usd > 0:
            print(f"   总费用: ${state.total_cost_usd:.6f}")
        print(f"   会话时长: {duration:.1f} 秒")
        if state.permission_denials:
            print(f"   权限拒绝: {len(state.permission_denials)} 次")
        if self.round > 0 and state.total_usage.total_tokens > 0:
            print(f"   平均 Token/轮: {state.total_usage.total_tokens // self.round}")
        print("=" * 60)

    def handle_input(self, user_input: str) -> bool:
        """
        处理用户输入

        Args:
            user_input: 用户输入

        Returns:
            True 表示继续对话，False 表示退出
        """
        user_input = user_input.strip()

        # 空输入
        if not user_input:
            return True

        # 退出命令
        if user_input in ['exit', 'quit', ':q', '/exit', '/quit']:
            return False

        # 帮助命令
        if user_input in ['help', '/help', '?']:
            self.show_help()
            return True

        # 清空历史命令
        if user_input in ['clear', '/clear']:
            self.loop.messages = []
            self.round = 0
            print("✅ 对话历史已清空")
            return True

        # 状态命令
        if user_input in ['status', '/status']:
            self.executor.execute('status', [])
            return True

        # 技能命令
        if user_input.startswith('/'):
            # 解析 /command 格式
            parts = user_input[1:].split()
            if parts:
                cmd_name = parts[0]
                cmd_args = parts[1:]
                # 执行命令，但无论成功失败都继续对话
                # （未知命令/执行失败不应终止会话）
                self.executor.execute(cmd_name, cmd_args)
                return True

        # 普通对话
        return self.process_round(user_input)

    def show_help(self):
        """显示帮助"""
        print()
        print("=" * 60)
        print("📖 可用命令")
        print("=" * 60)
        print()

        categories = {
            "system": "系统命令",
            "skills": "技能管理",
            "tools": "工具命令",
            "analysis": "代码分析"
        }

        for cat_key, cat_name in categories.items():
            commands = get_commands_by_category(cat_key)
            if commands:
                print(f"{cat_name}:")
                for cmd_name in commands:
                    cmd = COMMAND_REGISTRY[cmd_name]
                    args_help = cmd.get("args_help", "")
                    if args_help:
                        print(f"  {cmd_name:15} {args_help}")
                    else:
                        print(f"  {cmd_name}")
                    print(f"    {cmd['description']}")
                print()

        print("其他:")
        print("  直接输入问题或指令与 AI 对话")
        print()
        print("=" * 60)

    def _auto_save_on_exit(self):
        """退出时自动保存会话"""
        try:
            state = self.loop.state
            if not state.messages:
                return  # 没有消息，无需保存

            status = "completed"
            if state.is_aborted():
                status = "aborted"

            meta = auto_save_session(
                store=self._session_store,
                messages=state.messages,
                model=self.config.get("model", ""),
                turn_count=self.round,
                total_tokens=state.total_usage.total_tokens,
                total_cost_usd=state.total_cost_usd,
                status=status,
                existing_meta=self._session_meta,
            )
            if meta:
                self._session_meta = meta
                print(f"\n💾 会话已保存: [{meta.session_id[:8]}] ({meta.message_count} 条消息)")
                print(f"   使用 /resume {meta.session_id[:8]} 恢复此会话")
        except Exception as e:
            logger.warning(f"Auto-save on exit failed: {e}")

    def process_round(self, user_input: str) -> bool:
        """
        处理一轮对话（基于 QueryResult 结构化结果）

        Args:
            user_input: 用户输入

        Returns:
            True 表示继续，False 表示失败
        """
        self.round += 1

        print()
        print(f"🔄 第 {self.round} 轮")
        print("-" * 60)

        try:
            # 执行对话，返回 QueryResult
            result = self.loop.run(user_input)

            # 展示结构化结果摘要
            if result:
                print()
                print(result.format_summary())
            else:
                print(f"\n⚠️  未获得响应")

        except Exception as e:
            print(f"\n❌ 错误: {e}")
            logger.error(f"Round {self.round} failed: {e}", exc_info=True)

        print()
        return True

    def run(self, initial_input: str = None):
        """运行多轮对话循环"""
        self.show_welcome()

        try:
            # 处理初始输入
            if initial_input:
                if not self.handle_input(initial_input):
                    return

            # 对话循环
            while True:
                try:
                    user_input = input(f"[{self.round}]> ")
                    if not self.handle_input(user_input):
                        break
                except KeyboardInterrupt:
                    print("\n\n👋 用户中断")
                    break
                except EOFError:
                    print("\n\n👋 输入结束")
                    break
        finally:
            # 无论正常退出还是异常，都持久化会话
            self._auto_save_on_exit()
            # 显示会话统计
            self.show_stats()
            print("\n✅ 感谢使用！再见！")


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
    print("🚀 Starting AuraCode CLI...", flush=True)
    
    parser = argparse.ArgumentParser(
        description="AuraCode - AI 编程助手",
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

  # Bridge 远程控制模式
  python cli.py --bridge
  python cli.py --bridge --bridge-port 9000 --bridge-max-sessions 10
  python cli.py --bridge --bridge-token my-secret-token
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
        default="glm-4.7",
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

    # Bridge 远程控制模式
    parser.add_argument(
        "--bridge",
        action="store_true",
        help="启动 Bridge 远程控制服务器模式"
    )
    parser.add_argument(
        "--bridge-port",
        type=int,
        default=8765,
        help="Bridge 服务器端口 (默认: 8765)"
    )
    parser.add_argument(
        "--bridge-host",
        default="127.0.0.1",
        help="Bridge 服务器绑定地址 (默认: 127.0.0.1)"
    )
    parser.add_argument(
        "--bridge-max-sessions",
        type=int,
        default=5,
        help="Bridge 最大会话数 (默认: 5)"
    )
    parser.add_argument(
        "--bridge-token",
        default=None,
        help="Bridge 认证 Token (默认自动生成)"
    )

    args = parser.parse_args()
    print(f"✅ Arguments parsed: {args}", flush=True)

    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        print("🔍 Debug logging enabled", flush=True)

    # Bridge 远程控制模式
    if args.bridge:
        from bridge.server import start_bridge_server
        try:
            start_bridge_server(
                host=args.bridge_host,
                port=args.bridge_port,
                max_sessions=args.bridge_max_sessions,
                auth_token=args.bridge_token,
            )
        except KeyboardInterrupt:
            print("\n👋 Bridge 服务器已停止")
            sys.exit(0)
        return

    # 检查 API 密钥
    print("🔑 Checking API key...", flush=True)
    if not check_api_key():
        print("❌ API key check failed", flush=True)
        sys.exit(1)
    print("✅ API key verified", flush=True)

    # 加载配置文件
    config_manager.load()
    
    # 获取配置并合并命令行参数
    file_config = config_manager.get_all()
    
    # 构建配置（优先级：命令行参数 > 配置文件 > 默认值）
    config = {
        "api_key": os.environ.get("OPENAI_API_KEY"),
        "base_url": args.base_url or os.environ.get("OPENAI_BASE_URL") or file_config.get("llm", {}).get("base_url"),
        "model": args.model or file_config.get("llm", {}).get("model", "glm-4-plus"),
        "max_iterations": args.max_iterations or file_config.get("max_iterations", 20),
        "permission_mode": args.mode,
        # 启用扩展系统
        "enable_plugins": True,
        "enable_hooks": True,
        "enable_skills": True,
        "active_skills": [],
        # 从配置文件加载的其他配置
        # 默认输出 token 限制
        "max_tokens": file_config.get("llm", {}).get("max_tokens", 32000),
        "temperature": file_config.get("llm", {}).get("temperature", 0.2),
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
        executor = CommandExecutor(loop)
        success = executor.execute(command, command_args)
        sys.exit(0 if success else 1)

    # 对话模式（多轮）
    # 初始化 Agent Loop
    print("🔄 Initializing AgentLoop...", flush=True)
    try:
        loop = AgentLoop(config)
        print("✅ AgentLoop initialized successfully", flush=True)
    except Exception as e:
        print(f"❌ 初始化失败: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 初始化 Cron 调度器并注册回调
    try:
        from tools.builtin.cron_tool import get_cron_scheduler
        
        def cron_execute_callback(job):
            """Cron 任务触发时执行的回调"""
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[Cron] Executing job {job.job_id}: {job.prompt[:50]}...")
            # 将 prompt 发送到 AgentLoop
            try:
                result = loop.run(job.prompt)
                logger.info(f"[Cron] Job {job.job_id} completed: {result.summary[:50] if result.summary else 'done'}")
            except Exception as e:
                logger.error(f"[Cron] Job {job.job_id} failed: {e}")
        
        scheduler = get_cron_scheduler()
        scheduler.register_callback(cron_execute_callback)
        print("📅 Cron 调度器已启动")
    except Exception as e:
        print(f"⚠️ Cron 调度器初始化失败: {e}")

    # 创建命令执行器
    executor = CommandExecutor(loop)

    # 获取初始输入
    initial_input = None
    if args.prompt:
        initial_input = " ".join(args.prompt)

    # 运行多轮对话
    try:
        chat_mode = ChatMode(loop, config, executor)
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
