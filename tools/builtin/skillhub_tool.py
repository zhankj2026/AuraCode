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
SkillHub 工具 - 让 Agent 在执行过程中按需搜索/安装技能

用户方针：新技能不预装，除非必要；执行过程中可通过 SkillHub 搜索下载。
本工具把 bridge/server.py 已验证的 skillhub CLI 封装（_run_skillhub）复用为
Agent 可调用的工具，让「技能不足 → 搜索 → 安装 → 立即可用」闭环在会话内完成。

设计约束（对现有代码最小影响）：
- 纯新增文件，只依赖 tools.registry 的注册机制，不改 skill_tools.py / loader.py。
- 安装后调用 SkillManager.reload_skills() 使新技能立即可路由/调用。
- CLI 缺失时优雅降级（返回安装指引），不抛异常阻断 Agent 循环。
"""

import json
import logging
import os
import subprocess
import sys

from tools.registry import register_tool

logger = logging.getLogger(__name__)


def _decode_pipe(data: bytes) -> str:
    """子进程管道输出解码：utf-8 → gbk → replace 兜底（与 bridge 同策略）。"""
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _run_skillhub(*args: str, timeout: float = 60.0):
    """执行 skillhub CLI，返回 (returncode, stdout, stderr)。候选与 bridge 一致。"""
    home = os.path.expanduser("~")
    if os.name == "nt":
        candidates = [
            os.path.join(home, ".skillhub", "skills_store_cli.py"),
            os.path.join(home, ".local", "bin", "skillhub.exe"),
            os.path.join(home, ".local", "bin", "skillhub"),
        ]
    else:
        candidates = [
            os.path.join(home, ".local", "bin", "skillhub"),
            os.path.join(home, ".skillhub", "skills_store_cli.py"),
        ]

    env = dict(os.environ)
    # 剥离代理变量，避免经代理访问 skillhub.cn 失败（沙箱/公司环境常见坑）
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
              "all_proxy", "ALL_PROXY"):
        env.pop(k, None)
    # 强制子进程 UTF-8 输出（Windows GBK 控制台坑）
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    for target in candidates:
        if not os.path.exists(target):
            continue
        cmd = [sys.executable, target, *args] if target.endswith(".py") \
            else [target, *args]
        try:
            r = subprocess.run(cmd, capture_output=True,
                               timeout=timeout, env=env)
            return r.returncode, _decode_pipe(r.stdout), _decode_pipe(r.stderr)
        except Exception as e:
            logger.warning(f"skillhub 调用失败 ({target}): {e}")
            continue
    return 1, "", "skillhub CLI 未安装（参考 https://skillhub.cn/install/skillhub.md）"


def _skillhub_user_skills_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".auracode", "skills")


def _reload_skills() -> int:
    """安装后热重载，让新技能立即可路由/调用。"""
    try:
        from skills.context import SkillContext
        sm = SkillContext._skill_manager
        if sm is not None:
            return sm.reload_skills()
    except Exception as e:
        logger.warning(f"reload_skills 失败（不影响安装结果）: {e}")
    return -1


def skillhub_search_handler(query: str, limit: int = 8) -> str:
    """
    搜索 SkillHub 技能商店（联网）。

    Args:
        query: 搜索关键词（支持中英文，如 "ppt" / "文档" / "爬虫"）
        limit: 返回条数上限
    """
    q = (query or "").strip()
    if not q:
        return "❌ 请提供搜索关键词"
    code, out, err = _run_skillhub("search", q, "--json", timeout=30)
    if code != 0:
        return f"❌ 搜索失败: {err or out}"
    try:
        idx = out.find("{")
        data = json.loads(out[idx:]) if idx >= 0 else {}
    except json.JSONDecodeError:
        return f"❌ 返回无法解析: {out[:200]}"

    results = data.get("results", [])[: max(1, min(limit, 20))]
    if not results:
        return f"未找到与 {q!r} 相关的技能。可换个关键词，或用 skillhub_install 安装已知 slug。"

    installed_dirs = set()
    skills_root = _skillhub_user_skills_dir()
    if os.path.isdir(skills_root):
        for ns in os.listdir(skills_root):
            ns_path = os.path.join(skills_root, ns)
            if os.path.isdir(ns_path):
                for s in os.listdir(ns_path):
                    installed_dirs.add(s)

    lines = [f"SkillHub 搜索 {q!r}（共 {len(results)} 条）:", ""]
    for i, item in enumerate(results, 1):
        slug = item.get("publicSlug", "")
        ns = (item.get("namespace") or {}).get("handle", "")
        name = item.get("name") or slug
        desc = (item.get("description") or "").strip()[:120]
        installed = " [已安装]" if slug in installed_dirs else ""
        ns_part = f" @{ns}" if ns else ""
        lines.append(f"{i}. **{name}**{ns_part}{installed}")
        lines.append(f"   slug: `{slug}`")
        if desc:
            lines.append(f"   {desc}")
    lines.append("")
    lines.append("安装: skillhub_install(slug=..., namespace=...) 或 invoke_skill 前先安装。")
    return "\n".join(lines)


def skillhub_install_handler(slug: str, namespace: str = "") -> str:
    """
    安装 SkillHub 技能到用户级 ~/.auracode/skills/（安装后自动热重载）。

    Args:
        slug: 技能 slug（来自 skillhub_search 结果）
        namespace: 可选命名空间（搜索结果里的 @handle）
    """
    slug = (slug or "").strip()
    if not slug:
        return "❌ 请提供技能 slug"
    target_dir = _skillhub_user_skills_dir()

    # 幂等：已安装则直接热重载并返回成功（CLI 会报 Target exists 错误）
    ns_dir = os.path.join(target_dir, f"@{namespace}") if namespace else None
    search_dir = ns_dir if ns_dir and os.path.isdir(ns_dir) else target_dir
    already = os.path.isdir(os.path.join(search_dir, slug))
    if not already and os.path.isdir(search_dir):
        # 目录名与 slug 可能略有出入（如带版本后缀），前缀兜底再查一次
        try:
            already = any(e == slug or e.startswith(slug)
                          for e in os.listdir(search_dir)
                          if os.path.isdir(os.path.join(search_dir, e)))
        except OSError:
            pass
    if already:
        count = _reload_skills()
        reload_note = f"已热重载，当前共 {count} 个技能可用" if count >= 0 else "热重载跳过（技能系统未初始化）"
        return (
            f"✅ 技能 {slug} 此前已安装，无需重复安装。\n"
            f"{reload_note}\n"
            f"下一步: 用 invoke_skill(skill_name=\"{slug}\") 直接使用。"
        )

    args = ["install", slug, "--dir", target_dir, "--json"]
    if namespace:
        args += ["--namespace", namespace]

    code, out, err = _run_skillhub(*args, timeout=180)
    if code != 0:
        return f"❌ 安装失败: {err or out}"
    try:
        idx = out.find("{")
        data = json.loads(out[idx:]) if idx >= 0 else {}
    except json.JSONDecodeError:
        data = {"success": True, "raw": out[:300]}
    if not data.get("success", False):
        return f"❌ 安装失败: {out[:300]}"

    # 热重载：让新技能立即可路由/调用
    count = _reload_skills()
    reload_note = f"已热重载，当前共 {count} 个技能可用" if count >= 0 else "热重载跳过（技能系统未初始化）"

    # 找实际安装的技能名（@ns/slug 两层）
    installed_name = slug
    ns_dir = os.path.join(target_dir, f"@{namespace}") if namespace else None
    search_dir = ns_dir if ns_dir and os.path.isdir(ns_dir) else target_dir
    try:
        for entry in os.listdir(search_dir):
            if os.path.isdir(os.path.join(search_dir, entry)):
                if entry == slug or entry.startswith(slug):
                    installed_name = entry
                    break
    except OSError:
        pass

    return (
        f"✅ 技能 {slug} 安装成功（目录名: {installed_name}）\n"
        f"{reload_note}\n"
        f"下一步: 用 invoke_skill(skill_name=\"{installed_name}\") 立即使用，"
        f"或 activate_skill 持久激活。"
    )


# ── 注册工具 ──────────────────────────────────────────────

register_tool("skillhub_search", {
    "description": """搜索 SkillHub 技能商店（联网）。当本地技能不足以完成当前任务时使用。

使用时机:
- 任务需要的技能本地不存在（如生成 PPT/Excel/文档/图像等非研发任务）
- 用户要求某个新能力但 list_skills 中没有

流程: skillhub_search 找到候选 → skillhub_install 安装 → invoke_skill 使用。
示例: skillhub_search(query="ppt")""",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词（中英文均可，如 'ppt' / '文档' / 'web scraping'）"
            },
            "limit": {
                "type": "integer",
                "description": "返回条数上限（默认 8）",
                "default": 8
            }
        },
        "required": ["query"]
    },
    "handler": skillhub_search_handler,
    "permission_level": "read"
})

register_tool("skillhub_install", {
    "description": """安装 SkillHub 技能到用户级 ~/.auracode/skills/，安装后自动热重载。

前置: 通常先用 skillhub_search 找到 slug。
安装后: 用 invoke_skill(skill_name=...) 立即使用。
示例: skillhub_install(slug="some-skill", namespace="clawhub_xx")""",
    "parameters": {
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "技能 slug（来自 skillhub_search 结果）"
            },
            "namespace": {
                "type": "string",
                "description": "可选命名空间（搜索结果里的 @handle）",
                "default": ""
            }
        },
        "required": ["slug"]
    },
    "handler": skillhub_install_handler,
    "permission_level": "write"
})
