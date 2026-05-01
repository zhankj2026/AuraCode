"""
MCP configuration manager.

This module provides functionality to load and manage MCP server
configurations from various sources and scopes.
"""

import json
import os
from pathlib import Path
from typing import Any

from mcp.config.types import (
    ConfigScope,
    McpJsonConfig,
    McpServerConfig,
    ScopedMcpServerConfig,
)
from mcp.config.validation import validate_mcp_config, ConfigValidationError


class MCPConfigManager:
    """
    Manager for MCP server configurations.

    This manager loads configurations from:
    - Project-level .mcp.json files
    - User-level config directories
    - Global/Enterprise config files
    - Plugin configurations
    """

    def __init__(
        self,
        project_dir: str | None = None,
        user_config_dir: str | None = None,
    ):
        """
        Initialize the configuration manager.

        Args:
            project_dir: Optional project directory path.
            user_config_dir: Optional user config directory path.
        """
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.user_config_dir = (
            Path(user_config_dir)
            if user_config_dir
            else Path.home() / ".config" / "opencode"
        )
        self._cached_configs: dict[ConfigScope, dict[str, ScopedMcpServerConfig]] = {}

    def get_all_configs(
        self, include_disabled: bool = False
    ) -> dict[str, ScopedMcpServerConfig]:
        """
        Get all MCP server configurations from all scopes.

        Args:
            include_disabled: Whether to include disabled servers.

        Returns:
            Dictionary mapping server names to their scoped configurations.
        """
        all_configs: dict[str, ScopedMcpServerConfig] = {}

        # Load in priority order (highest to lowest)
        scopes = [
            ConfigScope.ENTERPRISE,
            ConfigScope.MANAGED,
            ConfigScope.USER,
            ConfigScope.PROJECT,
            ConfigScope.DYNAMIC,
        ]

        for scope in scopes:
            configs = self.get_configs_by_scope(scope)
            for name, config in configs.items():
                # Skip if already exists (higher scope wins)
                if name not in all_configs:
                    if include_disabled or not config.disabled:
                        all_configs[name] = config

        return all_configs

    def get_configs_by_scope(
        self, scope: ConfigScope
    ) -> dict[str, ScopedMcpServerConfig]:
        """
        Get configurations for a specific scope.

        Args:
            scope: The configuration scope.

        Returns:
            Dictionary mapping server names to their configurations.
        """
        # Check cache first
        if scope in self._cached_configs:
            return self._cached_configs[scope]

        configs: dict[str, ScopedMcpServerConfig] = {}

        try:
            if scope == ConfigScope.PROJECT:
                configs = self._load_project_configs()
            elif scope == ConfigScope.USER:
                configs = self._load_user_configs()
            elif scope == ConfigScope.ENTERPRISE:
                configs = self._load_enterprise_configs()
            elif scope == ConfigScope.MANAGED:
                configs = self._load_managed_configs()
            # Dynamic scope is populated externally (plugins, etc.)

        except Exception:
            # If loading fails, return empty dict
            configs = {}

        self._cached_configs[scope] = configs
        return configs

    def set_configs_for_scope(
        self,
        scope: ConfigScope,
        configs: dict[str, ScopedMcpServerConfig],
    ) -> None:
        """
        Set configurations for a specific scope.

        This is useful for externally-populated scopes like DYNAMIC.

        Args:
            scope: The configuration scope.
            configs: The configurations to set.
        """
        self._cached_configs[scope] = configs

    def add_dynamic_config(
        self,
        name: str,
        config: McpServerConfig,
        plugin_source: str | None = None,
    ) -> None:
        """
        Add a dynamically-loaded configuration (e.g., from a plugin).

        Args:
            name: Server name.
            config: Server configuration.
            plugin_source: Optional plugin source identifier.
        """
        dynamic_configs = self.get_configs_by_scope(ConfigScope.DYNAMIC)
        dynamic_configs[name] = ScopedMcpServerConfig(
            config=config,
            scope=ConfigScope.DYNAMIC,
            plugin_source=plugin_source,
            name=name,
            disabled=False,
        )
        self._cached_configs[ConfigScope.DYNAMIC] = dynamic_configs

    def save_project_config(self, config: McpJsonConfig) -> None:
        """
        Save configuration to the project's .mcp.json file.

        Args:
            config: The configuration to save.

        Raises:
            ConfigValidationError: If configuration is invalid.
            IOError: If file write fails.
        """
        # Validate before saving
        config_dict = {"mcpServers": {}}
        for name, server_config in config.mcpServers.items():
            config_dict["mcpServers"][name] = self._serialize_config(server_config)

        errors = validate_mcp_config(config_dict)
        if errors:
            raise ConfigValidationError(
                f"Configuration validation failed with {len(errors)} error(s)"
            )

        # Write to .mcp.json
        mcp_json_path = self.project_dir / ".mcp.json"
        with open(mcp_json_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2)

        # Clear cache
        self._cached_configs.pop(ConfigScope.PROJECT, None)

    def _load_project_configs(self) -> dict[str, ScopedMcpServerConfig]:
        """Load configurations from .mcp.json."""
        mcp_json_path = self.project_dir / ".mcp.json"

        if not mcp_json_path.exists():
            return {}

        try:
            with open(mcp_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return self._parse_mcp_json(data, ConfigScope.PROJECT)

        except (json.JSONDecodeError, IOError):
            return {}

    def _load_user_configs(self) -> dict[str, ScopedMcpServerConfig]:
        """Load configurations from user config directory."""
        mcp_json_path = self.user_config_dir / "mcp.json"

        if not mcp_json_path.exists():
            return {}

        try:
            with open(mcp_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return self._parse_mcp_json(data, ConfigScope.USER)

        except (json.JSONDecodeError, IOError):
            return {}

    def _load_enterprise_configs(self) -> dict[str, ScopedMcpServerConfig]:
        """Load configurations from enterprise config file."""
        # Check for enterprise config in user config dir
        enterprise_path = self.user_config_dir / "enterprise-mcp.json"

        if not enterprise_path.exists():
            return {}

        try:
            with open(enterprise_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return self._parse_mcp_json(data, ConfigScope.ENTERPRISE)

        except (json.JSONDecodeError, IOError):
            return {}

    def _load_managed_configs(self) -> dict[str, ScopedMcpServerConfig]:
        """Load configurations from managed config file."""
        # Check for managed config
        managed_path = self.user_config_dir / "managed-mcp.json"

        if not managed_path.exists():
            return {}

        try:
            with open(managed_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return self._parse_mcp_json(data, ConfigScope.MANAGED)

        except (json.JSONDecodeError, IOError):
            return {}

    def _parse_mcp_json(
        self, data: dict[str, Any], scope: ConfigScope
    ) -> dict[str, ScopedMcpServerConfig]:
        """Parse MCP JSON configuration."""
        mcp_servers = data.get("mcpServers", {})
        configs: dict[str, ScopedMcpServerConfig] = {}

        for name, config_data in mcp_servers.items():
            try:
                config = self._parse_config(config_data)
                configs[name] = ScopedMcpServerConfig(
                    config=config,
                    scope=scope,
                    name=name,
                    disabled=False,
                )
            except Exception:
                # Skip invalid configs
                continue

        return configs

    def _parse_config(self, data: dict[str, Any]) -> McpServerConfig:
        """Parse a single server configuration from dict."""
        # Import here to avoid circular imports
        from mcp.config.types import (
            McpStdioServerConfig,
            McpSSEServerConfig,
            McpHTTPServerConfig,
            McpWebSocketServerConfig,
        )

        server_type = data.get("type", "stdio")

        if server_type == "stdio":
            return McpStdioServerConfig(
                type=None,  # Default
                command=data.get("command", ""),
                args=data.get("args", []),
                env=data.get("env", {}),
            )
        elif server_type == "sse":
            from mcp.config.types import McpOAuthConfig

            oauth_data = data.get("oauth")
            oauth = (
                McpOAuthConfig(
                    client_id=oauth_data.get("client_id"),
                    callback_port=oauth_data.get("callback_port"),
                    auth_server_metadata_url=oauth_data.get("auth_server_metadata_url"),
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
            from mcp.config.types import McpOAuthConfig

            oauth_data = data.get("oauth")
            oauth = (
                McpOAuthConfig(
                    client_id=oauth_data.get("client_id"),
                    callback_port=oauth_data.get("callback_port"),
                    auth_server_metadata_url=oauth_data.get("auth_server_metadata_url"),
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

    def _serialize_config(self, config: McpServerConfig) -> dict[str, Any]:
        """Serialize a server configuration to dict."""
        if hasattr(config, "type") and config.type == "stdio":
            return {
                "type": "stdio",
                "command": config.command,
                "args": config.args,
                "env": config.env,
            }
        elif hasattr(config, "type") and config.type == "sse":
            data = {
                "type": "sse",
                "url": config.url,
                "headers": config.headers,
            }
            if config.headers_helper:
                data["headers_helper"] = config.headers_helper
            if config.oauth:
                data["oauth"] = {
                    "client_id": config.oauth.client_id,
                    "callback_port": config.oauth.callback_port,
                    "auth_server_metadata_url": config.oauth.auth_server_metadata_url,
                    "xaa": config.oauth.xaa,
                }
            return data
        elif hasattr(config, "type") and config.type == "http":
            data = {
                "type": "http",
                "url": config.url,
                "headers": config.headers,
            }
            if config.headers_helper:
                data["headers_helper"] = config.headers_helper
            if config.oauth:
                data["oauth"] = {
                    "client_id": config.oauth.client_id,
                    "callback_port": config.oauth.callback_port,
                    "auth_server_metadata_url": config.oauth.auth_server_metadata_url,
                    "xaa": config.oauth.xaa,
                }
            return data
        elif hasattr(config, "type") and config.type == "ws":
            data = {
                "type": "ws",
                "url": config.url,
                "headers": config.headers,
            }
            if config.headers_helper:
                data["headers_helper"] = config.headers_helper
            return data
        else:
            # Default to stdio
            return {
                "type": "stdio",
                "command": config.command,
                "args": config.args,
                "env": config.env,
            }

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cached_configs.clear()
