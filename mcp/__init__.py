"""
MCP (Model Context Protocol) integration module.

This module provides comprehensive functionality for integrating with MCP servers,
including client implementation, configuration management, tool adaptation,
OAuth authentication, skill discovery, and plugin integration.
"""

# Core client and configuration
from mcp.client.base import MCPClient, MCPSessionExpiredError
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

# Transport layer
from mcp.transport.base import Transport, TransportError
from mcp.transport.stdio import StdioTransport
from mcp.transport.http import HTTPTransport, SSETransport
from mcp.transport.websocket import WebSocketTransport

# Tool adaptation
from mcp.tools.adapter import MCPToolAdapter, create_mcp_tool, register_mcp_tools
from mcp.tools.validation import (
    validate_and_truncate_output,
    estimate_token_count,
    MAX_MCP_OUTPUT_TOKENS,
)
from mcp.tools.resources import ListMcpResourcesTool, ReadMcpResourceTool, register_resource_tools
from mcp.tools.prompts import ListMcpPromptsTool, GetMcpPromptTool, register_prompt_tools

# OAuth authentication
from mcp.auth import (
    OAuthClient,
    OAuthError,
    authenticate_oauth,
)

# Plugin integration
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

# Skills
from mcp.skills import (
    McpSkillDefinition,
    McpSkillDiscoverer,
    McpSkillExecutor,
    discover_mcp_skills,
    register_mcp_skill_tools,
)
from mcp.skills.registry import (
    McpSkillBuilders,
    register_mcp_skill_builders,
    create_mcp_skill_command,
    discover_and_create_mcp_skills,
    load_mcp_skills_to_registry,
    McpSkillFrontmatterParser,
)

# Utilities
from mcp.utils.strings import (
    mcp_info_from_string,
    build_mcp_tool_name,
    get_mcp_prefix,
    get_mcp_display_name,
    extract_mcp_tool_display_name,
)

__all__ = [
    # Core client
    "MCPClient",
    "MCPSessionExpiredError",
    # Config types
    "ConfigScope",
    "McpServerConfig",
    "McpStdioServerConfig",
    "McpSSEServerConfig",
    "McpHTTPServerConfig",
    "McpWebSocketServerConfig",
    "ScopedMcpServerConfig",
    # Config manager
    "MCPConfigManager",
    # Transport
    "Transport",
    "TransportError",
    "StdioTransport",
    "HTTPTransport",
    "SSETransport",
    "WebSocketTransport",
    # Tool adaptation
    "MCPToolAdapter",
    "create_mcp_tool",
    "register_mcp_tools",
    "validate_and_truncate_output",
    "estimate_token_count",
    "MAX_MCP_OUTPUT_TOKENS",
    # Resource tools
    "ListMcpResourcesTool",
    "ReadMcpResourceTool",
    "register_resource_tools",
    # Prompt tools
    "ListMcpPromptsTool",
    "GetMcpPromptTool",
    "register_prompt_tools",
    # OAuth authentication
    "OAuthClient",
    "OAuthError",
    "authenticate_oauth",
    # Plugin integration
    "MCPPluginIntegration",
    "load_mcp_from_plugin",
    "resolve_plugin_env",
    "expand_env_vars",
    "substitute_plugin_vars",
    "substitute_user_config_vars",
    "EnvExpansionError",
    # Skills
    "McpSkillDefinition",
    "McpSkillDiscoverer",
    "McpSkillExecutor",
    "discover_mcp_skills",
    "register_mcp_skill_tools",
    "McpSkillBuilders",
    "register_mcp_skill_builders",
    "create_mcp_skill_command",
    "discover_and_create_mcp_skills",
    "load_mcp_skills_to_registry",
    "McpSkillFrontmatterParser",
    # Utilities
    "mcp_info_from_string",
    "build_mcp_tool_name",
    "get_mcp_prefix",
    "get_mcp_display_name",
    "extract_mcp_tool_display_name",
]
