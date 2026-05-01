"""
MCP (Model Context Protocol) integration module.

This module provides core functionality for integrating with MCP servers,
including client implementation, configuration management, tool adaptation,
and plugin integration.
"""

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
from mcp.transport.base import Transport, TransportError
from mcp.transport.stdio import StdioTransport
from mcp.transport.http import HTTPTransport, SSETransport
from mcp.transport.websocket import WebSocketTransport

__all__ = [
    # Client
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
]
