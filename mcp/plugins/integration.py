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
MCP plugin integration.

This module provides functionality to load and integrate MCP servers
from plugins.
"""

import json
import os
from pathlib import Path
from typing import Any

from mcp.config.types import McpServerConfig, ScopedMcpServerConfig
from mcp.plugins.env_resolver import resolve_mcp_env, EnvExpansionError
from mcp.config.validation import validate_mcp_config


class MCPPluginIntegration:
    """
    Integration layer for loading MCP servers from plugins.

    This handles:
    - Loading .mcp.json files from plugin directories
    - Processing inline mcpServers configurations
    - Resolving plugin-specific environment variables
    - Scoping server names to avoid conflicts
    """

    def __init__(self):
        """Initialize the MCP plugin integration."""
        self._plugin_mcp_cache: dict[str, dict[str, McpServerConfig]] = {}

    async def load_from_plugin(
        self,
        plugin_path: str,
        plugin_name: str,
        plugin_source: str,
        user_config: dict[str, str] | None = None,
    ) -> dict[str, ScopedMcpServerConfig]:
        """
        Load MCP servers from a plugin.

        Args:
            plugin_path: Path to the plugin directory.
            plugin_name: Name of the plugin.
            plugin_source: Source identifier for the plugin.
            user_config: Optional user configuration values.

        Returns:
            Dictionary of scoped MCP server configurations.
        """
        # Check cache first
        cache_key = f"{plugin_source}:{plugin_name}"
        if cache_key in self._plugin_mcp_cache:
            base_configs = self._plugin_mcp_cache[cache_key]
        else:
            # Load from plugin
            base_configs = await self._load_plugin_configs(plugin_path)
            self._plugin_mcp_cache[cache_key] = base_configs

        # Resolve environment variables
        resolved_configs: dict[str, McpServerConfig] = {}

        plugin_obj = type("Plugin", (), {"path": plugin_path, "source": plugin_source})

        for server_name, config in base_configs.items():
            try:
                resolved = resolve_mcp_env(config, plugin_obj, user_config)
                resolved_configs[server_name] = resolved
            except EnvExpansionError as e:
                # Skip servers with missing configuration
                continue

        # Add plugin scope to avoid naming conflicts
        scoped_configs: dict[str, ScopedMcpServerConfig] = {}

        for server_name, config in resolved_configs.items():
            scoped_name = f"plugin:{plugin_name}:{server_name}"
            scoped_configs[scoped_name] = ScopedMcpServerConfig(
                config=config,
                scope="dynamic",
                plugin_source=plugin_source,
                name=scoped_name,
                disabled=False,
            )

        return scoped_configs

    async def _load_plugin_configs(
        self, plugin_path: str
    ) -> dict[str, McpServerConfig]:
        """
        Load base MCP configurations from a plugin.

        Args:
            plugin_path: Path to the plugin directory.

        Returns:
            Dictionary of server configurations (unresolved).
        """
        configs: dict[str, McpServerConfig] = {}

        # Check for .mcp.json in plugin directory
        mcp_json_path = Path(plugin_path) / ".mcp.json"
        if mcp_json_path.exists():
            try:
                with open(mcp_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                mcp_servers = data.get("mcpServers", {})
                for name, config_data in mcp_servers.items():
                    try:
                        config = self._parse_config(config_data)
                        configs[name] = config
                    except Exception:
                        # Skip invalid configs
                        continue

            except (json.JSONDecodeError, IOError):
                pass

        # Check for manifest file
        manifest_path = Path(plugin_path) / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

                mcp_servers = manifest.get("mcpServers")
                if mcp_servers:
                    if isinstance(mcp_servers, str):
                        # Path to another file
                        server_configs = await self._load_from_file(
                            plugin_path, mcp_servers
                        )
                        configs.update(server_configs)
                    elif isinstance(mcp_servers, list):
                        # List of file paths or inline configs
                        for item in mcp_servers:
                            if isinstance(item, str):
                                server_configs = await self._load_from_file(
                                    plugin_path, item
                                )
                                configs.update(server_configs)
                            elif isinstance(item, dict):
                                # Inline config
                                for name, config_data in item.items():
                                    try:
                                        config = self._parse_config(config_data)
                                        configs[name] = config
                                    except Exception:
                                        continue

            except (json.JSONDecodeError, IOError):
                pass

        return configs

    async def _load_from_file(
        self, plugin_path: str, relative_path: str
    ) -> dict[str, McpServerConfig]:
        """
        Load MCP configurations from a file relative to plugin path.

        Args:
            plugin_path: Plugin directory path.
            relative_path: Relative path to the config file.

        Returns:
            Dictionary of server configurations.
        """
        configs: dict[str, McpServerConfig] = {}

        file_path = Path(plugin_path) / relative_path
        if not file_path.exists():
            return configs

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            mcp_servers = data.get("mcpServers", data)
            for name, config_data in mcp_servers.items():
                try:
                    config = self._parse_config(config_data)
                    configs[name] = config
                except Exception:
                    continue

        except (json.JSONDecodeError, IOError):
            pass

        return configs

    def _parse_config(self, data: dict[str, Any]) -> McpServerConfig:
        """Parse a server configuration from dict."""
        from mcp.config.types import (
            McpStdioServerConfig,
            McpSSEServerConfig,
            McpHTTPServerConfig,
            McpWebSocketServerConfig,
            McpOAuthConfig,
        )

        server_type = data.get("type", "stdio")

        if server_type == "stdio":
            return McpStdioServerConfig(
                type=None,
                command=data.get("command", ""),
                args=data.get("args", []),
                env=data.get("env", {}),
            )
        elif server_type == "sse":
            oauth_data = data.get("oauth")
            oauth = (
                McpOAuthConfig(
                    client_id=oauth_data.get("client_id"),
                    callback_port=oauth_data.get("callback_port"),
                    auth_server_metadata_url=oauth_data.get(
                        "auth_server_metadata_url"
                    ),
                    xaa=oauth_data.get("xaa", False),
                )
                if oauth_data
                else None
            )
            return McpSSEServerConfig(
                type="sse",
                url=data.get("url", ""),
                headers=data.get("headers", {}),
                headers_helper=data.get("headers_helper"),
                oauth=oauth,
            )
        elif server_type == "http":
            oauth_data = data.get("oauth")
            oauth = (
                McpOAuthConfig(
                    client_id=oauth_data.get("client_id"),
                    callback_port=oauth_data.get("callback_port"),
                    auth_server_metadata_url=oauth_data.get(
                        "auth_server_metadata_url"
                    ),
                    xaa=oauth_data.get("xaa", False),
                )
                if oauth_data
                else None
            )
            return McpHTTPServerConfig(
                type="http",
                url=data.get("url", ""),
                headers=data.get("headers", {}),
                headers_helper=data.get("headers_helper"),
                oauth=oauth,
            )
        elif server_type == "ws":
            return McpWebSocketServerConfig(
                type="ws",
                url=data.get("url", ""),
                headers=data.get("headers", {}),
                headers_helper=data.get("headers_helper"),
            )
        else:
            # Default to stdio
            return McpStdioServerConfig(
                type=None,
                command=data.get("command", ""),
                args=data.get("args", []),
                env=data.get("env", {}),
            )

    def clear_cache(self) -> None:
        """Clear the plugin MCP cache."""
        self._plugin_mcp_cache.clear()


# Global integration instance
_integration = MCPPluginIntegration()


async def load_mcp_from_plugin(
    plugin_path: str,
    plugin_name: str,
    plugin_source: str,
    user_config: dict[str, str] | None = None,
) -> dict[str, ScopedMcpServerConfig]:
    """
    Load MCP servers from a plugin (convenience function).

    Args:
        plugin_path: Path to the plugin directory.
        plugin_name: Name of the plugin.
        plugin_source: Source identifier for the plugin.
        user_config: Optional user configuration values.

    Returns:
        Dictionary of scoped MCP server configurations.
    """
    return await _integration.load_from_plugin(
        plugin_path, plugin_name, plugin_source, user_config
    )


def resolve_plugin_env(
    config: McpServerConfig,
    plugin: Any,
    user_config: dict[str, str] | None = None,
) -> McpServerConfig:
    """
    Resolve environment variables in a plugin MCP configuration.

    Args:
        config: The configuration to resolve.
        plugin: Plugin object with path and source attributes.
        user_config: Optional user configuration values.

    Returns:
        Resolved configuration.
    """
    return resolve_mcp_env(config, plugin, user_config)
