#!/usr/bin/env python3
"""
文件列表命令 - 显示当前上下文中的文件

功能：
- 列出已读取的文件
- 显示相对路径
- 统计文件数量
"""

import os
from pathlib import Path
from typing import Any, Dict, List

from ..base import CommandContext, CommandResult, LocalCommand


class FilesCommand(LocalCommand):
    """文件列表命令"""
    
    name = "files"
    description = "显示当前上下文中的文件列表"
    aliases = ["list-files", "lf"]
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行文件列表命令"""
        
        # 从上下文获取已读取的文件
        # 这里假设 context 中有 file_state 或类似属性
        file_state = getattr(context, 'file_state', None)
        
        if file_state is None:
            # 尝试从 agent_loop 获取
            agent_loop = getattr(context, 'agent_loop', None)
            if agent_loop:
                file_state = getattr(agent_loop, 'read_file_state', {})
        
        # 提取文件列表
        files = list(file_state.keys()) if file_state else []
        
        if not files:
            return CommandResult(
                success=True,
                output="No files in context",
                data={"files": [], "count": 0}
            )
        
        # 转换为相对路径
        cwd = Path.cwd()
        relative_files = []
        
        for file_path in files:
            try:
                rel_path = os.path.relpath(file_path, cwd)
                relative_files.append(rel_path)
            except ValueError:
                # 如果路径不在同一驱动器，使用绝对路径
                relative_files.append(file_path)
        
        # 排序
        relative_files.sort()
        
        # 格式化输出
        file_list = "\n".join(relative_files)
        output = f"Files in context ({len(relative_files)}):\n{file_list}"
        
        return CommandResult(
            success=True,
            output=output,
            data={
                "files": relative_files,
                "count": len(relative_files)
            }
        )
    
    async def execute_non_interactive(
        self, args: str, context: CommandContext
    ) -> Dict[str, Any]:
        """非交互模式执行"""
        result = await self.execute(args, context)
        return {
            "type": "text",
            "value": result.output,
            "data": result.data
        }


# 注册命令
def register():
    """注册命令到全局注册表"""
    from ..registry import command_registry
    command_registry.register(FilesCommand())
