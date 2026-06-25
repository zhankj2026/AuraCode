"""
Plugin Zip Cache — 对标 Claude Code zipCache.ts

功能:
- 将插件目录打包为 .zip 归档存储
- 从 .zip 解压到临时会话目录
- 环境变量控制: AURACODE_PLUGIN_USE_ZIP_CACHE, AURACODE_PLUGIN_CACHE_DIR
- 适用于离线/容器场景（ephemeral container + mounted volume）

目录结构:
  $AURACODE_PLUGIN_CACHE_DIR/
    installed_plugins.json
    marketplaces/
      {marketplace-name}.json
    plugins/
      {marketplace}/
        {plugin}/
          {version}.zip
"""

import io
import logging
import os
import shutil
import tempfile
import zipfile
from typing import Optional

logger = logging.getLogger(__name__)


def is_zip_cache_enabled() -> bool:
    """检查 zip 缓存是否启用"""
    val = os.environ.get("AURACODE_PLUGIN_USE_ZIP_CACHE", "")
    return val.lower() in ("1", "true", "yes", "on")


def get_zip_cache_path() -> Optional[str]:
    """获取 zip 缓存根目录"""
    if not is_zip_cache_enabled():
        return None
    cache_dir = os.environ.get("AURACODE_PLUGIN_CACHE_DIR", "")
    if not cache_dir:
        # 默认 ~/.auracode/zip-cache
        cache_dir = os.path.join(os.path.expanduser("~"), ".auracode", "zip-cache")
    return os.path.expanduser(cache_dir)


def get_zip_plugins_dir() -> Optional[str]:
    """获取 zip 插件存储目录"""
    base = get_zip_cache_path()
    return os.path.join(base, "plugins") if base else None


def get_zip_marketplaces_dir() -> Optional[str]:
    """获取 zip marketplace 缓存目录"""
    base = get_zip_cache_path()
    return os.path.join(base, "marketplaces") if base else None


def ensure_zip_cache_dirs() -> bool:
    """确保 zip 缓存目录结构存在"""
    plugins_dir = get_zip_plugins_dir()
    mp_dir = get_zip_marketplaces_dir()
    if not plugins_dir or not mp_dir:
        return False
    try:
        os.makedirs(plugins_dir, exist_ok=True)
        os.makedirs(mp_dir, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create zip cache dirs: {e}")
        return False


# ── 打包/解压 ─────────────────────────────────────────────────


def create_zip_from_directory(dir_path: str) -> bytes:
    """
    将目录打包为 zip bytes

    Args:
        dir_path: 目录路径

    Returns:
        zip 文件的 bytes 数据
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dir_path):
            # 跳过 .git 和 __pycache__
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv')]
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, dir_path)
                zf.write(fpath, arcname)
    return buf.getvalue()


def extract_zip_to_directory(zip_data: bytes, target_dir: str) -> int:
    """
    解压 zip bytes 到目标目录

    Args:
        zip_data: zip bytes
        target_dir: 目标目录

    Returns:
        解压的文件数
    """
    os.makedirs(target_dir, exist_ok=True)
    buf = io.BytesIO(zip_data)
    count = 0
    with zipfile.ZipFile(buf, "r") as zf:
        zf.extractall(target_dir)
        count = len(zf.namelist())
    return count


def zip_plugin_directory(plugin_dir: str, marketplace: str,
                         plugin_name: str, version: str) -> Optional[str]:
    """
    将插件目录打包为 zip 并存储到缓存

    Args:
        plugin_dir: 插件源目录
        marketplace: marketplace 名称
        plugin_name: 插件名称
        version: 版本号

    Returns:
        zip 文件路径，失败返回 None
    """
    plugins_dir = get_zip_plugins_dir()
    if not plugins_dir:
        return None

    # 目标: {cache}/plugins/{marketplace}/{plugin}/{version}.zip
    zip_dir = os.path.join(plugins_dir, marketplace, plugin_name)
    os.makedirs(zip_dir, exist_ok=True)
    zip_path = os.path.join(zip_dir, f"{version}.zip")

    try:
        zip_data = create_zip_from_directory(plugin_dir)
        with open(zip_path, "wb") as f:
            f.write(zip_data)
        logger.info(f"Plugin zipped: {plugin_name}@{marketplace} v{version} -> {zip_path}")
        return zip_path
    except Exception as e:
        logger.error(f"Failed to zip plugin: {e}")
        return None


def unzip_plugin_to_session(marketplace: str, plugin_name: str,
                            version: str) -> Optional[str]:
    """
    从 zip 缓存解压插件到临时会话目录

    Args:
        marketplace: marketplace 名称
        plugin_name: 插件名称
        version: 版本号

    Returns:
        解压后的临时目录路径，失败返回 None
    """
    plugins_dir = get_zip_plugins_dir()
    if not plugins_dir:
        return None

    zip_path = os.path.join(plugins_dir, marketplace, plugin_name, f"{version}.zip")
    if not os.path.exists(zip_path):
        return None

    # 解压到 tempdir
    target_dir = os.path.join(tempfile.gettempdir(),
                              "auracode_plugins",
                              marketplace, plugin_name, version)

    if os.path.exists(target_dir):
        return target_dir  # 已解压过

    try:
        with open(zip_path, "rb") as f:
            zip_data = f.read()
        count = extract_zip_to_directory(zip_data, target_dir)
        logger.info(f"Plugin unzipped: {plugin_name}@{marketplace} v{version} "
                    f"({count} files) -> {target_dir}")
        return target_dir
    except Exception as e:
        logger.error(f"Failed to unzip plugin: {e}")
        return None


def cleanup_session_plugins():
    """清理会话临时插件目录"""
    session_dir = os.path.join(tempfile.gettempdir(), "auracode_plugins")
    if os.path.exists(session_dir):
        try:
            shutil.rmtree(session_dir)
            logger.debug(f"Cleaned up session plugins: {session_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup session plugins: {e}")


def sync_installed_to_zip_cache(installer):
    """
    将 installed_plugins.json 中的插件同步到 zip 缓存

    在 headless/容器模式下，安装新插件后调用此方法将插件
    打包到持久化 zip 缓存，供后续 ephemeral session 使用。
    """
    if not is_zip_cache_enabled():
        return

    ensure_zip_cache_dirs()

    for entry in installer.list_installed():
        if not os.path.isdir(entry.install_location):
            continue

        # 检查 zip 是否已存在
        plugins_dir = get_zip_plugins_dir()
        if not plugins_dir:
            continue
        zip_path = os.path.join(plugins_dir, entry.marketplace,
                                entry.name, f"{entry.version}.zip")
        if os.path.exists(zip_path):
            continue  # 已有缓存

        zip_plugin_directory(
            entry.install_location,
            entry.marketplace,
            entry.name,
            entry.version,
        )


def list_zip_cache() -> str:
    """列出 zip 缓存内容（格式化字符串）"""
    plugins_dir = get_zip_plugins_dir()
    if not plugins_dir or not os.path.exists(plugins_dir):
        return "Zip 缓存为空或目录不存在"

    lines = ["Zip 缓存内容:\n"]
    total_size = 0
    count = 0

    for marketplace in sorted(os.listdir(plugins_dir)):
        mp_dir = os.path.join(plugins_dir, marketplace)
        if not os.path.isdir(mp_dir):
            continue

        for plugin_name in sorted(os.listdir(mp_dir)):
            plugin_dir = os.path.join(mp_dir, plugin_name)
            if not os.path.isdir(plugin_dir):
                continue

            for version_zip in sorted(os.listdir(plugin_dir)):
                if not version_zip.endswith(".zip"):
                    continue
                zip_path = os.path.join(plugin_dir, version_zip)
                size = os.path.getsize(zip_path)
                total_size += size
                count += 1
                size_str = _format_size(size)
                lines.append(
                    f"  {plugin_name}@{marketplace} v{version_zip[:-4]} ({size_str})"
                )

    lines.append(f"\n总计: {count} 个 zip, {_format_size(total_size)}")
    return "\n".join(lines) if count > 0 else "Zip 缓存为空"


def _format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
