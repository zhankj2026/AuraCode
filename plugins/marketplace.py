"""
Marketplace 管理器 — 对标 Claude Code marketplaceManager.ts

功能:
- 注册/删除/更新 marketplace (Git clone 来源)
- 读取 marketplace.json 获取插件清单
- 持久化 known_marketplaces.json
- 支持多 marketplace 并存
- Seed marketplace (预缓存目录)

目录结构:
  ~/.opencode/
    known_marketplaces.json      # 已注册 marketplace 列表
    marketplaces/                # marketplace clone 缓存
      {marketplace-name}/
        marketplace.json         # 插件清单
        ...
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 路径常量 ──────────────────────────────────────────────────


def _opencode_dir() -> str:
    """获取 ~/.opencode 目录"""
    return os.path.join(os.path.expanduser("~"), ".opencode")


def _known_marketplaces_path() -> str:
    """known_marketplaces.json 路径"""
    return os.path.join(_opencode_dir(), "known_marketplaces.json")


def _marketplaces_cache_dir() -> str:
    """marketplace clone 缓存目录"""
    return os.path.join(_opencode_dir(), "marketplaces")


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class MarketplaceSource:
    """marketplace 来源配置"""
    source: str = "git"          # "github" | "git" | "url" | "file"
    url: str = ""                # git URL 或本地路径
    name: str = ""               # marketplace 名称
    auto_update: bool = True     # 自动更新
    strict: bool = False         # 严格模式（验证签名）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "url": self.url,
            "name": self.name,
            "auto_update": self.auto_update,
            "strict": self.strict,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'MarketplaceSource':
        return MarketplaceSource(
            source=data.get("source", "git"),
            url=data.get("url", ""),
            name=data.get("name", ""),
            auto_update=data.get("auto_update", True),
            strict=data.get("strict", False),
        )


@dataclass
class MarketplacePluginEntry:
    """marketplace.json 中的单个插件条目"""
    name: str
    description: str = ""
    version: str = "0.0.0"
    category: str = ""
    tags: List[str] = field(default_factory=list)
    source: str = ""            # 插件源码 URL (git clone 用)
    author: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "tags": self.tags,
            "source": self.source,
            "author": self.author,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'MarketplacePluginEntry':
        return MarketplacePluginEntry(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "0.0.0"),
            category=data.get("category", ""),
            tags=data.get("tags", []),
            source=data.get("source", ""),
            author=data.get("author", ""),
        )


@dataclass
class MarketplaceManifest:
    """marketplace.json 完整清单"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    plugins: List[MarketplacePluginEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "plugins": [p.to_dict() for p in self.plugins],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'MarketplaceManifest':
        plugins = [
            MarketplacePluginEntry.from_dict(p)
            for p in data.get("plugins", [])
        ]
        return MarketplaceManifest(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            plugins=plugins,
        )


# ── MarketplaceManager ────────────────────────────────────────


class MarketplaceManager:
    """
    Marketplace 管理器

    管理 marketplace 的完整生命周期:
    - add_marketplace: git clone + 注册到 known_marketplaces.json
    - remove_marketplace: 删除 clone + 从配置移除
    - update_marketplace: git pull 更新
    - list_marketplaces: 列出所有已注册 marketplace
    - get_plugins: 读取 marketplace.json 中的插件列表
    """

    def __init__(self):
        self._known: Dict[str, Dict[str, Any]] = {}
        self._load_known()

    # ── 持久化 ──

    def _load_known(self):
        """加载 known_marketplaces.json"""
        path = _known_marketplaces_path()
        if not os.path.exists(path):
            self._known = {}
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._known = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load known_marketplaces.json: {e}")
            self._known = {}

    def _save_known(self):
        """持久化 known_marketplaces.json"""
        path = _known_marketplaces_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._known, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save known_marketplaces.json: {e}")

    # ── 核心操作 ──

    def add_marketplace(self, url: str, name: str = None,
                        source_type: str = "git") -> str:
        """
        添加 marketplace (git clone + 注册)

        Args:
            url: Git URL 或本地路径
            name: marketplace 名称 (默认从 URL 提取)
            source_type: 来源类型 (git/github/file)

        Returns:
            操作结果消息
        """
        # 从 URL 提取名称
        if not name:
            name = url.rstrip("/").split("/")[-1]
            if name.endswith(".git"):
                name = name[:-4]

        if name in self._known:
            return f"⚠️ Marketplace '{name}' 已注册。先 remove 再重新添加。"

        cache_dir = _marketplaces_cache_dir()
        install_dir = os.path.join(cache_dir, name)

        if os.path.exists(install_dir):
            return f"⚠️ 目录已存在: {install_dir}\n使用 /plugins marketplace remove {name} 先移除"

        os.makedirs(cache_dir, exist_ok=True)

        # Git clone
        if source_type in ("git", "github"):
            try:
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", url, install_dir],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    return f"❌ Git clone 失败:\n{result.stderr.strip()[:500]}"
            except subprocess.TimeoutExpired:
                return "❌ Git clone 超时 (120s)"
            except FileNotFoundError:
                return "❌ git 命令不可用，请确保已安装 git"
        elif source_type == "file":
            # 本地目录：符号链接
            if not os.path.exists(url):
                return f"❌ 路径不存在: {url}"
            try:
                os.symlink(os.path.abspath(url), install_dir)
            except OSError as e:
                return f"❌ 创建符号链接失败: {e}"
        else:
            return f"❌ 不支持的来源类型: {source_type}"

        # 读取 marketplace.json
        manifest = self._read_manifest(install_dir)
        if manifest is None:
            # 清理失败的 clone
            import shutil
            shutil.rmtree(install_dir, ignore_errors=True)
            return f"❌ marketplace.json 不存在或格式错误: {install_dir}"

        # 注册
        self._known[name] = {
            "source": source_type,
            "url": url,
            "name": name,
            "install_location": install_dir,
            "auto_update": True,
            "manifest_version": manifest.version,
            "plugin_count": len(manifest.plugins),
        }
        self._save_known()

        return (
            f"✅ Marketplace '{name}' 已添加\n"
            f"   路径: {install_dir}\n"
            f"   插件数: {len(manifest.plugins)}"
        )

    def remove_marketplace(self, name: str) -> str:
        """移除 marketplace"""
        if name not in self._known:
            return f"❌ Marketplace '{name}' 不存在"

        entry = self._known[name]
        install_dir = entry.get("install_location", "")

        # 删除目录
        if install_dir and os.path.exists(install_dir):
            import shutil
            try:
                # 如果是符号链接则 unlink
                if os.path.islink(install_dir):
                    os.unlink(install_dir)
                else:
                    shutil.rmtree(install_dir)
            except Exception as e:
                logger.warning(f"Failed to remove marketplace dir: {e}")

        del self._known[name]
        self._save_known()
        return f"🗑️ Marketplace '{name}' 已移除"

    def update_marketplace(self, name: str = None) -> str:
        """更新 marketplace (git pull)"""
        if name:
            names = [name] if name in self._known else []
        else:
            names = [n for n, e in self._known.items() if e.get("auto_update", True)]

        if not names:
            return f"❌ Marketplace '{name}' 不存在" if name else "无已注册的 marketplace"

        results = []
        for mp_name in names:
            entry = self._known[mp_name]
            install_dir = entry.get("install_location", "")
            source_type = entry.get("source", "git")

            if source_type not in ("git", "github"):
                results.append(f"  ⏭️ {mp_name}: 非 Git 来源，跳过更新")
                continue

            if not os.path.isdir(install_dir) or os.path.islink(install_dir):
                results.append(f"  ⏭️ {mp_name}: 非标准目录，跳过")
                continue

            try:
                result = subprocess.run(
                    ["git", "pull", "--ff-only"],
                    cwd=install_dir,
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if "Already up to date" in output or "Already up-to-date" in output:
                        results.append(f"  ✅ {mp_name}: 已是最新")
                    else:
                        results.append(f"  ✅ {mp_name}: 已更新")
                else:
                    results.append(f"  ❌ {mp_name}: git pull 失败 — {result.stderr.strip()[:100]}")
            except Exception as e:
                results.append(f"  ❌ {mp_name}: {e}")

        return "Marketplace 更新:\n" + "\n".join(results)

    def list_marketplaces(self) -> str:
        """列出所有已注册 marketplace"""
        if not self._known:
            return "无已注册的 marketplace\n使用 /plugins marketplace add <url> 添加"

        lines = [f"已注册 Marketplace ({len(self._known)} 个):\n"]
        for name, entry in self._known.items():
            mp_dir = entry.get("install_location", "")
            exists = "✅" if os.path.exists(mp_dir) else "❌"
            plugin_count = entry.get("plugin_count", "?")
            url = entry.get("url", "")
            lines.append(f"  {exists} {name}")
            lines.append(f"     URL: {url}")
            lines.append(f"     路径: {mp_dir}")
            lines.append(f"     插件: {plugin_count} 个")
            lines.append("")
        return "\n".join(lines)

    def get_marketplace_plugins(self, name: str) -> List[MarketplacePluginEntry]:
        """获取 marketplace 中的插件列表"""
        if name not in self._known:
            return []
        entry = self._known[name]
        install_dir = entry.get("install_location", "")
        manifest = self._read_manifest(install_dir)
        return manifest.plugins if manifest else []

    def get_all_plugins(self) -> Dict[str, List[MarketplacePluginEntry]]:
        """获取所有 marketplace 的全部插件，按 marketplace 名分组"""
        result: Dict[str, List[MarketplacePluginEntry]] = {}
        for name in self._known:
            plugins = self.get_marketplace_plugins(name)
            if plugins:
                result[name] = plugins
        return result

    def search_plugins(self, keyword: str) -> List[Dict[str, Any]]:
        """在所有 marketplace 中搜索插件"""
        keyword_lower = keyword.lower()
        results = []
        for mp_name, plugins in self.get_all_plugins().items():
            for p in plugins:
                if (keyword_lower in p.name.lower() or
                    keyword_lower in p.description.lower() or
                    keyword_lower in p.category.lower() or
                    any(keyword_lower in t.lower() for t in p.tags)):
                    results.append({
                        "marketplace": mp_name,
                        "plugin_id": f"{p.name}@{mp_name}",
                        **p.to_dict(),
                    })
        return results

    def get_marketplace_names(self) -> List[str]:
        """获取所有已注册 marketplace 名称"""
        return list(self._known.keys())

    def get_install_location(self, name: str) -> Optional[str]:
        """获取 marketplace 的安装目录"""
        entry = self._known.get(name)
        return entry.get("install_location") if entry else None

    # ── Seed marketplace ──

    def register_seed_marketplaces(self) -> bool:
        """
        从 OPENCODE_PLUGIN_SEED_DIR 环境变量注册 seed marketplace。

        Seed 目录由管理员/容器镜像预装，优先级最高。
        多个 seed 目录用 os.pathsep 分隔。

        Returns:
            True if any entries were added/changed
        """
        seed_dirs = os.environ.get("OPENCODE_PLUGIN_SEED_DIR", "")
        if not seed_dirs:
            return False

        changed = False
        for seed_dir in seed_dirs.split(os.pathsep):
            seed_dir = seed_dir.strip()
            if not seed_dir or not os.path.exists(seed_dir):
                continue

            manifest = self._read_manifest(seed_dir)
            if manifest is None:
                logger.debug(f"Seed dir has no marketplace.json: {seed_dir}")
                continue

            name = manifest.name or os.path.basename(seed_dir)
            existing = self._known.get(name)

            if existing and existing.get("install_location") == seed_dir:
                continue  # 已注册且路径一致

            self._known[name] = {
                "source": "file",
                "url": seed_dir,
                "name": name,
                "install_location": seed_dir,
                "auto_update": False,  # seed 不可更新
                "manifest_version": manifest.version,
                "plugin_count": len(manifest.plugins),
                "is_seed": True,
            }
            changed = True
            logger.info(f"Seed marketplace registered: {name} from {seed_dir}")

        if changed:
            self._save_known()
        return changed

    # ── 内部方法 ──

    @staticmethod
    def _read_manifest(install_dir: str) -> Optional[MarketplaceManifest]:
        """读取 marketplace.json"""
        if not install_dir:
            return None

        candidates = [
            os.path.join(install_dir, "marketplace.json"),
            os.path.join(install_dir, ".opencode-plugin", "marketplace.json"),
        ]

        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return MarketplaceManifest.from_dict(data)
                except Exception as e:
                    logger.warning(f"Failed to read marketplace.json: {path}: {e}")
                    return None
        return None
