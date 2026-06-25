"""
内置插件注册表 — 对应 Claude Code builtinPlugins.ts

设计理念:
- 内置插件通过代码硬编码注册（不是目录扫描）
- 用户可通过 /plugin UI 启用/禁用（持久化到 JSON）
- 插件 ID 格式: {name}@builtin，区别于市场插件 {name}@{marketplace}
- 启用状态三级回退: 用户设置 > 插件默认值 > True

用法:
    from plugins.builtin import register_builtin_plugin, get_builtin_plugins

    # 启动时注册
    register_builtin_plugin(BuiltinPluginDefinition(
        name="auto-format",
        description="自动格式化代码",
        version="1.0.0",
        plugin_class=AutoFormatPlugin,
    ))

    # 查询
    enabled, disabled = get_builtin_plugins()
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────────

BUILTIN_MARKETPLACE_NAME = "builtin"

# 模块级全局注册表
_BUILTIN_PLUGINS: Dict[str, 'BuiltinPluginDefinition'] = {}

# 用户设置文件路径（惰性初始化）
_settings_path: Optional[str] = None


# ── 数据结构 ──────────────────────────────────────────────────


@dataclass
class BuiltinPluginDefinition:
    """
    内置插件定义

    对应 Claude Code 的 BuiltinPluginDefinition 接口。
    一个内置插件可携带工具、Hook、MCP Server 三类组件。
    """
    name: str
    description: str
    version: str = "1.0.0"
    plugin_class: Optional[Type] = None          # ToolPlugin 子类（延迟实例化）
    default_enabled: bool = True                 # 默认启用状态
    is_available_fn: Optional[Callable[[], bool]] = None  # 可用性检查
    skills: List[Dict[str, Any]] = field(default_factory=list)   # 技能定义
    hooks_config: Optional[Dict] = None          # Hook 配置
    mcp_servers: List[Dict[str, Any]] = field(default_factory=list)  # MCP Server 配置

    def is_available(self) -> bool:
        """检查插件是否可用（环境依赖满足）"""
        if self.is_available_fn is None:
            return True
        try:
            return self.is_available_fn()
        except Exception:
            return False


@dataclass
class LoadedPlugin:
    """
    已加载的插件实例（统一格式，内置/市场通用）

    对应 Claude Code 的 LoadedPlugin 接口。
    """
    name: str
    manifest: Dict[str, Any]          # {name, description, version}
    source: str                        # "{name}@builtin"
    plugin_id: str                     # 同 source
    enabled: bool
    is_builtin: bool = True
    hooks_config: Optional[Dict] = None
    mcp_servers: List[Dict] = field(default_factory=list)
    plugin_instance: Any = None        # ToolPlugin 实例（仅启用时存在）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.manifest.get("version", "unknown"),
            "description": self.manifest.get("description", ""),
            "source": self.source,
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "is_builtin": self.is_builtin,
        }


# ── 注册/查询 API ─────────────────────────────────────────────


def register_builtin_plugin(definition: BuiltinPluginDefinition) -> None:
    """
    注册内置插件（启动时调用）

    Args:
        definition: 插件定义
    """
    _BUILTIN_PLUGINS[definition.name] = definition
    logger.debug(f"Built-in plugin registered: {definition.name}")


def is_builtin_plugin_id(plugin_id: str) -> bool:
    """检查是否为内置插件 ID（以 @builtin 结尾）"""
    return plugin_id.endswith(f"@{BUILTIN_MARKETPLACE_NAME}")


def get_builtin_plugin_definition(name: str) -> Optional[BuiltinPluginDefinition]:
    """获取内置插件定义（不实例化）"""
    return _BUILTIN_PLUGINS.get(name)


def clear_builtin_plugins() -> None:
    """清空内置插件注册表（仅用于测试）"""
    _BUILTIN_PLUGINS.clear()


# ── 用户设置持久化 ─────────────────────────────────────────────


def _get_settings_path() -> str:
    """获取插件设置文件路径"""
    global _settings_path
    if _settings_path is None:
        config_dir = os.path.join(os.path.expanduser("~"), ".auracode")
        _settings_path = os.path.join(config_dir, "plugins_settings.json")
    return _settings_path


def _load_settings() -> Dict[str, Any]:
    """加载用户插件设置"""
    path = _get_settings_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("enabled_plugins", {})
    except Exception as e:
        logger.warning(f"Failed to load plugin settings: {e}")
        return {}


def _save_settings(settings: Dict[str, bool]) -> None:
    """持久化用户插件设置"""
    path = _get_settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"enabled_plugins": settings}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save plugin settings: {e}")


def get_plugin_enabled_state(plugin_id: str, default: bool = True) -> bool:
    """
    获取插件启用状态（三级回退链）

    优先级: 用户设置 > 插件 default_enabled > True

    Args:
        plugin_id: 插件 ID（如 "auto-format@builtin"）
        default: 插件默认值（来自 BuiltinPluginDefinition.default_enabled）

    Returns:
        是否启用
    """
    user_settings = _load_settings()
    user_value = user_settings.get(plugin_id)
    if user_value is not None:
        return bool(user_value)
    return default


def set_plugin_enabled(plugin_id: str, enabled: bool) -> None:
    """设置插件启用/禁用并持久化"""
    settings = _load_settings()
    settings[plugin_id] = enabled
    _save_settings(settings)
    logger.info(f"Plugin {plugin_id}: {'enabled' if enabled else 'disabled'}")


def enable_plugin(plugin_id: str) -> str:
    """启用插件（用户操作）"""
    set_plugin_enabled(plugin_id, True)
    return f"✅ 插件已启用: {plugin_id}"


def disable_plugin(plugin_id: str) -> str:
    """禁用插件（用户操作）"""
    set_plugin_enabled(plugin_id, False)
    return f"⏸️ 插件已禁用: {plugin_id}"


# ── 核心查询 ──────────────────────────────────────────────────


def get_builtin_plugins() -> Tuple[List[LoadedPlugin], List[LoadedPlugin]]:
    """
    获取所有内置插件，按启用/禁用分组

    is_available() 返回 False 的插件不出现（对应 Claude Code 的省略逻辑）

    Returns:
        (enabled_list, disabled_list)
    """
    enabled: List[LoadedPlugin] = []
    disabled: List[LoadedPlugin] = []

    for name, definition in _BUILTIN_PLUGINS.items():
        # 不可用插件完全隐藏
        if not definition.is_available():
            logger.debug(f"Plugin '{name}' unavailable, skipping")
            continue

        plugin_id = f"{name}@{BUILTIN_MARKETPLACE_NAME}"
        is_enabled = get_plugin_enabled_state(
            plugin_id,
            default=definition.default_enabled
        )

        plugin = LoadedPlugin(
            name=name,
            manifest={
                "name": name,
                "description": definition.description,
                "version": definition.version,
            },
            source=plugin_id,
            plugin_id=plugin_id,
            enabled=is_enabled,
            is_builtin=True,
            hooks_config=definition.hooks_config,
            mcp_servers=definition.mcp_servers,
        )

        # 启用时实例化插件
        if is_enabled and definition.plugin_class is not None:
            try:
                plugin.plugin_instance = definition.plugin_class()
            except Exception as e:
                logger.warning(f"Failed to instantiate plugin '{name}': {e}")

        if is_enabled:
            enabled.append(plugin)
        else:
            disabled.append(plugin)

    return enabled, disabled


def get_enabled_builtin_plugins() -> List[LoadedPlugin]:
    """获取已启用的内置插件列表（快捷方法）"""
    enabled, _ = get_builtin_plugins()
    return enabled


def get_builtin_plugin_tools() -> List[Dict[str, Any]]:
    """
    收集所有已启用内置插件提供的工具定义

    Returns:
        合并后的工具定义列表
    """
    tools = []
    for plugin in get_enabled_builtin_plugins():
        if plugin.plugin_instance and hasattr(plugin.plugin_instance, "get_tools"):
            try:
                plugin_tools = plugin.plugin_instance.get_tools()
                tools.extend(plugin_tools)
            except Exception as e:
                logger.warning(f"Failed to get tools from plugin '{plugin.name}': {e}")
    return tools


def get_builtin_plugin_hooks() -> List[Dict[str, Any]]:
    """
    收集所有已启用内置插件提供的 Hook 定义

    Returns:
        合并后的 Hook 定义列表
    """
    hooks = []
    for plugin in get_enabled_builtin_plugins():
        if plugin.plugin_instance and hasattr(plugin.plugin_instance, "get_hooks"):
            try:
                plugin_hooks = plugin.plugin_instance.get_hooks()
                hooks.extend(plugin_hooks)
            except Exception as e:
                logger.warning(f"Failed to get hooks from plugin '{plugin.name}': {e}")
    return hooks


def list_builtin_plugins_info() -> str:
    """
    列出所有内置插件（格式化字符串，供 /plugin 命令使用）

    Returns:
        格式化的插件列表
    """
    enabled, disabled = get_builtin_plugins()

    lines = [f"内置插件 (共 {len(enabled) + len(disabled)} 个):\n"]

    if enabled:
        lines.append("  ✅ 已启用:")
        for p in enabled:
            desc = p.manifest.get("description", "")
            lines.append(f"    • {p.name} v{p.manifest.get('version', '?')} — {desc}")

    if disabled:
        lines.append("\n  ⏸️  已禁用:")
        for p in disabled:
            desc = p.manifest.get("description", "")
            lines.append(f"    • {p.name} v{p.manifest.get('version', '?')} — {desc}")

    if not enabled and not disabled:
        lines.append("  （无内置插件）")

    return "\n".join(lines)
