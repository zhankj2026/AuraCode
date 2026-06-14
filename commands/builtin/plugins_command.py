"""
/plugins 命令 — 插件生态管理

子命令:
  /plugins list        列出所有插件及状态
  /plugins info <name> 查看插件详情
  /plugins enable <n>  启用插件
  /plugins disable <n> 禁用插件
  /plugins reload      重新加载所有插件
  /plugins bus         查看事件总线状态
  /plugins deps        查看依赖关系
  /plugins stats       插件统计
"""

from commands.registry import register_command

# 全局插件注册中心引用
_plugin_registry = None


def get_plugin_registry():
    """获取或创建全局插件注册中心"""
    global _plugin_registry
    if _plugin_registry is None:
        try:
            from plugins.registry import PluginRegistry
            _plugin_registry = PluginRegistry()
        except ImportError:
            return None
    return _plugin_registry


def _cmd_list() -> str:
    """列出所有插件"""
    reg = get_plugin_registry()
    if not reg:
        return "插件系统不可用"

    plugins = reg.list_plugins()
    if not plugins:
        return "暂无已注册插件\n使用 /plugins reload 加载插件"

    lines = [f"已注册插件 ({len(plugins)} 个):", ""]
    status_icons = {"active": "🟢", "registered": "🟡", "error": "🔴", "disabled": "⚫"}

    for p in plugins:
        icon = status_icons.get(p["status"], "❓")
        deps = f"  依赖: {', '.join(p['dependencies'])}" if p["dependencies"] else ""
        provides = f"  提供: {', '.join(p['provides'])}" if p["provides"] else ""
        lines.append(f"  {icon} {p['name']} v{p['version']} [{p['status']}]")
        if p["description"]:
            lines.append(f"     {p['description']}")
        if deps:
            lines.append(f"     {deps}")
        if provides:
            lines.append(f"     {provides}")
        if p["load_time_ms"] > 0:
            lines.append(f"     加载耗时: {p['load_time_ms']:.1f}ms")
        lines.append("")

    return "\n".join(lines)


def _cmd_info(name: str) -> str:
    """查看插件详情"""
    reg = get_plugin_registry()
    if not reg:
        return "插件系统不可用"

    plugin = reg.get_plugin(name)
    if not plugin:
        return f"插件 '{name}' 不存在\n使用 /plugins list 查看已注册插件"

    entry = reg._entries.get(name)
    lines = [
        f"插件详情: {name}",
        f"  版本: {entry.manifest.version}",
        f"  描述: {entry.manifest.description}",
        f"  作者: {entry.manifest.author or 'N/A'}",
        f"  许可: {entry.manifest.license}",
        f"  状态: {entry.status}",
        f"  注册时间: {entry.registered_at}",
        f"  加载耗时: {entry.load_time_ms:.1f}ms",
    ]

    if entry.manifest.dependencies:
        lines.append(f"  依赖: {', '.join(entry.manifest.dependencies)}")
    if entry.manifest.provides:
        lines.append(f"  能力: {', '.join(entry.manifest.provides)}")
    if entry.error:
        lines.append(f"  错误: {entry.error}")

    if hasattr(plugin, 'get_tools'):
        tools = plugin.get_tools()
        if tools:
            lines.append(f"  工具: {len(tools)} 个")
            for t in tools:
                lines.append(f"    - {t.get('name', '?')}: {t.get('description', '')[:50]}")

    if hasattr(plugin, 'get_hooks'):
        hooks = plugin.get_hooks()
        if hooks:
            lines.append(f"  钩子: {len(hooks)} 个")
            for h in hooks:
                lines.append(f"    - {h.get('event', '?')}: {h.get('matcher', '*')}")

    return "\n".join(lines)


def _cmd_enable(name: str) -> str:
    """启用插件"""
    reg = get_plugin_registry()
    if not reg:
        return "插件系统不可用"
    entry = reg._entries.get(name)
    if not entry:
        return f"插件 '{name}' 不存在"
    entry.manifest.enabled = True
    if reg.activate_plugin(name):
        return f"✅ 插件 '{name}' 已启用"
    return f"❌ 启用失败: {entry.error}"


def _cmd_disable(name: str) -> str:
    """禁用插件"""
    reg = get_plugin_registry()
    if not reg:
        return "插件系统不可用"
    if reg.deactivate_plugin(name):
        entry = reg._entries.get(name)
        if entry:
            entry.manifest.enabled = False
        return f"⚫ 插件 '{name}' 已禁用"
    return f"插件 '{name}' 未激活或不存在"


def _cmd_reload() -> str:
    """重新加载所有插件"""
    reg = get_plugin_registry()
    if not reg:
        return "插件系统不可用"
    reg.stop_all()
    try:
        from plugins.loader import PluginLoader
        loader = PluginLoader()
        loaded = loader.load_all_plugins()
        for plugin in loaded:
            if plugin.name not in reg._entries:
                reg.register_plugin(plugin)
        results = reg.start_all()
        active = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)
        lines = [f"插件重载完成:", f"  激活: {active}", f"  失败: {failed}"]
        if failed > 0:
            for name, ok in results.items():
                if not ok:
                    entry = reg._entries.get(name)
                    err = entry.error if entry else "unknown"
                    lines.append(f"  ❌ {name}: {err}")
        return "\n".join(lines)
    except Exception as e:
        return f"重载失败: {e}"


def _cmd_bus() -> str:
    """事件总线状态"""
    reg = get_plugin_registry()
    if not reg:
        return "插件系统不可用"
    bus = reg.bus
    subs = bus.get_subscription_count()
    log = bus.get_event_log(limit=10)
    lines = ["事件总线状态:", ""]
    lines.append(f"  订阅事件数: {len(subs)}")
    for event, count in sorted(subs.items()):
        lines.append(f"    {event}: {count} 订阅")
    lines.append(f"\n  最近事件 ({len(log)}):")
    for entry in log[-5:]:
        lines.append(f"    [{entry['event']}] keys={entry.get('data_keys', [])}")
    return "\n".join(lines)


def _cmd_deps() -> str:
    """依赖关系"""
    reg = get_plugin_registry()
    if not reg:
        return "插件系统不可用"
    resolver = reg._resolver
    order = resolver.resolve_load_order()
    cycles = resolver.detect_cycles()
    lines = ["依赖关系:", ""]
    lines.append(f"  加载顺序: {' → '.join(order) if order else '(无插件)'}")
    if cycles:
        lines.append(f"\n  ⚠️ 循环依赖:")
        for cycle in cycles:
            lines.append(f"    {' → '.join(cycle)}")
    lines.append(f"\n  插件依赖图:")
    for name in order:
        deps = resolver._graph.get(name, [])
        if deps:
            lines.append(f"    {name} ← {', '.join(deps)}")
        else:
            lines.append(f"    {name} (无依赖)")
    return "\n".join(lines)


def _cmd_stats() -> str:
    """插件统计"""
    reg = get_plugin_registry()
    if not reg:
        return "插件系统不可用"
    stats = reg.get_stats()
    bus_stats = {"event_types": len(reg.bus._subscribers), "recent_events": len(reg.bus._event_log)}
    lines = [
        "插件系统统计:",
        f"  总插件: {stats['total']}",
        f"  活跃: {stats['active']}",
        f"  错误: {stats['error']}",
        f"  禁用: {stats['disabled']}",
        f"  事件类型: {bus_stats['event_types']}",
        f"  事件日志: {bus_stats['recent_events']} 条",
    ]
    return "\n".join(lines)


def plugins_handler(args: list, loop=None) -> str:
    """执行 /plugins 命令"""
    sub = args[0].lower() if args else "list"
    rest = " ".join(args[1:]).strip() if len(args) > 1 else ""

    handlers = {
        "list": lambda: _cmd_list(),
        "info": lambda: _cmd_info(rest) if rest else "用法: /plugins info <name>",
        "enable": lambda: _cmd_enable(rest) if rest else "用法: /plugins enable <name>",
        "disable": lambda: _cmd_disable(rest) if rest else "用法: /plugins disable <name>",
        "reload": lambda: _cmd_reload(),
        "bus": lambda: _cmd_bus(),
        "deps": lambda: _cmd_deps(),
        "stats": lambda: _cmd_stats(),
    }

    handler = handlers.get(sub)
    if not handler:
        return (
            "可用子命令:\n"
            "  /plugins list        列出所有插件\n"
            "  /plugins info <name> 查看插件详情\n"
            "  /plugins enable <n>  启用插件\n"
            "  /plugins disable <n> 禁用插件\n"
            "  /plugins reload      重新加载插件\n"
            "  /plugins bus         事件总线状态\n"
            "  /plugins deps        依赖关系\n"
            "  /plugins stats       统计信息"
        )

    return handler()


# 注册命令
register_command("plugins", {
    "description": "插件生态管理 (注册/启用/禁用/依赖/事件总线)",
    "handler": plugins_handler,
    "category": "system",
    "args_help": "[list|info|enable|disable|reload|bus|deps|stats]",
})
