"""
权限管理器

实现三道防线安全机制:
1. 黑名单检查 - 拦截危险命令(最高优先级)
2. Plan 模式拦截 - 禁止所有修改操作
3. 用户确认 - normal 模式下需手动批准

支持 4 种权限模式: normal/auto/plan/bypass
"""

import sys
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PermissionManager:
    """
    权限管理器 - 实现三道防线
    
    防线 1: 黑名单检查(任何模式都生效)
    防线 2: Plan 模式拦截
    防线 3: 用户确认(normal 模式)
    """
    
    # 危险命令黑名单
    DANGEROUS_PATTERNS = [
        "rm -rf /",
        "rm -rf *",
        "sudo ",
        "shutdown",
        "reboot",
        "mkfs",
        "dd if=/dev/zero",
        "> /dev/sd",
        ":(){ :|:& };:",  # Fork bomb
        "chmod 777 /",
        "chown -R root:root /"
    ]
    
    def __init__(self, mode: str = "normal"):
        """
        初始化权限管理器

        Args:
            mode: 权限模式(normal/auto/plan/bypass)
        """
        valid_modes = ["normal", "auto", "plan", "bypass"]
        if mode not in valid_modes:
            raise ValueError(f"无效的权限模式: {mode},必须是 {valid_modes}")

        self.mode = mode
        self._interactive_enabled = self._check_interactive_available()
        if not self._interactive_enabled:
            logger.warning("交互式输入不可用，将自动拒绝需要确认的操作。"
                         "请设置环境变量 AUTO_CONFIRM=true 来自动允许，或使用 auto/bypass 模式。")

    def _check_interactive_available(self) -> bool:
        """
        检查交互式输入是否可用

        Returns:
            True 如果可用，False 否则
        """
        # 检查是否设置了自动确认环境变量
        if os.environ.get("AUTO_CONFIRM", "").lower() == "true":
            return True

        # 检查 stdin 是否是终端
        try:
            return sys.stdin.isatty()
        except:
            return False

    def _get_user_confirmation(
        self,
        tool_name: str,
        prompt: str = "确认?"
    ) -> Optional[bool]:
        """
        获取用户确认（支持交互式输入和环境变量）

        Args:
            tool_name: 工具名称
            prompt: 提示信息

        Returns:
            True 如果确认，False 如果拒绝，None 如果无法获取输入
        """
        # 1. 检查自动确认环境变量
        auto_confirm = os.environ.get("AUTO_CONFIRM", "").lower()
        if auto_confirm == "true":
            logger.info(f"AUTO_CONFIRM=true，自动允许: {tool_name}")
            return True
        elif auto_confirm == "false":
            logger.info(f"AUTO_CONFIRM=false，自动拒绝: {tool_name}")
            return False

        # 2. 如果交互式输入不可用，返回 None
        if not self._interactive_enabled:
            return None

        # 3. 尝试获取用户输入
        try:
            # 使用 sys.stdin 直接读取，避免 input() 在某些环境下的问题
            sys.stdout.write(f"⚠️  执行 {tool_name}? {prompt} (y/N): ")
            sys.stdout.flush()

            # 直接从 stdin 读取一行
            line = sys.stdin.readline()
            if not line:
                # EOF
                return False

            confirm = line.strip().lower()
            return confirm == "y" or confirm == "yes"

        except EOFError:
            logger.warning(f"遇到 EOF，拒绝操作: {tool_name}")
            return False
        except KeyboardInterrupt:
            logger.warning(f"用户中断，拒绝操作: {tool_name}")
            return False
        except Exception as e:
            logger.error(f"获取用户输入失败: {e}")
            return None
    
    def check_permission(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        """
        检查工具调用权限
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            是否允许执行
        """
        # 防线 1: 命令黑名单检查(最高优先级,任何模式都拦截)
        if tool_name == "run_command":
            command = arguments.get("command", "")
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern.lower() in command.lower():
                    print(f"[Security] ❌ 阻止危险命令: {command[:50]}...")
                    return False
        
        # 防线 2: Bypass 模式直接通过(黑名单之后)
        if self.mode == "bypass":
            return True
        
        # 防线 3: Plan 模式拒绝所有修改操作
        if self.mode == "plan":
            if tool_name in ["write_file", "run_command"]:
                print(f"[Plan Mode] ❌ 阻止修改操作: {tool_name}")
                return False
        
        # 防线 4: 用户确认(normal 模式需要确认写入和命令)
        if self.mode == "normal":
            if tool_name in ["write_file", "run_command"]:
                confirm = self._get_user_confirmation(tool_name, "确认?")
                if confirm is False:
                    print("用户取消操作")
                    return False
                elif confirm is None:
                    # 无法获取输入，拒绝操作
                    print(f"⚠️  无法获取用户确认，拒绝操作: {tool_name}")
                    print(f"   提示: 设置环境变量 AUTO_CONFIRM=true 来自动允许")
                    logger.warning(f"权限拒绝: {tool_name} 操作被安全策略拦截 (无法获取用户确认)")
                    return False
                # confirm is True，继续执行

        # Auto 模式: 文件操作自动通过,命令仍需确认
        if self.mode == "auto":
            if tool_name == "run_command":
                confirm = self._get_user_confirmation(tool_name, "执行命令?")
                if confirm is False:
                    return False
                elif confirm is None:
                    # 无法获取输入，拒绝操作
                    print(f"⚠️  无法获取用户确认，拒绝操作: {tool_name}")
                    logger.warning(f"权限拒绝: {tool_name} 操作被安全策略拦截 (无法获取用户确认)")
                    return False
                # confirm is True，继续执行
        
        return True
    
    def truncate_output(self, output: str, max_lines: int = 500) -> str:
        """
        输出截断 - 防止上下文溢出
        
        Args:
            output: 原始输出
            max_lines: 最大行数
            
        Returns:
            截断后的输出
        """
        lines = output.splitlines()
        if len(lines) <= max_lines:
            return output
        
        # 保留前半部分和后半部分
        half = max_lines // 2
        truncated = (
            lines[:half] + 
            [f"... (截断 {len(lines) - max_lines} 行) ..."] + 
            lines[-half:]
        )
        return "\n".join(truncated)
