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
工具智能增强模块

功能:
1. ToolResultSummarizer: 大工具输出智能摘要
   - 超过阈值的输出自动提取关键信息
   - 支持结构化/非结构化输出不同摘要策略

2. ToolRetryPolicy: 幂等工具失败自动重试
   - 可重试工具白名单
   - 指数退避重试策略
   - 重试次数上限

3. ToolOutputTrimmer: 工具输出智能裁剪
   - 保留关键行(错误/警告/文件路径)
   - 移除冗余重复内容

用法:
    enhancer = ToolEnhancer()
    enhanced_result = enhancer.process_tool_result("run_command", result_text)
    should_retry = enhancer.should_retry("read_file", error, attempt=2)
"""

import re
import time
import logging
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── 工具结果摘要器 ─────────────────────────────────────────


class ToolResultSummarizer:
    """
    工具结果智能摘要

    策略:
    - 短结果 (<阈值): 原样返回
    - 代码类结果: 保留文件路径 + 关键行
    - 命令类结果: 保留首尾 + 错误行
    - 搜索类结果: 保留匹配数 + 前N个结果
    """

    # 默认摘要阈值 (字符数)
    DEFAULT_THRESHOLD = 4000

    # 按工具类型的摘要策略
    STRATEGIES = {
        "run_command": "command",
        "run_powershell": "command",
        "read_file": "file_content",
        "grep_search": "search",
        "find_files": "search",
        "glob_tool": "search",
        "list_directory": "list",
        "web_fetch": "web",
        "web_search": "search",
    }

    def __init__(self, threshold: int = DEFAULT_THRESHOLD):
        self.threshold = threshold
        self._summary_cache: Dict[str, str] = {}
        self._max_cache = 100

    def should_summarize(self, tool_name: str, result: str) -> bool:
        """判断是否需要摘要"""
        if not result or len(result) <= self.threshold:
            return False
        # 特定工具总是跳过摘要 (brief 模式除外)
        if tool_name in ("write_file", "replace_in_file", "todo_write"):
            return False
        return True

    def summarize(self, tool_name: str, result: str) -> str:
        """
        对工具结果进行智能摘要

        Returns:
            摘要文本 (如果不需要摘要则返回原文)
        """
        if not self.should_summarize(tool_name, result):
            return result

        # 检查缓存
        cache_key = hashlib.md5(f"{tool_name}:{result[:200]}".encode()).hexdigest()[:12]
        if cache_key in self._summary_cache:
            return self._summary_cache[cache_key]

        strategy = self.STRATEGIES.get(tool_name, "generic")
        summary = self._apply_strategy(strategy, tool_name, result)

        # 缓存
        if len(self._summary_cache) >= self._max_cache:
            # 淘汰最旧
            oldest = next(iter(self._summary_cache))
            del self._summary_cache[oldest]
        self._summary_cache[cache_key] = summary

        logger.info(f"Summarized {tool_name}: {len(result)} → {len(summary)} chars")
        return summary

    def _apply_strategy(self, strategy: str, tool_name: str, result: str) -> str:
        """应用摘要策略"""
        if strategy == "command":
            return self._summarize_command(result)
        elif strategy == "file_content":
            return self._summarize_file(result)
        elif strategy == "search":
            return self._summarize_search(tool_name, result)
        elif strategy == "list":
            return self._summarize_list(result)
        elif strategy == "web":
            return self._summarize_web(result)
        else:
            return self._summarize_generic(result)

    def _summarize_command(self, result: str) -> str:
        """命令输出摘要: 保留首尾 + 错误行"""
        lines = result.splitlines()
        if len(lines) <= 40:
            return result

        # 关键行
        key_lines = []
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(kw in ll for kw in ["error", "fail", "warning", "exception",
                                         "traceback", "denied", "fatal"]):
                key_lines.append((i, line))

        header = f"[命令输出: {len(lines)} 行, 已摘要]\n"
        # 首 10 行
        head = "\n".join(lines[:10])
        # 尾 10 行
        tail = "\n".join(lines[-10:])

        parts = [header, "--- 开头 ---", head]
        if key_lines:
            parts.append("\n--- 关键行 ---")
            for idx, line in key_lines[:15]:
                parts.append(f"L{idx}: {line}")
        parts.extend(["\n--- 结尾 ---", tail])

        return "\n".join(parts)

    def _summarize_file(self, result: str) -> str:
        """文件内容摘要: 保留首尾 + 函数/类定义"""
        lines = result.splitlines()
        if len(lines) <= 60:
            return result

        # 提取结构
        structure = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if (stripped.startswith("def ") or stripped.startswith("class ") or
                stripped.startswith("async def ") or stripped.startswith("#") and len(stripped) > 3):
                structure.append(f"L{i+1}: {stripped[:80]}")

        header = f"[文件内容: {len(lines)} 行, 已摘要]\n"
        head = "\n".join(lines[:15])
        tail = "\n".join(lines[-10:])

        parts = [header, "--- 文件头部 ---", head]
        if structure:
            parts.append("\n--- 代码结构 ---")
            parts.extend(structure[:30])
        parts.extend(["\n--- 文件尾部 ---", tail])

        return "\n".join(parts)

    def _summarize_search(self, tool_name: str, result: str) -> str:
        """搜索结果摘要: 保留匹配数 + 前N个结果"""
        lines = result.splitlines()
        # 计算匹配数
        match_count = sum(1 for l in lines if l.strip() and not l.startswith(" "))

        header = f"[{tool_name}: {match_count} 个匹配, {len(lines)} 行]\n"
        # 保留前 30 个结果行
        kept = []
        for line in lines:
            if len(kept) >= 30:
                break
            if line.strip():
                kept.append(line)

        return header + "\n".join(kept)

    def _summarize_list(self, result: str) -> str:
        """目录列表摘要: 保留前30项"""
        lines = [l for l in result.splitlines() if l.strip()]
        if len(lines) <= 30:
            return result
        header = f"[目录: {len(lines)} 项, 显示前30]\n"
        return header + "\n".join(lines[:30])

    def _summarize_web(self, result: str) -> str:
        """网页内容摘要: 保留标题 + 前几段"""
        lines = result.splitlines()
        if len(lines) <= 40:
            return result
        header = f"[网页内容: {len(lines)} 行, 已摘要]\n"
        # 保留非空行前 25 行
        non_empty = [l for l in lines if l.strip()][:25]
        return header + "\n".join(non_empty)

    def _summarize_generic(self, result: str) -> str:
        """通用摘要: 首尾各保留一部分"""
        lines = result.splitlines()
        half = 20
        header = f"[输出: {len(lines)} 行, 已摘要]\n"
        head = "\n".join(lines[:half])
        tail = "\n".join(lines[-half:])
        return f"{header}{head}\n... ({len(lines) - 2*half} 行省略) ...\n{tail}"


# ── 工具重试策略 ────────────────────────────────────────────


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 2
    base_delay: float = 0.5        # 基础延迟 (秒)
    max_delay: float = 5.0         # 最大延迟
    backoff_factor: float = 2.0    # 退避因子
    retryable_errors: List[str] = field(default_factory=lambda: [
        "timeout", "connection", "temporary", "unavailable",
        "rate_limit", "throttl", "busy", "try again",
        "timeoutexpired", "connectionerror",
    ])


class ToolRetryPolicy:
    """
    工具重试策略

    特性:
    - 仅重试幂等工具 (读操作/搜索)
    - 指数退避延迟
    - 可重试错误类型匹配
    - 重试统计追踪
    """

    # 幂等工具白名单 (可安全重试)
    IDEMPOTENT_TOOLS = {
        "read_file", "list_directory", "grep_search", "find_files",
        "glob_tool", "web_fetch", "web_search", "lsp_tool",
        "tool_search", "sleep_tool", "get_relevant_memories",
        "list_mcp_resources", "read_mcp_resource",
    }

    # 非幂等工具 (写入操作, 不自动重试)
    NON_IDEMPOTENT_TOOLS = {
        "write_file", "replace_in_file", "run_command", "run_powershell",
        "notebook_edit", "todo_write", "config_tool",
    }

    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self._retry_stats: Dict[str, Dict[str, int]] = {}

    def is_retryable_tool(self, tool_name: str) -> bool:
        """判断工具是否可重试 (幂等)"""
        if tool_name in self.IDEMPOTENT_TOOLS:
            return True
        if tool_name in self.NON_IDEMPOTENT_TOOLS:
            return False
        # 默认: 未知工具视为可重试 (保守策略: 只有明确的写入工具不重试)
        return True

    def is_retryable_error(self, error: str) -> bool:
        """判断错误是否可重试"""
        error_lower = error.lower()
        return any(
            pattern in error_lower
            for pattern in self.config.retryable_errors
        )

    def should_retry(self, tool_name: str, error: str, attempt: int) -> bool:
        """
        判断是否应该重试

        Args:
            tool_name: 工具名
            error: 错误信息
            attempt: 当前尝试次数 (从 0 开始)

        Returns:
            是否重试
        """
        if attempt >= self.config.max_retries:
            return False
        if not self.is_retryable_tool(tool_name):
            return False
        if not self.is_retryable_error(error):
            return False
        return True

    def get_retry_delay(self, attempt: int) -> float:
        """计算重试延迟 (指数退避)"""
        delay = self.config.base_delay * (self.config.backoff_factor ** attempt)
        return min(delay, self.config.max_delay)

    def record_retry(self, tool_name: str, attempt: int, success: bool):
        """记录重试结果"""
        if tool_name not in self._retry_stats:
            self._retry_stats[tool_name] = {"retries": 0, "successes": 0, "failures": 0}
        self._retry_stats[tool_name]["retries"] += 1
        if success:
            self._retry_stats[tool_name]["successes"] += 1
        else:
            self._retry_stats[tool_name]["failures"] += 1

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """重试统计"""
        return dict(self._retry_stats)


# ── 工具输出裁剪器 ──────────────────────────────────────────


class ToolOutputTrimmer:
    """
    工具输出智能裁剪

    规则:
    - 保留包含错误/警告/关键信息的行
    - 移除连续空行 (合并为 1 行)
    - 移除重复行 (保留首次出现)
    - 超过最大行数时截断
    """

    MAX_LINES = 500
    KEY_PATTERNS = re.compile(
        r'(error|fail|warning|exception|traceback|fatal|denied|'
        r'assert|raise|import|from|class |def |\d+:\d+|'
        r'\.py:|\.js:|\.ts:|file not found|permission)',
        re.IGNORECASE
    )

    def __init__(self, max_lines: int = MAX_LINES):
        self.max_lines = max_lines

    def trim(self, output: str, max_lines: int = None) -> str:
        """裁剪工具输出

        关键行密集（代码/日志）: 保留关键行 + 首尾各 20 行
        关键行稀疏（文档/数据）: 首/中/尾三段采样 + 显式省略区间标注，
                                 模型能明确知道缺了哪几行、可精确分段补读
        """
        if max_lines is None:
            max_lines = self.max_lines
        lines = output.splitlines()
        if len(lines) <= max_lines:
            # 即使不截断也清理连续空行
            return self._collapse_blank_lines("\n".join(lines))

        # 标记关键行
        key_idx = [i for i, line in enumerate(lines)
                   if self.KEY_PATTERNS.search(line)]

        # 关键行足够多以支撑"关键行+首尾"策略时走原路径，
        # 否则（如中文文档对代码向正则零命中）走区间采样
        if len(key_idx) >= max(15, max_lines // 20):
            return self._trim_key_lines(lines, key_idx)
        return self._trim_sparse(lines, key_idx, max_lines)

    def _trim_key_lines(self, lines: List[str], key_idx: List[int]) -> str:
        """关键行密集: 保留首尾各 20 行 + 所有关键行"""
        keep = set()
        for i in range(min(20, len(lines))):
            keep.add(i)
        for i in range(max(0, len(lines) - 20), len(lines)):
            keep.add(i)
        keep.update(key_idx)

        kept_lines = [lines[i] for i in sorted(keep)]
        result = self._collapse_blank_lines("\n".join(kept_lines))

        if len(kept_lines) < len(lines):
            header = f"[输出已裁剪: {len(lines)} → {len(kept_lines)} 行]\n"
            result = header + result

        return result

    def _trim_sparse(self, lines: List[str], key_idx: List[int], max_lines: int) -> str:
        """关键行稀疏: 首/中/尾三段采样 + 省略区间标注"""
        total = len(lines)
        head_n = max_lines // 4
        tail_n = max_lines // 4
        mid_n = max_lines // 4
        mid_start = head_n + max(0, (total - head_n - tail_n - mid_n) // 2)
        tail_start = total - tail_n

        parts = list(lines[:head_n])
        parts.append(f"⋯ 已省略第 {head_n + 1}-{mid_start} 行（全文 {total} 行），"
                     f"如需该段内容请用 start_line/end_line 分段读取 ⋯")
        parts.extend(lines[mid_start:mid_start + mid_n])
        parts.append(f"⋯ 已省略第 {mid_start + mid_n + 1}-{tail_start} 行（全文 {total} 行），"
                     f"如需该段内容请用 start_line/end_line 分段读取 ⋯")
        parts.extend(lines[tail_start:])

        # 稀疏但存在的关键行（错误/告警等）附加在末尾，避免丢失
        kept = (set(range(head_n)) | set(range(mid_start, mid_start + mid_n))
                | set(range(tail_start, total)))
        for i in key_idx:
            if i not in kept and len(parts) < max_lines:
                parts.append(f"L{i + 1}: {lines[i]}")

        result = self._collapse_blank_lines("\n".join(parts))
        header = (f"[输出已采样: {total} → {len(parts)} 行 | "
                  f"关键行稀疏，保留首/中/尾三段并标注省略区间]\n")
        return header + result

    def _collapse_blank_lines(self, text: str) -> str:
        """合并连续空行为最多 1 行"""
        return re.sub(r'\n{3,}', '\n\n', text)


# ── 统一增强器入口 ──────────────────────────────────────────


class ToolEnhancer:
    """
    工具智能增强统一入口

    组合: Summarizer + RetryPolicy + OutputTrimmer
    """

    def __init__(self, summary_threshold: int = 4000, max_output_lines: int = 500,
                 read_file_exempt_lines: int = 2000,
                 read_file_exempt_chars: int = 32768):
        self.summarizer = ToolResultSummarizer(threshold=summary_threshold)
        self.retry = ToolRetryPolicy()
        self.trimmer = ToolOutputTrimmer(max_lines=max_output_lines)
        self.read_file_exempt_lines = read_file_exempt_lines
        self.read_file_exempt_chars = read_file_exempt_chars

    def process_tool_result(self, tool_name: str, result: str) -> str:
        """处理工具结果: 裁剪 → 摘要

        read_file 豁免: 常规大小文件全文进上下文——关键行正则是为
        代码/报错设计的，对文档类内容会裁到只剩首尾各 20 行，迫使
        模型分段重读同一个文件。超限的读取只裁剪（带省略区间标注）
        不再摘要，保住"缺哪段"的指针信息。
        """
        if not result:
            return result
        if tool_name == "read_file":
            if self._is_small_read(result):
                return result
            return self.trimmer.trim(result)
        # 1. 裁剪
        trimmed = self.trimmer.trim(result)
        # 2. 摘要
        summarized = self.summarizer.summarize(tool_name, trimmed)
        return summarized

    def _is_small_read(self, result: str) -> bool:
        """read_file 豁免判定: 行数与字符数均在豁免线内"""
        return (len(result.splitlines()) <= self.read_file_exempt_lines
                and len(result) <= self.read_file_exempt_chars)

    def should_retry(self, tool_name: str, error: str, attempt: int) -> bool:
        """判断是否重试"""
        return self.retry.should_retry(tool_name, error, attempt)

    def get_retry_delay(self, attempt: int) -> float:
        """获取重试延迟"""
        return self.retry.get_retry_delay(attempt)

    def get_stats(self) -> Dict[str, Any]:
        """统计信息"""
        return {
            "summarizer_cache": len(self.summarizer._summary_cache),
            "retry_stats": self.retry.get_stats(),
        }


# 全局实例
_enhancer: Optional[ToolEnhancer] = None


def get_tool_enhancer() -> ToolEnhancer:
    """获取全局工具增强器

    阈值可经 config.yaml 的 tools.* 键覆盖:
      tools.output_max_lines       工具输出裁剪行数上限 (默认 500)
      tools.summary_threshold      摘要触发字符数阈值 (默认 4000)
      tools.read_file_exempt_lines read_file 豁免裁剪的行数上限 (默认 2000)
      tools.read_file_exempt_chars read_file 豁免裁剪的字符数上限 (默认 32768)
    """
    global _enhancer
    if _enhancer is None:
        kwargs = {}
        try:
            from config.manager import config_manager
            kwargs = {
                "max_output_lines": int(config_manager.get("tools.output_max_lines", 500)),
                "summary_threshold": int(config_manager.get("tools.summary_threshold", 4000)),
                "read_file_exempt_lines": int(config_manager.get("tools.read_file_exempt_lines", 2000)),
                "read_file_exempt_chars": int(config_manager.get("tools.read_file_exempt_chars", 32768)),
            }
        except Exception:
            kwargs = {}
        _enhancer = ToolEnhancer(**kwargs)
    return _enhancer
