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
配置 Schema - 配置结构定义

定义配置文件的结构和验证规则。
"""

from typing import Dict, Any


# 默认配置 Schema
DEFAULT_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "llm": {
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "model": {"type": "string"},
                "base_url": {"type": "string"},
                "api_key": {"type": "string"},
                "max_tokens": {"type": "integer"},
                "temperature": {"type": "number"},
            },
            "required": ["provider", "model"]
        },
        "permissions": {
            "type": "object",
            "properties": {
                "allow_rules": {"type": "array"},
                "deny_rules": {"type": "array"},
            }
        },
        "mcp_servers": {
            "type": "object",
        },
        "hooks": {
            "type": "object",
        },
        "plugins": {
            "type": "object",
        },
        "logging": {
            "type": "object",
            "properties": {
                "level": {"type": "string"},
                "file": {"type": "string"},
            }
        },
    },
    "required": ["llm"]
}


# 默认配置值
DEFAULT_CONFIG = {
    "llm": {
        "provider": "openai",
        "model": "gpt-4",
        # 默认输出 token 限制
        "max_tokens": 32_000,
        "temperature": 0.2,
        # 上下文窗口大小
        "context_window": 200_000,
    },
    "permissions": {
        "allow_rules": [],
        "deny_rules": [],
    },
    "mcp_servers": {},
    "hooks": {},
    "plugins": {},
    "logging": {
        "level": "INFO",
    }
}


class ConfigSchema:
    """
    配置 Schema 定义
    
    用于验证配置文件的结构和类型。
    
    使用示例：
        schema = ConfigSchema()
        errors = schema.validate(config_dict)
        
        if errors:
            print(f"Validation errors: {errors}")
    """
    
    def __init__(self, schema: Dict[str, Any] = None):
        """
        初始化 Schema
        
        Args:
            schema: 自定义 Schema（默认使用 DEFAULT_CONFIG_SCHEMA）
        """
        self.schema = schema or DEFAULT_CONFIG_SCHEMA
    
    def validate(self, config: Dict[str, Any]) -> list:
        """
        验证配置
        
        Args:
            config: 配置字典
        
        Returns:
            错误列表（空列表表示验证通过）
        """
        errors = []
        
        # 检查类型
        if not isinstance(config, dict):
            errors.append("Config must be a dictionary")
            return errors
        
        # 检查必填字段
        required = self.schema.get("required", [])
        for field in required:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # 检查属性类型
        properties = self.schema.get("properties", {})
        for key, prop_schema in properties.items():
            if key in config:
                value = config[key]
                expected_type = prop_schema.get("type")
                
                if expected_type:
                    if not self._check_type(value, expected_type):
                        errors.append(f"Invalid type for '{key}': expected {expected_type}, got {type(value).__name__}")
                
                # 递归验证嵌套对象
                if expected_type == "object" and isinstance(value, dict):
                    nested_schema = {
                        "type": "object",
                        "properties": prop_schema.get("properties", {}),
                        "required": prop_schema.get("required", [])
                    }
                    nested_validator = ConfigSchema(nested_schema)
                    nested_errors = nested_validator.validate(value)
                    errors.extend([f"{key}.{err}" for err in nested_errors])
        
        return errors
    
    def get_defaults(self) -> Dict[str, Any]:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        return DEFAULT_CONFIG.copy()
    
    def merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        将配置与默认值合并
        
        Args:
            config: 用户配置
        
        Returns:
            合并后的配置
        """
        merged = DEFAULT_CONFIG.copy()
        self._deep_merge(merged, config)
        return merged
    
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
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
