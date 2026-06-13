"""
工具执行链追踪与结果缓存

ToolTracker:
- 追踪每次工具调用的输入、输出、耗时、状态
- 生成调用链报告（调用树 + 耗时分布 + 错误统计）
- 集成到 AgentLoop._execute_tool

ToolCache:
- 基于 (tool_name, args_hash) 缓存工具结果
- 支持 TTL 过期和手动清除
- 可配置缓存白名单/黑名单
"""

import hashlib
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRecord:
    """单次工具调用记录"""
    tool_name: str
    arguments: Dict[str, Any]
    result_preview: str = ""        # 结果预览（前200字符）
    success: bool = True
    error: Optional[str] = None
    start_time: float = 0.0
    duration_ms: float = 0.0
    turn: int = 0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
            "turn": self.turn,
            "timestamp": self.timestamp,
        }


class ToolTracker:
    """工具执行链追踪器"""

    def __init__(self):
        self._records: List[ToolCallRecord] = []
        self._current: Optional[ToolCallRecord] = None
        # 统计数据
        self._tool_stats: Dict[str, Dict[str, Any]] = {}  # tool_name -> stats

    def start_call(self, tool_name: str, arguments: Dict[str, Any], turn: int = 0) -> ToolCallRecord:
        """标记工具调用开始"""
        record = ToolCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            start_time=time.time(),
            turn=turn,
            timestamp=datetime.now().isoformat(),
        )
        self._current = record
        return record

    def end_call(
        self,
        success: bool = True,
        result_preview: str = "",
        error: Optional[str] = None,
    ) -> Optional[ToolCallRecord]:
        """标记工具调用结束"""
        if self._current is None:
            return None

        record = self._current
        record.duration_ms = (time.time() - record.start_time) * 1000
        record.success = success
        record.result_preview = result_preview[:200] if result_preview else ""
        record.error = error

        self._records.append(record)
        self._current = None

        # 更新统计
        name = record.tool_name
        if name not in self._tool_stats:
            self._tool_stats[name] = {
                "calls": 0,
                "successes": 0,
                "failures": 0,
                "total_ms": 0.0,
                "min_ms": float("inf"),
                "max_ms": 0.0,
            }
        s = self._tool_stats[name]
        s["calls"] += 1
        s["successes" if success else "failures"] += 1
        s["total_ms"] += record.duration_ms
        s["min_ms"] = min(s["min_ms"], record.duration_ms)
        s["max_ms"] = max(s["max_ms"], record.duration_ms)

        return record

    def get_records(self, limit: int = 50) -> List[ToolCallRecord]:
        """获取最近的调用记录"""
        return self._records[-limit:]

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取工具统计信息"""
        return dict(self._tool_stats)

    def get_call_chain(self, turn: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取调用链（可按轮次过滤）"""
        records = self._records
        if turn is not None:
            records = [r for r in records if r.turn == turn]
        return [r.to_dict() for r in records]

    def get_timeline(self, limit: int = 30) -> str:
        """生成时间线可视化"""
        records = self.get_records(limit)
        if not records:
            return "📭 无工具调用记录"

        lines = [f"🔗 工具调用时间线 (最近 {len(records)} 次)", ""]
        for r in records:
            icon = "✅" if r.success else "❌"
            dur = f"{r.duration_ms:.0f}ms"
            preview = r.result_preview[:40].replace("\n", " ") if r.result_preview else ""
            lines.append(f"  {icon} T{r.turn} {r.tool_name:<20} {dur:>8}  {preview}")
            if r.error:
                lines.append(f"    ⚠️ {r.error[:60]}")
        return "\n".join(lines)

    def get_report(self) -> str:
        """生成完整报告"""
        if not self._records:
            return "📊 工具执行报告: 无调用记录"

        total_calls = len(self._records)
        total_ms = sum(r.duration_ms for r in self._records)
        success_count = sum(1 for r in self._records if r.success)
        fail_count = total_calls - success_count

        lines = [
            f"📊 工具执行报告",
            f"  总调用: {total_calls} | 成功: {success_count} | 失败: {fail_count}",
            f"  总耗时: {total_ms:.0f}ms ({total_ms/1000:.1f}s)",
            f"  平均耗时: {total_ms/max(total_calls,1):.0f}ms",
            f"",
            f"  📋 按工具统计:",
            f"  {'工具':<20} {'调用':>5} {'成功':>5} {'失败':>5} {'总耗时':>10} {'平均':>8} {'最大':>8}",
            f"  {'-'*70}",
        ]

        for name, s in sorted(self._tool_stats.items(), key=lambda x: x[1]["total_ms"], reverse=True):
            avg_ms = s["total_ms"] / max(s["calls"], 1)
            lines.append(
                f"  {name:<20} {s['calls']:>5} {s['successes']:>5} {s['failures']:>5} "
                f"{s['total_ms']:>9.0f}ms {avg_ms:>7.0f}ms {s['max_ms']:>7.0f}ms"
            )

        # 错误汇总
        errors = [r for r in self._records if r.error]
        if errors:
            lines.append(f"\n  ❌ 错误汇总 ({len(errors)} 个):")
            seen = set()
            for r in errors:
                key = f"{r.tool_name}: {r.error[:50]}"
                if key not in seen:
                    seen.add(key)
                    count = sum(1 for e in errors if e.tool_name == r.tool_name and e.error[:50] == r.error[:50])
                    lines.append(f"    {r.tool_name}: {r.error[:60]} (×{count})")

        return "\n".join(lines)

    def clear(self):
        """清空所有记录"""
        self._records.clear()
        self._tool_stats.clear()
        self._current = None


class ToolCache:
    """工具结果缓存（避免重复执行）"""

    def __init__(self, default_ttl: float = 300.0, max_size: int = 100):
        """
        Args:
            default_ttl: 默认缓存过期时间（秒），默认 300s
            max_size: 最大缓存条目数
        """
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (result, expire_time)
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

        # 缓存策略：只缓存这些工具的结果
        self._cacheable_tools = {
            "read_file", "grep_search", "glob_search", "find_files",
            "web_fetch", "web_search", "lsp_query", "list_dir",
            "get_file_info", "tool_search",
        }
        # 永不缓存的工具
        self._no_cache_tools = {
            "write_file", "run_command", "run_powershell",
            "replace_in_file", "repl_execute", "ask_user",
            "todo_write", "task_create", "notebook_edit",
        }

    def _make_key(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """生成缓存键"""
        args_str = json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:12]
        return f"{tool_name}:{args_hash}"

    def is_cacheable(self, tool_name: str) -> bool:
        """检查工具是否可缓存"""
        if tool_name in self._no_cache_tools:
            return False
        if tool_name in self._cacheable_tools:
            return True
        # 默认不缓存未知工具
        return False

    def get(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Any]:
        """查询缓存"""
        if not self.is_cacheable(tool_name):
            return None

        key = self._make_key(tool_name, arguments)
        if key not in self._cache:
            self._misses += 1
            return None

        result, expire_time = self._cache[key]
        if time.time() > expire_time:
            # 过期
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        logger.debug(f"缓存命中: {key}")
        return result

    def put(self, tool_name: str, arguments: Dict[str, Any], result: Any, ttl: float = None):
        """写入缓存"""
        if not self.is_cacheable(tool_name):
            return

        # 清理过期条目
        self._evict_expired()

        # 限制大小
        if len(self._cache) >= self._max_size:
            # 移除最早的
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        key = self._make_key(tool_name, arguments)
        expire_time = time.time() + (ttl or self._default_ttl)
        self._cache[key] = (result, expire_time)

    def invalidate(self, tool_name: str = None):
        """失效缓存"""
        if tool_name is None:
            self._cache.clear()
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{tool_name}:")]
            for k in keys_to_remove:
                del self._cache[k]

    def _evict_expired(self):
        """清理过期条目"""
        now = time.time()
        expired = [k for k, (_, exp) in self._cache.items() if now > exp]
        for k in expired:
            del self._cache[k]

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / max(total, 1) * 100
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 1),
            "default_ttl": self._default_ttl,
        }

    def get_stats_text(self) -> str:
        """格式化缓存统计"""
        s = self.get_stats()
        return (
            f"📦 工具缓存统计\n"
            f"  大小: {s['size']}/{s['max_size']}\n"
            f"  命中: {s['hits']} | 未命中: {s['misses']} | 命中率: {s['hit_rate_pct']:.1f}%\n"
            f"  默认TTL: {s['default_ttl']:.0f}s"
        )


# 全局实例
_tool_tracker: Optional[ToolTracker] = None
_tool_cache: Optional[ToolCache] = None


def get_tool_tracker() -> ToolTracker:
    global _tool_tracker
    if _tool_tracker is None:
        _tool_tracker = ToolTracker()
    return _tool_tracker


def get_tool_cache() -> ToolCache:
    global _tool_cache
    if _tool_cache is None:
        _tool_cache = ToolCache()
    return _tool_cache
