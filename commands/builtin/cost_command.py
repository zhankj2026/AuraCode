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
Cost 命令 - 会话费用追踪与展示

功能:
- 显示当前会话的总费用
- 按模型维度展示费用明细（input/output tokens、缓存 token、API 调用次数）
- 显示每模型的定价信息
- 支持预算状态展示

用法:
  /cost          显示费用概览
  /cost detail   显示每模型详细费用
"""

from commands.registry import register_command
from core.session_state import get_model_pricing


def _fmt_cost(cost: float) -> str:
    """格式化费用显示"""
    if cost > 0.5:
        return f"${cost:.2f}"
    elif cost > 0.001:
        return f"${cost:.4f}"
    else:
        return f"${cost:.6f}"


def _fmt_tokens(n: int) -> str:
    """格式化 token 数量"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def cost_handler(args: list, loop=None) -> str:
    """cost 命令处理函数"""
    if loop is None:
        return "❌ AgentLoop 未初始化"

    state = getattr(loop, 'state', None)
    if state is None:
        return "❌ SessionState 未初始化"

    lines = []
    lines.append("💰 会话费用统计")
    lines.append("=" * 60)

    # ── 总览 ──
    total_cost = state.total_cost_usd
    total_usage = state.total_usage
    turn_count = state.turn_count

    lines.append(f"  总费用:     {_fmt_cost(total_cost)}")
    lines.append(f"  总 Token:   {_fmt_tokens(total_usage.total_tokens)}"
                 f" (输入={_fmt_tokens(total_usage.prompt_tokens)},"
                 f" 输出={_fmt_tokens(total_usage.completion_tokens)})")
    lines.append(f"  API 轮次:   {turn_count}")

    # ── 预算状态 ──
    if state.max_budget_usd is not None:
        remaining = state.budget_remaining()
        pct = (total_cost / state.max_budget_usd * 100) if state.max_budget_usd > 0 else 0
        bar_width = 25
        filled = int(pct / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        icon = "🟢" if pct < 50 else ("🟡" if pct < 80 else "🔴")
        lines.append(f"\n  预算: {_fmt_cost(state.max_budget_usd)}")
        lines.append(f"  {icon} [{bar}] {pct:.1f}%")
        lines.append(f"  剩余: {_fmt_cost(remaining) if remaining is not None else 'N/A'}")

    # ── 每模型明细 ──
    breakdown = state.get_cost_breakdown()
    if breakdown:
        lines.append(f"\n📊 每模型费用明细:")
        lines.append(f"  {'模型':<20} {'输入':>8} {'输出':>8} {'缓存读':>8} {'调用':>4} {'费用':>10}")
        lines.append(f"  {'-' * 62}")

        for entry in breakdown:
            model_name = entry["model"]
            if len(model_name) > 18:
                model_name = model_name[:16] + ".."
            lines.append(
                f"  {model_name:<20}"
                f" {_fmt_tokens(entry['input_tokens']):>8}"
                f" {_fmt_tokens(entry['output_tokens']):>8}"
                f" {_fmt_tokens(entry['cache_read']):>8}"
                f" {entry['api_calls']:>4}"
                f" {_fmt_cost(entry['cost_usd']):>10}"
            )

        # 定价信息
        detail_mode = args and args[0].lower() in ('detail', 'pricing', '详细')
        if detail_mode:
            lines.append(f"\n💲 模型定价 (USD/M tokens):")
            lines.append(f"  {'模型':<20} {'输入':>8} {'输出':>8} {'缓存读':>8} {'缓存写':>8}")
            lines.append(f"  {'-' * 56}")
            seen = set()
            for entry in breakdown:
                m = entry["model"]
                if m in seen:
                    continue
                seen.add(m)
                p = entry["pricing"]
                pricing = get_model_pricing(m)
                lines.append(
                    f"  {m:<20}"
                    f" ${p['input']:>6.2f}"
                    f" ${p['output']:>6.2f}"
                    f" ${pricing.cache_read_per_mtok:>6.2f}"
                    f" ${pricing.cache_write_per_mtok:>6.2f}"
                )
    else:
        lines.append("\n  ℹ️  暂无 API 调用记录")

    # ── 当前模型信息 ──
    model = getattr(loop, 'model', 'unknown')
    active = state.get_active_model(model)
    lines.append(f"\n  当前模型: {active}")
    if state.fallback_model and state._active_model_override:
        lines.append(f"  ⚠️  已切换到 fallback 模型: {state.fallback_model}")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("cost", {
    "description": "显示当前会话的费用统计 - 总费用、每模型明细、定价信息",
    "handler": cost_handler,
    "category": "info",
    "args_help": "[detail] 显示详细定价信息"
})
