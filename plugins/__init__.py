"""
插件系统

三层架构:
- base.py: ToolPlugin 抽象基类（插件必须继承）
- builtin.py: 内置插件注册表（对应 Claude Code builtinPlugins.ts）
- loader.py: 目录扫描 + 多源加载器
- registry.py: 插件注册中心 + 事件总线 + 依赖解析
"""
from .base import ToolPlugin
from .loader import PluginLoader
from .builtin import (
    BuiltinPluginDefinition,
    LoadedPlugin,
    BUILTIN_MARKETPLACE_NAME,
    register_builtin_plugin,
    get_builtin_plugins,
    get_enabled_builtin_plugins,
    get_builtin_plugin_tools,
    get_builtin_plugin_hooks,
    is_builtin_plugin_id,
    enable_plugin,
    disable_plugin,
    list_builtin_plugins_info,
    clear_builtin_plugins,
)
from .registry import (
    PluginRegistry,
    PluginManifest,
    PluginBus,
    DependencyResolver,
    PluginEntry,
)
