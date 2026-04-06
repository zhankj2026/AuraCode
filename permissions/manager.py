"""
权限管理器

实现三道防线安全机制:
1. 黑名单检查 - 拦截危险命令(最高优先级)
2. Plan 模式拦截 - 禁止所有修改操作
3. 用户确认 - normal 模式下需手动批准

支持 4 种权限模式: normal/auto/plan/bypass
"""

from typing import Dict, Any


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
                confirm = input(f"⚠️  执行 {tool_name}? 确认? (y/N): ")
                if confirm.lower() != "y":
                    print("用户取消操作")
                    return False
        
        # Auto 模式: 文件操作自动通过,命令仍需确认
        if self.mode == "auto":
            if tool_name == "run_command":
                confirm = input(f"⚠️  执行命令? 确认? (y/N): ")
                return confirm.lower() == "y"
        
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
