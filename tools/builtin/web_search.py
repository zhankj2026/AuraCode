"""
WebSearch 工具 - 搜索互联网获取实时信息

支持多种搜索后端（按优先级尝试）：
1. DuckDuckGo HTML 搜索（免费，无需 API Key）
2. Tavily Search API（需 Tavily API Key）
3. SerpAPI（需 Google SerpAPI Key）

结果格式与 OpenCode WebSearchTool 对齐。
"""

import os
import re
import logging
from typing import List, Dict, Optional
from urllib.parse import quote_plus

import httpx

from tools.registry import register_tool

logger = logging.getLogger(__name__)


# ── DuckDuckGo HTML 搜索（免费） ────────────────────────────────────────────────

def _search_duckduckgo(query: str, max_results: int, timeout: int) -> List[Dict]:
    """
    通过 DuckDuckGo HTML 搜索获取结果。
    无需 API Key，但结果质量可能不如付费 API。
    """
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"q": query, "b": ""}

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = client.post(url, data=data)
            resp.raise_for_status()
            html = resp.text

        # 简易解析搜索结果（正则提取）
        results = []
        # 匹配 result__url, result__snippet
        url_pattern = re.compile(r'class="result__url"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', re.S)
        snippet_pattern = re.compile(r'class="result__snippet"[^>]*>(.+?)</a>', re.S)

        urls = url_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for i, ((link, display_url), snippet) in enumerate(zip(urls, snippets)):
            if i >= max_results:
                break
            # 清理 HTML 标签
            clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            clean_title = display_url.strip()
            results.append({
                "title": clean_title,
                "url": link.strip(),
                "snippet": clean_snippet,
            })

        return results

    except Exception as e:
        logger.warning(f"DuckDuckGo 搜索失败: {e}")
        return []


# ── Tavily API 搜索 ──────────────────────────────────────────────────────────────

def _search_tavily(query: str, max_results: int, timeout: int, api_key: str) -> List[Dict]:
    """
    使用 Tavily Search API（https://tavily.com）。
    专为 AI 代理设计，返回结构化结果。
    """
    url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json"}
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "include_answer": True,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            })

        # Tavily 提供 AI 答案摘要
        answer = data.get("answer", "")
        if answer:
            results.insert(0, {
                "title": "[AI 摘要]",
                "url": "",
                "snippet": answer,
            })

        return results

    except Exception as e:
        logger.warning(f"Tavily 搜索失败: {e}")
        return []


# ── SerpAPI 搜索 ──────────────────────────────────────────────────────────────────

def _search_serpapi(query: str, max_results: int, timeout: int, api_key: str) -> List[Dict]:
    """使用 SerpAPI（Google 搜索结果）。"""
    url = "https://serpapi.com/search"
    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": max_results,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("organic_results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })

        # 精选摘要（如果有）
        answer_box = data.get("answer_box", {})
        if answer_box and answer_box.get("answer"):
            results.insert(0, {
                "title": "[Google 答案]",
                "url": "",
                "snippet": answer_box["answer"],
            })

        return results

    except Exception as e:
        logger.warning(f"SerpAPI 搜索失败: {e}")
        return []


# ── 主处理函数 ──────────────────────────────────────────────────────────────────

def web_search_handler(
    query: str,
    max_results: int = 8,
    timeout: int = 20,
    search_backend: str = "auto",
) -> str:
    """
    搜索互联网获取实时信息。

    支持多种搜索后端：
    - auto: 自动选择（优先 Tavily → SerpAPI → DuckDuckGo）
    - duckduckgo: 免费，无需 API Key
    - tavily: 需 TAVILY_API_KEY 环境变量
    - serpapi: 需 SERPAPI_API_KEY 环境变量

    Args:
        query: 搜索关键词
        max_results: 最大结果数
        timeout: 请求超时（秒）
        search_backend: 搜索后端（auto/duckduckgo/tavily/serpapi）

    Returns:
        搜索结果（标题 + URL + 摘要）
    """
    if not query:
        return "错误: query 不能为空"

    results: List[Dict] = []
    backend_used = ""

    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    serpapi_key = os.environ.get("SERPAPI_API_KEY", "")

    if search_backend == "auto":
        # 优先使用付费 API，降级到 DuckDuckGo
        if tavily_key:
            results = _search_tavily(query, max_results, timeout, tavily_key)
            if results:
                backend_used = "Tavily"
        if not results and serpapi_key:
            results = _search_serpapi(query, max_results, timeout, serpapi_key)
            if results:
                backend_used = "SerpAPI"
        if not results:
            results = _search_duckduckgo(query, max_results, timeout)
            backend_used = "DuckDuckGo"

    elif search_backend == "tavily":
        if not tavily_key:
            return "错误: 使用 Tavily 需要设置 TAVILY_API_KEY 环境变量"
        results = _search_tavily(query, max_results, timeout, tavily_key)
        backend_used = "Tavily"

    elif search_backend == "serpapi":
        if not serpapi_key:
            return "错误: 使用 SerpAPI 需要设置 SERPAPI_API_KEY 环境变量"
        results = _search_serpapi(query, max_results, timeout, serpapi_key)
        backend_used = "SerpAPI"

    else:  # duckduckgo
        results = _search_duckduckgo(query, max_results, timeout)
        backend_used = "DuckDuckGo"

    if not results:
        return f"未找到 '{query}' 的搜索结果（后端: {backend_used}）"

    # 格式化输出
    lines = [f"搜索: '{query}'（后端: {backend_used}，结果: {len(results)} 条）\n"]

    for i, r in enumerate(results, 1):
        title = r["title"]
        url = r["url"]
        snippet = r["snippet"]
        if url:
            lines.append(f"{i}. **[{title}]({url})**\n   {snippet}\n")
        else:
            lines.append(f"{i}. **{title}**\n   {snippet}\n")

    lines.append("---")
    lines.append("Sources:")
    for r in results:
        if r["url"]:
            lines.append(f"- [{r['title']}]({r['url']})")

    return "\n".join(lines)


register_tool("web_search", {
    "description": (
        "搜索互联网获取实时信息。\n"
        "返回搜索结果（标题 + URL + 摘要），支持 DuckDuckGo（免费）、Tavily、SerpAPI。\n"
        "适用于：查询最新文档、API 参考、Bug 解决方案、技术趋势等。\n"
        "搜索后应引用来源 URL。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词（建议包含具体技术名词和年份）"
            },
            "max_results": {
                "type": "integer",
                "description": "最大结果数（默认 8）",
                "default": 8
            },
            "timeout": {
                "type": "integer",
                "description": "请求超时（秒）",
                "default": 20
            },
            "search_backend": {
                "type": "string",
                "enum": ["auto", "duckduckgo", "tavily", "serpapi"],
                "description": (
                    "搜索后端：\n"
                    "auto - 自动选择（优先付费API→免费）\n"
                    "duckduckgo - 免费，无需 Key\n"
                    "tavily - 需 TAVILY_API_KEY\n"
                    "serpapi - 需 SERPAPI_API_KEY"
                ),
                "default": "auto"
            }
        },
        "required": ["query"]
    },
    "handler": web_search_handler,
    "permission_level": "read"
})
