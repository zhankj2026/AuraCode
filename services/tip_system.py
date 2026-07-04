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
TipSystem 服务 — 功能发现提示

在适当时机向用户展示功能使用提示，
帮助用户发现 auracode 的高级功能。
支持提示注册、冷却机制、历史记录和上下文感知调度。
"""
import json
import os
import time
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable


# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class Tip:
    """一条功能提示"""
    tip_id: str
    title: str
    content: str
    category: str           # command / tool / workflow / shortcut
    cooldown_sessions: int = 5  # 展示后冷却 N 个会话
    condition: Optional[str] = None  # 条件标识符 (如 "has_git", "large_project")
    priority: int = 50      # 优先级 (0-100, 越高越优先)
    emoji: str = "💡"


@dataclass
class TipContext:
    """提示展示上下文"""
    session_count: int = 0      # 当前会话编号
    has_git: bool = True
    has_mcp: bool = False
    project_size: str = "medium"  # small/medium/large
    used_commands: List[str] = field(default_factory=list)
    used_tools: List[str] = field(default_factory=list)
    os_platform: str = "unknown"


# ── 内置提示注册表 ──────────────────────────────────────

BUILTIN_TIPS: List[Tip] = [
    # 命令类
    Tip(
        tip_id="cmd_review",
        title="代码审查",
        content="使用 /review 对 Git 变更进行 AI 代码审查，快速发现 bug 和安全问题。",
        category="command",
        cooldown_sessions=10,
        priority=80,
        emoji="🔍",
    ),
    Tip(
        tip_id="cmd_security",
        title="安全扫描",
        content="使用 /security-review 扫描分支变更中的 16 类安全漏洞（注入/XSS/硬编码密钥等）。",
        category="command",
        cooldown_sessions=10,
        priority=85,
        emoji="🔒",
    ),
    Tip(
        tip_id="cmd_compact",
        title="压缩对话",
        content="对话太长时，使用 /compact 压缩历史消息，保留摘要释放上下文空间。",
        category="command",
        cooldown_sessions=8,
        priority=70,
        emoji="📦",
    ),
    Tip(
        tip_id="cmd_cost",
        title="费用追踪",
        content="使用 /cost 查看当前会话的 token 使用和费用明细（按模型分类统计）。",
        category="command",
        cooldown_sessions=10,
        priority=60,
        emoji="💰",
    ),
    Tip(
        tip_id="cmd_context",
        title="上下文可视化",
        content="使用 /context overview 查看 token 使用分布，/context detail 查看每条消息的 token 占比。",
        category="command",
        cooldown_sessions=10,
        priority=65,
        emoji="📊",
    ),
    Tip(
        tip_id="cmd_plan",
        title="任务规划",
        content="使用 /plan 进入计划模式，让 AI 先分析问题并制定方案，再逐步执行。适合复杂重构任务。",
        category="command",
        cooldown_sessions=8,
        priority=75,
        emoji="📋",
    ),
    Tip(
        tip_id="cmd_rewind",
        title="会话回退",
        content="使用 /rewind 撤销上一轮对话，回到之前的检查点。AI 犯错时可以无损回退。",
        category="command",
        cooldown_sessions=10,
        priority=80,
        emoji="⏪",
    ),
    Tip(
        tip_id="cmd_export",
        title="导出对话",
        content="使用 /export 将对话导出为 Markdown 或 JSON 文件，方便归档和分享。",
        category="command",
        cooldown_sessions=15,
        priority=50,
        emoji="📄",
    ),
    Tip(
        tip_id="cmd_model",
        title="模型切换",
        content="使用 /model <name> 运行时切换 AI 模型，/model compare 可多模型并行对比结果。",
        category="command",
        cooldown_sessions=10,
        priority=60,
        emoji="🤖",
    ),
    Tip(
        tip_id="cmd_history",
        title="会话历史",
        content="使用 /history 查看最近的会话记录，/resume 可以恢复之前的会话继续对话。",
        category="command",
        cooldown_sessions=10,
        priority=55,
        emoji="📜",
    ),

    # 工具类
    Tip(
        tip_id="tool_web",
        title="网络搜索",
        content="AI 可以自动使用 web_search 和 web_fetch 搜索网络信息，帮你查找文档和解决方案。",
        category="tool",
        cooldown_sessions=15,
        priority=55,
        emoji="🌐",
    ),
    Tip(
        tip_id="tool_glob",
        title="文件搜索",
        content="AI 使用 glob 工具按模式搜索文件（如 **/*.py），使用 grep 按内容搜索代码。",
        category="tool",
        cooldown_sessions=15,
        priority=50,
        emoji="🔎",
    ),

    # 工作流类
    Tip(
        tip_id="wf_brief",
        title="输出模式",
        content="输入 /brief 切换简洁输出模式，减少冗余说明，只看关键结果。",
        category="workflow",
        cooldown_sessions=15,
        priority=60,
        emoji="✂️",
    ),
    Tip(
        tip_id="wf_memory",
        title="记忆系统",
        content="使用 /memory 管理 AI 的长期记忆。AI 会记住你的项目偏好和编码习惯。",
        category="workflow",
        cooldown_sessions=15,
        priority=55,
        emoji="🧠",
    ),
    Tip(
        tip_id="wf_hooks",
        title="Hook 自动化",
        content="使用 /hooks 管理自动化钩子。可以在 AI 执行工具前后添加自定义逻辑。",
        category="workflow",
        cooldown_sessions=20,
        priority=45,
        emoji="🪝",
    ),
    Tip(
        tip_id="wf_plugins",
        title="插件生态",
        content="使用 /plugins 查看和管理插件。插件可以扩展 AI 的能力（自动格式化、lint等）。",
        category="workflow",
        cooldown_sessions=20,
        priority=40,
        emoji="🧩",
    ),

    # 快捷键类
    Tip(
        tip_id="sc_abort",
        title="中断执行",
        content="按 Ctrl+C 可以随时中断 AI 的当前操作，不会丢失已完成的工作。",
        category="shortcut",
        cooldown_sessions=10,
        priority=70,
        emoji="⛔",
    ),
]


# ── 提示历史管理 ──────────────────────────────────────────

class TipHistory:
    """提示展示历史记录"""

    def __init__(self, history_file: str = None):
        self._history_file = history_file or self._default_path()
        self._history: Dict[str, int] = {}  # tip_id -> last_shown_session
        self._session_count: int = 0
        self._load()

    def _default_path(self) -> str:
        config_dir = os.path.join(os.path.expanduser("~"), ".auracode")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "tip_history.json")

    def _load(self):
        """从磁盘加载历史"""
        try:
            if os.path.exists(self._history_file):
                with open(self._history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._history = data.get("history", {})
                self._session_count = data.get("session_count", 0)
        except Exception:
            self._history = {}
            self._session_count = 0

    def _save(self):
        """保存历史到磁盘"""
        try:
            os.makedirs(os.path.dirname(self._history_file), exist_ok=True)
            with open(self._history_file, "w", encoding="utf-8") as f:
                json.dump({
                    "history": self._history,
                    "session_count": self._session_count,
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def increment_session(self):
        """递增会话计数"""
        self._session_count += 1
        self._save()

    def get_session_count(self) -> int:
        return self._session_count

    def sessions_since_shown(self, tip_id: str) -> int:
        """获取距离上次展示的会话数"""
        last = self._history.get(tip_id)
        if last is None:
            return float("inf")
        return self._session_count - last

    def record_shown(self, tip_id: str):
        """记录提示已展示"""
        self._history[tip_id] = self._session_count
        self._save()


# ── 提示调度器 ──────────────────────────────────────────

class TipScheduler:
    """提示调度器 — 选择最合适的提示展示"""

    def __init__(self, tips: List[Tip] = None, history: TipHistory = None):
        self._tips = tips or list(BUILTIN_TIPS)
        self._history = history or TipHistory()
        self._lock = threading.Lock()

    def get_relevant_tips(self, context: TipContext = None,
                          limit: int = 1) -> List[Tip]:
        """
        获取当前可用的相关提示列表。

        Args:
            context: 当前上下文
            limit: 返回数量限制

        Returns:
            按优先级排序的可用提示列表
        """
        ctx = context or TipContext()
        candidates = []

        for tip in self._tips:
            # 冷却检查
            since = self._history.sessions_since_shown(tip.tip_id)
            if since < tip.cooldown_sessions:
                continue

            # 已使用命令/工具的提示降权
            if tip.category == "command":
                cmd_name = tip.tip_id.replace("cmd_", "/")
                if cmd_name in ctx.used_commands:
                    continue  # 用户已知道这个命令

            candidates.append((tip, since))

        # 按展示间隔排序（最久没展示的优先），然后按优先级
        candidates.sort(key=lambda x: (-x[1], -x[0].priority))

        return [tip for tip, _ in candidates[:limit]]

    def get_tip_to_show(self, context: TipContext = None) -> Optional[Tip]:
        """获取一条要展示的提示"""
        tips = self.get_relevant_tips(context, limit=1)
        return tips[0] if tips else None

    def record_shown(self, tip: Tip):
        """记录提示已展示"""
        self._history.record_shown(tip.tip_id)

    def format_tip(self, tip: Tip) -> str:
        """格式化提示为显示文本"""
        return (
            f"\n{tip.emoji} Tip: {tip.title}\n"
            f"   {tip.content}\n"
        )

    def get_and_format_tip(self, context: TipContext = None) -> Optional[str]:
        """获取并格式化一条提示，同时记录已展示"""
        tip = self.get_tip_to_show(context)
        if tip:
            self.record_shown(tip)
            return self.format_tip(tip)
        return None

    def list_all_tips(self) -> List[Tip]:
        """列出所有可用提示"""
        return list(self._tips)

    def register_tip(self, tip: Tip):
        """注册新提示"""
        with self._lock:
            self._tips.append(tip)

    def remove_tip(self, tip_id: str):
        """移除提示"""
        with self._lock:
            self._tips = [t for t in self._tips if t.tip_id != tip_id]


# ── /tips 命令 ──────────────────────────────────────────

def tips_handler(args: list, loop=None) -> str:
    """
    管理功能提示。

    用法:
        /tips          — 显示一条随机提示
        /tips list     — 列出所有提示
        /tips reset    — 重置提示历史
    """
    scheduler = get_tip_scheduler()

    if "list" in args:
        tips = scheduler.list_all_tips()
        lines = ["📋 所有功能提示:", ""]
        categories = {}
        for tip in tips:
            cat = tip.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(tip)

        for cat, cat_tips in sorted(categories.items()):
            lines.append(f"  [{cat}]")
            for tip in cat_tips:
                lines.append(f"    {tip.emoji} {tip.title}: {tip.content}")
            lines.append("")

        return "\n".join(lines)

    elif "reset" in args:
        scheduler._history._history = {}
        scheduler._history._save()
        return "✅ 提示历史已重置。"

    else:
        formatted = scheduler.get_and_format_tip()
        if formatted:
            return formatted
        return "暂无更多提示。使用 /tips list 查看所有提示。"


# ── 全局单例 ──────────────────────────────────────────────

_tip_scheduler: Optional[TipScheduler] = None


def get_tip_scheduler() -> TipScheduler:
    """获取全局 TipScheduler 实例"""
    global _tip_scheduler
    if _tip_scheduler is None:
        _tip_scheduler = TipScheduler()
    return _tip_scheduler


# ── 注册命令 ──────────────────────────────────────────────

try:
    from commands.registry import register_command
    register_command("tips", {
        "description": "功能发现提示 — 查看 auracode 高级功能",
        "handler": tips_handler,
        "category": "help",
        "args_help": "[list|reset]  显示提示/列出所有/重置历史",
    })
except Exception:
    pass  # 命令注册表未初始化时静默跳过
