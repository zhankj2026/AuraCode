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
Model 命令 - 运行时模型切换、历史回滚与多模型对比

功能:
- 查看当前模型
- 切换到指定模型
- 列出可用模型
- 显示 fallback 模型状态
- 模型切换历史记录与回滚
- 多模型并行对比（同一 prompt 多模型响应）

用法:
  /model              显示当前模型
  /model <name>       切换到指定模型
  /model list         列出可用模型
  /model reset        恢复默认模型
  /model history      模型切换历史
  /model rollback     回滚到上一个模型
  /model compare <prompt>  多模型并行对比
"""

import time
import threading
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from commands.registry import register_command
from core.session_state import MODEL_PRICING, get_model_pricing

logger = logging.getLogger(__name__)


# ── 模型切换历史 ──
_model_history: List[Dict] = []  # [{from, to, timestamp, reason}]
_HISTORY_MAX = 50


def _record_switch(from_model: str, to_model: str, reason: str = "user"):
    """记录一次模型切换"""
    _model_history.append({
        "from": from_model,
        "to": to_model,
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
    })
    # 限制历史大小
    if len(_model_history) > _HISTORY_MAX:
        _model_history.pop(0)


# 内置可用模型列表（常见模型）
AVAILABLE_MODELS = [
    # Claude 系列
    "claude-opus-4",
    "claude-sonnet-4",
    "claude-3.5-sonnet",
    "claude-3.5-haiku",
    # GLM 系列
    "glm-4-plus",
    "glm-4",
    "glm-4.5",
    "glm-4.7",
    # GPT 系列
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "o1",
    "o3-mini",
    # DeepSeek
    "deepseek-chat",
    "deepseek-reasoner",
    # Qwen
    "qwen-max",
    "qwen-plus",
    "qwen-turbo",
]


def model_handler(args: list, loop=None) -> str:
    """model 命令处理函数"""
    if loop is None:
        return "❌ AgentLoop 未初始化"

    state = getattr(loop, 'state', None)
    base_model = getattr(loop, 'model', 'unknown')
    active_model = state.get_active_model(base_model) if state else base_model

    # 无参数 → 显示当前模型
    if not args:
        lines = []
        lines.append("🤖 当前模型配置")
        lines.append("=" * 60)
        lines.append(f"  基础模型:   {base_model}")
        lines.append(f"  活跃模型:   {active_model}")
        if state and state.fallback_model:
            lines.append(f"  Fallback:   {state.fallback_model}")
            if state._active_model_override:
                lines.append(f"  ⚠️  当前使用 fallback 模型")
        pricing = get_model_pricing(active_model)
        lines.append(f"  定价:       ${pricing.input_per_mtok}/M 输入, ${pricing.output_per_mtok}/M 输出")
        lines.append("")
        lines.append("  使用 /model <name> 切换模型")
        lines.append("  使用 /model list 查看可用模型")
        lines.append("  使用 /model reset 恢复默认模型")
        lines.append("=" * 60)
        return "\n".join(lines)

    action = args[0].lower()

    # list → 列出可用模型
    if action in ('list', 'ls', '列表'):
        lines = []
        lines.append("🤖 可用模型列表")
        lines.append("=" * 60)
        lines.append(f"  {'模型':<24} {'输入':>8} {'输出':>8}")
        lines.append(f"  {'-' * 44}")
        for m in AVAILABLE_MODELS:
            p = get_model_pricing(m)
            marker = " ← 当前" if m == active_model else ""
            lines.append(
                f"  {m:<24} ${p.input_per_mtok:>6.2f} ${p.output_per_mtok:>6.2f}{marker}"
            )
        lines.append("")
        lines.append("  提示: 也可输入任意 OpenAI 兼容模型名")
        lines.append("=" * 60)
        return "\n".join(lines)

    # reset → 恢复默认模型
    if action in ('reset', 'default', '默认'):
        old_model = active_model
        if state:
            state.reset_model_override()
        _record_switch(old_model, base_model, "reset")
        lines = []
        lines.append(f"✅ 已恢复默认模型: {old_model} → {base_model}")
        return "\n".join(lines)

    # history → 模型切换历史
    if action in ('history', 'hist', '历史'):
        return _cmd_history()

    # rollback / back → 回滚到上一个模型
    if action in ('rollback', 'back', '回滚'):
        return _cmd_rollback(loop, state, active_model)

    # compare → 多模型并行对比
    if action in ('compare', 'cmp', '对比'):
        prompt = " ".join(args[1:]) if len(args) > 1 else ""
        return _cmd_compare(loop, prompt)

    # <name> → 切换模型
    target_model = " ".join(args)
    lines = []

    # 验证模型（尝试 API 调用）
    try:
        client = getattr(loop, 'client', None)
        if client:
            # 轻量验证
            resp = client.chat.completions.create(
                model=target_model,
                messages=[{"role": "user", "content": "."}],
                max_tokens=1,
                temperature=0,
            )
            validation_ok = True
        else:
            validation_ok = False
    except Exception as e:
        # 模型可能有效但当前无法验证，仍然允许切换
        lines.append(f"⚠️  无法验证模型: {str(e)[:60]}")
        lines.append(f"   将尝试切换，如模型无效将在下次调用时报错")
        validation_ok = None  # 未确定

    # 执行切换
    old_model = active_model
    loop.model = target_model
    if state:
        state.reset_model_override()
        state.set_current_model(target_model)

    _record_switch(old_model, target_model, "user")

    pricing = get_model_pricing(target_model)
    lines.insert(0, f"✅ 模型已切换: {old_model} → {target_model}")
    lines.append(f"   定价: ${pricing.input_per_mtok}/M 输入, ${pricing.output_per_mtok}/M 输出")
    if validation_ok is True:
        lines.append(f"   ✅ API 验证通过")

    lines.append("=" * 60)
    return "\n".join(lines)


def _cmd_history() -> str:
    """显示模型切换历史"""
    if not _model_history:
        return "📜 模型切换历史: 暂无记录"

    lines = [
        f"📜 模型切换历史 (最近 {len(_model_history)} 次)",
        "=" * 60,
    ]
    for i, h in enumerate(reversed(_model_history[-20:]), 1):
        ts = h['timestamp'][:19].replace('T', ' ')
        lines.append(f"  {i:>3}. {h['from']} → {h['to']}  [{h['reason']}]  {ts}")
    lines.append("=" * 60)
    lines.append("  使用 /model rollback 回滚到上一个模型")
    return "\n".join(lines)


def _cmd_rollback(loop, state, active_model: str) -> str:
    """回滚到上一个模型"""
    if not _model_history:
        return "❌ 没有可回滚的模型切换记录"

    last = _model_history[-1]
    target = last["from"]
    _record_switch(active_model, target, "rollback")

    loop.model = target
    if state:
        state.reset_model_override()
        state.set_current_model(target)

    pricing = get_model_pricing(target)
    lines = [
        f"⏪ 模型已回滚: {active_model} → {target}",
        f"   定价: ${pricing.input_per_mtok}/M 输入, ${pricing.output_per_mtok}/M 输出",
        "=" * 60,
    ]
    return "\n".join(lines)


def _cmd_compare(loop, prompt: str) -> str:
    """多模型并行对比"""
    if not prompt:
        return (
            "❌ 请提供对比 prompt\n"
            "用法: /model compare <你的问题>\n"
            "示例: /model compare 解释Python的GIL是什么"
        )

    client = getattr(loop, 'client', None)
    if not client:
        return "❌ OpenAI client 未初始化"

    # 选择对比模型（当前 + 常见模型，最多 4 个）
    current = getattr(loop, 'model', 'unknown')
    compare_models = [current]
    candidates = ["gpt-4o", "claude-3.5-sonnet", "deepseek-chat", "glm-4-plus"]
    for m in candidates:
        if m != current and len(compare_models) < 4:
            compare_models.append(m)

    lines = [
        f"🔄 多模型对比 ({len(compare_models)} 个模型)",
        f"   Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}",
        "=" * 60,
    ]

    results: Dict[str, Tuple[str, float]] = {}

    def _call_model(model_name: str):
        """调用单个模型"""
        try:
            start = time.time()
            resp = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7,
            )
            elapsed = time.time() - start
            text = resp.choices[0].message.content or "(空响应)"
            results[model_name] = (text, elapsed)
        except Exception as e:
            results[model_name] = (f"❌ 错误: {str(e)[:100]}", -1)

    # 并行调用
    threads = []
    for m in compare_models:
        t = threading.Thread(target=_call_model, args=(m,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=60)

    # 输出结果
    for m in compare_models:
        if m in results:
            text, elapsed = results[m]
            dur_str = f"{elapsed:.1f}s" if elapsed >= 0 else "N/A"
            marker = " ← 当前" if m == current else ""
            lines.append(f"\n  🤖 {m} ({dur_str}){marker}")
            lines.append(f"  {'─' * 50}")
            # 截取前 300 字符
            preview = text[:300]
            if len(text) > 300:
                preview += f"... (截断 {len(text) - 300} 字符)"
            for line in preview.split("\n"):
                lines.append(f"  {line}")
        else:
            lines.append(f"\n  🤖 {m} — ⏱️ 超时")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


register_command("model", {
    "description": "模型切换/历史/回滚/对比 - 支持 list/reset/history/rollback/compare",
    "handler": model_handler,
    "category": "config",
    "args_help": "[模型名|list|reset|history|rollback|compare <prompt>]"
})
