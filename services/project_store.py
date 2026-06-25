"""
项目级配置存储 (Project Store)

对标 Claude Code: ~/.claude/projects/{sanitized-cwd}/.config.json
每个项目目录维护独立的配置，包括:
- 允许的工具列表
- MCP 服务器配置
- 信任对话状态
- 项目级 onboarding 状态

存储结构:
~/.auracode/projects/{sanitized-cwd}/.config.json

何时读取:
- 会话启动时加载项目配置
- /config-edit 命令修改时

何时写入:
- 用户通过命令修改项目配置时
- 权限规则变更时
"""

import json
import os
import re
import logging
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 路径工具 ──

def _auracode_home() -> str:
    return os.path.join(os.path.expanduser("~"), ".auracode")


def _sanitize_path(path: str) -> str:
    normalized = os.path.normpath(os.path.abspath(path))
    if len(normalized) >= 2 and normalized[1] == ':':
        normalized = normalized[2:]
    sanitized = re.sub(r'[^a-zA-Z0-9]', '-', normalized)
    sanitized = re.sub(r'-+', '-', sanitized).strip('-')
    if len(sanitized) > 200:
        h = abs(hash(path)) % (16 ** 8)
        sanitized = f"{sanitized[:200]}-{h:08x}"
    return sanitized


def get_project_dir(cwd: str) -> str:
    return os.path.join(_auracode_home(), "projects", _sanitize_path(cwd))


def get_project_config_path(cwd: str) -> str:
    return os.path.join(get_project_dir(cwd), ".config.json")


# ── 项目配置数据 ──

@dataclass
class ProjectConfig:
    """项目级配置"""
    # 工具权限
    allowed_tools: List[str] = field(default_factory=list)
    denied_tools: List[str] = field(default_factory=list)

    # MCP 服务器
    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    enabled_mcp_servers: List[str] = field(default_factory=list)
    disabled_mcp_servers: List[str] = field(default_factory=list)

    # 信任与安全
    trust_accepted: bool = False
    onboarding_seen_count: int = 0

    # 权限规则
    permission_rules: List[Dict[str, str]] = field(default_factory=list)
    # [{"pattern": "*.py", "action": "allow"}, ...]

    # 模型偏好
    preferred_model: str = ""

    # 会话设置
    auto_compact_enabled: bool = True
    file_checkpointing_enabled: bool = True
    auto_memory_enabled: bool = True

    # 元数据
    last_updated: str = ""
    project_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid}
        return cls(**filtered)


# ── 项目配置管理器 ──

class ProjectStore:
    """
    项目级配置管理器

    用法:
        store = ProjectStore(cwd="/home/user/myproject")
        config = store.load()
        config.allowed_tools.append("bash")
        store.save(config)
    """

    def __init__(self, cwd: str):
        self.cwd = cwd
        self._config_path = get_project_config_path(cwd)
        self._config_dir = get_project_dir(cwd)
        self._lock = threading.Lock()
        self._cache: Optional[ProjectConfig] = None

        os.makedirs(self._config_dir, exist_ok=True)
        logger.debug(f"ProjectStore initialized: {self._config_dir}")

    def load(self) -> ProjectConfig:
        """加载项目配置（带缓存）"""
        if self._cache is not None:
            return self._cache

        with self._lock:
            if not os.path.exists(self._config_path):
                self._cache = ProjectConfig(project_path=self.cwd)
                return self._cache

            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._cache = ProjectConfig.from_dict(data)
                self._cache.project_path = self.cwd
            except Exception as e:
                logger.warning(f"Failed to load project config: {e}")
                self._cache = ProjectConfig(project_path=self.cwd)

            return self._cache

    def save(self, config: Optional[ProjectConfig] = None) -> bool:
        """
        保存项目配置

        Args:
            config: 要保存的配置（None 则保存缓存）
        """
        if config is not None:
            self._cache = config

        if self._cache is None:
            return False

        self._cache.last_updated = datetime.now().isoformat()
        self._cache.project_path = self.cwd

        with self._lock:
            try:
                with open(self._config_path, "w", encoding="utf-8") as f:
                    json.dump(self._cache.to_dict(), f, indent=2, ensure_ascii=False)
                logger.info(f"Project config saved: {self._config_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to save project config: {e}")
                return False

    def update(self, **kwargs) -> bool:
        """
        更新部分配置字段

        用法:
            store.update(allowed_tools=["bash", "write_file"], preferred_model="gpt-4")
        """
        config = self.load()
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return self.save(config)

    def get(self, key: str, default: Any = None) -> Any:
        """获取单个配置值"""
        config = self.load()
        return getattr(config, key, default)

    def invalidate_cache(self):
        """清除缓存，强制下次重新加载"""
        self._cache = None

    def exists(self) -> bool:
        """检查项目配置文件是否存在"""
        return os.path.exists(self._config_path)

    def delete(self) -> bool:
        """删除项目配置"""
        try:
            if os.path.exists(self._config_path):
                os.remove(self._config_path)
                self._cache = None
                return True
        except Exception as e:
            logger.error(f"Failed to delete project config: {e}")
        return False


# ── 全局单例 ──

_stores: Dict[str, ProjectStore] = {}


def get_project_store(cwd: Optional[str] = None) -> ProjectStore:
    """获取指定项目的配置存储"""
    if cwd is None:
        cwd = os.getcwd()
    cwd = os.path.normpath(os.path.abspath(cwd))
    if cwd not in _stores:
        _stores[cwd] = ProjectStore(cwd=cwd)
    return _stores[cwd]


def list_project_configs() -> List[Dict[str, Any]]:
    """列出所有项目的配置"""
    results = []
    projects_dir = os.path.join(_auracode_home(), "projects")
    if not os.path.exists(projects_dir):
        return results

    for dirname in os.listdir(projects_dir):
        config_path = os.path.join(projects_dir, dirname, ".config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "project_dir": dirname,
                    "config_path": config_path,
                    "config": data,
                })
            except Exception:
                pass

    return results
