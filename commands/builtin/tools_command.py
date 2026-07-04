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
Tools 命令 - 工具执行追踪与缓存管理

功能:
- 查看工具调用时间线
- 查看工具执行统计报告
- 查看/清除工具缓存
- 查看按轮次的调用链

用法:
  /tools              显示工具执行概览
  /tools timeline     工具调用时间线
  /tools report       完整执行报告（含统计表）
  /tools stats        按工具统计
  /tools cache        缓存统计
  /tools cache-clear  清除所有缓存
  /tools clear        清除追踪记录
  /tools chain [N]    第 N 轮调用链
"""

from commands.registry import register_command
from core.tool_tracker import get_tool_tracker, get_tool_cache


def tools_handler(args: list, loop=None) -> str:
    """tools 命令处理函数"""
    tracker = get_tool_tracker()
    cache = get_tool_cache()

    if not args:
        return _cmd_overview(tracker, cache)

    action = args[0].lower()

    if action in ('timeline', 'tl', '时间线'):
        return _cmd_timeline(tracker)
    elif action in ('report', 'rpt', '报告'):
        return _cmd_report(tracker)
    elif action in ('stats', 'st', '统计'):
        return _cmd_stats(tracker)
    elif action == 'cache':
        return _cmd_cache_stats(cache)
    elif action in ('cache-clear', 'cc', '清缓存'):
        return _cmd_cache_clear(cache)
    elif action in ('clear', 'clr', '清除'):
        return _cmd_clear(tracker)
    elif action in ('chain', 'ch', '调用链'):
        turn = None
        if len(args) > 1:
            try:
                turn = int(args[1])
            except ValueError:
                pass
        return _cmd_chain(tracker, turn)
    else:
        return f"❌ 未知子命令: {action}\n可用: timeline / report / stats / cache / cache-clear / clear / chain"


def _cmd_overview(tracker, cache) -> str:
    """概览：最近调用 + 统计摘要 + 缓存状态"""
    records = tracker.get_records(10)
    stats = tracker.get_stats()
    cache_stats = cache.get_stats()

    total_calls = len(tracker._records)
    total_ms = sum(r.duration_ms for r in tracker._records)
    success_count = sum(1 for r in tracker._records if r.success)
    fail_count = total_calls - success_count

    lines = [
        "🔧 工具执行概览",
        "=" * 60,
    ]

    # 总览
    if total_calls == 0:
        lines.append("  📭 暂无工具调用记录")
    else:
        lines.append(f"  总调用: {total_calls} | ✅ {success_count} | ❌ {fail_count}")
        lines.append(f"  总耗时: {total_ms:.0f}ms ({total_ms/1000:.1f}s)")
        avg_ms = total_ms / max(total_calls, 1)
        lines.append(f"  平均耗时: {avg_ms:.0f}ms")

    # 缓存状态
    lines.append("")
    lines.append(f"  📦 缓存: {cache_stats['size']}/{cache_stats['max_size']} | "
                 f"命中率 {cache_stats['hit_rate_pct']:.1f}% ({cache_stats['hits']}命中/{cache_stats['misses']}未命中)")

    # 最近 5 次调用
    if records:
        lines.append("")
        lines.append(f"  📋 最近 {min(5, len(records))} 次调用:")
        for r in records[-5:]:
            icon = "✅" if r.success else "❌"
            dur = f"{r.duration_ms:.0f}ms"
            cached = " [缓存]" if r.result_preview.startswith("[cached]") else ""
            lines.append(f"    {icon} T{r.turn} {r.tool_name:<18} {dur:>8}{cached}")

    # 子命令提示
    lines.append("")
    lines.append("  子命令: timeline / report / stats / cache / chain [N] / clear / cache-clear")
    lines.append("=" * 60)
    return "\n".join(lines)


def _cmd_timeline(tracker) -> str:
    """时间线"""
    return tracker.get_timeline(limit=30)


def _cmd_report(tracker) -> str:
    """完整报告"""
    return tracker.get_report()


def _cmd_stats(tracker) -> str:
    """按工具统计"""
    stats = tracker.get_stats()
    if not stats:
        return "📊 暂无工具统计数据"

    lines = [
        "📊 工具统计（按总耗时排序）",
        "=" * 70,
        f"  {'工具':<20} {'调用':>5} {'成功':>5} {'失败':>5} {'总耗时':>10} {'平均':>8} {'最大':>8}",
        f"  {'-' * 64}",
    ]

    for name, s in sorted(stats.items(), key=lambda x: x[1]["total_ms"], reverse=True):
        avg_ms = s["total_ms"] / max(s["calls"], 1)
        fail_mark = " ⚠️" if s["failures"] > 0 else ""
        lines.append(
            f"  {name:<20} {s['calls']:>5} {s['successes']:>5} {s['failures']:>5} "
            f"{s['total_ms']:>9.0f}ms {avg_ms:>7.0f}ms {s['max_ms']:>7.0f}ms{fail_mark}"
        )

    # 总计
    total_calls = sum(s["calls"] for s in stats.values())
    total_ms = sum(s["total_ms"] for s in stats.values())
    total_fail = sum(s["failures"] for s in stats.values())
    lines.append(f"  {'-' * 64}")
    lines.append(f"  {'TOTAL':<20} {total_calls:>5} {'':>5} {total_fail:>5} {total_ms:>9.0f}ms")
    lines.append("=" * 70)
    return "\n".join(lines)


def _cmd_cache_stats(cache) -> str:
    """缓存统计"""
    lines = [
        cache.get_stats_text(),
        "",
        "  可缓存工具: " + ", ".join(sorted(cache._cacheable_tools)),
        "  禁缓存工具: " + ", ".join(sorted(cache._no_cache_tools)),
        "",
        "  使用 /tools cache-clear 清除所有缓存",
    ]
    return "\n".join(lines)


def _cmd_cache_clear(cache) -> str:
    """清除缓存"""
    old_size = len(cache._cache)
    cache.invalidate()
    return f"✅ 已清除 {old_size} 条缓存记录"


def _cmd_clear(tracker) -> str:
    """清除追踪记录"""
    old_count = len(tracker._records)
    tracker.clear()
    return f"✅ 已清除 {old_count} 条工具调用记录"


def _cmd_chain(tracker, turn=None) -> str:
    """调用链"""
    chain = tracker.get_call_chain(turn=turn)
    if not chain:
        target = f"第 {turn} 轮" if turn is not None else "所有轮次"
        return f"📭 {target}无工具调用记录"

    turn_label = f"第 {turn} 轮" if turn is not None else "所有轮次"
    lines = [
        f"🔗 工具调用链 — {turn_label} ({len(chain)} 次)",
        "=" * 60,
    ]

    for i, c in enumerate(chain, 1):
        icon = "✅" if c["success"] else "❌"
        dur = f"{c['duration_ms']:.0f}ms"
        lines.append(f"  {i:>3}. {icon} {c['tool_name']:<20} {dur:>8}  T{c['turn']}")
        if c.get("error"):
            lines.append(f"       ⚠️ {c['error'][:60]}")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("tools", {
    "description": "工具执行追踪与缓存管理 - timeline/report/stats/cache/chain",
    "handler": tools_handler,
    "category": "debug",
    "args_help": "[timeline|report|stats|cache|cache-clear|clear|chain [N]]"
})
