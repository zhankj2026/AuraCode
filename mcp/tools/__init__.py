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

"""MCP tool adaptation layer."""

from mcp.tools.adapter import MCPToolAdapter, create_mcp_tool
from mcp.tools.validation import (
    validate_and_truncate_output,
    estimate_token_count,
    MAX_MCP_OUTPUT_TOKENS,
)

__all__ = [
    "MCPToolAdapter",
    "create_mcp_tool",
    "validate_and_truncate_output",
    "estimate_token_count",
    "MAX_MCP_OUTPUT_TOKENS",
]
