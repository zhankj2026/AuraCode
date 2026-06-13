"""
/hooks 命令 - Hook 链可视化管理

管理配置驱动的 Hook 规则，查看执行日志，动态添加/移除 Hook。

用法:
  /hooks                 - 列出所有 Hook（含配置和运行时）
  /hooks config          - 查看配置文件信息
  /hooks log             - 查看最近执行日志
  /hooks log <N>         - 查看最近 N 条日志
  /hooks reload          - 重新加载配置文件
  /hooks add <event> <command>  - 动态添加 Hook
  /hooks remove <id>     - 移除指定 Hook
  /hooks enable/disable <id>    - 启用/禁用 Hook
  /hooks test <event>    - 测试指定事件的 Hook
  /hooks clear-log       - 清空执行日志
  /hooks stats           - Hook 统计信息
"""

import logging
from commands.registry import register_command

logger = logging.getLogger(__name__)

# 全局配置加载器实例
_config_loader = None


def get_config_loader():
    """获取全局 HookConfigLoader 实例"""
    global _config_loader
    return _config_loader


def init_config_loader(hook_manager, project_root="."):
    """初始化全局配置加载器并启动文件监听"""
    global _config_loader
    from hooks.config_loader import HookConfigLoader
    _config_loader = HookConfigLoader(
        hook_manager=hook_manager,
        project_root=project_root,
    )
    loaded = _config_loader.load()
    if loaded > 0:
        logger.info(f"Hook config loader initialized: {loaded} hooks loaded")

    # 启动热重载: 注册重载回调 + 启动文件监听
    config_path = _config_loader._config_path or _config_loader.find_config()
    if config_path and hasattr(hook_manager, 'start_file_watcher'):
        hook_manager.set_reload_callback(_config_loader.reload)
        hook_manager.start_file_watcher(config_path)

    return _config_loader


def hooks_handler(args, loop=None):
    """
    /hooks 命令处理函数

    Args:
        args: 命令参数列表
        loop: AgentLoop 实例
    """
    from hooks.manager import HOOK_EVENTS
    from hooks.config_loader import HookConfigEntry

    loader = get_config_loader()

    # 尝试从 AgentLoop 获取配置加载器
    if not loader and loop and hasattr(loop, '_hook_config_loader'):
        loader = loop._hook_config_loader

    # 获取 hook_manager
    hook_manager = None
    if loop and hasattr(loop, 'hook_manager'):
        hook_manager = loop.hook_manager

    # 无参数 → 列出所有 Hook
    if not args:
        lines = ["🪝 Hook 系统状态:\n"]

        # 事件类型统计
        if hook_manager:
            stats = hook_manager.get_hook_stats()
            active_events = {k: v for k, v in stats.items() if v > 0}
            if active_events:
                lines.append("  运行时 Hook:")
                for event, count in sorted(active_events.items()):
                    lines.append(f"    {event}: {count} 个")
            else:
                lines.append("  运行时 Hook: (无)")
            lines.append("")

        # 配置 Hook
        if loader and loader.entries:
            lines.append(f"  配置 Hook (来自 {loader._config_path or '内存'}):")
            for i, entry in enumerate(loader.entries):
                status = "🟢" if entry.enabled else "🔴"
                matcher = f" [{entry.matcher}]" if entry.matcher else ""
                desc = f" — {entry.description}" if entry.description else ""
                lines.append(
                    f"    {status} [{i}] {entry.event}{matcher} "
                    f"P{entry.priority}{desc}"
                )
                lines.append(f"       cmd: {entry.command[:80]}")
                lines.append(f"       on_fail={entry.on_fail} timeout={entry.timeout}s")
            lines.append("")
        elif loader:
            lines.append("  配置 Hook: (未加载配置文件)")
            config_path = loader.find_config()
            if config_path:
                lines.append(f"  💡 发现配置文件: {config_path}")
                lines.append(f"     使用 /hooks reload 加载")
        else:
            lines.append("  配置加载器: (未初始化)")

        lines.append(f"  可用事件: {', '.join(HOOK_EVENTS)}")
        lines.append("")
        lines.append("  💡 用法: /hooks config|log|reload|add|remove|test|stats")
        return "\n".join(lines)

    action = args[0]

    # /hooks config → 配置信息
    if action == "config":
        if not loader:
            return "❌ 配置加载器未初始化"

        info = loader.get_config_info()
        lines = ["📋 Hook 配置信息:\n"]
        lines.append(f"  配置文件: {info['config_path'] or '(未加载)'}")
        lines.append(f"  配置条目: {info['entries_count']}")
        lines.append(f"  注册 Hook: {info['registered_hooks']}")
        lines.append(f"  日志大小: {info['log_size']}")

        if info['entries']:
            lines.append("\n  配置详情:")
            for i, entry in enumerate(info['entries']):
                lines.append(f"    [{i}] {entry['event']}"
                           f"{' [' + entry['matcher'] + ']' if entry.get('matcher') else ''}")
                lines.append(f"       command: {entry['command']}")
                lines.append(f"       priority: {entry['priority']}, "
                           f"timeout: {entry['timeout']}s, "
                           f"on_fail: {entry['on_fail']}, "
                           f"enabled: {entry['enabled']}")
                if entry.get('description'):
                    lines.append(f"       desc: {entry['description']}")

        return "\n".join(lines)

    # /hooks log [N] → 执行日志
    if action == "log":
        if not loader:
            return "❌ 配置加载器未初始化"

        limit = 20
        if len(args) > 1:
            try:
                limit = int(args[1])
            except ValueError:
                pass

        logs = loader.get_execution_log(limit=limit)
        if not logs:
            return "📭 暂无 Hook 执行日志"

        lines = [f"📋 Hook 执行日志 (最近 {len(logs)} 条):\n"]
        for log_entry in reversed(logs):
            icon = {
                "success": "✅",
                "failed": "❌",
                "timeout": "⏱️",
                "blocked": "🚫",
            }.get(log_entry.result, "⚪")

            lines.append(
                f"  {icon} [{log_entry.timestamp[:19]}] "
                f"{log_entry.event}"
                f"{' (' + log_entry.tool_name + ')' if log_entry.tool_name else ''}"
            )
            lines.append(f"     cmd: {log_entry.command[:80]}")
            lines.append(f"     {log_entry.result} | {log_entry.duration_ms:.0f}ms"
                       f"{' | exit=' + str(log_entry.exit_code) if log_entry.exit_code is not None else ''}")
            if log_entry.error:
                lines.append(f"     error: {log_entry.error[:100]}")
            if log_entry.stderr and log_entry.result == "failed":
                lines.append(f"     stderr: {log_entry.stderr[:200]}")
            lines.append("")

        return "\n".join(lines)

    # /hooks reload → 重新加载配置
    if action == "reload":
        if not loader:
            return "❌ 配置加载器未初始化"

        count = loader.reload()
        return f"🔄 重新加载完成: {count} 个 Hook 已注册"

    # /hooks add <event> <command> [--matcher <tool>] [--priority <N>] [--on-fail <strategy>]
    if action == "add":
        if len(args) < 3:
            return (
                "❌ 用法: /hooks add <event> <command> [--matcher <tool>] "
                "[--priority <N>] [--on-fail ignore|warn|block]\n\n"
                f"可用事件: {', '.join(HOOK_EVENTS)}"
            )

        event = args[1]
        command = args[2]

        if event not in HOOK_EVENTS:
            return f"❌ 无效事件: {event}\n可用: {', '.join(HOOK_EVENTS)}"

        # 解析可选参数
        matcher = None
        priority = 0
        on_fail = "ignore"
        description = ""
        i = 3
        while i < len(args):
            if args[i] == "--matcher" and i + 1 < len(args):
                matcher = args[i + 1]
                i += 2
            elif args[i] == "--priority" and i + 1 < len(args):
                try:
                    priority = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif args[i] == "--on-fail" and i + 1 < len(args):
                on_fail = args[i + 1]
                i += 2
            elif args[i] == "--desc" and i + 1 < len(args):
                description = args[i + 1]
                i += 2
            else:
                i += 1

        entry = HookConfigEntry(
            event=event,
            command=command,
            matcher=matcher,
            priority=priority,
            on_fail=on_fail,
            description=description,
        )

        if loader:
            hook_id = loader.add_entry(entry)
            if hook_id >= 0:
                matcher_str = f" [{matcher}]" if matcher else ""
                return (
                    f"✅ 已添加 Hook [ID: {hook_id}]\n"
                    f"   {event}{matcher_str} → {command[:60]}\n"
                    f"   priority={priority}, on_fail={on_fail}"
                )
            else:
                return "❌ Hook 注册失败"
        else:
            return "❌ 配置加载器未初始化"

    # /hooks remove <id> → 移除 Hook
    if action == "remove":
        if len(args) < 2:
            return "❌ 用法: /hooks remove <hook_id>"

        if not hook_manager:
            return "❌ HookManager 不可用"

        try:
            hook_id = int(args[1])
        except ValueError:
            return "❌ Hook ID 必须是数字"

        success = hook_manager.unregister_hook(hook_id)
        if success:
            # 同步移除 loader 中的条目
            if loader:
                if hook_id in loader._registered_hook_ids:
                    idx = loader._registered_hook_ids.index(hook_id)
                    loader._registered_hook_ids.pop(idx)
                    if idx < len(loader.entries):
                        loader.entries.pop(idx)
            return f"🗑️ 已移除 Hook [ID: {hook_id}]"
        else:
            return f"❌ 未找到 Hook [ID: {hook_id}]"

    # /hooks test <event> → 测试事件
    if action == "test":
        if len(args) < 2:
            return f"❌ 用法: /hooks test <event>\n可用事件: {', '.join(HOOK_EVENTS)}"

        event = args[1]
        if event not in HOOK_EVENTS:
            return f"❌ 无效事件: {event}"

        if not hook_manager:
            return "❌ HookManager 不可用"

        import asyncio
        try:
            loop_async = asyncio.new_event_loop()
            asyncio.set_event_loop(loop_async)
            result = loop_async.run_until_complete(
                hook_manager.execute_hooks(event, tool_name="test_tool")
            )
            loop_async.close()

            lines = [
                f"🧪 测试事件 {event}:",
                f"   allow: {result.allow}",
            ]
            if result.block_reason:
                lines.append(f"   block_reason: {result.block_reason}")
            if result.additional_context:
                lines.append(f"   context: {result.additional_context[:200]}")
            if result.short_circuit:
                lines.append(f"   short_circuit: True")
            return "\n".join(lines)

        except Exception as e:
            return f"❌ 测试失败: {e}"

    # /hooks clear-log → 清空日志
    if action == "clear-log":
        if loader:
            loader.clear_log()
            return "✅ 执行日志已清空"
        return "❌ 配置加载器未初始化"

    # /hooks stats → 统计信息
    if action == "stats":
        lines = ["📊 Hook 统计:\n"]

        if hook_manager:
            stats = hook_manager.get_hook_stats()
            total = sum(stats.values())
            lines.append(f"  运行时 Hook 总数: {total}")
            for event, count in sorted(stats.items()):
                if count > 0:
                    lines.append(f"    {event}: {count}")

        if loader:
            lines.append(f"\n  配置 Hook: {len(loader.entries)}")
            lines.append(f"  执行日志: {len(loader._execution_log)} 条")

            # 成功率统计
            if loader._execution_log:
                success_count = sum(1 for l in loader._execution_log if l.result == "success")
                total_log = len(loader._execution_log)
                rate = success_count / total_log * 100
                lines.append(f"  成功率: {rate:.1f}% ({success_count}/{total_log})")

                # 平均耗时
                avg_ms = sum(l.duration_ms for l in loader._execution_log) / total_log
                lines.append(f"  平均耗时: {avg_ms:.1f}ms")

        return "\n".join(lines)

    return f"❌ 未知操作: {action}\n可用: config, log, reload, add, remove, test, clear-log, stats"


# 注册命令
register_command("hooks", {
    "description": "Hook 链管理 (查看/配置/日志/测试)",
    "handler": hooks_handler,
    "args_help": "[config|log|reload|add|remove|test|stats|clear-log]",
    "category": "system",
})
