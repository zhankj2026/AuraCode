"""
全局用户设置 (settings.json)

管理 ~/.opencode/settings.json，存储用户级偏好和全局配置。
支持项目级覆盖 (.opencode/settings.json)。

设计参考:
- Claude Code: ~/.claude/settings.json (全局) + .claude/settings.json (项目级)
- 支持热重载、文件锁、时间戳备份
"""

import json
import os
import time
import shutil
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 默认值 ──────────────────────────────────────────────────────────────────

_DEFAULT_SETTINGS = {
    # 模型偏好
    "preferred_model": "",
    "fallback_model": "",

    # 权限默认值
    "default_permission_mode": "normal",

    # 显示偏好
    "theme": "auto",           # auto / dark / light
    "language": "zh",          # zh / en
    "verbose": False,          # 详细输出模式
    "show_token_count": True,  # 显示 token 统计
    "show_cost": True,         # 显示费用

    # Agent 行为
    "max_iterations": 20,
    "auto_compact_threshold": 0.7,  # 上下文使用率超过此阈值时自动压缩
    "streaming_enabled": True,

    # 持久化控制
    "auto_save_sessions": True,
    "file_history_enabled": True,
    "history_log_enabled": True,

    # MCP 服务器
    "mcp_servers": {},

    # 自定义指令（注入到 system prompt）
    "custom_instructions": "",

    # 工具偏好
    "disabled_tools": [],      # 禁用的工具名列表
    "preferred_shell": "",     # 首选 shell（空=系统默认）

    # 安全
    "trusted_paths": [],       # 信任的路径列表
    "blocked_commands": [],    # 阻止的命令模式

    # 元数据
    "_version": 1,
    "_last_modified": "",
}


# ── 路径工具 ────────────────────────────────────────────────────────────────

def _global_settings_path() -> str:
    """全局设置文件路径"""
    home = os.path.expanduser("~")
    return os.path.join(home, ".opencode", "settings.json")


def _project_settings_path(project_root: str) -> str:
    """项目级设置文件路径"""
    return os.path.join(project_root, ".opencode", "settings.json")


def _backups_dir() -> str:
    """设置备份目录"""
    home = os.path.expanduser("~")
    return os.path.join(home, ".opencode", "backups")


# ── SettingsStore ────────────────────────────────────────────────────────────

class SettingsStore:
    """
    全局用户设置管理器

    层级优先级（高到低）:
    1. 项目级 .opencode/settings.json
    2. 全局级 ~/.opencode/settings.json
    3. 内置默认值 _DEFAULT_SETTINGS

    功能:
    - get(): 获取设置值（支持点分路径如 'agent.max_iterations'）
    - set(): 设置值（自动持久化）
    - get_merged(): 获取合并后的完整配置
    - reset(): 重置为默认值
    - backup(): 创建时间戳备份
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        Args:
            project_root: 项目根目录（None 则仅使用全局设置）
        """
        self._global_path = _global_settings_path()
        self._project_path = _project_settings_path(project_root) if project_root else None
        self._backups_dir = _backups_dir()

        # 缓存
        self._global_cache: Optional[Dict[str, Any]] = None
        self._project_cache: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0.0
        self._cache_ttl: float = 5.0  # 缓存有效期（秒）

        logger.debug(
            f"SettingsStore initialized: global={self._global_path}, "
            f"project={self._project_path}"
        )

    # ── 读取 ────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取设置值（支持点分路径）

        优先级: 项目级 > 全局级 > 默认值

        Args:
            key: 配置键名（如 'preferred_model' 或 'agent.max_iterations'）
            default: 键不存在时的默认值

        Returns:
            设置值
        """
        merged = self.get_merged()
        return self._get_nested(merged, key, default)

    def get_merged(self) -> Dict[str, Any]:
        """
        获取合并后的完整配置

        合并顺序: 默认值 ← 全局设置 ← 项目设置
        """
        result = dict(_DEFAULT_SETTINGS)

        # 全局设置覆盖
        global_settings = self._load_global()
        if global_settings:
            result.update(global_settings)

        # 项目设置覆盖
        if self._project_path:
            project_settings = self._load_project()
            if project_settings:
                # 项目设置只覆盖非元数据字段
                for k, v in project_settings.items():
                    if not k.startswith("_"):
                        result[k] = v

        return result

    def get_global(self, key: str, default: Any = None) -> Any:
        """仅从全局设置中获取值"""
        settings = self._load_global() or dict(_DEFAULT_SETTINGS)
        return self._get_nested(settings, key, default)

    # ── 写入 ────────────────────────────────────────────────────────────

    def set(self, key: str, value: Any, scope: str = "global") -> bool:
        """
        设置值并持久化

        Args:
            key: 配置键名（支持点分路径）
            value: 值
            scope: 作用域 ("global" 或 "project")

        Returns:
            True 如果成功
        """
        if scope == "project" and self._project_path:
            settings = self._load_project() or {}
            self._set_nested(settings, key, value)
            success = self._save_file(self._project_path, settings)
            if success:
                self._project_cache = settings
        else:
            settings = self._load_global() or dict(_DEFAULT_SETTINGS)
            self._set_nested(settings, key, value)
            settings["_last_modified"] = datetime.now().isoformat()
            success = self._save_file(self._global_path, settings)
            if success:
                self._global_cache = settings

        # 使缓存失效
        self._cache_time = 0.0
        return success

    def remove(self, key: str, scope: str = "global") -> bool:
        """删除指定设置键"""
        if scope == "project" and self._project_path:
            settings = self._load_project() or {}
        else:
            settings = self._load_global() or dict(_DEFAULT_SETTINGS)

        parts = key.split(".")
        if len(parts) == 1:
            settings.pop(key, None)
        else:
            parent = settings
            for part in parts[:-1]:
                parent = parent.get(part, {})
                if not isinstance(parent, dict):
                    return False
            parent.pop(parts[-1], None)

        if scope == "project" and self._project_path:
            success = self._save_file(self._project_path, settings)
            self._project_cache = settings
        else:
            settings["_last_modified"] = datetime.now().isoformat()
            success = self._save_file(self._global_path, settings)
            self._global_cache = settings

        self._cache_time = 0.0
        return success

    def reset(self, scope: str = "global") -> bool:
        """重置为默认值"""
        if scope == "project" and self._project_path:
            try:
                if os.path.exists(self._project_path):
                    self.backup(scope)
                    os.remove(self._project_path)
                self._project_cache = None
                return True
            except Exception as e:
                logger.error(f"Failed to reset project settings: {e}")
                return False
        else:
            self.backup("global")
            settings = dict(_DEFAULT_SETTINGS)
            settings["_last_modified"] = datetime.now().isoformat()
            success = self._save_file(self._global_path, settings)
            self._global_cache = settings
            return success

    # ── 备份 ────────────────────────────────────────────────────────────

    def backup(self, scope: str = "global") -> Optional[str]:
        """
        创建设置文件的时间戳备份

        备份存储在 ~/.opencode/backups/ 目录下。

        Args:
            scope: "global" 或 "project"

        Returns:
            备份文件路径，失败时返回 None
        """
        source = self._project_path if scope == "project" else self._global_path
        if not source or not os.path.exists(source):
            return None

        try:
            os.makedirs(self._backups_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            basename = "settings_project" if scope == "project" else "settings"
            backup_name = f"{basename}_{timestamp}.json"
            backup_path = os.path.join(self._backups_dir, backup_name)

            shutil.copy2(source, backup_path)
            logger.info(f"Settings backed up: {backup_path}")

            # 清理旧备份（保留最近 10 个）
            self._cleanup_backups(scope)

            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup settings: {e}")
            return None

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份文件"""
        backups = []
        try:
            if not os.path.exists(self._backups_dir):
                return backups
            for filename in sorted(os.listdir(self._backups_dir), reverse=True):
                if not filename.startswith("settings") or not filename.endswith(".json"):
                    continue
                path = os.path.join(self._backups_dir, filename)
                backups.append({
                    "filename": filename,
                    "path": path,
                    "size_bytes": os.path.getsize(path),
                    "modified": datetime.fromtimestamp(
                        os.path.getmtime(path)
                    ).isoformat(),
                })
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
        return backups

    def _cleanup_backups(self, scope: str, keep: int = 10):
        """清理旧备份"""
        try:
            prefix = "settings_project" if scope == "project" else "settings_"
            files = []
            for filename in os.listdir(self._backups_dir):
                if filename.startswith(prefix) and filename.endswith(".json"):
                    path = os.path.join(self._backups_dir, filename)
                    files.append((path, os.path.getmtime(path)))

            files.sort(key=lambda x: x[1], reverse=True)
            for path, _ in files[keep:]:
                os.remove(path)
                logger.debug(f"Old backup removed: {path}")
        except Exception as e:
            logger.debug(f"Backup cleanup failed: {e}")

    # ── 文件 I/O ─────────────────────────────────────────────────────────

    def _load_global(self) -> Optional[Dict[str, Any]]:
        """加载全局设置（带缓存）"""
        now = time.time()
        if self._global_cache is not None and (now - self._cache_time) < self._cache_ttl:
            return self._global_cache

        data = self._load_file(self._global_path)
        if data is not None:
            self._global_cache = data
            self._cache_time = now
        return data

    def _load_project(self) -> Optional[Dict[str, Any]]:
        """加载项目级设置（带缓存）"""
        if not self._project_path:
            return None

        now = time.time()
        if self._project_cache is not None and (now - self._cache_time) < self._cache_ttl:
            return self._project_cache

        data = self._load_file(self._project_path)
        if data is not None:
            self._project_cache = data
            self._cache_time = now
        return data

    def _load_file(self, path: str) -> Optional[Dict[str, Any]]:
        """从 JSON 文件加载设置"""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning(f"Invalid settings format in {path}")
                return None
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Settings JSON parse error in {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load settings from {path}: {e}")
            return None

    def _save_file(self, path: str, data: Dict[str, Any]) -> bool:
        """保存设置到 JSON 文件"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)

            # 原子写入：先写临时文件再重命名（防止并发写入损坏）
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # Windows 上 rename 需要目标不存在
            if os.path.exists(path):
                os.replace(tmp_path, path)
            else:
                os.rename(tmp_path, path)

            logger.debug(f"Settings saved: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings to {path}: {e}")
            # 清理临时文件
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            return False

    # ── 辅助方法 ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_nested(data: Dict, key: str, default: Any = None) -> Any:
        """按点分路径获取嵌套值"""
        parts = key.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return default
            else:
                return default
        return current

    @staticmethod
    def _set_nested(data: Dict, key: str, value: Any):
        """按点分路径设置嵌套值"""
        parts = key.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def to_display_dict(self) -> Dict[str, Any]:
        """生成用户友好的显示格式（隐藏敏感字段）"""
        merged = self.get_merged()
        display = {}
        sensitive_keys = {"api_key", "secret", "token", "password"}
        for key, value in merged.items():
            if any(s in key.lower() for s in sensitive_keys):
                display[key] = "***" if value else "(not set)"
            else:
                display[key] = value
        return display


# ── 全局单例 ────────────────────────────────────────────────────────────────

_settings_store: Optional[SettingsStore] = None


def get_settings_store(project_root: Optional[str] = None) -> SettingsStore:
    """获取全局 SettingsStore 实例"""
    global _settings_store
    if _settings_store is None:
        _settings_store = SettingsStore(project_root=project_root)
    return _settings_store
