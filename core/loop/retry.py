#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.retry — 错误分类与重试退避（纯函数）

从 ``AgentLoop`` 提取的错误处理策略，全部为无状态纯函数，可独立单测。
不依赖 ``self`` / ``loop``，是整个拆分中最底层、最先稳定的模块。
"""

import logging
import math
import random
import re
from typing import Optional

from openai import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# ── 重试策略常量 ──────────────────────────────────────────────
_MAX_BACKOFF_S = 32          # 非速率限制退避上限（秒）
_RATE_LIMIT_FLOOR_S = 8     # 速率限制最低等待（秒）
_RATE_LIMIT_CAP_S = 60      # 速率限制最大等待（秒），避免过度等待

# 瞬时错误关键词（超时/网络/服务器故障）
_TRANSIENT_ERROR_KEYWORDS = (
    "timeout", "timed out", "connection", "network",
    "temporary failure", "server_error", "502", "503", "504",
    "reset by peer", "broken pipe", "eof occurred",
    "overloaded", "overloaded_error",
)

# 速率限制关键词（需要更长的等待时间）
_RATE_LIMIT_KEYWORDS = (
    "rate limit", "rate_limit", "rate-limit", "ratelimit",
    "too many requests", "429",
    "速率限制", "请求频率", "请求次数",
    "1302",  # GLM 速率限制错误码
)


def extract_status_code(error: Exception) -> Optional[int]:
    """从异常中提取 HTTP 状态码（兼容 openai SDK 各种异常类型）"""
    code = getattr(error, 'status_code', None)
    if code is not None:
        return int(code)
    code = getattr(error, 'status', None)
    if code is not None:
        return int(code)
    return None


def classify_error(error: Exception) -> str:
    """
    精确分类 API 错误，优先使用 HTTP 状态码，回退到关键词匹配。
    返回: 'rate_limit' | 'server_overload' | 'timeout' | 'connection' |
          'server_error' | 'prompt_too_long' | 'auth' | 'unknown'
    """
    status = extract_status_code(error)
    error_str = str(error).lower()

    # 1. 按 HTTP 状态码精确分类
    if status == 429:
        return 'rate_limit'
    if status == 529 or (status == 500 and 'overloaded' in error_str):
        return 'server_overload'
    if status in (408, 409):
        return 'timeout'
    if status in (401, 403):
        return 'auth'
    if status and status >= 500:
        return 'server_error'

    # 2. 类型检查（openai SDK 异常类）
    if isinstance(error, APITimeoutError):
        return 'timeout'
    if isinstance(error, APIConnectionError):
        return 'connection'
    if isinstance(error, RateLimitError):
        return 'rate_limit'

    # 3. 关键词回退（处理非标准 API 如 GLM）
    if is_rate_limit_error(error):
        return 'rate_limit'
    if 'timeout' in error_str or 'timed out' in error_str:
        return 'timeout'
    if 'context_length' in error_str or 'too_long' in error_str or 'too long' in error_str:
        return 'prompt_too_long'
    if any(kw in error_str for kw in ('connection', 'network', 'reset by peer', 'broken pipe')):
        return 'connection'

    return 'unknown'


def is_transient_error(error: Exception) -> bool:
    """判断是否为瞬时可重试错误（超时/网络/服务器过载/速率限制等）"""
    category = classify_error(error)
    return category in (
        'rate_limit', 'server_overload', 'timeout',
        'connection', 'server_error',
    )


def is_rate_limit_error(error: Exception) -> bool:
    """判断是否为速率限制错误（429 / GLM 1302 等）"""
    if isinstance(error, RateLimitError):
        return True
    status = extract_status_code(error)
    if status == 429:
        return True
    error_str = str(error).lower()
    return any(kw in error_str for kw in _RATE_LIMIT_KEYWORDS)


def is_server_error(error: Exception) -> bool:
    """判断是否为服务器端错误（5xx / 529 overloaded）"""
    status = extract_status_code(error)
    if status and status >= 500:
        return True
    error_str = str(error).lower()
    return 'overloaded' in error_str or 'server_error' in error_str


def get_retry_wait(error: Exception, attempt: int) -> float:
    """
    根据错误类型计算重试等待时间。

    优先级:
    1. Retry-After 响应头（最精确，直接使用 + 10% 抖动）
    2. 错误消息中的等待时间提示（GLM 等 API 在 message 中嵌入等待秒数）
    3. 默认退避策略:
       - 速率限制: 8 * sqrt(attempt) 秒，上限 60s
       - 其他瞬时错误: 指数退避 1/2/4/8/16/32s + 25% 抖动
    """
    if is_rate_limit_error(error):
        # ── 策略 1: 读取 Retry-After 响应头 ──
        retry_after = extract_retry_after(error)
        if retry_after is not None:
            jitter = random.uniform(0, max(1, retry_after * 0.1))
            return min(retry_after + jitter, 300)  # 最多 5 分钟

        # ── 策略 2: 从错误消息中提取等待时间 ──
        hint = extract_wait_hint(error)
        if hint is not None:
            jitter = random.uniform(0, max(1, hint * 0.1))
            return hint + jitter

        # ── 策略 3: 默认退避 — 平方根增长，避免过度等待 ──
        # attempt: 1→8s, 2→11s, 3→14s, 4→16s, 5→18s, 8→23s
        # 比 30*attempt (30/60/90s) 快得多，减少用户等待
        base = min(
            _RATE_LIMIT_FLOOR_S * math.sqrt(attempt),
            _RATE_LIMIT_CAP_S,
        )
        jitter = random.uniform(0, 5)
        return base + jitter
    else:
        # 普通瞬时错误：指数退避 (base 1s) + 25% 抖动，上限 32s
        base = min(2 ** (attempt - 1), _MAX_BACKOFF_S)
        jitter = random.uniform(0, 0.25 * base)
        return base + jitter


def extract_retry_after(error: Exception) -> Optional[float]:
    """
    从异常中提取 Retry-After 响应头。
    兼容 openai SDK 多种异常类型的 headers 访问路径。
    """
    # 路径 1: error.response.headers (httpx.Response)
    resp = getattr(error, 'response', None)
    if resp is not None:
        try:
            ra = resp.headers.get('retry-after')
            if ra and str(ra).isdigit():
                return min(float(ra), 300)  # 最多 5 分钟
        except Exception:
            pass

    # 路径 2: error.headers (dict / httpx.Headers)
    headers = getattr(error, 'headers', None)
    if headers is not None:
        try:
            ra = headers.get('retry-after') if hasattr(headers, 'get') else None
            if ra and str(ra).isdigit():
                return min(float(ra), 300)
        except Exception:
            pass

    return None


def extract_wait_hint(error: Exception) -> Optional[float]:
    """
    从错误消息中提取等待时间提示。
    某些 API (如 GLM) 在错误消息中嵌入建议等待时间，例如:
    - "Xs 后重试"
    - "X秒后重试"
    - "retry after Xs"
    """
    msg = str(error)
    for pattern in (
        r'(\d+)\s*[sS秒]\s*后?\s*重试',
        r'retry\s+after\s+(\d+)',
        r'wait\s+(\d+)\s*[sS]',
        r'please\s+wait\s+(\d+)',
    ):
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if 1 <= val <= 300:  # 只接受 1-300 秒的合理值
                return val
    return None
