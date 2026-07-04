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

"""MCP plugin integration."""

from mcp.plugins.integration import (
    MCPPluginIntegration,
    load_mcp_from_plugin,
    resolve_plugin_env,
)
from mcp.plugins.env_resolver import (
    expand_env_vars,
    substitute_plugin_vars,
    substitute_user_config_vars,
    EnvExpansionError,
)

__all__ = [
    "MCPPluginIntegration",
    "load_mcp_from_plugin",
    "resolve_plugin_env",
    "expand_env_vars",
    "substitute_plugin_vars",
    "substitute_user_config_vars",
    "EnvExpansionError",
]
