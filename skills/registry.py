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
技能路由层 —— 阶段0：把「技能路由」与「技能执行」解耦

设计目标（对照 WorkBuddy 参考架构的「两套机制」之一：渐进式技能披露/路由）：
- SkillRegistry：只读元数据索引层。在现有 SkillManager 之上提供
  按 生态(ecosystem) / 分类(category) / 关键词(keywords) / 依赖(dependencies)
  的索引，并预留「插件技能目录」挂载点（后续 office/design 生态以插件包形式注册）。
  Registry 不加载 prompt、不执行技能，因此对现有执行链路零侵入。
- IntentRouter：把自然语言意图映射为排序后的候选技能列表，由调用方
  （如 AgentLoop）决定是否 invoke_skill。路由策略为确定性打分，预留 LLM 打分钩子。

本模块刻意不 import loader，避免循环依赖；只在运行时持有 manager 引用并动态读取属性。
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# 生态定义（对应「三大生态」）
ECOSYSTEMS: Dict[str, str] = {
    "dev": "研发",
    "office": "办公",
    "design": "设计",
}

DEFAULT_ECOSYSTEM = "dev"


def _tokenize(text: str) -> List[str]:
    """
    极简分词：按非「中文/英文/数字」切分，保留中文词与英文单词；
    连续中文段额外产出二元组合（bigram），缓解无分词库时的子串匹配问题
    （如「做幻灯片」→ 幻灯 / 灯片 / 幻灯片 三种粒度都可命中）。

    不引入第三方分词库，足够支撑意图→关键词的粗匹配。
    """
    if not text:
        return []
    text = text.lower()
    # \u4e00-\u9fff 覆盖常用汉字；与 a-z0-9 一起作为保留字符
    parts = re.split(r"[^一-鿿a-z0-9]+", text)
    tokens: List[str] = []
    for p in parts:
        if not p:
            continue
        if re.fullmatch(r"[一-鿿]+", p):
            tokens.append(p)                # 整段（最长粒度）
            if len(p) >= 2:
                tokens.extend(p[i:i+2] for i in range(len(p) - 1))  # bigram
        else:
            tokens.append(p)
    # 去重保持顺序
    seen = set()
    out = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


class SkillRegistry:
    """
    技能元数据注册表（只读索引层）。

    与 SkillManager 解耦：只读取 manager.skills 的元数据，
    不加载 prompt、不执行技能。提供：
    - 按生态 / 分类 / 关键词索引
    - 插件式技能挂载点（后续 office/design 生态以插件包形式注册）
    - 依赖声明查询
    """

    def __init__(self, manager: Any):
        """
        Args:
            manager: SkillManager 实例（仅持有引用，不修改其状态）
        """
        self._manager = manager
        # 插件技能目录（阶段2/3 使用，此处仅预留挂载点）
        self.plugin_dirs: List[str] = []

    # ---- 读取现有技能元数据（只读，不改 manager） ----

    def all_skills(self) -> List[Dict[str, Any]]:
        """返回所有技能的轻量元数据列表。"""
        return self._manager.get_available_skills()

    def _skills_with_meta(self) -> List[Dict[str, Any]]:
        """
        返回 (key, skill) 补全了生态/分类/依赖/关键词等元数据后的列表。

        通过 getattr 读取新字段，并设置安全默认值，因此对旧 Skill 对象也兼容。
        """
        out: List[Dict[str, Any]] = []
        skills = getattr(self._manager, "skills", {}) or {}
        sources = getattr(self._manager, "_skill_sources", {}) or {}
        for key, skill in skills.items():
            meta = {
                "key": key,
                "name": getattr(skill, "name", key),
                "description": getattr(skill, "description", ""),
                "trigger": getattr(skill, "trigger", ""),
                "when_to_use": getattr(skill, "when_to_use", "") or "",
                "ecosystem": getattr(skill, "ecosystem", DEFAULT_ECOSYSTEM) or DEFAULT_ECOSYSTEM,
                "category": getattr(skill, "category", "general") or "general",
                "dependencies": getattr(skill, "dependencies", []) or [],
                "keywords": getattr(skill, "keywords", []) or [],
                "source": sources.get(key, "builtin"),
            }
            out.append(meta)
        return out

    def by_ecosystem(self, ecosystem: str) -> List[Dict[str, Any]]:
        """按生态筛选技能。"""
        return [m for m in self._skills_with_meta() if m["ecosystem"] == ecosystem]

    def by_category(self, category: str) -> List[Dict[str, Any]]:
        """按分类筛选技能。"""
        return [m for m in self._skills_with_meta() if m["category"] == category]

    def ecosystems(self) -> Dict[str, int]:
        """返回 生态 -> 技能数量。"""
        counts: Dict[str, int] = {}
        for m in self._skills_with_meta():
            eco = m["ecosystem"]
            counts[eco] = counts.get(eco, 0) + 1
        return counts

    def get_meta(self, name: str) -> Optional[Dict[str, Any]]:
        """按 技能名 或 字典键 取单个技能元数据。"""
        for m in self._skills_with_meta():
            if m["name"] == name or m["key"] == name:
                return m
        return None

    def dependents_of(self, skill_name: str) -> List[str]:
        """返回声明依赖了 skill_name 的技能名列表（用于链路分析，阶段4）。"""
        result: List[str] = []
        for m in self._skills_with_meta():
            if skill_name in (m.get("dependencies") or []):
                result.append(m["name"])
        return result

    # ---- 插件挂载点（阶段2/3 接入 office/design） ----

    def register_plugin_dir(self, path: str) -> None:
        """登记一个插件技能目录（后续阶段扫描用）。"""
        if path and path not in self.plugin_dirs:
            self.plugin_dirs.append(path)
            logger.info(f"登记插件技能目录: {path}")


class IntentRouter:
    """
    意图路由器：把自然语言意图映射到候选技能。

    解耦「选技能」与「执行技能」——只返回排序后的候选技能名列表，
    由调用方（AgentLoop）决定是否 invoke_skill。

    路由策略（确定性，可扩展 LLM 打分钩子）：
    1. 精确/包含名称匹配（最强信号）
    2. 关键词命中（意图分词 ∩ 技能 keywords）
    3. 分词命中 when_to_use / description / name
    4. 生态加权（非研发生态命中给加成，避免被研发技能淹没）
    """

    def __init__(self, registry: SkillRegistry, llm_scorer: Optional[Any] = None):
        """
        Args:
            registry: SkillRegistry 实例
            llm_scorer: 可选 LLM 打分钩子，签名 (intent, meta) -> float；
                        默认 None 表示走确定性打分。
        """
        self.registry = registry
        self.llm_scorer = llm_scorer

    def route(self, intent: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        返回按相关度降序排列的候选技能元数据列表（含 score 字段）。

        Args:
            intent: 用户/模型的意图文本
            top_k: 返回前 N 个候选
        """
        intent_lower = (intent or "").lower()
        tokens = _tokenize(intent_lower)
        if not tokens and not intent_lower:
            return []

        candidates: List[Dict[str, Any]] = []
        for m in self.registry._skills_with_meta():
            score = self._score(m, intent_lower, tokens)
            if score > 0:
                cand = dict(m)
                cand["score"] = round(score, 3)
                candidates.append(cand)

        # 若有 LLM 打分钩子，在其基础上叠加（确定性分作为保底）
        if self.llm_scorer is not None:
            for cand in candidates:
                try:
                    extra = float(self.llm_scorer(intent, cand)) or 0.0
                    cand["score"] = round(cand["score"] + extra, 3)
                except Exception as e:  # 钩子异常不应阻断路由
                    logger.warning(f"LLM 打分钩子异常，已忽略: {e}")

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates[:top_k]

    def _score(self, m: Dict[str, Any], intent_lower: str, tokens: List[str]) -> float:
        """确定性打分：名称 > 关键词 > 分词命中 > 生态加权。"""
        score = 0.0
        name = (m.get("name") or "").lower()
        desc = (m.get("description") or "").lower()
        wtu = (m.get("when_to_use") or "").lower()
        keywords = [k.lower() for k in (m.get("keywords") or [])]

        # 1. 精确/包含名称匹配（最强信号）
        if name and name in intent_lower:
            score += 10.0
        if name and intent_lower.strip() == name:
            score += 5.0

        # 2. 关键词命中
        for kw in keywords:
            if kw and kw in intent_lower:
                score += 6.0

        # 3. 分词命中描述 / when_to_use / name
        for tok in tokens:
            if tok in desc:
                score += 2.0
            if tok in wtu:
                score += 3.0
            if tok in name:
                score += 1.0

        # 4. 生态加权：未来 office/design 技能命中时给加成，避免被研发技能淹没
        eco = m.get("ecosystem", DEFAULT_ECOSYSTEM)
        if eco != DEFAULT_ECOSYSTEM:
            score += 1.0

        return score

    def best(self, intent: str) -> Optional[Dict[str, Any]]:
        """返回最匹配的技能（无匹配返回 None）。"""
        res = self.route(intent, top_k=1)
        return res[0] if res else None


def build_router(manager: Any, llm_scorer: Optional[Any] = None):
    """
    便捷工厂：基于一个 SkillManager 构建 (registry, router)。

    调用方（如 AgentLoop）可一次性拿到两个对象，无需关心内部装配。
    """
    registry = SkillRegistry(manager)
    router = IntentRouter(registry, llm_scorer=llm_scorer)
    return registry, router
