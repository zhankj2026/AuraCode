"""
会话智能增强模块

功能:
1. SessionBrancher: 会话分支与合并
   - 从任意消息点创建分支
   - 多分支并行探索
   - 合并最优分支结果

2. SessionSearch: 跨会话全文检索
   - 搜索历史会话消息
   - 按时间/关键词/工具过滤
   - 搜索结果排序与高亮

用法:
    brancher = SessionBrancher()
    branch = brancher.create_branch(messages, from_index=5, name="explore-a")
    merged = brancher.merge_branches([branch_a, branch_b], strategy="best")

    search = SessionSearch()
    search.index_session(session_id, messages)
    results = search.query("authentication error", limit=10)
"""

import re
import time
import json
import logging
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ── 会话分支 ────────────────────────────────────────────────


@dataclass
class SessionBranch:
    """会话分支"""
    branch_id: str
    name: str
    parent_id: Optional[str]       # 父分支 ID (None=主干)
    fork_point: int                # 从消息列表的第几条开始分支
    messages: List[Dict[str, Any]] # 分支消息
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 分支评估分数 (用于合并选择)
    score: Optional[float] = None
    score_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "fork_point": self.fork_point,
            "message_count": len(self.messages),
            "created_at": self.created_at,
            "score": self.score,
            "score_reason": self.score_reason,
        }


class SessionBrancher:
    """
    会话分支管理器

    支持:
    - 从任意消息点创建分支 (create_branch)
    - 列出所有分支 (list_branches)
    - 合并分支 (merge_branches)
    - 分支评估打分 (evaluate_branch)
    """

    def __init__(self):
        self._branches: Dict[str, SessionBranch] = {}
        self._counter = 0

    def create_branch(
        self,
        messages: List[Dict[str, Any]],
        from_index: int = 0,
        name: str = None,
        parent_id: str = None,
        metadata: Dict = None,
    ) -> SessionBranch:
        """
        从消息列表的指定位置创建分支

        Args:
            messages: 完整消息列表
            from_index: 分支起始位置 (保留 0..from_index 的消息)
            name: 分支名称
            parent_id: 父分支 ID
            metadata: 额外元数据

        Returns:
            SessionBranch
        """
        self._counter += 1
        branch_id = f"branch_{self._counter}_{int(time.time())}"
        if not name:
            name = f"branch-{self._counter}"

        # 复制消息到分支点
        branch_messages = list(messages[:from_index + 1])

        branch = SessionBranch(
            branch_id=branch_id,
            name=name,
            parent_id=parent_id,
            fork_point=from_index,
            messages=branch_messages,
            metadata=metadata or {},
        )

        self._branches[branch_id] = branch
        logger.info(f"Created branch: {name} at message {from_index}")
        return branch

    def get_branch(self, branch_id: str) -> Optional[SessionBranch]:
        """获取分支"""
        return self._branches.get(branch_id)

    def list_branches(self, parent_id: str = None) -> List[Dict[str, Any]]:
        """列出所有分支"""
        branches = list(self._branches.values())
        if parent_id is not None:
            branches = [b for b in branches if b.parent_id == parent_id]
        return [b.to_dict() for b in branches]

    def evaluate_branch(self, branch_id: str, criteria: Dict[str, float] = None) -> float:
        """
        评估分支质量 (用于合并选择)

        评估维度:
        - 消息完整度 (是否有成功的工具调用)
        - 错误率 (错误消息比例)
        - token 效率 (总 token 消耗)
        - 结果长度 (assistant 消息的总长度)

        Returns:
            0.0 - 1.0 分数
        """
        branch = self._branches.get(branch_id)
        if not branch:
            return 0.0

        criteria = criteria or {
            "completeness": 0.3,   # 完整度权重
            "error_rate": 0.3,     # 错误率权重 (越低越好)
            "efficiency": 0.2,     # 效率权重
            "result_quality": 0.2, # 结果质量
        }

        msgs = branch.messages
        total = len(msgs)
        if total == 0:
            return 0.0

        # 完整度: 有 assistant + tool 消息
        has_assistant = any(m.get("role") == "assistant" for m in msgs)
        has_tool = any(m.get("role") == "tool" for m in msgs)
        completeness = 1.0 if (has_assistant and has_tool) else 0.5

        # 错误率
        tool_msgs = [m for m in msgs if m.get("role") == "tool"]
        errors = sum(1 for m in tool_msgs if m.get("content", "").startswith("Error:"))
        error_rate = 1.0 - (errors / max(len(tool_msgs), 1))

        # 效率: 消息数越少越好 (相同结果下)
        efficiency = max(0, 1.0 - (total - 5) / 50)

        # 结果质量: assistant 消息的总长度
        assistant_content = sum(
            len(m.get("content", "")) for m in msgs if m.get("role") == "assistant"
        )
        result_quality = min(1.0, assistant_content / 2000)

        score = (
            criteria.get("completeness", 0.3) * completeness +
            criteria.get("error_rate", 0.3) * error_rate +
            criteria.get("efficiency", 0.2) * efficiency +
            criteria.get("result_quality", 0.2) * result_quality
        )

        branch.score = round(score, 4)
        branch.score_reason = (
            f"complete={completeness:.1f} error={error_rate:.1f} "
            f"eff={efficiency:.1f} quality={result_quality:.1f}"
        )

        return branch.score

    def merge_branches(
        self,
        branch_ids: List[str],
        strategy: str = "best",
    ) -> Optional[List[Dict[str, Any]]]:
        """
        合并多个分支

        Args:
            branch_ids: 要合并的分支 ID 列表
            strategy:
                - "best": 选择评分最高的分支
                - "concat": 拼接所有分支的最终结果
                - "interleave": 按轮次交叉合并

        Returns:
            合并后的消息列表
        """
        branches = [self._branches.get(bid) for bid in branch_ids]
        branches = [b for b in branches if b is not None]

        if not branches:
            return None
        if len(branches) == 1:
            return branches[0].messages

        # 确保所有分支有评分
        for b in branches:
            if b.score is None:
                self.evaluate_branch(b.branch_id)

        if strategy == "best":
            # 选择评分最高的分支
            best = max(branches, key=lambda b: b.score or 0)
            logger.info(f"Merged (best): selected '{best.name}' score={best.score}")
            return best.messages

        elif strategy == "concat":
            # 拼接: 公共前缀 + 各分支独有部分
            common_len = min(b.fork_point + 1 for b in branches)
            common = branches[0].messages[:common_len]

            merged = list(common)
            for b in branches:
                unique = b.messages[common_len:]
                if unique:
                    # 添加分支标记
                    merged.append({
                        "role": "system",
                        "content": f"[Branch: {b.name} (score: {b.score})]"
                    })
                    merged.extend(unique)

            return merged

        elif strategy == "interleave":
            # 交叉: 按轮次交替取消息
            common_len = min(b.fork_point + 1 for b in branches)
            merged = list(branches[0].messages[:common_len])

            max_len = max(len(b.messages) for b in branches)
            for i in range(common_len, max_len):
                for b in branches:
                    if i < len(b.messages):
                        merged.append(b.messages[i])

            return merged

        return None

    def delete_branch(self, branch_id: str) -> bool:
        """删除分支"""
        return self._branches.pop(branch_id, None) is not None

    def get_stats(self) -> Dict[str, Any]:
        """统计"""
        return {
            "total_branches": len(self._branches),
            "by_parent": {},
        }


# ── 跨会话搜索 ─────────────────────────────────────────────


@dataclass
class SearchResult:
    """搜索结果"""
    session_id: str
    message_index: int
    role: str
    content: str
    timestamp: Optional[str] = None
    score: float = 0.0
    matched_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "message_index": self.message_index,
            "role": self.role,
            "content_preview": self.content[:200],
            "timestamp": self.timestamp,
            "score": round(self.score, 4),
            "matched_terms": self.matched_terms,
        }


class SessionSearch:
    """
    跨会话全文检索引擎

    支持:
    - 索引会话消息 (index_session)
    - 关键词搜索 (query)
    - 按角色/时间/工具过滤
    - 评分排序
    """

    def __init__(self):
        self._index: Dict[str, List[Dict[str, Any]]] = {}  # session_id -> messages
        self._token_index: Dict[str, List[Tuple[str, int]]] = {}  # token -> [(session_id, msg_idx)]

    def index_session(self, session_id: str, messages: List[Dict[str, Any]]):
        """
        索引会话消息

        Args:
            session_id: 会话 ID
            messages: 消息列表
        """
        indexed = []
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            if not content:
                continue
            indexed.append({
                "index": i,
                "role": msg.get("role", ""),
                "content": content,
                "timestamp": msg.get("timestamp"),
            })

            # 分词并建立倒排索引
            tokens = self._tokenize(content)
            for token in tokens:
                if token not in self._token_index:
                    self._token_index[token] = []
                self._token_index[token].append((session_id, i))

        self._index[session_id] = indexed
        logger.info(f"Indexed session {session_id}: {len(indexed)} messages")

    def query(
        self,
        query_text: str,
        limit: int = 10,
        role_filter: str = None,
        session_filter: str = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索会话消息

        Args:
            query_text: 搜索关键词
            limit: 最大返回数
            role_filter: 按角色过滤 (user/assistant/tool/system)
            session_filter: 按会话 ID 过滤

        Returns:
            搜索结果列表
        """
        tokens = self._tokenize(query_text)
        if not tokens:
            return []

        # 收集匹配
        matches: Dict[Tuple[str, int], Dict] = {}  # (session_id, msg_idx) -> match_info

        for token in tokens:
            # 精确匹配 + 前缀匹配
            for indexed_token, locations in self._token_index.items():
                if indexed_token == token or indexed_token.startswith(token):
                    for session_id, msg_idx in locations:
                        key = (session_id, msg_idx)
                        if key not in matches:
                            matches[key] = {"score": 0, "terms": []}
                        matches[key]["score"] += 1.0 if indexed_token == token else 0.5
                        if indexed_token not in matches[key]["terms"]:
                            matches[key]["terms"].append(indexed_token)

        # 过滤
        results = []
        for (session_id, msg_idx), info in matches.items():
            if session_filter and session_id != session_filter:
                continue

            session_msgs = self._index.get(session_id, [])
            msg_data = next((m for m in session_msgs if m["index"] == msg_idx), None)
            if not msg_data:
                continue

            if role_filter and msg_data["role"] != role_filter:
                continue

            results.append(SearchResult(
                session_id=session_id,
                message_index=msg_idx,
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=msg_data.get("timestamp"),
                score=info["score"],
                matched_terms=info["terms"],
            ))

        # 按分数排序
        results.sort(key=lambda r: r.score, reverse=True)
        return [r.to_dict() for r in results[:limit]]

    def remove_session(self, session_id: str):
        """移除会话索引"""
        self._index.pop(session_id, None)
        # 清理倒排索引
        tokens_to_clean = []
        for token, locations in self._token_index.items():
            self._token_index[token] = [
                (sid, idx) for sid, idx in locations if sid != session_id
            ]
            if not self._token_index[token]:
                tokens_to_clean.append(token)
        for token in tokens_to_clean:
            del self._token_index[token]

    def get_stats(self) -> Dict[str, Any]:
        """索引统计"""
        total_msgs = sum(len(msgs) for msgs in self._index.values())
        return {
            "indexed_sessions": len(self._index),
            "indexed_messages": total_msgs,
            "unique_tokens": len(self._token_index),
        }

    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 小写化 + 按非字母数字分词
        tokens = re.findall(r'[a-zA-Z\u4e00-\u9fff]{2,}', text.lower())
        # 去重
        return list(set(tokens))


# ── 统一入口 ───────────────────────────────────────────────


class SessionIntelligence:
    """会话智能统一入口"""

    def __init__(self):
        self.brancher = SessionBrancher()
        self.search = SessionSearch()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "branches": self.brancher.get_stats(),
            "search": self.search.get_stats(),
        }


_session_intel: Optional[SessionIntelligence] = None


def get_session_intelligence() -> SessionIntelligence:
    """获取全局会话智能实例"""
    global _session_intel
    if _session_intel is None:
        _session_intel = SessionIntelligence()
    return _session_intel
