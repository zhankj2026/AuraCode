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
插件加载器 - 扫描并加载插件

基于 code.md Phase 4 实现
参考: 第 6.1 节

v2.0 增强:
- 集成 builtin.py 内置插件注册表
- 区分插件来源 (builtin/project/user)
- 生成规范 plugin_id: {name}@{source}
"""

import os
import importlib
import logging
from typing import List, Dict, Any, Optional
from .base import ToolPlugin
from .builtin import (
    get_enabled_builtin_plugins,
    BUILTIN_MARKETPLACE_NAME,
)

logger = logging.getLogger(__name__)

# 插件来源常量
SOURCE_BUILTIN = "builtin"
SOURCE_PROJECT = "project"
SOURCE_USER = "user"


class PluginLoader:
    """
    插件加载器

    加载来源:
    1. 内置插件 — builtin.py 注册表（程序化注册，对应标准builtinPlugins.ts）
    2. 目录插件 — plugins/ 目录下 .py 文件（动态扫描）
    3. 项目级插件 — .auracode/plugins/ 目录
    4. 用户级插件 — ~/.auracode/plugins/ 目录

    每个插件都有规范 plugin_id: {name}@{source}
    """
    
    def __init__(self, plugins_dir: str = None, project_root: str = "."):
        """
        初始化插件加载器
        
        Args:
            plugins_dir: 插件目录路径,默认为 auracode/plugins/
            project_root: 项目根目录（用于查找项目级插件）
        """
        if plugins_dir is None:
            # 默认为 auracode/plugins/
            plugins_dir = os.path.dirname(__file__)
        
        self.plugins_dir = os.path.abspath(plugins_dir)
        self.project_root = os.path.abspath(project_root)

        # 项目级 / 用户级插件目录
        self.project_plugins_dir = os.path.join(self.project_root, '.auracode', 'plugins')
        self.user_plugins_dir = os.path.join(os.path.expanduser('~'), '.auracode', 'plugins')

        self.plugins: List[ToolPlugin] = []
        self.plugins_map: Dict[str, ToolPlugin] = {}
        self._plugin_sources: Dict[str, str] = {}  # name -> source
    
    def scan_plugins(self) -> List[str]:
        """
        扫描插件目录,返回可用的插件文件列表
        
        Returns:
            插件文件名列表
        """
        if not os.path.exists(self.plugins_dir):
            logger.warning(f"插件目录不存在: {self.plugins_dir}")
            return []
        
        # 跳过非插件文件
        skip_files = {
            '__init__.py', 'base.py', 'loader.py', 'builtin.py',
            'marketplace.py', 'plugin_installer.py', 'registry.py', 'zip_cache.py'
        }
        
        plugin_files = []
        for filename in os.listdir(self.plugins_dir):
            # 只加载 plugins/ 目录下的 .py 文件
            # 跳过 __init__.py, base.py, loader.py, builtin.py
            # 跳过 marketplace.py, plugin_installer.py, registry.py, zip_cache.py
            # 跳过 example_ 开头的示例插件
            if (filename.endswith('.py') and 
                not filename.startswith('_') and
                filename not in skip_files and
                not filename.startswith('example_')):
                plugin_files.append(filename)
        
        logger.info(f"扫描到 {len(plugin_files)} 个插件文件")
        return plugin_files
    
    def load_plugin(self, module_name: str, source: str = SOURCE_USER) -> Optional[ToolPlugin]:
        """
        加载单个插件
        
        Args:
            module_name: 插件模块名(不含 .py)
            source: 插件来源 (builtin/project/user)
        
        Returns:
            插件实例，失败返回 None
        """
        try:
            # 动态导入模块
            module = importlib.import_module(f'plugins.{module_name}')
            
            # 查找 ToolPlugin 的子类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                
                # 检查是否是 ToolPlugin 的子类
                if (isinstance(attr, type) and 
                    issubclass(attr, ToolPlugin) and 
                    attr != ToolPlugin):
                    
                    # 实例化插件
                    plugin = attr()
                    
                    # 检查是否可用
                    if plugin.is_available():
                        # 初始化插件
                        if plugin.initialize():
                            # 记录来源
                            self._plugin_sources[plugin.name] = source
                            logger.info(f"插件加载成功: {plugin.plugin_id} v{plugin.version}")
                            return plugin
                        else:
                            logger.warning(f"插件初始化失败: {module_name}")
                    else:
                        logger.warning(f"插件不可用: {module_name}")
            
            logger.warning(f"插件 {module_name} 中未找到有效的插件类")
            return None
            
        except Exception as e:
            logger.error(f"加载插件 {module_name} 失败: {e}")
            return None
    
    def _load_from_dir(self, plugins_dir: str, source: str) -> int:
        """
        从指定目录加载插件

        Args:
            plugins_dir: 目录路径
            source: 来源标识

        Returns:
            成功加载数量
        """
        if not os.path.exists(plugins_dir):
            return 0

        count = 0
        # 将目录临时加入 sys.path 以便 importlib 找到
        import sys
        parent = os.path.dirname(plugins_dir)
        pkg_name = os.path.basename(plugins_dir)
        added = False
        if parent not in sys.path:
            sys.path.insert(0, parent)
            added = True

        try:
            for filename in os.listdir(plugins_dir):
                if (filename.endswith('.py') and
                    not filename.startswith('_')):
                    module_name = filename[:-3]
                    full_module = f"{pkg_name}.{module_name}"
                    try:
                        module = importlib.import_module(full_module)
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (isinstance(attr, type) and
                                issubclass(attr, ToolPlugin) and
                                attr != ToolPlugin):
                                plugin = attr()
                                if plugin.is_available() and plugin.initialize():
                                    if plugin.name not in self.plugins_map:
                                        self._plugin_sources[plugin.name] = source
                                        self.plugins.append(plugin)
                                        self.plugins_map[plugin.name] = plugin
                                        count += 1
                                        logger.info(f"插件加载成功 [{source}]: {plugin.plugin_id}")
                    except Exception as e:
                        logger.warning(f"加载 {full_module} 失败: {e}")
        finally:
            if added:
                sys.path.remove(parent)

        return count

    def load_all_plugins(self, include_builtin: bool = True) -> List[ToolPlugin]:
        """
        加载所有可用的插件

        加载顺序（优先级由低到高，同名时后者覆盖前者）:
        1. 内置插件（builtin.py 注册表）
        2. auracode/plugins/ 目录扫描
        3. 项目级插件 (.auracode/plugins/)
        4. 用户级插件 (~/.auracode/plugins/)
        5. Marketplace 安装的插件 (~/.auracode/plugins/cache/)
        
        Args:
            include_builtin: 是否加载内置插件

        Returns:
            成功加载的插件列表
        """
        import sys
        import time
        
        total_start = time.time()
        print(f"DEBUG [plugins] Starting plugin loading...", file=sys.__stderr__, flush=True)
        
        # 1. 加载内置插件（来自 builtin.py 注册表）
        step_start = time.time()
        builtin_count = 0
        if include_builtin:
            print(f"DEBUG [plugins] Step 1: Loading builtin plugins...", file=sys.__stderr__, flush=True)
            for loaded in get_enabled_builtin_plugins():
                if loaded.plugin_instance is not None:
                    plugin = loaded.plugin_instance
                    if plugin.name not in self.plugins_map:
                        self._plugin_sources[plugin.name] = SOURCE_BUILTIN
                        self.plugins.append(plugin)
                        self.plugins_map[plugin.name] = plugin
                        builtin_count += 1
            if builtin_count:
                logger.info(f"从 builtin 注册表加载 {builtin_count} 个内置插件")
        print(f"DEBUG [plugins] Step 1 done: {builtin_count} builtin plugins ({time.time() - step_start:.2f}s)", file=sys.__stderr__, flush=True)

        # 2. 扫描 auracode/plugins/ 目录
        step_start = time.time()
        print(f"DEBUG [plugins] Step 2: Scanning plugins directory...", file=sys.__stderr__, flush=True)
        plugin_files = self.scan_plugins()
        print(f"DEBUG [plugins] Step 2 done: found {len(plugin_files)} files ({time.time() - step_start:.2f}s)", file=sys.__stderr__, flush=True)
        
        dir_count = 0
        step_start = time.time()
        print(f"DEBUG [plugins] Step 3: Loading directory plugins...", file=sys.__stderr__, flush=True)
        for filename in plugin_files:
            module_name = filename[:-3]
            plugin = self.load_plugin(module_name, source=SOURCE_USER)
            if plugin and plugin.name not in self.plugins_map:
                self.plugins.append(plugin)
                self.plugins_map[plugin.name] = plugin
                dir_count += 1
        print(f"DEBUG [plugins] Step 3 done: {dir_count} plugins ({time.time() - step_start:.2f}s)", file=sys.__stderr__, flush=True)

        # 3. 项目级插件
        step_start = time.time()
        print(f"DEBUG [plugins] Step 4: Loading project plugins...", file=sys.__stderr__, flush=True)
        project_count = self._load_from_dir(self.project_plugins_dir, SOURCE_PROJECT)
        print(f"DEBUG [plugins] Step 4 done: {project_count} plugins ({time.time() - step_start:.2f}s)", file=sys.__stderr__, flush=True)

        # 4. 用户级插件
        step_start = time.time()
        print(f"DEBUG [plugins] Step 5: Loading user plugins...", file=sys.__stderr__, flush=True)
        user_count = self._load_from_dir(self.user_plugins_dir, SOURCE_USER)
        print(f"DEBUG [plugins] Step 5 done: {user_count} plugins ({time.time() - step_start:.2f}s)", file=sys.__stderr__, flush=True)

        # 4.3 官方 marketplace 自动安装检查（首次启动自动 clone）
        step_start = time.time()
        print(f"DEBUG [plugins] Step 6: Checking official marketplace...", file=sys.__stderr__, flush=True)
        self._check_official_marketplace()
        print(f"DEBUG [plugins] Step 6 done ({time.time() - step_start:.2f}s)", file=sys.__stderr__, flush=True)

        # 4.5 Seed marketplace 注册（容器/部署预装，优先级最高）
        step_start = time.time()
        print(f"DEBUG [plugins] Step 7: Registering seed marketplaces...", file=sys.__stderr__, flush=True)
        self._register_seed_marketplaces()
        print(f"DEBUG [plugins] Step 7 done ({time.time() - step_start:.2f}s)", file=sys.__stderr__, flush=True)

        # 5. Marketplace 安装的插件（从 cache 目录 + installed_plugins.json）
        step_start = time.time()
        print(f"DEBUG [plugins] Step 8: Loading marketplace plugins...", file=sys.__stderr__, flush=True)
        marketplace_count = self._load_marketplace_plugins()
        print(f"DEBUG [plugins] Step 8 done: {marketplace_count} plugins ({time.time() - step_start:.2f}s)", file=sys.__stderr__, flush=True)

        total = builtin_count + dir_count + project_count + user_count + marketplace_count
        logger.info(
            f"成功加载 {total} 个插件 "
            f"(builtin={builtin_count}, dir={dir_count}, "
            f"project={project_count}, user={user_count}, "
            f"marketplace={marketplace_count})"
        )
        print(f"DEBUG [plugins] Total: {total} plugins loaded in {time.time() - total_start:.2f}s", file=sys.__stderr__, flush=True)
        return self.plugins
    
    def get_plugin(self, name: str) -> ToolPlugin:
        """
        获取指定名称的插件
        
        Args:
            name: 插件名称
        
        Returns:
            插件实例
        
        Raises:
            KeyError: 如果插件不存在
        """
        if name not in self.plugins_map:
            raise KeyError(f"插件不存在: {name}")
        return self.plugins_map[name]
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        获取所有插件提供的工具定义
        
        Returns:
            工具定义列表
        """
        all_tools = []
        for plugin in self.plugins:
            tools = plugin.get_tools()
            all_tools.extend(tools)
        
        logger.info(f"从 {len(self.plugins)} 个插件中获取 {len(all_tools)} 个工具")
        return all_tools
    
    def get_all_hooks(self) -> List[Dict[str, Any]]:
        """
        获取所有插件提供的钩子定义
        
        Returns:
            钩子定义列表
        """
        all_hooks = []
        for plugin in self.plugins:
            hooks = plugin.get_hooks()
            all_hooks.extend(hooks)
        
        logger.info(f"从 {len(self.plugins)} 个插件中获取 {len(all_hooks)} 个钩子")
        return all_hooks
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        列出所有已加载的插件信息
        
        Returns:
            插件信息列表（含 plugin_id 和 source）
        """
        return [
            {
                'name': plugin.name,
                'plugin_id': plugin.plugin_id,
                'version': plugin.version,
                'description': plugin.description,
                'source': self._plugin_sources.get(plugin.name, SOURCE_USER),
                'available': plugin.is_available(),
                'default_enabled': plugin.default_enabled,
            }
            for plugin in self.plugins
        ]
    
    # ── Marketplace 插件加载 + Skill 自动发现 ─────────────────

    def _check_official_marketplace(self) -> None:
        """
        启动时检查并自动安装官方 marketplace。

        参考标准checkAndInstallOfficialMarketplace()。
        首次启动自动 git clone 官方 marketplace，后续启动跳过。
        失败时指数退避重试（1h → 1w，最多 10 次）。
        """
        try:
            from plugins.marketplace import MarketplaceManager
            mm = MarketplaceManager()
            result = mm.check_and_install_official_marketplace()
            if result.get("installed"):
                logger.info("Official marketplace auto-installed successfully")
            elif result.get("skipped"):
                reason = result.get("reason", "unknown")
                logger.debug(f"Official marketplace auto-install skipped: {reason}")
        except Exception as e:
            logger.warning(f"Failed to check/install official marketplace: {e}")

    def _register_seed_marketplaces(self) -> None:
        """
        从 AURACODE_PLUGIN_SEED_DIR 注册 seed marketplace。

        容器/部署场景下，管理员在镜像中预装 marketplace，
        启动时自动注册，seed 条目优先级最高。
        """
        try:
            from plugins.marketplace import MarketplaceManager
            mm = MarketplaceManager()
            if mm.register_seed_marketplaces():
                logger.info("Seed marketplace(s) registered from AURACODE_PLUGIN_SEED_DIR")
        except Exception as e:
            logger.warning(f"Failed to register seed marketplaces: {e}")

    def _load_marketplace_plugins(self) -> int:
        """
        从 marketplace 缓存目录加载插件

        扫描 ~/.auracode/plugins/cache/ 下所有 marketplace/plugin 目录，
        加载最新版本目录中的 ToolPlugin，并自动发现 skills/ 子目录。

        Returns:
            成功加载数量
        """
        try:
            from plugins.plugin_installer import PluginInstaller
            installer = PluginInstaller()
            cache_dirs = installer.get_cache_dirs()
        except Exception:
            cache_dirs = []

        if not cache_dirs:
            return 0

        count = 0
        for plugin_dir in cache_dirs:
            source = self._extract_marketplace_source(plugin_dir)
            loaded = self._load_from_dir(plugin_dir, source)
            count += loaded
            # 自动发现 skills/
            self._discover_plugin_skills(plugin_dir, source)

        if count:
            logger.info(f"从 marketplace 缓存加载 {count} 个插件")
        return count

    def _extract_marketplace_source(self, plugin_dir: str) -> str:
        """从插件路径提取 marketplace 来源标识"""
        # 路径格式: ~/.auracode/plugins/cache/{marketplace}/{plugin}/{version}/
        parts = plugin_dir.replace("\\", "/").split("/")
        try:
            cache_idx = parts.index("cache")
            if cache_idx + 1 < len(parts):
                return f"marketplace:{parts[cache_idx + 1]}"
        except ValueError:
            pass
        return "marketplace:unknown"

    def _discover_plugin_skills(self, plugin_dir: str, source: str):
        """
        扫描插件目录下的 skills/ 子目录，自动注册到 SkillManager

        参考标准loadPluginCommands.ts 中的 loadSkillsFromDirectory。
        插件可以携带 skills/ 目录，其中每个子目录包含 SKILL.md。

        Args:
            plugin_dir: 插件安装目录
            source: 来源标识 (如 "marketplace:official")
        """
        skills_dir = os.path.join(plugin_dir, "skills")
        if not os.path.exists(skills_dir):
            return

        try:
            from skills.context import SkillContext
            sm = SkillContext._skill_manager
            if sm is None:
                logger.debug("SkillManager 未初始化，跳过 skill 自动发现")
                return

            loaded = sm._load_skills_from_dir(skills_dir, source)
            if loaded:
                logger.info(f"自动发现 {loaded} 个 skill from {source}")
        except ImportError:
            logger.debug("skills 模块不可用，跳过 skill 自动发现")
        except Exception as e:
            logger.warning(f"Skill 自动发现失败 ({source}): {e}")

    def unload_all(self):
        """卸载所有插件"""
        for plugin in self.plugins:
            try:
                plugin.cleanup()
                logger.info(f"插件已卸载: {plugin.name}")
            except Exception as e:
                logger.error(f"卸载插件 {plugin.name} 失败: {e}")
        
        self.plugins.clear()
        self.plugins_map.clear()
        logger.info("所有插件已卸载")
