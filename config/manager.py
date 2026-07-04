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
配置管理器 - 统一配置管理

提供集中化的配置管理功能：
- 配置加载和验证
- 配置热更新
- 配置持久化
- 配置变更通知
"""

import os
import yaml
import json
import copy
import logging
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    统一配置管理器
    
    功能：
    - 加载 YAML/JSON 配置文件
    - 验证配置结构
    - 支持运行时配置修改
    - 配置热更新（无需重启）
    - 配置变更通知机制
    - 配置持久化
    
    使用示例：
        config_manager = ConfigManager()
        config_manager.load("config.yaml")
        
        # 获取配置
        model = config_manager.get("llm.model")
        
        # 设置配置
        config_manager.set("llm.temperature", 0.5)
        
        # 保存配置
        config_manager.save()
    """
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._file_config: Dict[str, Any] = {}  # 文件中的原始配置
        self._config_path: Optional[str] = None
        self._watchers: List[Callable[[str, Any, Any], None]] = []  # 配置变更监听器
        self._schema: Optional[Dict[str, Any]] = None  # 配置 Schema
    
    def load(self, path: str = None, config_dict: Dict[str, Any] = None) -> bool:
        """
        加载配置
        
        Args:
            path: 配置文件路径（YAML 或 JSON）
            config_dict: 直接传入配置字典（优先级高于 path）
        
        Returns:
            是否加载成功
        """
        try:
            if config_dict:
                # 直接从字典加载
                self._config = copy.deepcopy(config_dict)
                self._file_config = copy.deepcopy(config_dict)
                logger.info("Loaded config from dict")
                return True
            
            if not path:
                # 使用默认路径
                path = self._find_config_file()
            
            if not path or not os.path.exists(path):
                logger.warning(f"Config file not found: {path}")
                return False
            
            self._config_path = path
            
            # 根据文件扩展名选择加载方式
            if path.endswith(('.yaml', '.yml')):
                with open(path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            elif path.endswith('.json'):
                with open(path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            else:
                logger.error(f"Unsupported config format: {path}")
                return False
            
            self._file_config = copy.deepcopy(self._config)
            
            # 验证配置
            if self._schema:
                self._validate_config(self._config)
            
            logger.info(f"Loaded config from {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False
    
    def save(self, path: str = None) -> bool:
        """
        保存配置到文件
        
        Args:
            path: 保存路径（默认使用加载时的路径）
        
        Returns:
            是否保存成功
        """
        save_path = path or self._config_path
        
        if not save_path:
            logger.error("No config path specified")
            return False
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 根据文件扩展名选择保存方式
            if save_path.endswith(('.yaml', '.yml')):
                with open(save_path, 'w', encoding='utf-8') as f:
                    yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
            elif save_path.endswith('.json'):
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
            else:
                logger.error(f"Unsupported config format: {save_path}")
                return False
            
            self._file_config = copy.deepcopy(self._config)
            logger.info(f"Saved config to {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持点分隔的嵌套键）
        
        Args:
            key: 配置键（如 "llm.model"）
            default: 默认值
        
        Returns:
            配置值
        
        示例：
            model = config_manager.get("llm.model", "gpt-4")
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any, notify: bool = True) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键（如 "llm.model"）
            value: 配置值
            notify: 是否通知监听器
        
        示例：
            config_manager.set("llm.temperature", 0.5)
        """
        keys = key.split('.')
        config = self._config
        
        # 导航到父级
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        old_value = config.get(keys[-1])
        config[keys[-1]] = value
        
        # 通知监听器
        if notify and old_value != value:
            self._notify_watchers(key, old_value, value)
        
        logger.debug(f"Set config {key} = {value}")
    
    def delete(self, key: str) -> bool:
        """
        删除配置项
        
        Args:
            key: 配置键
        
        Returns:
            是否删除成功
        """
        keys = key.split('.')
        config = self._config
        
        # 导航到父级
        for k in keys[:-1]:
            if k not in config:
                return False
            config = config[k]
        
        # 删除键
        if keys[-1] in config:
            del config[keys[-1]]
            logger.debug(f"Deleted config {key}")
            return True
        
        return False
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return copy.deepcopy(self._config)
    
    def update(self, updates: Dict[str, Any], notify: bool = True) -> None:
        """
        批量更新配置
        
        Args:
            updates: 更新的配置字典
            notify: 是否通知监听器
        """
        for key, value in updates.items():
            self.set(key, value, notify=notify)
    
    def reload(self) -> bool:
        """
        从文件重新加载配置
        
        Returns:
            是否重载成功
        """
        if not self._config_path:
            logger.error("No config file path")
            return False
        
        return self.load(self._config_path)
    
    def diff(self) -> Dict[str, Any]:
        """
        对比运行时配置与文件配置
        
        Returns:
            差异字典
        """
        return {
            "added": self._get_added_keys(self._file_config, self._config),
            "removed": self._get_removed_keys(self._file_config, self._config),
            "modified": self._get_modified_keys(self._file_config, self._config),
        }
    
    def add_watcher(self, callback: Callable[[str, Any, Any], None]) -> None:
        """
        添加配置变更监听器
        
        Args:
            callback: 回调函数 callback(key, old_value, new_value)
        """
        self._watchers.append(callback)
        logger.debug(f"Added config watcher")
    
    def remove_watcher(self, callback: Callable[[str, Any, Any], None]) -> None:
        """移除配置变更监听器"""
        if callback in self._watchers:
            self._watchers.remove(callback)
    
    def set_schema(self, schema: Dict[str, Any]) -> None:
        """
        设置配置 Schema（用于验证）
        
        Args:
            schema: Schema 定义
        """
        self._schema = schema
        logger.info("Config schema set")
    
    def validate(self) -> List[str]:
        """
        验证当前配置
        
        Returns:
            错误列表（空列表表示验证通过）
        """
        if not self._schema:
            return []
        
        return self._validate_config(self._config)
    
    def _find_config_file(self) -> Optional[str]:
        """查找配置文件"""
        search_paths = [
            "config.yaml",
            "config.yml",
            "config.json",
            ".auracode/config.yaml",
            ".auracode/config.yml",
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _validate_config(self, config: Dict[str, Any]) -> List[str]:
        """验证配置"""
        errors = []
        
        # 简单的 Schema 验证
        if self._schema:
            # 检查必填字段
            required = self._schema.get("required", [])
            for field in required:
                if not self._has_key(config, field):
                    errors.append(f"Missing required field: {field}")
            
            # 检查类型
            properties = self._schema.get("properties", {})
            for key, prop_schema in properties.items():
                if self._has_key(config, key):
                    value = self.get(key)
                    expected_type = prop_schema.get("type")
                    
                    if expected_type and not self._check_type(value, expected_type):
                        errors.append(f"Invalid type for {key}: expected {expected_type}")
        
        return errors
    
    def _has_key(self, config: Dict[str, Any], key: str) -> bool:
        """检查配置是否包含某个键"""
        keys = key.split('.')
        value = config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return False
        
        return True
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值的类型"""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        expected = type_map.get(expected_type)
        if not expected:
            return True
        
        return isinstance(value, expected)
    
    def _notify_watchers(self, key: str, old_value: Any, new_value: Any) -> None:
        """通知所有监听器"""
        for watcher in self._watchers:
            try:
                watcher(key, old_value, new_value)
            except Exception as e:
                logger.error(f"Config watcher error: {e}")
    
    def _get_added_keys(self, old: Dict, new: Dict, prefix: str = "") -> List[str]:
        """获取新增的键"""
        added = []
        for key in new:
            full_key = f"{prefix}.{key}" if prefix else key
            if key not in old:
                added.append(full_key)
            elif isinstance(new[key], dict) and isinstance(old.get(key), dict):
                added.extend(self._get_added_keys(old[key], new[key], full_key))
        return added
    
    def _get_removed_keys(self, old: Dict, new: Dict, prefix: str = "") -> List[str]:
        """获取删除的键"""
        removed = []
        for key in old:
            full_key = f"{prefix}.{key}" if prefix else key
            if key not in new:
                removed.append(full_key)
            elif isinstance(old[key], dict) and isinstance(new.get(key), dict):
                removed.extend(self._get_removed_keys(old[key], new[key], full_key))
        return removed
    
    def _get_modified_keys(self, old: Dict, new: Dict, prefix: str = "") -> List[str]:
        """获取修改的键"""
        modified = []
        for key in new:
            full_key = f"{prefix}.{key}" if prefix else key
            if key in old:
                if isinstance(new[key], dict) and isinstance(old.get(key), dict):
                    modified.extend(self._get_modified_keys(old[key], new[key], full_key))
                elif new[key] != old[key]:
                    modified.append(full_key)
        return modified


# 全局配置管理器实例
config_manager = ConfigManager()
