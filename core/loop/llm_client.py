#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.loop.llm_client — LLM 调用封装

包含流式调用（含智能退避重试）、同步调用降级方案、截断 JSON 修复，
以及流式累积数据类 ``StreamResult`` / ``_StreamToolCall``。
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.loop.retry import (
    classify_error,
    get_retry_wait,
    is_transient_error,
)

logger = logging.getLogger(__name__)

# API 级最大重试次数（流式调用内置退避重试）
MAX_API_RETRIES = 10


@dataclass
class StreamResult:
    """流式响应的归一化结果（兼容同步 API 接口）"""
    content: str = ""
    tool_calls: List[Any] = field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Any = None
    reasoning_content: str = ""  # Thinking/Reasoning block (DeepSeek-R1, GLM-4 等)


class _StreamToolCall:
    """流式累积的工具调用对象（模拟 OpenAI ToolCall 接口）"""

    class _Function:
        def __init__(self, name: str, arguments: str):
            self.name = name
            self.arguments = arguments

    def __init__(self, data: Dict[str, str]):
        self.id = data.get("id", "")
        self.type = "function"
        self.function = self._Function(
            data.get("name", ""),
            data.get("arguments", ""),
        )


class LLMClient:
    """封装 OpenAI 兼容客户端的流式 / 同步调用。"""

    def __init__(self, loop):
        self.loop = loop

    def call_streaming(self) -> StreamResult:
        """
        流式调用 LLM — 逐 token 实时输出，同时累积工具调用。
        内置智能退避重试：最多 10 次，优先读取 Retry-After header，
        速率限制默认 8-60s，普通错误指数退避 1-32s。
        """
        loop = self.loop
        active_model = loop.state.get_active_model(loop.model)
        logger.debug(f"Streaming LLM ({active_model}) with {len(loop.messages)} messages")
        print(f"\n🤔 思考中... (模型={active_model}, {len(loop.messages)} 条消息)")

        max_retries = MAX_API_RETRIES

        for attempt in range(1, max_retries + 1):
            try:
                _llm_call_start = time.time()

                # ── 写入请求日志 ──
                loop.events.write_llm_log("REQUEST", active_model, attempt)

                response = loop.client.chat.completions.create(
                    model=active_model,
                    messages=loop.messages,
                    tools=loop.tools,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=loop.max_tokens,
                    stream=True,
                )

                # 流式处理
                full_content = ""
                reasoning_content = ""  # Thinking/Reasoning block 累积
                tool_calls_map: Dict[int, Dict] = {}  # index -> accumulated data
                finish_reason = None
                usage = None
                first_chunk = True
                reasoning_started = False

                try:
                    for chunk in response:
                        # 中断检查（每个 chunk 都检查）
                        if loop.state.is_aborted():
                            logger.info("Stream aborted by user")
                            finish_reason = "aborted"
                            break

                        if not chunk.choices:
                            # 最后一个 chunk 可能携带 usage（无 choices）
                            if hasattr(chunk, 'usage') and chunk.usage:
                                usage = chunk.usage
                            continue

                        choice = chunk.choices[0]
                        delta = choice.delta

                        # finish_reason 在最后一个 chunk
                        if choice.finish_reason:
                            finish_reason = choice.finish_reason

                        # ── Thinking/Reasoning block（DeepSeek-R1, GLM-4 等）──
                        # 部分模型通过 delta.reasoning_content 或 delta.reasoning 传递思维链
                        delta_reasoning = None
                        if delta:
                            delta_reasoning = (
                                getattr(delta, 'reasoning_content', None)
                                or getattr(delta, 'reasoning', None)
                            )
                        if delta_reasoning:
                            if not reasoning_started:
                                reasoning_started = True
                                print("\n💭 [Thinking] ", end="", flush=True)
                            print(delta_reasoning, end="", flush=True)
                            reasoning_content += delta_reasoning

                        # 文本增量 — 实时输出
                        if delta and delta.content:
                            if reasoning_started:
                                # Thinking 结束，正文开始，换行分隔
                                print("\n", end="", flush=True)
                                reasoning_started = False
                            if first_chunk:
                                print("\n🤖 Assistant: ", end="", flush=True)
                                first_chunk = False
                            print(delta.content, end="", flush=True)
                            full_content += delta.content

                            # 发出 text_chunk 事件（Token 级流式）
                            loop.events.emit_text_chunk(delta.content)

                        # 工具调用增量累积
                        if delta and hasattr(delta, 'tool_calls') and delta.tool_calls:
                            for tc_chunk in delta.tool_calls:
                                idx = tc_chunk.index
                                if idx not in tool_calls_map:
                                    tool_calls_map[idx] = {
                                        "id": tc_chunk.id or "",
                                        "type": "function",
                                        "name": "",
                                        "arguments": "",
                                    }
                                if tc_chunk.id:
                                    tool_calls_map[idx]["id"] = tc_chunk.id
                                if tc_chunk.function:
                                    if tc_chunk.function.name:
                                        tool_calls_map[idx]["name"] += tc_chunk.function.name
                                    if tc_chunk.function.arguments:
                                        tool_calls_map[idx]["arguments"] += tc_chunk.function.arguments

                        # usage 可能在最后一个 chunk（部分 API）
                        if hasattr(chunk, 'usage') and chunk.usage:
                            usage = chunk.usage

                finally:
                    # 显式关闭流式连接，确保 HTTP 资源释放
                    try:
                        if hasattr(response, 'close'):
                            response.close()
                        elif hasattr(response, '_response') and hasattr(response._response, 'close'):
                            response._response.close()
                    except Exception:
                        pass

                # 流式结束
                if reasoning_started:
                    print("\n")  # Thinking 块结束换行
                if not first_chunk:
                    print()  # 换行

                # 构建工具调用对象列表（模拟 OpenAI ToolCall）
                tool_calls_list = []
                for idx in sorted(tool_calls_map.keys()):
                    tc_data = tool_calls_map[idx]
                    tool_calls_list.append(_StreamToolCall(tc_data))

                # Token 统计
                if usage:
                    logger.info(f"Token: prompt={getattr(usage, 'prompt_tokens', '?')}, "
                               f"completion={getattr(usage, 'completion_tokens', '?')}, "
                               f"total={getattr(usage, 'total_tokens', '?')}")
                    print(f"💰 Token: 输入={getattr(usage, 'prompt_tokens', '?')}, "
                          f"输出={getattr(usage, 'completion_tokens', '?')}, "
                          f"总计={getattr(usage, 'total_tokens', '?')}")

                # 记录 reasoning_content 到日志（用于调试/审计）
                if reasoning_content:
                    logger.debug(f"Reasoning block ({len(reasoning_content)} chars): {reasoning_content[:300]}...")

                # 发射 LLM API 调用详情事件（网络报文）
                _llm_duration = round((time.time() - _llm_call_start) * 1000)
                loop.events.emit("llm_call", {
                    "turn": loop.state.turn_count,
                    "attempt": attempt,
                    "duration_ms": _llm_duration,
                    "request": {
                        "model": active_model,
                        "message_count": len(loop.messages),
                        "tool_count": len(loop.tools) if loop.tools else 0,
                        "temperature": 0.2,
                        "max_tokens": loop.max_tokens,
                    },
                    "response": {
                        "finish_reason": finish_reason,
                        "content_length": len(full_content),
                        "content_preview": full_content[:500] if full_content else "",
                        "tool_calls": len(tool_calls_list),
                        "tool_names": [tc.function.name for tc in tool_calls_list],
                        "prompt_tokens": getattr(usage, 'prompt_tokens', 0) or 0 if usage else 0,
                        "completion_tokens": getattr(usage, 'completion_tokens', 0) or 0 if usage else 0,
                        "total_tokens": getattr(usage, 'total_tokens', 0) or 0 if usage else 0,
                        "has_reasoning": bool(reasoning_content),
                        "reasoning_length": len(reasoning_content),
                    },
                })

                # ── 写入响应日志 ──
                loop.events.write_llm_log("RESPONSE", active_model, attempt, {
                    "finish_reason": finish_reason,
                    "content_length": len(full_content),
                    "content_preview": full_content[:1000] if full_content else "",
                    "tool_calls": len(tool_calls_list),
                    "tool_names": [tc.function.name for tc in tool_calls_list],
                    "prompt_tokens": getattr(usage, 'prompt_tokens', 0) or 0 if usage else 0,
                    "completion_tokens": getattr(usage, 'completion_tokens', 0) or 0 if usage else 0,
                    "duration_ms": _llm_duration,
                })

                return StreamResult(
                    content=full_content,
                    tool_calls=tool_calls_list,
                    finish_reason=finish_reason,
                    usage=usage,
                    reasoning_content=reasoning_content,
                )

            except Exception as e:
                # 瞬时错误 → 按类型计算等待时间并重试
                if is_transient_error(e) and attempt < max_retries:
                    wait = get_retry_wait(e, attempt)
                    category = classify_error(e)
                    error_labels = {
                        'rate_limit': '速率限制',
                        'server_overload': '服务器过载',
                        'timeout': '请求超时',
                        'connection': '连接失败',
                        'server_error': '服务器错误',
                    }
                    error_label = error_labels.get(category, '网络故障')
                    logger.warning(
                        f"LLM streaming {error_label} (attempt {attempt}/{max_retries}): {e}, "
                        f"retrying in {wait:.1f}s..."
                    )
                    print(f"\n⚠️ API {error_label} ({e}), {wait:.0f}s 后重试 ({attempt}/{max_retries})...")
                    loop.events.emit("api_retry", {
                        "attempt": attempt,
                        "max_retries": max_retries,
                        "wait_seconds": round(wait, 1),
                        "error": str(e),
                        "category": category,
                        "is_rate_limit": category == 'rate_limit',
                    })
                    time.sleep(wait)
                    continue

                # 不可重试错误或重试已耗尽
                logger.error(f"LLM streaming 调用失败 ({active_model}): {e}")
                raise

    def call(self):
        """同步调用 LLM（流式不可用时的降级方案）"""
        loop = self.loop
        active_model = loop.state.get_active_model(loop.model)
        logger.debug(f"Calling LLM ({active_model}) with {len(loop.messages)} messages")
        print(f"\n🤔 思考中... (模型={active_model}, {len(loop.messages)} 条消息)")

        try:
            response = loop.client.chat.completions.create(
                model=active_model,
                messages=loop.messages,
                tools=loop.tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=loop.max_tokens
            )
            usage = response.usage
            if usage:
                print(f"💰 Token: 输入={usage.prompt_tokens}, 输出={usage.completion_tokens}, 总计={usage.total_tokens}")
            return response
        except Exception as e:
            logger.error(f"LLM API 调用失败 ({active_model}): {e}")
            raise

    @staticmethod
    def try_fix_json(raw: str) -> Optional[Dict]:
        """尝试修复 LLM 返回的截断/不完整 JSON"""
        if not raw or not raw.strip():
            return {}

        s = raw.strip()

        # 策略 1: 补全未闭合的字符串和括号
        # 统计未闭合的引号
        in_string = False
        escape = False
        for i, ch in enumerate(s):
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string

        # 如果字符串未闭合，补全引号
        if in_string:
            s += '"'

        # 补全未闭合的花括号
        open_braces = s.count('{') - s.count('}')
        if open_braces > 0:
            s += '}' * open_braces

        try:
            result = json.loads(s)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # 策略 2: 截断到最后一个完整的 key-value 对
        # 找最后一个 "key": "value" 或 "key": number 模式
        # 移除末尾不完整的键值对
        truncated = re.sub(r',\s*"[^"]*"\s*:\s*("[^"]*|[0-9]+|true|false|null)?$', '}', s)
        if truncated != s:
            # 确保括号平衡
            open_b = truncated.count('{') - truncated.count('}')
            if open_b > 0:
                truncated += '}' * open_b
            try:
                result = json.loads(truncated)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        return None
