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
意图路由前置门（Intent Gate）—— 用户消息进入 Agent Loop 前的自动技能路由

定位：把「技能获取」从模型自觉（模型看到工具列表后自己决定调 skill_acquire）
升级为**机制**：每条用户消息先过本地路由，本地 miss 且带领域能力信号时，
自动走 skill_acquire（本地强匹配短路 → 商店搜索 → 下载量+匹配度混合排序
→ 安装最高分 → 热重载），完成后把获得的技能提示注入本轮对话。

设计约束（对主循环最小侵入）：
- 独立模块，orchestrator.run() 仅插一行 try/except 调用；
- 任何异常全部吞掉（log 后返回 None），绝不阻断主循环；
- 可通过 config「skill_routing」开关整体关闭（默认开）；
- 防抖：同一意图短期内不重复路由/下载；纯研发短消息不触发联网。

流程：
1. 消息预检：太短/命令样/无领域能力信号 → 直接返回（不联网）
2. 本地路由（IntentRouter 强匹配）→ 命中 → 自动激活技能 → 返回注入提示
3. 本地 miss + 领域能力信号（ppt/excel/表格/文档/图片…）→ skill_acquire
   （dry_run=False 自动安装）→ 返回注入提示
"""

import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# 路由开关（config.skill_routing.enable，默认 True）
DEFAULT_ENABLED = True

# 触发商店获取的「领域能力信号」：这些词暗示任务超出纯研发技能覆盖面
# （office/design 生态词 + 高频交付物词）。纯研发消息不触发联网下载。
_DOMAIN_SIGNALS = [
    # office 生态
    "ppt", "pptx", "slides", "幻灯片", "演示文稿", "幻灯",
    "excel", "xlsx", "表格", "电子表格", "报表",
    "word", "docx", "文档", "报告", "简历", "标书",
    "pdf",
    # design 生态
    "画", "图像", "图片", "海报", "logo", "插画", "视频", "配音", "音频",
    # 通用交付物
    "思维导图", "流程图", "图表",
]

# 不触发路由的消息样式（斜杠命令、纯代码、太短寒暄）
_SKIP_PATTERNS = [
    r"^/\w+",           # 斜杠命令 /verify
    r"^(y|n|yes|no|ok|好的|嗯|继续|不用了)$",  # 确认类短答
]

# 防抖：意图关键词指纹 → 上次处理时间；窗口内不重复路由
_DEBOUNCE_SECONDS = 300  # 5 分钟
_last_routed: dict = {}  # fingerprint -> timestamp


def _fingerprint(user_input: str) -> str:
    """意图指纹：小写去空白，取前 80 字符（够区分不同任务）。"""
    return re.sub(r"\s+", "", (user_input or "").lower())[:80]


def _should_skip(user_input: str) -> bool:
    """消息预检：命令样/确认类短答/过短 → 跳过路由。"""
    text = (user_input or "").strip()
    if len(text) < 6:
        return True
    for pat in _SKIP_PATTERNS:
        if re.match(pat, text.lower()):
            return True
    return False


def _has_domain_signal(user_input: str) -> bool:
    """是否含领域能力信号（office/design/交付物词）——决定是否联网获取技能。"""
    text = (user_input or "").lower()
    return any(sig in text for sig in _DOMAIN_SIGNALS)


def _debounced(fingerprint: str) -> bool:
    """True = 窗口内已处理过，跳过。"""
    now = time.time()
    ts = _last_routed.get(fingerprint)
    if ts is not None and now - ts < _DEBOUNCE_SECONDS:
        return True
    return False


def _mark_routed(fingerprint: str) -> None:
    _last_routed[fingerprint] = time.time()
    # 防字典无限增长：超 200 条清掉最旧的一半
    if len(_last_routed) > 200:
        for k in sorted(_last_routed, key=_last_routed.get)[:100]:
            _last_routed.pop(k, None)


def route_intent(loop, user_input: str) -> Optional[str]:
    """
    意图路由前置门主入口。

    在 orchestrator.run() 的 init_messages 之前调用。返回值：
    - None：无需注入（预检跳过/防抖/无信号/路由失败），主循环照常
    - str：注入到本轮对话的技能提示（前缀说明 + 技能引导）

    任何异常吞掉返回 None，绝不阻断主循环。
    """
    try:
        text = (user_input or "").strip()
        if not text or _should_skip(text):
            return None

        # 配置开关
        cfg = getattr(loop, "config", {}) or {}
        routing_cfg = cfg.get("skill_routing", {}) if isinstance(cfg, dict) else {}
        if not routing_cfg.get("enable", DEFAULT_ENABLED):
            return None

        # 技能系统可用性
        sm = getattr(loop, "skill_manager", None)
        if sm is None or not getattr(loop, "skills_enabled", False):
            return None
        router = getattr(sm, "router", None)
        if router is None:
            return None

        # 防抖
        fp = _fingerprint(text)
        if _debounced(fp):
            return None

        # ① 本地强匹配 → 自动激活
        local_hit = _strong_local_match(router, text)
        if local_hit is not None:
            name, meta = local_hit
            _mark_routed(fp)
            return _inject_for_local(loop, name, meta)

        # ② 本地 miss + 领域能力信号 → skill_acquire（联网）
        if _has_domain_signal(text):
            _mark_routed(fp)  # 先标记防抖（即使失败也不反复联网）
            return _acquire_from_store(text)

        return None

    except Exception as e:  # 任何失败都不阻断主循环
        logger.warning(f"意图路由前置门异常（已忽略）: {e}")
        return None


def _strong_local_match(router, text: str):
    """
    本地强匹配：复用 skill_acquire 的判定标准——
    意图须包含技能「名称」或「keywords」子串（描述弱命中不算）。
    返回 (name, meta) 或 None。
    """
    try:
        il = text.lower()
        for m in router.route(text, top_k=3):
            name_l = (m.get("name") or "").lower()
            strong = False
            for kw in [name_l] + [k.lower() for k in (m.get("keywords") or [])]:
                if kw and kw in il:
                    strong = True
                    break
            if strong:
                return m["name"], m
    except Exception as e:
        logger.debug(f"本地强匹配失败: {e}")
    return None


def _inject_for_local(loop, name: str, meta: dict) -> str:
    """本地命中：激活技能并返回注入提示。"""
    try:
        sm = loop.skill_manager
        sm.activate_skill(name)
        eco = {"dev": "研发", "office": "办公", "design": "设计"}.get(
            meta.get("ecosystem", "dev"), meta.get("ecosystem", ""))
        hint = (
            f"[技能路由] 检测到任务与技能 **{name}**（{eco}/{meta.get('category','')}）"
            f"强匹配，已自动激活。请按该技能的专业规范执行任务。"
        )
        logger.info(f"[IntentGate] 本地强匹配: {name}")
        return hint
    except Exception as e:
        logger.warning(f"激活技能 {name} 失败: {e}")
        return None


def _acquire_from_store(text: str) -> Optional[str]:
    """本地 miss：走 skill_acquire 编排（搜索→排序→安装→热重载）。"""
    try:
        from tools.builtin.skillhub_tool import skill_acquire_handler
        result = skill_acquire_handler(intent=text, auto_install=True, dry_run=False)
        if not result or "❌" in result:
            logger.info(f"[IntentGate] 商店获取未成功: {(result or '')[:80]}")
            return None
        logger.info("[IntentGate] 已通过商店获取技能")
        # 注入提示：告诉模型技能已就位，结果里已含技能名与 invoke 指引
        return f"[技能路由] 本地无匹配，已自动从 SkillHub 获取技能：\n{result}"
    except Exception as e:
        logger.warning(f"商店获取失败: {e}")
        return None
