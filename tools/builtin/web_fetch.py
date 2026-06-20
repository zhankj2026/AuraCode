"""
WebFetch 工具 - 获取网页内容并用 AI 分析

参考 WebFetchTool 设计：
- 获取 URL 内容（HTML→Markdown）
- 可选用 LLM 小模型对内容进行摘要/分析
- 内置 15 分钟 TTL 缓存
- 自动处理 HTTP→HTTPS 升级、重定向
"""

import time
import re
import hashlib
from html.parser import HTMLParser
from typing import Optional, Dict
from urllib.parse import urlparse, urljoin

import httpx

from tools.registry import register_tool

# ── 缓存 ──────────────────────────────────────────────────────────────────────

_CACHE_TTL_SECONDS = 15 * 60  # 15 分钟
_CACHE_MAX_SIZE = 50

_page_cache: Dict[str, tuple] = {}  # url -> (timestamp, content)


def _cache_get(url: str) -> Optional[str]:
    if url in _page_cache:
        ts, content = _page_cache[url]
        if time.time() - ts < _CACHE_TTL_SECONDS:
            return content
        del _page_cache[url]
    return None


def _cache_set(url: str, content: str):
    if len(_page_cache) >= _CACHE_MAX_SIZE:
        # 删除最旧条目
        oldest_key = min(_page_cache, key=lambda k: _page_cache[k][0])
        del _page_cache[oldest_key]
    _page_cache[url] = (time.time(), content)


# ── HTML → 纯文本（轻量实现） ──────────────────────────────────────────────────

class _HTMLToTextParser(HTMLParser):
    """简易 HTML→文本转换器"""

    _BLOCK_TAGS = frozenset({
        'p', 'div', 'section', 'article', 'header', 'footer',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'pre', 'code',
        'table', 'tr', 'td', 'th', 'br', 'hr',
    })
    _SKIP_TAGS = frozenset({
        'script', 'style', 'noscript', 'iframe', 'svg',
        'nav', 'footer', 'header',  # 常见噪声区域
    })

    def __init__(self):
        super().__init__()
        self._chunks: list = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs):
        tag_lower = tag.lower()
        if tag_lower in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag_lower in self._BLOCK_TAGS:
            self._chunks.append('\n')
        elif tag_lower == 'a':
            href = dict(attrs).get('href', '')
            if href:
                self._chunks.append(f' [{href}] ')

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag_lower in self._BLOCK_TAGS:
            self._chunks.append('\n')

    def handle_data(self, data: str):
        if self._skip_depth == 0:
            self._chunks.append(data)

    def get_text(self) -> str:
        raw = ''.join(self._chunks)
        # 折叠多个空行
        raw = re.sub(r'\n{3,}', '\n\n', raw)
        raw = re.sub(r'[ \t]+', ' ', raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    parser = _HTMLToTextParser()
    parser.feed(html)
    return parser.get_text()


# ── LLM 摘要 ────────────────────────────────────────────────────────────────────

def _summarize_with_llm(markdown_content: str, prompt: str) -> str:
    """
    使用当前 AgentLoop 的 LLM 客户端对内容进行摘要。
    若无法访问 LLM，则直接返回原始文本截断。
    """
    try:
        from openai import OpenAI
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.environ.get("OPENAI_MODEL", "glm-4-plus")
        if not api_key:
            return _truncate(markdown_content, 4000)
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个网页内容分析助手。根据用户提示词，从网页内容中提取相关信息并给出简洁回答。"},
                {"role": "user", "content": f"网页内容:\n---\n{markdown_content[:8000]}\n---\n\n{prompt}"}
            ],
            max_tokens=2048,
        )
        return resp.choices[0].message.content or _truncate(markdown_content, 4000)
    except Exception as e:
        return f"(LLM 摘要失败，返回原始文本截断)\n\n{_truncate(markdown_content, 4000)}\n\n[错误: {e}]"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n\n... (截断，共 {len(text)} 字符)"


# ── 主处理函数 ──────────────────────────────────────────────────────────────────

def web_fetch_handler(
    url: str,
    prompt: str = "",
    timeout: int = 30,
) -> str:
    """
    获取网页内容并可选地用 AI 分析。

    Args:
        url: 目标 URL（http 自动升级为 https）
        prompt: 对网页内容的分析提示（留空则返回原始文本摘要）
        timeout: HTTP 请求超时（秒）

    Returns:
        网页内容分析结果
    """
    if not url:
        return "错误: url 不能为空"

    # HTTP → HTTPS 升级
    parsed = urlparse(url)
    if parsed.scheme == 'http':
        url = 'https' + url[4:]

    # 缓存查询
    cached = _cache_get(url)
    page_text = None

    if cached is None:
        # 请求网页
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; opencode-bot/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "html" in content_type:
                    page_text = html_to_text(resp.text)
                else:
                    page_text = resp.text
                _cache_set(url, page_text)
        except httpx.HTTPStatusError as e:
            return f"HTTP 错误 {e.response.status_code}: {url}\n{e.response.text[:500]}"
        except httpx.RequestError as e:
            return f"请求失败: {url}\n错误: {e}"
    else:
        page_text = cached

    if not page_text:
        return f"网页内容为空: {url}"

    # 有 prompt → 用 LLM 分析
    if prompt:
        return _summarize_with_llm(page_text, prompt)

    # 无 prompt → 返回截断文本
    return (
        f"URL: {url}\n"
        f"内容长度: {len(page_text)} 字符\n"
        f"---\n"
        f"{_truncate(page_text, 6000)}"
    )


register_tool("web_fetch", {
    "description": (
        "Fetch and analyze web page content. "
        "Retrieves URL content, converts HTML to markdown, "
        "and optionally uses AI to summarize or extract information. "
        "Built-in 15-minute cache for repeated URLs. "
        "Use for: reading docs, API references, issues, blog posts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Target URL (http auto-upgrades to https)"
            },
            "prompt": {
                "type": "string",
                "description": (
                    "Analysis prompt for the content. "
                    "E.g. 'Extract function usage examples' or 'What is the auth method'. "
                    "Leave empty for raw content summary."
                ),
                "default": ""
            },
            "timeout": {
                "type": "integer",
                "description": "HTTP request timeout in seconds",
                "default": 30
            }
        },
        "required": ["url"]
    },
    "handler": web_fetch_handler,
    "permission_level": "read"
})
