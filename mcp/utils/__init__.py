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

"""MCP utility functions."""

from mcp.utils.strings import (
    mcp_info_from_string,
    build_mcp_tool_name,
    get_mcp_prefix,
    get_mcp_display_name,
    extract_mcp_tool_display_name,
)

__all__ = [
    "mcp_info_from_string",
    "build_mcp_tool_name",
    "get_mcp_prefix",
    "get_mcp_display_name",
    "extract_mcp_tool_display_name",
]
