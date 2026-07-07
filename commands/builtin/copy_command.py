#!/usr/bin/env python3
"""
复制命令 - 复制 AI 响应到剪贴板或文件

功能：
- 复制完整响应
- 提取代码块
- 写入临时文件
"""

import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import CommandContext, CommandResult, LocalCommand


class CopyCommand(LocalCommand):
    """复制命令"""
    
    name = "copy"
    description = "复制 AI 响应到剪贴板或文件"
    aliases = []
    
    # 最大回溯消息数
    MAX_LOOKBACK = 20
    
    def extract_code_blocks(self, markdown: str) -> List[Dict[str, str]]:
        """从 Markdown 中提取代码块"""
        pattern = r'```(\w+)?\n(.*?)```'
        matches = re.findall(pattern, markdown, re.DOTALL)
        
        blocks = []
        for lang, code in matches:
            blocks.append({
                "lang": lang or "txt",
                "code": code.strip()
            })
        
        return blocks
    
    def collect_recent_assistant_texts(
        self, messages: List[Dict]
    ) -> List[str]:
        """收集最近的助手消息文本"""
        texts = []
        
        # 从后往前遍历
        for msg in reversed(messages):
            if len(texts) >= self.MAX_LOOKBACK:
                break
            
            if msg.get("role") != "assistant":
                continue
            
            # 跳过 API 错误消息
            if msg.get("is_api_error"):
                continue
            
            content = msg.get("content", "")
            if isinstance(content, list):
                # 提取文本内容
                text_parts = [
                    part.get("text", "")
                    for part in content
                    if part.get("type") == "text"
                ]
                content = "\n\n".join(text_parts)
            
            if content:
                texts.append(content)
        
        return texts
    
    def file_extension(self, lang: Optional[str]) -> str:
        """根据语言获取文件扩展名"""
        if lang:
            # 清理非法字符
            sanitized = re.sub(r'[^a-zA-Z0-9]', '', lang)
            if sanitized and sanitized != "plaintext":
                return f".{sanitized}"
        return ".txt"
    
    async def execute(self, args: str, context: CommandContext) -> CommandResult:
        """执行复制命令"""
        
        # 获取消息历史
        messages = context.messages or []
        texts = self.collect_recent_assistant_texts(messages)
        
        if not texts:
            return CommandResult(
                success=False,
                output="No assistant message to copy"
            )
        
        # 解析参数（支持 /copy N 回溯）
        age = 0
        arg = args.strip() if args else ""
        
        if arg:
            try:
                n = int(arg)
                if n < 1:
                    return CommandResult(
                        success=False,
                        output=f"Usage: /copy [N] where N is 1 (latest), 2, 3, ... Got: {arg}"
                    )
                if n > len(texts):
                    return CommandResult(
                        success=False,
                        output=f"Only {len(texts)} assistant {'message' if len(texts) == 1 else 'messages'} available to copy"
                    )
                age = n - 1
            except ValueError:
                return CommandResult(
                    success=False,
                    output=f"Invalid argument: {arg}. Expected a number."
                )
        
        # 获取目标文本
        text = texts[age]
        code_blocks = self.extract_code_blocks(text)
        
        # 如果没有代码块，复制完整响应
        if not code_blocks:
            # 写入临时文件
            temp_dir = Path(tempfile.gettempdir()) / "auracode"
            temp_dir.mkdir(exist_ok=True)
            temp_file = temp_dir / "response.md"
            temp_file.write_text(text, encoding="utf-8")
            
            return CommandResult(
                success=True,
                output=f"Copied to clipboard ({len(text)} characters, {text.count(chr(10)) + 1} lines)\nAlso written to {temp_file}",
                data={
                    "text": text,
                    "file": str(temp_file)
                }
            )
        
        # 有代码块时，返回选择器（简化版：直接返回第一个代码块）
        # TODO: 实现交互式选择器
        first_block = code_blocks[0]
        block_text = first_block["code"]
        ext = self.file_extension(first_block.get("lang"))
        
        # 写入临时文件
        temp_dir = Path(tempfile.gettempdir()) / "auracode"
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / f"copy{ext}"
        temp_file.write_text(block_text, encoding="utf-8")
        
        return CommandResult(
            success=True,
            output=f"Copied code block ({len(block_text)} characters)\nLanguage: {first_block.get('lang', 'unknown')}\nWritten to {temp_file}",
            data={
                "text": block_text,
                "file": str(temp_file),
                "lang": first_block.get("lang")
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
    command_registry.register(CopyCommand())
