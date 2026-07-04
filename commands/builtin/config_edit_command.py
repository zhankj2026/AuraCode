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
/config-edit 命令 - 运行时配置热编辑

支持查看、修改、重载 config.yaml 中的配置项。
修改后立即生效（热更新），无需重启。

用法:
    /config-edit                  — 显示当前配置概览
    /config-edit show [section]   — 显示配置（可指定节）
    /config-edit get <key>        — 获取单个配置值
    /config-edit set <key> <val>  — 设置配置值（热生效）
    /config-edit reload           — 从文件重新加载配置
    /config-edit diff             — 对比运行时配置与文件配置
    /config-edit path             — 显示配置文件路径
"""

import os
import yaml
import copy
import logging
from typing import Optional, Dict, Any
from commands.registry import register_command

logger = logging.getLogger(__name__)

# 运行时配置（内存中的副本）
_runtime_config: Dict[str, Any] = {}
# 配置文件路径
_config_path: Optional[str] = None
# 原始文件配置（用于 diff）
_file_config: Dict[str, Any] = {}


def set_config(config: Dict[str, Any], config_path: str = None):
    """初始化运行时配置"""
    global _runtime_config, _config_path, _file_config
    _runtime_config = copy.deepcopy(config)
    _file_config = copy.deepcopy(config)
    _config_path = config_path


def get_runtime_config() -> Dict[str, Any]:
    """获取运行时配置（供其他模块读取）"""
    return _runtime_config


def _load_config() -> Dict[str, Any]:
    """从文件加载配置"""
    if not _config_path or not os.path.exists(_config_path):
        return {}
    try:
        with open(_config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        return {}


def _save_config(cfg: Dict[str, Any]) -> bool:
    """保存配置到文件"""
    if not _config_path:
        return False
    try:
        with open(_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return False


def _get_nested(config: Dict, key: str) -> Any:
    """获取嵌套配置值（支持 dot notation: llm.model）"""
    parts = key.split(".")
    current = config
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _set_nested(config: Dict, key: str, value: Any) -> bool:
    """设置嵌套配置值"""
    parts = key.split(".")
    current = config
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    last = parts[-1]
    # 尝试类型转换
    old_val = current.get(last)
    if old_val is not None:
        value = _coerce_type(value, type(old_val))
    current[last] = value
    return True


def _coerce_type(value: str, target_type: type) -> Any:
    """尝试将字符串值转换为目标类型"""
    if target_type == bool:
        return value.lower() in ["true", "1", "yes", "on"]
    elif target_type == int:
        try:
            return int(value)
        except ValueError:
            return value
    elif target_type == float:
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _format_config(cfg: Dict, indent: int = 0, max_depth: int = 3) -> str:
    """格式化配置为可读文本"""
    lines = []
    prefix = "  " * indent
    for key, value in cfg.items():
        if isinstance(value, dict) and indent < max_depth:
            lines.append(f"{prefix}{key}:")
            lines.append(_format_config(value, indent + 1, max_depth))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}: [{', '.join(str(v) for v in value)}]")
        else:
            # 隐藏敏感字段
            display = value
            if "key" in key.lower() or "secret" in key.lower() or "password" in key.lower():
                display = "***"
            lines.append(f"{prefix}{key}: {display}")
    return "\n".join(lines)


def config_edit_handler(args: str, loop=None) -> str:
    """配置热编辑命令处理器"""
    parts = args.strip().split()

    if not parts:
        return _cmd_overview()

    sub = parts[0].lower()
    rest = parts[1:]

    if sub == "show":
        return _cmd_show(rest)
    elif sub == "get":
        return _cmd_get(rest)
    elif sub == "set":
        return _cmd_set(rest)
    elif sub == "reload":
        return _cmd_reload()
    elif sub == "diff":
        return _cmd_diff()
    elif sub == "path":
        return _cmd_path()
    elif sub == "help":
        return _cmd_help()
    else:
        return f"未知子命令: {sub}\n\n{_cmd_help()}"


def _cmd_overview() -> str:
    """配置概览"""
    if not _runtime_config:
        return "📋 运行时配置为空"

    lines = ["📋 运行时配置概览", ""]
    # 按节显示
    sections = list(_runtime_config.keys())
    for section in sections:
        value = _runtime_config[section]
        if isinstance(value, dict):
            lines.append(f"  [{section}]")
            for k, v in list(value.items())[:5]:
                display = v
                if "key" in k.lower() or "secret" in k.lower():
                    display = "***"
                elif isinstance(v, str) and len(v) > 40:
                    display = v[:40] + "..."
                lines.append(f"    {k}: {display}")
            if len(value) > 5:
                lines.append(f"    ... 还有 {len(value) - 5} 项")
            lines.append("")
        else:
            lines.append(f"  {section}: {value}")

    lines.append(f"  配置文件: {_config_path or '未指定'}")
    return "\n".join(lines)


def _cmd_show(rest) -> str:
    """显示配置"""
    if not rest:
        return _format_config(_runtime_config)

    section = rest[0]
    value = _runtime_config.get(section)
    if value is None:
        return f"❌ 配置节不存在: {section}"

    if isinstance(value, dict):
        return f"[{section}]\n{_format_config(value)}"
    return f"{section}: {value}"


def _cmd_get(rest) -> str:
    """获取配置值"""
    if not rest:
        return "用法: /config-edit get <key> (支持 dot notation: llm.model)"

    key = rest[0]
    value = _get_nested(_runtime_config, key)
    if value is None:
        return f"❌ 配置项不存在: {key}"

    # 隐藏敏感字段
    if "key" in key.lower() or "secret" in key.lower():
        value = "***"
    return f"{key} = {value}"


def _cmd_set(rest) -> str:
    """设置配置值"""
    if len(rest) < 2:
        return "用法: /config-edit set <key> <value> (支持 dot notation: llm.model gpt-4o)"

    key = rest[0]
    value = " ".join(rest[1:])

    old_value = _get_nested(_runtime_config, key)

    # 设置运行时配置
    _set_nested(_runtime_config, key, value)

    # 持久化到文件
    file_cfg = _load_config()
    _set_nested(file_cfg, key, value)
    saved = _save_config(file_cfg)

    # 更新文件配置副本
    _file_config = copy.deepcopy(file_cfg)

    new_value = _get_nested(_runtime_config, key)
    change = f"{old_value} → {new_value}" if old_value is not None else f"(新增) {new_value}"
    suffix = "（已持久化）" if saved else "（仅运行时生效）"
    return f"✅ {key}: {change} {suffix}"


def _cmd_reload() -> str:
    """从文件重新加载配置"""
    new_cfg = _load_config()
    if not new_cfg:
        return "❌ 加载配置失败或文件为空"

    global _runtime_config, _file_config
    old_keys = set(_runtime_config.keys())
    new_keys = set(new_cfg.keys())

    _runtime_config = copy.deepcopy(new_cfg)
    _file_config = copy.deepcopy(new_cfg)

    added = new_keys - old_keys
    removed = old_keys - new_keys

    lines = ["🔄 配置已从文件重新加载"]
    if added:
        lines.append(f"  新增节: {', '.join(added)}")
    if removed:
        lines.append(f"  移除节: {', '.join(removed)}")
    lines.append(f"  配置文件: {_config_path}")
    return "\n".join(lines)


def _cmd_diff() -> str:
    """对比运行时配置与文件配置"""
    file_cfg = _load_config()
    if not file_cfg:
        return "❌ 无法加载文件配置"

    # 简单递归比较
    diffs = _compare_dicts(_runtime_config, file_cfg)
    if not diffs:
        return "✅ 运行时配置与文件配置一致"

    lines = ["⚠️ 运行时配置与文件配置存在差异:", ""]
    for path, runtime_val, file_val in diffs:
        lines.append(f"  {path}:")
        lines.append(f"    运行时: {runtime_val}")
        lines.append(f"    文件:   {file_val}")
    lines.append("")
    lines.append("  使用 /config-edit reload 从文件重新加载")
    return "\n".join(lines)


def _compare_dicts(d1: Dict, d2: Dict, prefix: str = "") -> list:
    """递归比较两个字典"""
    diffs = []
    all_keys = set(d1.keys()) | set(d2.keys())
    for key in sorted(all_keys):
        path = f"{prefix}.{key}" if prefix else key
        if key not in d1:
            diffs.append((path, "(不存在)", d2[key]))
        elif key not in d2:
            diffs.append((path, d1[key], "(不存在)"))
        elif isinstance(d1[key], dict) and isinstance(d2[key], dict):
            diffs.extend(_compare_dicts(d1[key], d2[key], path))
        elif d1[key] != d2[key]:
            diffs.append((path, d1[key], d2[key]))
    return diffs


def _cmd_path() -> str:
    """显示配置文件路径"""
    if _config_path:
        exists = os.path.exists(_config_path)
        return f"配置文件路径: {_config_path}\n文件状态: {'存在' if exists else '不存在'}"
    return "❌ 未设置配置文件路径"


def _cmd_help() -> str:
    return """配置热编辑命令 /config-edit

用法:
  /config-edit                   显示运行时配置概览
  /config-edit show [section]    显示配置（可指定节: llm/permissions/agent 等）
  /config-edit get <key>         获取配置值（dot notation: llm.model）
  /config-edit set <key> <val>   设置配置值（热生效 + 持久化）
  /config-edit reload            从文件重新加载配置
  /config-edit diff              对比运行时配置与文件配置
  /config-edit path              显示配置文件路径

Key 格式 (dot notation):
  llm.model          — LLM 模型
  llm.max_tokens     — 最大 token 数
  llm.temperature    — 温度
  permissions.mode   — 权限模式
  agent.max_iterations — 最大迭代次数
  context.max_files_read — 最大文件读取数"""


register_command("config-edit", {
    "description": "运行时配置热编辑 (查看/修改/重载/diff)",
    "handler": config_edit_handler,
    "args_help": "[show|get|set|reload|diff|path]",
    "category": "system",
})
