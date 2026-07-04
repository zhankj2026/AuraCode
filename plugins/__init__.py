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
插件系统

五层架构:
- base.py: ToolPlugin 抽象基类（插件必须继承）
- builtin.py: 内置插件注册表（对应标准builtinPlugins.ts）
- loader.py: 目录扫描 + 多源加载器（含 marketplace）
- registry.py: 插件注册中心 + 事件总线 + 依赖解析
- marketplace.py: Marketplace 管理器 (Git clone 来源)
- plugin_installer.py: 插件安装器 (install/uninstall/update)
- zip_cache.py: Zip 缓存（离线/容器场景）
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
from .marketplace import (
    MarketplaceManager,
    MarketplaceSource,
    MarketplacePluginEntry,
    MarketplaceManifest,
    OFFICIAL_MARKETPLACE_NAME,
    OFFICIAL_MARKETPLACE_SOURCE,
    ENV_DISABLE_OFFICIAL_AUTOINSTALL,
    RETRY_CONFIG,
)
from .plugin_installer import (
    PluginInstaller,
    InstalledPlugin,
    PluginJson,
)
from .zip_cache import (
    is_zip_cache_enabled,
    get_zip_cache_path,
    ensure_zip_cache_dirs,
    zip_plugin_directory,
    unzip_plugin_to_session,
    cleanup_session_plugins,
    sync_installed_to_zip_cache,
    list_zip_cache,
)
