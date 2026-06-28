"""
Plugin Installer — 从 marketplace 安装/卸载/更新插件

参考标准pluginLoader.ts + headlessPluginInstall.ts

功能:
- install_plugin: git clone 插件到缓存目录
- uninstall_plugin: 删除插件 + 清理
- update_plugin: git pull 更新
- list_installed: 列出已安装插件
- is_installed: 检查安装状态
- reconcile: 对账（声明 vs 实际安装）

目录结构:
  ~/.auracode/
    installed_plugins.json                    # 已安装插件记录
    plugins/cache/                            # 插件安装缓存
      {marketplace_name}/
        {plugin_name}/
          {version}/                          # 版本目录
            plugin.json                       # 插件清单
            __init__.py                       # ToolPlugin 实现
            skills/                           # 可选 skill 目录
              {skill_name}/
                SKILL.md
"""

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _installed_plugins_path() -> str:
    """installed_plugins.json 路径"""
    return os.path.join(os.path.expanduser("~"), ".auracode", "installed_plugins.json")


def _plugin_cache_dir() -> str:
    """插件缓存根目录"""
    return os.path.join(os.path.expanduser("~"), ".auracode", "plugins", "cache")


def _get_plugin_dir(marketplace: str, plugin_name: str, version: str) -> str:
    """获取插件版本目录"""
    return os.path.join(_plugin_cache_dir(), marketplace, plugin_name, version)


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class InstalledPlugin:
    """已安装插件记录"""
    plugin_id: str          # {name}@{marketplace}
    name: str
    marketplace: str
    version: str
    install_location: str
    installed_at: str = ""
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "marketplace": self.marketplace,
            "version": self.version,
            "install_location": self.install_location,
            "installed_at": self.installed_at,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'InstalledPlugin':
        return InstalledPlugin(
            plugin_id=data.get("plugin_id", ""),
            name=data.get("name", ""),
            marketplace=data.get("marketplace", ""),
            version=data.get("version", ""),
            install_location=data.get("install_location", ""),
            installed_at=data.get("installed_at", ""),
            enabled=data.get("enabled", True),
        )


@dataclass
class PluginJson:
    """plugin.json — 插件清单"""
    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    license: str = "MIT"
    homepage: str = ""
    entry_point: str = "__init__.py"
    skills: List[str] = field(default_factory=list)
    mcp_servers: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @staticmethod
    def from_file(path: str) -> Optional['PluginJson']:
        """从 plugin.json 加载"""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PluginJson(
                name=data.get("name", ""),
                version=data.get("version", "0.0.0"),
                description=data.get("description", ""),
                author=data.get("author", ""),
                license=data.get("license", "MIT"),
                homepage=data.get("homepage", ""),
                entry_point=data.get("entry_point", "__init__.py"),
                skills=data.get("skills", []),
                mcp_servers=data.get("mcp_servers", []),
                tags=data.get("tags", []),
            )
        except Exception as e:
            logger.warning(f"Failed to read plugin.json: {path}: {e}")
            return None


# ── PluginInstaller ───────────────────────────────────────────


class PluginInstaller:
    """
    插件安装器

    管理从 marketplace 安装/卸载/更新插件的完整流程。
    持久化到 installed_plugins.json。
    """

    def __init__(self):
        self._installed: Dict[str, InstalledPlugin] = {}
        self._load_installed()

    def _load_installed(self):
        """加载 installed_plugins.json"""
        path = _installed_plugins_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for plugin_id, entry in data.items():
                self._installed[plugin_id] = InstalledPlugin.from_dict(entry)
        except Exception as e:
            logger.warning(f"Failed to load installed_plugins.json: {e}")

    def _save_installed(self):
        """持久化 installed_plugins.json"""
        path = _installed_plugins_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            data = {pid: p.to_dict() for pid, p in self._installed.items()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save installed_plugins.json: {e}")

    def install_plugin(self, plugin_name: str, marketplace: str,
                       source_url: str = "", version: str = "latest") -> str:
        """
        安装插件

        Args:
            plugin_name: 插件名称
            marketplace: 所属 marketplace 名称
            source_url: 插件源码 URL (git clone 用)
            version: 版本号 (默认 latest)

        Returns:
            操作结果消息
        """
        plugin_id = f"{plugin_name}@{marketplace}"

        if plugin_id in self._installed:
            return f"⚠️ 插件 '{plugin_id}' 已安装\n使用 /plugins uninstall {plugin_id} 先卸载"

        # 确定版本
        actual_version = version if version != "latest" else "1.0.0"
        plugin_dir = _get_plugin_dir(marketplace, plugin_name, actual_version)

        if os.path.exists(plugin_dir):
            return f"⚠️ 插件目录已存在: {plugin_dir}"

        os.makedirs(os.path.dirname(plugin_dir), exist_ok=True)

        # Git clone
        if source_url:
            try:
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", source_url, plugin_dir],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    return f"❌ Git clone 失败:\n{result.stderr.strip()[:500]}"
            except subprocess.TimeoutExpired:
                return "❌ Git clone 超时"
            except FileNotFoundError:
                return "❌ git 命令不可用"
        else:
            # 从 marketplace clone 的子目录中查找
            from plugins.marketplace import MarketplaceManager
            mm = MarketplaceManager()
            mp_dir = mm.get_install_location(marketplace)
            if not mp_dir or not os.path.exists(mp_dir):
                known = mm.get_marketplace_names()
                available = ", ".join(known) if known else "(无)"
                return (
                    f"❌ Marketplace '{marketplace}' 不存在或目录已丢失。\n"
                    f"\n"
                    f"已注册的 marketplace: {available}\n"
                    f"\n"
                    f"请先注册 marketplace:\n"
                    f"  /plugins marketplace add <git-url> --name {marketplace}\n"
                    f"\n"
                    f"或直接从 Git URL 安装:\n"
                    f"  /plugins install {plugin_name}@git:<url>"
                )

            # 检查 marketplace 目录中是否有插件子目录
            plugin_subdir = os.path.join(mp_dir, plugin_name)
            if not os.path.isdir(plugin_subdir):
                # 列出 marketplace 中可用的插件目录
                available_dirs = [
                    d for d in os.listdir(mp_dir)
                    if os.path.isdir(os.path.join(mp_dir, d))
                    and not d.startswith('.')
                    and d != 'node_modules'
                ]
                return (
                    f"❌ 插件 '{plugin_name}' 不在 marketplace '{marketplace}' 中。\n"
                    f"\n"
                    f"可用插件目录: {', '.join(available_dirs[:15]) or '(无)'}"
                )

            # 复制到缓存
            shutil.copytree(plugin_subdir, plugin_dir)

        # 读取 plugin.json
        manifest = PluginJson.from_file(os.path.join(plugin_dir, "plugin.json"))
        actual_version = manifest.version if manifest else actual_version

        # 记录安装
        from datetime import datetime
        self._installed[plugin_id] = InstalledPlugin(
            plugin_id=plugin_id,
            name=plugin_name,
            marketplace=marketplace,
            version=actual_version,
            install_location=plugin_dir,
            installed_at=datetime.now().isoformat(),
            enabled=True,
        )
        self._save_installed()

        desc = f" — {manifest.description}" if manifest and manifest.description else ""
        return (
            f"✅ 插件已安装: {plugin_id} v{actual_version}\n"
            f"   路径: {plugin_dir}{desc}\n"
            f"   使用 /plugins reload 激活"
        )

    def uninstall_plugin(self, plugin_id: str) -> str:
        """卸载插件"""
        if plugin_id not in self._installed:
            return f"❌ 插件 '{plugin_id}' 未安装"

        entry = self._installed[plugin_id]
        plugin_dir = entry.install_location

        # 删除目录
        if plugin_dir and os.path.exists(plugin_dir):
            try:
                shutil.rmtree(plugin_dir)
            except Exception as e:
                logger.warning(f"Failed to remove plugin dir: {e}")

        # 清理空目录
        parent = os.path.dirname(plugin_dir) if plugin_dir else ""
        if parent and os.path.isdir(parent) and not os.listdir(parent):
            try:
                os.rmdir(parent)
            except OSError:
                pass

        del self._installed[plugin_id]
        self._save_installed()
        return f"🗑️ 插件已卸载: {plugin_id}"

    def update_plugin(self, plugin_id: str) -> str:
        """更新插件 (git pull)"""
        if plugin_id not in self._installed:
            return f"❌ 插件 '{plugin_id}' 未安装"

        entry = self._installed[plugin_id]
        plugin_dir = entry.install_location

        if not os.path.isdir(plugin_dir):
            return f"❌ 插件目录不存在: {plugin_dir}"

        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=plugin_dir,
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if "Already up to date" in output or "Already up-to-date" in output:
                    return f"✅ {plugin_id}: 已是最新"
                return f"✅ {plugin_id}: 已更新"
            else:
                return f"❌ {plugin_id}: git pull 失败 — {result.stderr.strip()[:200]}"
        except Exception as e:
            return f"❌ {plugin_id}: {e}"

    def list_installed(self) -> List[InstalledPlugin]:
        """列出所有已安装插件"""
        return list(self._installed.values())

    def list_installed_str(self) -> str:
        """列出已安装插件（格式化字符串）"""
        if not self._installed:
            return "无已安装的市场place插件\n使用 /plugins install <name>@<marketplace> 安装"

        lines = [f"已安装插件 ({len(self._installed)} 个):\n"]
        for pid, entry in self._installed.items():
            status = "✅" if entry.enabled else "⏸️"
            lines.append(f"  {status} {pid} v{entry.version}")
            lines.append(f"     路径: {entry.install_location}")
            lines.append(f"     安装于: {entry.installed_at[:10]}")
            lines.append("")
        return "\n".join(lines)

    def is_installed(self, plugin_id: str) -> bool:
        """检查插件是否已安装"""
        return plugin_id in self._installed

    def get_installed(self, plugin_id: str) -> Optional[InstalledPlugin]:
        """获取已安装插件信息"""
        return self._installed.get(plugin_id)

    def set_enabled(self, plugin_id: str, enabled: bool) -> str:
        """设置插件启用/禁用"""
        if plugin_id not in self._installed:
            return f"❌ 插件 '{plugin_id}' 未安装"
        self._installed[plugin_id].enabled = enabled
        self._save_installed()
        state = "启用" if enabled else "禁用"
        return f"✅ 插件 '{plugin_id}' 已{state}"

    def get_cache_dirs(self) -> List[str]:
        """获取所有已安装插件的缓存目录（供 loader.py 扫描）"""
        dirs = []
        for entry in self._installed.values():
            if entry.enabled and os.path.isdir(entry.install_location):
                dirs.append(entry.install_location)
        return dirs

    def reconcile(self, marketplace_manager) -> Dict[str, List[str]]:
        """
        对账: 比较 marketplace 声明 vs 实际安装

        Returns:
            {"missing": [...], "extra": [...], "up_to_date": [...]}
        """
        result = {"missing": [], "extra": [], "up_to_date": []}

        # 所有 marketplace 的插件
        declared = {}  # plugin_id -> (marketplace, entry)
        for mp_name, plugins in marketplace_manager.get_all_plugins().items():
            for p in plugins:
                pid = f"{p.name}@{mp_name}"
                declared[pid] = (mp_name, p)

        # 检查 missing (声明但未安装)
        for pid in declared:
            if pid not in self._installed:
                result["missing"].append(pid)

        # 检查 extra (安装但不在任何 marketplace 中)
        for pid in self._installed:
            if pid not in declared:
                result["extra"].append(pid)

        # 检查 up_to_date
        for pid in self._installed:
            if pid in declared:
                result["up_to_date"].append(pid)

        return result
