"""
replace_in_file 工具 - 精确替换文件中的文本

对标 FileEditTool，增强匹配失败时的反馈。
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
) -> str:
    """
    替换文件中的文本。
    匹配失败时返回文件中最相近的内容片段，帮助 LLM 修正 old_text。
    """
    try:
        if not os.path.exists(path):
            return f"Error: file not found: {path}"
        
        with open(path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        total_lines = original_content.count('\n') + (0 if original_content.endswith('\n') else 1)
        
        # 查找匹配
        if old_text not in original_content:
            # ── 关键增强: 返回最相近的内容片段 ──
            hint = _build_mismatch_hint(original_content, old_text, total_lines)
            return hint
        
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

        # ── 精简返回值: 不返回完整 diff ──
        changed_lines = _count_changed_lines(original_content, new_content)
        return f"Replaced {count} occurrence(s) in {path} ({changed_lines} lines changed)"
    
    except Exception as e:
        return f"Error: {str(e)}"


def _build_mismatch_hint(content: str, old_text: str, total_lines: int) -> str:
    """
    匹配失败时构建诊断提示，包含文件中最相近的内容片段。
    帮助 LLM 理解为什么匹配不上并修正 old_text。
    """
    lines = content.split('\n')
    old_lines = old_text.strip().split('\n')
    old_first = old_lines[0].strip() if old_lines else ""
    
    hint_parts = [
        f"Error: old_text not found in {total_lines}-line file.",
        "",
    ]
    
    # 策略1: 搜索 old_text 首行的精确匹配
    if old_first:
        matches = []
        for i, line in enumerate(lines):
            if old_first in line or line.strip() == old_first:
                # 取匹配位置 ±5 行的上下文
                start = max(0, i - 5)
                end = min(len(lines), i + 6)
                ctx = '\n'.join(f"{j+1}: {lines[j]}" for j in range(start, end))
                matches.append((i + 1, ctx))
        
        if matches:
            hint_parts.append("Lines containing similar text:")
            for line_num, ctx in matches[:3]:
                hint_parts.append(f"\n--- near line {line_num} ---")
                hint_parts.append(ctx)
            return '\n'.join(hint_parts)
    
    # 策略2: 用 SequenceMatcher 找最相近的连续区域
    best_ratio = 0.0
    best_start = 0
    search_len = min(len(old_lines), 10)
    
    if search_len > 0 and len(lines) >= search_len:
        old_sample = '\n'.join(old_lines[:search_len])
        for i in range(len(lines) - search_len + 1):
            candidate = '\n'.join(lines[i:i + search_len])
            ratio = difflib.SequenceMatcher(
                None, old_sample[:500], candidate[:500]
            ).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_start = i
        
        if best_ratio > 0.3:
            start = max(0, best_start - 2)
            end = min(len(lines), best_start + search_len + 2)
            ctx = '\n'.join(f"{j+1}: {lines[j]}" for j in range(start, end))
            hint_parts.append(f"Closest match (similarity: {best_ratio:.0%}):")
            hint_parts.append(ctx)
            return '\n'.join(hint_parts)
    
    # 策略3: 返回文件前 30 行 + 后 10 行
    hint_parts.append("File content (first 30 lines):")
    for i, line in enumerate(lines[:30]):
        hint_parts.append(f"{i+1}: {line}")
    if total_lines > 40:
        hint_parts.append(f"... ({total_lines - 40} lines omitted) ...")
        for i in range(max(30, total_lines - 10), total_lines):
            if i < len(lines):
                hint_parts.append(f"{i+1}: {lines[i]}")
    
    return '\n'.join(hint_parts)


def _count_changed_lines(old: str, new: str) -> int:
    """快速统计变更行数（不生成完整 diff）"""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    changed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != 'equal':
            changed += max(i2 - i1, j2 - j1)
    return changed


def _create_backup(path: str) -> str:
    """创建文件备份"""
    backup_dir = os.path.join(os.path.dirname(path) or '.', '.backup')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = os.path.basename(path)
    backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")
    
    counter = 1
    while os.path.exists(backup_path):
        backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}_{counter}.bak")
        counter += 1

    with open(path, 'r', encoding='utf-8') as src:
        with open(backup_path, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    
    return backup_path


# 注册工具
register_tool("replace_in_file", {
    "description": (
        "Replace exact text in a file. "
        "old_text must match EXACTLY (including whitespace and indentation). "
        "If match fails, returns closest matching content to help you fix old_text."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path"
            },
            "old_text": {
                "type": "string",
                "description": "Exact text to find (must match file content precisely, including whitespace)"
            },
            "new_text": {
                "type": "string",
                "description": "Text to replace with"
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: first only)",
                "default": False
            },
        },
        "required": ["path", "old_text", "new_text"]
    },
    "handler": replace_in_file_handler,
    "permission_level": "write"
})
