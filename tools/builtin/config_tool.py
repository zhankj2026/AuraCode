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
Config 工具 - 环境配置读写

参考 ConfigTool 设计，支持读取和修改项目配置，
包括 config.yaml、环境变量、项目元数据等。
"""

import os
import json
import yaml
from typing import Optional
from tools.registry import register_tool


# 默认配置文件路径
DEFAULT_CONFIG_FILE = "config.yaml"


def _load_yaml(path: str) -> dict:
    """加载 YAML 配置文件"""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: str, data: dict):
    """保存 YAML 配置文件"""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def config_handler(
    action: str = "get",
    key: str = "",
    value: str = "",
    file: str = "",
    scope: str = "project",
) -> str:
    """
    读写项目配置

    Args:
        action: 操作类型 (get/set/list/env)
        key: 配置键名（支持点分路径如 'model.name'）
        value: 要设置的值（action='set' 时必填）
        file: 配置文件路径（默认 config.yaml）
        scope: 作用域 (project/user/env)
    """
    if action == "env":
        # 列出环境变量
        filtered = []
        prefix = key.upper() if key else ""
        for k, v in sorted(os.environ.items()):
            if prefix and not k.startswith(prefix):
                continue
            # 隐藏敏感值
            masked = v[:8] + "..." if len(v) > 8 else v
            if any(s in k.lower() for s in ("key", "secret", "token", "password")):
                masked = "***"
            filtered.append(f"  {k} = {masked}")
            if len(filtered) >= 50:
                break
        if not filtered:
            return f"未找到匹配 '{key}' 的环境变量"
        return f"环境变量 ({len(filtered)} 项):\n" + "\n".join(filtered)

    # 确定配置文件
    config_path = file or DEFAULT_CONFIG_FILE
    if scope == "user":
        home = os.path.expanduser("~")
        config_path = os.path.join(home, ".auracode", "config.yaml")

    if action == "list":
        # 列出所有配置
        if not os.path.exists(config_path):
            return f"配置文件不存在: {config_path}\n使用 action='set' 创建"
        data = _load_yaml(config_path)
        if not data:
            return f"配置文件为空: {config_path}"
        return f"配置 ({config_path}):\n" + yaml.dump(
            data, allow_unicode=True, default_flow_style=False
        )

    if action == "get":
        if not key:
            return "错误: action='get' 需要提供 key 参数"
        if not os.path.exists(config_path):
            return f"配置文件不存在: {config_path}"
        data = _load_yaml(config_path)
        # 支持点分路径
        parts = key.split(".")
        current = data
        for p in parts:
            if isinstance(current, dict) and p in current:
                current = current[p]
            else:
                return f"键 '{key}' 不存在于 {config_path}"
        if isinstance(current, dict):
            return f"{key}:\n" + yaml.dump(current, allow_unicode=True)
        return f"{key} = {current}"

    if action == "set":
        if not key:
            return "错误: action='set' 需要提供 key 参数"
        if not value:
            return "错误: action='set' 需要提供 value 参数"

        # 加载现有配置
        data = _load_yaml(config_path) if os.path.exists(config_path) else {}

        # 类型推断
        if value.lower() in ("true", "yes"):
            parsed_value = True
        elif value.lower() in ("false", "no"):
            parsed_value = False
        elif value.isdigit():
            parsed_value = int(value)
        else:
            try:
                parsed_value = float(value)
            except ValueError:
                parsed_value = value

        # 支持点分路径
        parts = key.split(".")
        current = data
        for p in parts[:-1]:
            if p not in current or not isinstance(current[p], dict):
                current[p] = {}
            current = current[p]
        current[parts[-1]] = parsed_value

        # 确保目录存在
        config_dir = os.path.dirname(config_path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

        _save_yaml(config_path, data)
        return f"已设置 {key} = {parsed_value} ({config_path})"

    return f"未知操作: {action}（支持 get/set/list/env）"


register_tool("config", {
    "description": (
        "Read/write project configuration. Supports YAML config files and environment variables. "
        "Use action='get' to read a key, 'set' to write, 'list' to show all, "
        "'env' to view environment variables. Supports dot-path notation (e.g. 'model.name')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Operation: get/set/list/env",
                "default": "get",
                "enum": ["get", "set", "list", "env"],
            },
            "key": {
                "type": "string",
                "description": "Config key (supports dot-path like 'model.name')",
                "default": "",
            },
            "value": {
                "type": "string",
                "description": "Value to set (required for action='set')",
                "default": "",
            },
            "file": {
                "type": "string",
                "description": "Config file path (default: config.yaml)",
                "default": "",
            },
            "scope": {
                "type": "string",
                "description": "Scope: project/user/env",
                "default": "project",
                "enum": ["project", "user", "env"],
            },
        },
        "required": ["action"],
    },
    "handler": config_handler,
    "permission_level": "write",
})
