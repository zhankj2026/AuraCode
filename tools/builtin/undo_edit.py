"""
undo_edit 工具 - 撤销上次文件编辑

基于 code.md Phase 2 实现
参考: 第 4.2 节
"""

import os
import json
import shutil
from datetime import datetime
from tools.registry import register_tool

# 编辑历史记录文件
EDIT_HISTORY_FILE = ".backup/edit_history.json"


def _load_history() -> list:
    """加载编辑历史"""
    if os.path.exists(EDIT_HISTORY_FILE):
        with open(EDIT_HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_history(history: list):
    """保存编辑历史"""
    os.makedirs(os.path.dirname(EDIT_HISTORY_FILE), exist_ok=True)
    with open(EDIT_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def record_edit(path: str, backup_path: str, original_content: str):
    """记录编辑操作(供 replace_in_file 调用)"""
    history = _load_history()
    history.append({
        "path": os.path.abspath(path),
        "backup_path": os.path.abspath(backup_path),
        "timestamp": datetime.now().isoformat()
    })
    # 只保留最近 50 条记录
    if len(history) > 50:
        history = history[-50:]
    _save_history(history)


def undo_edit_handler(path: str = None) -> str:
    """
    撤销上次编辑
    
    Args:
        path: 可选,指定要撤销的文件路径。如果不指定,撤销最近一次的编辑
    
    Returns:
        撤销结果
    """
    try:
        history = _load_history()
        
        if not history:
            return "没有可撤销的操作"
        
        # 如果指定了路径,找到该文件的最近编辑记录
        if path:
            path = os.path.abspath(path)
            # 从后往前找
            for i in range(len(history) - 1, -1, -1):
                if history[i]["path"] == path:
                    edit_record = history.pop(i)
                    break
            else:
                return f"未找到 {path} 的编辑记录"
        else:
            # 撤销最近一次编辑
            edit_record = history.pop()
        
        # 恢复备份
        backup_path = edit_record["backup_path"]
        original_path = edit_record["path"]
        
        if not os.path.exists(backup_path):
            return f"错误: 备份文件不存在: {backup_path}"
        
        # 复制备份回原文件
        shutil.copy2(backup_path, original_path)
        
        # 保存更新后的历史
        _save_history(history)
        
        return f"✅ 已撤销编辑\n文件: {original_path}\n恢复自: {backup_path}"
    
    except Exception as e:
        return f"错误: {str(e)}"


def edit_history_handler(limit: int = 10) -> str:
    """
    查看编辑历史
    
    Args:
        limit: 显示最近多少条记录,默认 10
    
    Returns:
        编辑历史列表
    """
    try:
        history = _load_history()
        
        if not history:
            return "没有编辑历史"
        
        # 显示最近的记录
        recent = history[-limit:]
        recent.reverse()  # 最近的在前面
        
        lines = [f"编辑历史(最近 {len(recent)} 条):", ""]
        for i, record in enumerate(recent, 1):
            time_str = record["timestamp"][:19]  # 去掉毫秒
            lines.append(f"{i}. {time_str}")
            lines.append(f"   文件: {record['path']}")
            lines.append(f"   备份: {record['backup_path']}")
            lines.append("")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"错误: {str(e)}"


# 注册工具
register_tool("undo_edit", {
    "description": "撤销上次的文件编辑操作",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "可选,指定要撤销的文件路径。不指定则撤销最近一次编辑"
            }
        },
        "required": []
    },
    "handler": undo_edit_handler,
    "permission_level": "write"
})

register_tool("edit_history", {
    "description": "查看编辑历史记录",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "显示最近多少条记录",
                "default": 10
            }
        },
        "required": []
    },
    "handler": edit_history_handler,
    "permission_level": "read"
})
