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
Benchmark 命令 — 性能基准测试

测量 auracode 核心操作的性能指标：
- LLM 调用延迟
- 工具执行速度
- 上下文压缩耗时
- Token 吞吐率
"""
import time
import os
from commands.registry import register_command


def benchmark_handler(args: list, loop=None) -> str:
    """
    执行性能基准测试。

    用法:
        /benchmark          — 完整基准测试
        /benchmark quick    — 快速测试（跳过 LLM）
        /benchmark llm      — 仅测试 LLM 延迟
    """
    mode = args[0] if args else "full"

    lines = []
    lines.append("=" * 60)
    lines.append("⚡ 性能基准测试")
    lines.append("=" * 60)
    lines.append(f"模式: {mode}")
    lines.append("")

    results = []

    # 1. 工具注册表加载速度
    t0 = time.perf_counter()
    from tools.registry import TOOL_REGISTRY
    t1 = time.perf_counter()
    tool_count = len(TOOL_REGISTRY)
    results.append(("工具注册表加载", t1 - t0, f"{tool_count} 个工具"))

    # 2. 命令注册表加载速度
    t0 = time.perf_counter()
    from commands.registry import COMMAND_REGISTRY
    t1 = time.perf_counter()
    cmd_count = len(COMMAND_REGISTRY)
    results.append(("命令注册表加载", t1 - t0, f"{cmd_count} 个命令"))

    # 3. Hook 系统
    t0 = time.perf_counter()
    from hooks.manager import HookManager, HOOK_EVENTS
    hm = HookManager()
    t1 = time.perf_counter()
    results.append(("HookManager 初始化", t1 - t0, f"{len(HOOK_EVENTS)} 事件类型"))

    # 4. 文件 I/O 性能
    test_size = 100 * 1024  # 100KB
    test_content = "x" * test_size
    test_path = os.path.join(os.path.dirname(__file__), "_bench_tmp.txt")
    t0 = time.perf_counter()
    with open(test_path, "w") as f:
        f.write(test_content)
    with open(test_path, "r") as f:
        _ = f.read()
    os.remove(test_path)
    t1 = time.perf_counter()
    throughput = test_size * 2 / (t1 - t0) / 1024 / 1024
    results.append(("文件 I/O (100KB r+w)", t1 - t0, f"{throughput:.1f} MB/s"))

    # 5. Microcompact 性能（模拟）
    if loop:
        msgs_backup = list(loop.state.messages)
        try:
            # 注入测试消息
            loop.state.messages = [
                {"role": "system", "content": "test"},
            ] + [
                {"role": "assistant", "content": f"msg {i}", "tool_calls": [
                    {"id": f"tc_{i}", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
                ]} if i % 2 == 0 else
                {"role": "tool", "tool_call_id": f"tc_{i-1}", "content": "x" * 500}
                for i in range(1, 21)
            ]
            t0 = time.perf_counter()
            cleared = loop._microcompact()
            t1 = time.perf_counter()
            results.append(("Microcompact (20 msgs)", t1 - t0, f"清除 {cleared} 条"))
        finally:
            loop.state.messages = msgs_backup

    # 6. LLM 延迟测试（需要 loop 且非 quick 模式）
    if loop and mode != "quick":
        try:
            t0 = time.perf_counter()
            resp = loop.client.chat.completions.create(
                model=loop.model,
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=5,
                temperature=0,
            )
            t1 = time.perf_counter()
            tokens = 0
            if resp.usage:
                tokens = resp.usage.total_tokens
            tps = tokens / (t1 - t0) if (t1 - t0) > 0 else 0
            results.append(("LLM 延迟 (简单请求)", t1 - t0, f"{tokens} tokens, {tps:.1f} t/s"))
        except Exception as e:
            results.append(("LLM 延迟", 0, f"失败: {str(e)[:50]}"))

    # 7. 上下文压缩性能（需要 loop）
    if loop and mode == "full":
        msgs_backup = list(loop.state.messages)
        try:
            # 注入 30 条测试消息
            loop.state.messages = [
                {"role": "system", "content": "test system prompt"},
            ] + [
                {"role": "user" if i % 3 == 0 else "assistant", "content": f"message {i} " * 50}
                for i in range(30)
            ]
            old_count = len(loop.state.messages)
            t0 = time.perf_counter()
            loop._snip_old_tool_results()
            t1 = time.perf_counter()
            results.append(("Snip (30 msgs)", t1 - t0, f"{old_count} 条消息"))
        finally:
            loop.state.messages = msgs_backup

    # 输出结果
    for name, duration, detail in results:
        if duration > 0:
            if duration < 0.001:
                dur_str = f"{duration * 1_000_000:.0f} μs"
            elif duration < 1:
                dur_str = f"{duration * 1000:.1f} ms"
            else:
                dur_str = f"{duration:.2f} s"
        else:
            dur_str = "N/A"
        lines.append(f"  {name:<25} {dur_str:>12}  | {detail}")

    # 总结
    lines.append("")
    lines.append("─" * 40)
    total_time = sum(d for _, d, _ in results if d > 0)
    lines.append(f"总耗时: {total_time:.3f}s ({len(results)} 项测试)")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("benchmark", {
    "description": "性能基准测试（测量核心操作延迟和吞吐率）",
    "handler": benchmark_handler,
    "category": "analysis",
    "args_help": "[quick|full|llm]  quick=跳过LLM, full=完整测试",
})
