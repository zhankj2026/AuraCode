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
MCP output validation and truncation.

This module provides functionality to validate and truncate MCP tool
output to prevent excessive token usage.
"""

import os
import re
from typing import Any


# Configuration
MAX_MCP_OUTPUT_TOKENS = int(
    os.getenv("MAX_MCP_OUTPUT_TOKENS", "25000")
)
TOKEN_COUNT_THRESHOLD_FACTOR = 0.5
IMAGE_TOKEN_ESTIMATE = 1600


def estimate_token_count(text: str) -> int:
    """
    Estimate token count for a string.

    Uses a simple heuristic: approximately 4 characters per token.

    Args:
        text: The text to estimate.

    Returns:
        Estimated token count.
    """
    if not text:
        return 0

    # Remove whitespace for more accurate estimate
    cleaned = re.sub(r"\s+", "", text)
    return len(cleaned) // 4


def estimate_content_size(content: Any) -> int:
    """
    Estimate the size of content in tokens.

    Args:
        content: String, list of content blocks, or other.

    Returns:
        Estimated token count.
    """
    if not content:
        return 0

    if isinstance(content, str):
        return estimate_token_count(content)

    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    total += estimate_token_count(item.get("text", ""))
                elif item_type == "image":
                    total += IMAGE_TOKEN_ESTIMATE
                else:
                    # Other content types
                    total += estimate_token_count(str(item))
            else:
                total += estimate_token_count(str(item))
        return total

    return estimate_token_count(str(content))


async def content_needs_truncation(content: Any) -> bool:
    """
    Check if content needs truncation based on size estimate.

    Args:
        content: The content to check.

    Returns:
        True if content should be truncated.
    """
    size = estimate_content_size(content)
    threshold = MAX_MCP_OUTPUT_TOKENS * TOKEN_COUNT_THRESHOLD_FACTOR

    return size > threshold


async def truncate_content(content: Any) -> Any:
    """
    Truncate content to fit within token limits.

    Args:
        content: The content to truncate.

    Returns:
        Truncated content with truncation message.
    """
    max_chars = MAX_MCP_OUTPUT_TOKENS * 4
    truncation_msg = (
        f"\n\n[OUTPUT TRUNCATED - exceeded {MAX_MCP_OUTPUT_TOKENS} token limit]\n\n"
        "If this MCP server provides pagination or filtering tools, "
        "use them to retrieve specific portions of the data. "
        "If pagination is not available, inform the user that you are "
        "working with truncated output and results may be incomplete."
    )

    if isinstance(content, str):
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + truncation_msg

    if isinstance(content, list):
        result = []
        current_chars = 0

        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "text":
                    text = item.get("text", "")
                    remaining = max_chars - current_chars

                    if remaining <= 0:
                        break

                    if len(text) <= remaining:
                        result.append(item)
                        current_chars += len(text)
                    else:
                        result.append({
                            "type": "text",
                            "text": text[:remaining]
                        })
                        current_chars += remaining
                        break
                elif item_type == "image":
                    # Estimate image size
                    image_chars = IMAGE_TOKEN_ESTIMATE * 4
                    if current_chars + image_chars <= max_chars:
                        result.append(item)
                        current_chars += image_chars
                    # else: skip image
                else:
                    # Other content
                    text = str(item)
                    remaining = max_chars - current_chars

                    if remaining > 0 and len(text) <= remaining:
                        result.append(item)
                        current_chars += len(text)
                    else:
                        break

        # Add truncation message
        result.append({
            "type": "text",
            "text": truncation_msg
        })

        return result

    # For other types, convert to string and truncate
    text = str(content)
    if len(text) <= max_chars:
        return content
    return text[:max_chars] + truncation_msg


async def validate_and_truncate_output(content: Any) -> Any:
    """
    Validate and truncate MCP tool output if needed.

    Args:
        content: The content to validate and possibly truncate.

    Returns:
        Original content if within limits, truncated content otherwise.
    """
    if await content_needs_truncation(content):
        return await truncate_content(content)

    return content


def get_max_tokens() -> int:
    """Get the maximum output token limit."""
    return MAX_MCP_OUTPUT_TOKENS


def set_max_tokens(tokens: int) -> None:
    """
    Set the maximum output token limit.

    Args:
        tokens: New token limit.
    """
    global MAX_MCP_OUTPUT_TOKENS
    MAX_MCP_OUTPUT_TOKENS = tokens
