"""
插件加载器 - 扫描并加载插件

基于 code.md Phase 4 实现
参考: 第 6.1 节
"""

import os
import importlib
import logging
from typing import List, Dict, Any
from .base import ToolPlugin

logger = logging.getLogger(__name__)


class PluginLoader:
    """插件加载器"""
    
    def __init__(self, plugins_dir: str = None):
        """
        初始化插件加载器
        
        Args:
            plugins_dir: 插件目录路径,默认为 plugins/
        """
        if plugins_dir is None:
            # 默认为 opencode/plugins/
            plugins_dir = os.path.dirname(__file__)
        
        self.plugins_dir = os.path.abspath(plugins_dir)
        self.plugins: List[ToolPlugin] = []
        self.plugins_map: Dict[str, ToolPlugin] = {}
    
    def scan_plugins(self) -> List[str]:
        """
        扫描插件目录,返回可用的插件文件列表
        
        Returns:
            插件文件名列表
        """
        if not os.path.exists(self.plugins_dir):
            logger.warning(f"插件目录不存在: {self.plugins_dir}")
            return []
        
        plugin_files = []
        for filename in os.listdir(self.plugins_dir):
            # 只加载 plugins/ 目录下的 .py 文件
            # 跳过 __init__.py, base.py, loader.py
            # 跳过 example_ 开头的示例插件
            if (filename.endswith('.py') and 
                not filename.startswith('_') and
                filename not in ['base.py', 'loader.py']):
                plugin_files.append(filename)
        
        logger.info(f"扫描到 {len(plugin_files)} 个插件文件")
        return plugin_files
    
    def load_plugin(self, module_name: str) -> ToolPlugin:
        """
        加载单个插件
        
        Args:
            module_name: 插件模块名(不含 .py)
        
        Returns:
            插件实例
        
        Raises:
            Exception: 如果加载失败
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
                            logger.info(f"插件加载成功: {plugin.name} v{plugin.version}")
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
    
    def load_all_plugins(self) -> List[ToolPlugin]:
        """
        加载所有可用的插件
        
        Returns:
            成功加载的插件列表
        """
        plugin_files = self.scan_plugins()
        
        for filename in plugin_files:
            module_name = filename[:-3]  # 去掉 .py
            plugin = self.load_plugin(module_name)
            
            if plugin:
                self.plugins.append(plugin)
                self.plugins_map[plugin.name] = plugin
        
        logger.info(f"成功加载 {len(self.plugins)} 个插件")
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
    
    def list_plugins(self) -> List[Dict[str, str]]:
        """
        列出所有已加载的插件信息
        
        Returns:
            插件信息列表
        """
        return [
            {
                'name': plugin.name,
                'version': plugin.version,
                'description': plugin.description,
                'available': plugin.is_available()
            }
            for plugin in self.plugins
        ]
    
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
