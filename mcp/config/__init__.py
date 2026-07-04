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

"""MCP configuration management."""

from mcp.config.types import (
    ConfigScope,
    McpHTTPServerConfig,
    McpSSEServerConfig,
    McpServerConfig,
    McpStdioServerConfig,
    McpWebSocketServerConfig,
    ScopedMcpServerConfig,
)
from mcp.config.manager import MCPConfigManager
from mcp.config.validation import validate_mcp_config, ConfigValidationError

__all__ = [
    "ConfigScope",
    "McpServerConfig",
    "McpStdioServerConfig",
    "McpSSEServerConfig",
    "McpHTTPServerConfig",
    "McpWebSocketServerConfig",
    "ScopedMcpServerConfig",
    "MCPConfigManager",
    "validate_mcp_config",
    "ConfigValidationError",
]
