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

编排机制（skill_acquire）：
- 一步完成 本地路由 → 商店搜索 → 排序选择 → 安装 → 热重载。
- 排序 = 相关度(0.55) + 下载量对数归一(0.45)：下载量来自 `skill rankings`
  六榜（hot/featured/newest/recommended/trending/paid），带 TTL 缓存；
  榜单获取失败时退化为纯相关度排序（优雅降级）。
"""

import json
import logging
import math
import os
import subprocess
import sys
import time

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


# ── 下载量榜单（带 TTL 缓存，用于技能选择排序）─────────────────

_RANKINGS_CACHE = {"data": None, "fetched_at": 0.0}
_RANKINGS_TTL = 3600.0  # 1 小时


def _fetch_rankings(force: bool = False) -> dict:
    """
    获取 SkillHub 六榜（hot/featured/newest/recommended/trending/paid），
    返回 {canonical_slug: downloads} 映射。带 1h TTL 缓存。

    失败返回空 dict（调用方退化为纯相关度排序，不阻断）。
    """
    now = time.time()
    if (not force and _RANKINGS_CACHE["data"] is not None
            and now - _RANKINGS_CACHE["fetched_at"] < _RANKINGS_TTL):
        return _RANKINGS_CACHE["data"]

    code, out, err = _run_skillhub("skill", "rankings", timeout=30)
    mapping: dict = {}
    if code == 0:
        try:
            idx = out.find("{")
            data = json.loads(out[idx:]) if idx >= 0 else {}
            for block in (data.get("rankings") or {}).values():
                for s in block.get("skills", []) or []:
                    # rankings 条目：namespace.canonicalName 形如 "@ake/dev-god"；
                    # 退化路径 handle + slug（注意 rankings 用 slug，搜索用 publicSlug）
                    ns = s.get("namespace") or {}
                    canonical = ns.get("canonicalName") or ""
                    if not canonical:
                        handle = ns.get("handle", "")
                        slug = s.get("slug") or s.get("publicSlug") or ""
                        canonical = f"@{handle}/{slug}" if handle and slug else ""
                    if not canonical:
                        continue
                    try:
                        dl = int(s.get("downloads", 0) or 0)
                    except (TypeError, ValueError):
                        dl = 0
                    # 同一技能可能进多个榜，取最大值
                    if dl > mapping.get(canonical, -1):
                        mapping[canonical] = dl
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"rankings 解析失败（退化为纯相关度排序）: {e}")
    else:
        logger.warning(f"rankings 获取失败（退化为纯相关度排序）: {err[:100]}")

    _RANKINGS_CACHE["data"] = mapping
    _RANKINGS_CACHE["fetched_at"] = now
    return mapping


def _rank_candidates(results: list, intent: str) -> list:
    """
    对搜索结果做「相关度 × 下载量」混合排序。

    score = 0.55 × rel + 0.45 × log10(1+downloads)/log10(1+max_dl)
    - rel: 名称/描述/关键词与意图的粗相关度（0~1）
    - 下载量取对数归一（避免 800 万下载的弱相关技能碾压精准小众技能）
    榜单缺数据时 rel=1.0 兜底（纯下载量排序）。
    """
    if not results:
        return []
    downloads = _fetch_rankings()
    il = intent.lower()

    # 用全量榜单最大下载量归一（而非候选集内最大），保证跨意图可比；
    # 榜单为空时 norm=1.0，dl_score=0，退化为纯相关度。
    max_dl = max(downloads.values(), default=0)
    norm = math.log10(1 + max_dl) if max_dl > 0 else 1.0

    ranked = []
    for r in results:
        # ── 相关度（粗粒度，0~1；名称/slug 命中 > 子词命中 > 描述命中）──
        name = (r.get("name") or r.get("publicSlug") or "").lower()
        desc = (r.get("description") or "").lower()
        slug = (r.get("publicSlug") or "").lower()
        import re as _re
        segs = [s for s in _re.split(r"[^一-鿿a-z0-9]+", il) if len(s) > 1]
        if segs:
            # 命中 name/slug 记 1.0，中文子词(bigram)命中 name 记 0.8，
            # 命中 desc 记 0.5、子词命中 desc 记 0.4，产生区分度
            weights = []
            for s in segs:
                bigrams = [s[i:i+2] for i in range(len(s) - 1)] \
                    if _re.fullmatch(r"[一-鿿]+", s) and len(s) > 2 else []
                if s in name or s in slug:
                    weights.append(1.0)
                elif any(b in name or b in slug for b in bigrams):
                    weights.append(0.8)
                elif s in desc:
                    weights.append(0.5)
                elif any(b in desc for b in bigrams):
                    weights.append(0.4)
            rel = (sum(weights) / len(segs)) if weights else 0.0
        else:
            rel = 0.0
        # 相关度太低的直接淘汰（避免下载量大但完全跑题的技能入选）
        if rel < 0.15:
            continue

        dl = downloads.get(_canonical_of(r), 0)
        dl_score = math.log10(1 + dl) / norm if norm > 0 else 0.0
        final = round(0.55 * rel + 0.45 * dl_score, 4)
        ranked.append((final, rel, dl, r))

    ranked.sort(key=lambda t: t[0], reverse=True)
    return ranked


def _canonical_of(result: dict) -> str:
    """搜索结果 → rankings 的 canonical slug（@handle/slug）。"""
    ns = (result.get("namespace") or {}).get("handle", "")
    slug = result.get("publicSlug") or ""
    return f"@{ns}/{slug}" if ns and slug else ""


def _search_query_from_intent(intent: str) -> str:
    """
    从意图文本提取商店搜索词。整句直接当查询会跑题（返回通用榜单），
    策略：英文/数字词（如 excel/ppt/pdf）> 最长中文字段。
    """
    import re as _re
    segs = [s for s in _re.split(r"[^一-鿿a-z0-9]+", (intent or "").lower()) if s]
    if not segs:
        return (intent or "").strip()
    # 英文/数字词优先（excel、ppt、pdf、3d……信息量最高）
    latin = [s for s in segs if _re.fullmatch(r"[a-z0-9][a-z0-9\-\+\.]*", s)]
    if latin:
        return max(latin, key=len)
    # 纯中文：取最长字段（「数据分析」优于「做」「一份」）
    return max(segs, key=len)


# ── skill_acquire：编排机制（本地路由 → 搜索 → 排序 → 安装 → 热重载）──


def skill_acquire_handler(intent: str, auto_install: bool = True,
                          limit: int = 10, dry_run: bool = False) -> str:
    """
    编排机制：确保「能处理该意图的技能」可用，一步到位。

    流程：
    1. 本地路由（IntentRouter）：命中 → 直接返回技能名（本地候选也参与后续排序）
    2. 本地无匹配 → skillhub 搜索
    3. 混合排序（相关度 0.55 + 下载量对数 0.45），取最高分
    4. auto_install=True 时安装最高分技能并热重载
    5. 返回可直接 invoke_skill 的技能名

    Args:
        intent: 用户意图/任务描述（中英文）
        auto_install: 自动安装最高分技能（默认 True）
        limit: 搜索候选上限
        dry_run: 只看排序不安装
    """
    from skills.context import SkillContext

    sm = SkillContext._skill_manager
    router = getattr(sm, "router", None) if sm else None

    local_lines: list = []
    installed_names: set = set()
    if sm is not None:
        for m in getattr(sm, "registry", None)._skills_with_meta() if sm.registry else []:
            installed_names.add(m["name"])
            installed_names.add(m["key"])

    # ① 本地路由：命中即无需下载（强匹配：关键词/名称命中才算，避免描述弱相关误报）
    local_best = None
    if router is not None:
        from skills.registry import _tokenize
        il = (intent or "").lower()
        for m in router.route(intent, top_k=3):
            strong = False
            name_l = (m.get("name") or "").lower()
            for kw in [name_l] + [k.lower() for k in (m.get("keywords") or [])]:
                if kw and kw in il:
                    strong = True
                    break
            if strong:
                local_best = m
                break
    if local_best:
        local_lines.append(
            f"✅ 本地已有匹配技能: **{local_best['name']}** "
            f"({local_best['ecosystem']}/{local_best['category']})，无需下载。\n"
            f"直接 invoke_skill(skill_name=\"{local_best['name']}\") 使用。"
        )

    # ② 商店搜索（无论本地是否命中，都给出可对比的商店候选）
    q = _search_query_from_intent(intent)
    if not q:
        return "❌ 请提供意图描述"

    code, out, err = _run_skillhub("search", q, "--json", timeout=30)
    results: list = []
    if code == 0:
        try:
            idx = out.find("{")
            data = json.loads(out[idx:]) if idx >= 0 else {}
            results = data.get("results", [])[: max(1, min(limit, 20))]
        except json.JSONDecodeError:
            pass

    header = [f"意图 {intent!r} 的技能获取编排:", ""]
    if local_lines:
        header += local_lines + [""]

    if not results:
        if local_best:
            return "\n".join(header) + "\n(商店无额外候选，本地技能已够用)"
        return "\n".join(header) + "商店搜索无结果，建议换个关键词。"

    # ③ 混合排序（相关度按完整意图计算，而非提取后的搜索词）
    ranked = _rank_candidates(results, (intent or "").lower() or q)
    if not ranked and local_best:
        return "\n".join(header) + "\n(商店候选与意图相关度均过低，本地技能已够用)"
    if not ranked:
        return "\n".join(header) + "\n商店候选与意图相关度均过低（<0.15），未选取。"

    header.append("商店候选（相关度 0.55 + 下载量 0.45 混合排序）:")
    for i, (final, rel, dl, r) in enumerate(ranked[:5], 1):
        ns = (r.get("namespace") or {}).get("handle", "")
        name = r.get("name") or r.get("publicSlug")
        slug = r.get("publicSlug", "")
        tag = " [已安装]" if (slug in installed_names or name in installed_names) else ""
        header.append(
            f"  {i}. **{name}** @{ns}{tag} — 综合 {final} | 相关度 {rel:.2f} | 下载 {dl:,}"
        )
    header.append("")

    if dry_run:
        header.append("（dry_run=True，未安装。需安装用 skillhub_install。）")
        return "\n".join(header)

    top_final, top_rel, top_dl, top = ranked[0]
    if not (auto_install and ranked):
        header.append("（auto_install=False，未安装。用 skillhub_install 安装任意候选。）")
        return "\n".join(header)

    top_slug = top.get("publicSlug", "")
    top_ns = (top.get("namespace") or {}).get("handle", "")
    top_name = top.get("name") or top_slug

    # 已安装则直接返回（幂等，不重复装）
    if top_slug in installed_names or top_name in installed_names:
        header.append(f"✅ 最高分候选 **{top_name}** 已安装，直接 invoke_skill 使用。")
        return "\n".join(header)

    # ④ 安装最高分
    install_out = skillhub_install_handler(slug=top_slug, namespace=top_ns)
    header.append(f"安装最高分候选: {top_name}（综合 {top_final}，下载 {top_dl:,}）")
    header.append(install_out)
    return "\n".join(header)


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

register_tool("skill_acquire", {
    "description": """编排机制：一步确保「能处理该意图的技能」可用（本地路由→商店搜索→排序→安装→热重载）。

优先级:
1. 本地技能已匹配 → 直接返回技能名，不下载
2. 本地无匹配 → 搜索 SkillHub，按「相关度0.55 + 下载量0.45」混合排序，
   自动安装最高分技能并热重载（下载量来自官方六榜，1h 缓存）

使用时机:
- 遇到非研发任务（PPT/Excel/文档/图像等）且不确定有无技能时
- 想让系统自动选「最匹配或下载量最高」的技能时

示例:
- skill_acquire(intent="生成一份项目汇报PPT")
- skill_acquire(intent="excel 数据分析", dry_run=true)  # 只看排序不安装""",
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "用户意图或任务描述（中英文均可）"
            },
            "auto_install": {
                "type": "boolean",
                "description": "自动安装最高分技能（默认 true）",
                "default": True
            },
            "limit": {
                "type": "integer",
                "description": "搜索候选上限（默认 10）",
                "default": 10
            },
            "dry_run": {
                "type": "boolean",
                "description": "只返回排序结果，不安装（默认 false）",
                "default": False
            }
        },
        "required": ["intent"]
    },
    "handler": skill_acquire_handler,
    "permission_level": "write"
})
