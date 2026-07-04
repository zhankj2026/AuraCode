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
  /plugins marketplace list/add/remove/update/official  Marketplace 管理
  /plugins install <name@marketplace>   安装插件
  /plugins uninstall <name@marketplace> 卸载插件
  /plugins installed   列出已安装插件
  /plugins search <keyword> 搜索可用插件
  /plugins reconcile   对账（声明 vs 安装）
  /plugins zip-cache   查看 zip 缓存
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


# ── Marketplace 子命令 ──────────────────────────────────────


def _get_marketplace_manager():
    """获取 MarketplaceManager 实例"""
    try:
        from plugins.marketplace import MarketplaceManager
        return MarketplaceManager()
    except ImportError:
        return None


# 官方 marketplace 常量引用
try:
    from plugins.marketplace import ENV_DISABLE_OFFICIAL_AUTOINSTALL
except ImportError:
    ENV_DISABLE_OFFICIAL_AUTOINSTALL = "AURACODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL"


def _get_plugin_installer():
    """获取 PluginInstaller 实例"""
    try:
        from plugins.plugin_installer import PluginInstaller
        return PluginInstaller()
    except ImportError:
        return None


def _cmd_marketplace(args: list) -> str:
    """Marketplace 管理子命令"""
    mm = _get_marketplace_manager()
    if mm is None:
        return "Marketplace 模块不可用"

    sub = args[0].lower() if args else "list"
    rest = " ".join(args[1:]).strip() if len(args) > 1 else ""

    if sub == "list":
        return mm.list_marketplaces()
    elif sub == "add":
        if not rest:
            return "用法: /plugins marketplace add <git-url> [--name <name>]"
        # 解析 --name
        name = None
        url = rest
        if "--name" in rest:
            parts = rest.split("--name")
            url = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else None
        return mm.add_marketplace(url, name=name)
    elif sub == "remove":
        if not rest:
            return "用法: /plugins marketplace remove <name>"
        return mm.remove_marketplace(rest)
    elif sub == "update":
        return mm.update_marketplace(rest if rest else None)
    elif sub == "official":
        return _cmd_marketplace_official(mm)
    else:
        return (
            "Marketplace 子命令:\n"
            "  list            列出已注册 marketplace\n"
            "  add <url>       添加 marketplace (git clone)\n"
            "  remove <name>   移除 marketplace\n"
            "  update [name]   更新 marketplace (git pull)\n"
            "  official        查看官方 marketplace 状态"
        )


def _cmd_marketplace_official(mm) -> str:
    """查看官方 marketplace 状态"""
    status = mm.get_official_marketplace_status()
    lines = [
        "官方 Marketplace 状态:",
        "",
        f"  名称: {status['name']}",
        f"  仓库: {status['source'].get('url', 'N/A')}",
        f"  已注册: {'✅ 是' if status['registered'] else '❌ 否'}",
    ]
    if status['install_location']:
        lines.append(f"  路径: {status['install_location']}")
    if status['env_disabled']:
        lines.append(f"  自动安装: ❌ 已禁用 (via {ENV_DISABLE_OFFICIAL_AUTOINSTALL})")
    else:
        lines.append(f"  自动安装: ✅ 启用")

    state = status.get('state', {})
    if state:
        lines.append("")
        lines.append("  安装状态:")
        lines.append(f"    已尝试: {'是' if state.get('attempted') else '否'}")
        lines.append(f"    已安装: {'是' if state.get('installed') else '否'}")
        if state.get('fail_reason'):
            lines.append(f"    失败原因: {state['fail_reason']}")
        retry_count = state.get('retry_count', 0)
        if retry_count > 0:
            lines.append(f"    重试次数: {retry_count}")
        if state.get('next_retry_time'):
            import time
            remaining = state['next_retry_time'] - time.time()
            if remaining > 0:
                hours = remaining / 3600
                lines.append(f"    下次重试: {hours:.1f}h 后")

    return "\n".join(lines)


def _cmd_install(target: str) -> str:
    """安装插件: /plugins install <name>@<marketplace> 或 <name>@git:<url>"""
    installer = _get_plugin_installer()
    mm = _get_marketplace_manager()
    if installer is None or mm is None:
        return "插件安装模块不可用"

    if not target:
        return (
            "用法:\n"
            "  /plugins install <name>@<marketplace>  从已注册 marketplace 安装\n"
            "  /plugins install <name>@git:<url>      直接从 Git URL 安装\n"
            "\n"
            "示例:\n"
            "  /plugins install superpowers@my-marketplace\n"
            "  /plugins install my-plugin@git:https://github.com/user/plugin.git"
        )

    # 解析 name@marketplace 或 name@git:url
    if "@" in target:
        name, source = target.split("@", 1)
    else:
        # 尝试在第一个 marketplace 中查找
        names = mm.get_marketplace_names()
        if not names:
            return (
                "无已注册的 marketplace。\n"
                "\n"
                "请先添加一个 marketplace:\n"
                "  /plugins marketplace add <git-url>\n"
                "\n"
                "或直接从 Git URL 安装:\n"
                "  /plugins install <name>@git:<url>"
            )
        name = target
        source = names[0]

    # 直接 Git URL 安装: name@git:https://...
    if source.startswith("git:") or source.startswith("http://") or source.startswith("https://"):
        git_url = source[4:] if source.startswith("git:") else source
        return installer.install_plugin(
            name, marketplace="direct",
            source_url=git_url, version="latest",
        )

    marketplace = source

    # 检查 marketplace 是否已注册
    known_names = mm.get_marketplace_names()
    if marketplace not in known_names:
        available = ", ".join(known_names) if known_names else "(无)"
        return (
            f"❌ Marketplace '{marketplace}' 未注册。\n"
            f"\n"
            f"已注册的 marketplace: {available}\n"
            f"\n"
            f"你可以:\n"
            f"  1. 先添加 marketplace:\n"
            f"     /plugins marketplace add <git-url> --name {marketplace}\n"
            f"\n"
            f"  2. 直接从 Git URL 安装（无需 marketplace）:\n"
            f"     /plugins install {name}@git:<plugin-git-url>\n"
            f"\n"
            f"  3. 查看已注册的 marketplace:\n"
            f"     /plugins marketplace list"
        )

    # 从 marketplace 查找插件源码 URL
    plugins = mm.get_marketplace_plugins(marketplace)
    source_url = ""
    version = "latest"
    for p in plugins:
        if p.name == name:
            source_url = p.source
            version = p.version
            break

    if not source_url and not plugins:
        return (
            f"❌ Marketplace '{marketplace}' 中没有找到任何插件。\n"
            f"请检查 marketplace.json 是否包含 plugins 列表。"
        )

    if not source_url:
        available_plugins = [p.name for p in plugins[:10]]
        return (
            f"❌ 插件 '{name}' 不在 marketplace '{marketplace}' 中。\n"
            f"\n"
            f"可用插件: {', '.join(available_plugins)}"
            + (f" (共 {len(plugins)} 个)" if len(plugins) > 10 else "")
        )

    return installer.install_plugin(name, marketplace, source_url=source_url, version=version)


def _cmd_uninstall(plugin_id: str) -> str:
    """卸载插件: /plugins uninstall <name>@<marketplace>"""
    installer = _get_plugin_installer()
    if installer is None:
        return "插件安装模块不可用"

    if not plugin_id:
        return "用法: /plugins uninstall <name>@<marketplace>"

    return installer.uninstall_plugin(plugin_id)


def _cmd_installed() -> str:
    """列出已安装插件"""
    installer = _get_plugin_installer()
    if installer is None:
        return "插件安装模块不可用"
    return installer.list_installed_str()


def _cmd_search(keyword: str) -> str:
    """搜索可用插件"""
    mm = _get_marketplace_manager()
    if mm is None:
        return "Marketplace 模块不可用"

    if not keyword:
        return "用法: /plugins search <keyword>"

    installer = _get_plugin_installer()
    results = mm.search_plugins(keyword)

    if not results:
        return f"未找到匹配 '{keyword}' 的插件"

    lines = [f"搜索结果: '{keyword}' ({len(results)} 个匹配)\n"]
    for r in results:
        installed = ""
        if installer and installer.is_installed(r["plugin_id"]):
            installed = " (已安装)"
        lines.append(f"  {r['plugin_id']}{installed}")
        lines.append(f"     {r['description']}")
        if r.get('tags'):
            lines.append(f"     标签: {', '.join(r['tags'])}")
        lines.append("")
    return "\n".join(lines)


def _cmd_reconcile() -> str:
    """对账: marketplace 声明 vs 实际安装"""
    mm = _get_marketplace_manager()
    installer = _get_plugin_installer()
    if mm is None or installer is None:
        return "模块不可用"

    result = installer.reconcile(mm)
    lines = ["Marketplace 对账:\n"]

    if result["missing"]:
        lines.append(f"  缺少 ({len(result['missing'])} 个, 未安装):")
        for pid in result["missing"][:10]:
            lines.append(f"    - {pid}")
        if len(result["missing"]) > 10:
            lines.append(f"    ... 及 {len(result['missing']) - 10} 个")

    if result["extra"]:
        lines.append(f"\n  多余 ({len(result['extra'])} 个, 不在 marketplace 中):")
        for pid in result["extra"]:
            lines.append(f"    - {pid}")

    lines.append(f"\n  已同步: {len(result['up_to_date'])} 个")

    if not result["missing"] and not result["extra"]:
        lines.append("\n  ✅ 所有插件同步一致")

    return "\n".join(lines)


def _cmd_zip_cache() -> str:
    """查看 zip 缓存"""
    try:
        from plugins.zip_cache import is_zip_cache_enabled, list_zip_cache
        enabled = "✅ 启用" if is_zip_cache_enabled() else "⏸️ 未启用"
        lines = [f"Zip 缓存: {enabled}\n"]
        lines.append(list_zip_cache())
        return "\n".join(lines)
    except ImportError:
        return "Zip 缓存模块不可用"


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
        # Marketplace 子命令
        "marketplace": lambda: _cmd_marketplace(args[1:]) if len(args) > 1 else _cmd_marketplace([]),
        "install": lambda: _cmd_install(rest),
        "uninstall": lambda: _cmd_uninstall(rest) if rest else "用法: /plugins uninstall <name>@<marketplace>",
        "installed": lambda: _cmd_installed(),
        "search": lambda: _cmd_search(rest) if rest else "用法: /plugins search <keyword>",
        "reconcile": lambda: _cmd_reconcile(),
        "zip-cache": lambda: _cmd_zip_cache(),
    }

    handler = handlers.get(sub)
    if not handler:
        return (
            "可用子命令:\n"
            "  /plugins list                     列出所有插件\n"
            "  /plugins info <name>              查看插件详情\n"
            "  /plugins enable <n>               启用插件\n"
            "  /plugins disable <n>              禁用插件\n"
            "  /plugins reload                   重新加载插件\n"
            "  /plugins bus                      事件总线状态\n"
            "  /plugins deps                     依赖关系\n"
            "  /plugins stats                    统计信息\n"
            "  /plugins marketplace list/add/remove/update/official  Marketplace 管理\n"
            "  /plugins install <name@marketplace>   安装插件\n"
            "  /plugins uninstall <name@marketplace> 卸载插件\n"
            "  /plugins installed                列出已安装插件\n"
            "  /plugins search <keyword>         搜索可用插件\n"
            "  /plugins reconcile                对账（声明 vs 安装）\n"
            "  /plugins zip-cache                查看 zip 缓存"
        )

    return handler()


# 注册命令
register_command("plugins", {
    "description": "插件生态管理 (marketplace/install/enable/disable/search)",
    "handler": plugins_handler,
    "category": "system",
    "args_help": "[list|info|enable|disable|reload|bus|deps|stats|marketplace|install|uninstall|installed|search|reconcile|zip-cache]",
})
