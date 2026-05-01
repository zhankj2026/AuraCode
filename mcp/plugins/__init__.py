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
