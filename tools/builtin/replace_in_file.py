"""
replace_in_file 工具 - 精确替换文件中的文本(显示差异)

基于 code.md Phase 2 实现
参考: 第 4.1 节
"""

import os
import difflib
from datetime import datetime
from tools.registry import register_tool
from .undo_edit import record_edit


def replace_in_file_handler(
    path: str,
    old_text: str,
    new_text: str,
    replace_all: bool = False,
    show_diff: bool = True
) -> str:
    """
    替换文件中的文本(支持预览差异)
    
    Args:
        path: 文件路径
        old_text: 要替换的文本
        new_text: 新文本
        replace_all: 是否替换所有匹配,默认只替换第一个
        show_diff: 是否显示差异对比,默认显示
    
    Returns:
        替换结果和差异对比
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(path):
            return f"错误: 文件不存在: {path}"
        
        # 读取原文件
        with open(path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # 查找匹配
        if old_text not in original_content:
            return f"错误: 未找到匹配文本\n\n搜索内容: '{old_text[:100]}{'...' if len(old_text) > 100 else ''}'"
        
        # 执行替换
        if replace_all:
            new_content = original_content.replace(old_text, new_text)
            count = original_content.count(old_text)
        else:
            new_content = original_content.replace(old_text, new_text, 1)
            count = 1
        
        # 创建备份
        backup_path = _create_backup(path)
        
        # 写入新内容
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 记录编辑历史
        record_edit(path, backup_path, original_content)

        # 生成结果
        result = [f"✅ 成功替换 {count} 处"]
        result.append(f"文件: {path}")
        result.append(f"备份: {backup_path}")
        result.append("")
        
        # 生成差异
        if show_diff:
            diff = _generate_diff(original_content, new_content, path)
            result.append("差异对比:")
            result.append(diff)
        
        return "\n".join(result)
    
    except Exception as e:
        return f"错误: {str(e)}"


def _create_backup(path: str) -> str:
    """创建文件备份"""
    backup_dir = os.path.join(os.path.dirname(path) or '.', '.backup')
    os.makedirs(backup_dir, exist_ok=True)
    
    # 使用微秒 + 计数器确保唯一性
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = os.path.basename(path)
    backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")
    
    # 如果文件已存在,添加计数器
    counter = 1
    while os.path.exists(backup_path):
        backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}_{counter}.bak")
        counter += 1

    # 复制文件
    with open(path, 'r', encoding='utf-8') as src:
        with open(backup_path, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    
    return backup_path


def _generate_diff(old: str, new: str, path: str, context_lines: int = 3) -> str:
    """
    生成 unified diff
    
    Args:
        old: 原始内容
        new: 新内容
        path: 文件路径
        context_lines: 上下文行数
    
    Returns:
        unified diff 格式的字符串
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=context_lines
    )
    
    return "".join(diff)


# 注册工具
register_tool("replace_in_file", {
    "description": "精确替换文件中的文本(显示差异并自动备份)",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径"
            },
            "old_text": {
                "type": "string",
                "description": "要替换的原始文本"
            },
            "new_text": {
                "type": "string",
                "description": "新的文本内容"
            },
            "replace_all": {
                "type": "boolean",
                "description": "是否替换所有匹配项",
                "default": False
            },
            "show_diff": {
                "type": "boolean",
                "description": "是否显示差异对比",
                "default": True
            }
        },
        "required": ["path", "old_text", "new_text"]
    },
    "handler": replace_in_file_handler,
    "permission_level": "write"
})
