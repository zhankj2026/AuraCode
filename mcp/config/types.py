"""
MCP configuration type definitions.

This module defines the configuration types for MCP servers,
including stdio, SSE, HTTP, and WebSocket transports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union


class ConfigScope(Enum):
    """Configuration scope levels."""

    LOCAL = "local"
    USER = "user"
    PROJECT = "project"
    DYNAMIC = "dynamic"
    ENTERPRISE = "enterprise"
    CLAUDEAI = "claudeai"
    MANAGED = "managed"


class TransportType(Enum):
    """Transport protocol types."""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    WS = "ws"
    SDK = "sdk"


@dataclass
class McpStdioServerConfig:
    """Configuration for stdio-based MCP servers."""

    type: Optional[TransportType] = TransportType.STDIO
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class McpOAuthConfig:
    """OAuth configuration for MCP servers."""

    client_id: Optional[str] = None
    callback_port: Optional[int] = None
    auth_server_metadata_url: Optional[str] = None
    xaa: bool = False


@dataclass
class McpSSEServerConfig:
    """Configuration for SSE-based MCP servers."""

    type: TransportType = TransportType.SSE
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    headers_helper: Optional[str] = None
    oauth: Optional[McpOAuthConfig] = None


@dataclass
class McpHTTPServerConfig:
    """Configuration for HTTP-based MCP servers."""

    type: TransportType = TransportType.HTTP
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    headers_helper: Optional[str] = None
    oauth: Optional[McpOAuthConfig] = None


@dataclass
class McpWebSocketServerConfig:
    """Configuration for WebSocket-based MCP servers."""

    type: TransportType = TransportType.WS
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    headers_helper: Optional[str] = None


@dataclass
class McpSdkServerConfig:
    """Configuration for SDK-based MCP servers."""

    type: TransportType = TransportType.SDK
    name: str = ""


@dataclass
class McpSSEIDEServerConfig:
    """Configuration for IDE-based SSE servers (internal use)."""

    type: TransportType = TransportType.SSE
    url: str = ""
    ide_name: str = ""
    ide_running_in_windows: bool = False


@dataclass
class McpWebSocketIDEServerConfig:
    """Configuration for IDE-based WebSocket servers (internal use)."""

    type: TransportType = TransportType.WS
    url: str = ""
    ide_name: str = ""
    auth_token: Optional[str] = None
    ide_running_in_windows: bool = False


@dataclass
class McpClaudeAIProxyServerConfig:
    """Configuration for Claude.ai proxy servers."""

    type: str = "claudeai-proxy"
    url: str = ""
    id: str = ""


# Union type for all server configurations
McpServerConfig = Union[
    McpStdioServerConfig,
    McpSSEServerConfig,
    McpHTTPServerConfig,
    McpWebSocketServerConfig,
    McpSdkServerConfig,
    McpSSEIDEServerConfig,
    McpWebSocketIDEServerConfig,
    McpClaudeAIProxyServerConfig,
]


@dataclass
class ScopedMcpServerConfig:
    """MCP server configuration with scope information."""

    # Base config (one of the types above)
    config: McpServerConfig
    # Scope level
    scope: ConfigScope = ConfigScope.PROJECT
    # Plugin source if from a plugin
    plugin_source: Optional[str] = None
    # Server name
    name: str = ""
    # Whether the server is disabled
    disabled: bool = False


@dataclass
class McpJsonConfig:
    """Configuration from .mcp.json file."""

    mcpServers: dict[str, McpServerConfig] = field(default_factory=dict)


# Helper functions to work with configs


def get_config_transport_type(config: McpServerConfig) -> TransportType:
    """Get the transport type from a config object."""
    if isinstance(config, McpStdioServerConfig):
        return TransportType.STDIO
    elif isinstance(config, McpSSEServerConfig):
        return TransportType.SSE
    elif isinstance(config, McpHTTPServerConfig):
        return TransportType.HTTP
    elif isinstance(config, McpWebSocketServerConfig):
        return TransportType.WS
    elif isinstance(config, McpSdkServerConfig):
        return TransportType.SDK
    elif isinstance(config, McpSSEIDEServerConfig):
        return TransportType.SSE
    elif isinstance(config, McpWebSocketIDEServerConfig):
        return TransportType.WS
    else:
        # Default to stdio for backward compatibility
        return TransportType.STDIO


def is_stdio_config(config: McpServerConfig) -> bool:
    """Check if config is a stdio config."""
    return (
        isinstance(config, McpStdioServerConfig)
        or config.type == TransportType.STDIO
        or config.type is None
    )


def get_command_array(config: McpServerConfig) -> Optional[list[str]]:
    """Extract command array from stdio config."""
    if not is_stdio_config(config):
        return None
    stdio_config = config if isinstance(config, McpStdioServerConfig) else config
    if isinstance(stdio_config, McpStdioServerConfig):
        return [stdio_config.command] + (stdio_config.args or [])
    return None
