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
MCP client implementation.

This module provides the main MCP client that handles communication
with MCP servers using various transport protocols.
"""

import asyncio
from typing import Any

from mcp.config.types import (
    McpHTTPServerConfig,
    McpSSEServerConfig,
    McpServerConfig,
    McpStdioServerConfig,
    McpWebSocketServerConfig,
)
from mcp.transport.base import Transport, TransportError, TransportClosedError
from mcp.transport.stdio import StdioTransport
from mcp.transport.http import HTTPTransport, SSETransport
from mcp.transport.websocket import WebSocketTransport


class MCPSessionExpiredError(Exception):
    """Raised when an MCP session has expired."""

    def __init__(self, server_name: str):
        self.server_name = server_name
        super().__init__(f'MCP server "{server_name}" session expired')


class MCPClient:
    """
    Main MCP client for communicating with MCP servers.

    This client handles:
    - Connection management
    - Tool listing and calling
    - Resource access
    - Prompt management
    """

    def __init__(self, server_name: str, config: McpServerConfig):
        """
        Initialize the MCP client.

        Args:
            server_name: Name of the MCP server.
            config: Server configuration.
        """
        self.server_name = server_name
        self.config = config
        self._transport: Transport | None = None
        self._capabilities: dict[str, Any] | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        """Check if the client is connected."""
        return self._connected and self._transport is not None

    @property
    def capabilities(self) -> dict[str, Any] | None:
        """Get server capabilities."""
        return self._capabilities

    async def connect(self) -> None:
        """
        Connect to the MCP server.

        Raises:
            TransportError: If connection fails.
        """
        if self._connected:
            return

        # Create appropriate transport
        self._transport = self._create_transport()

        # Start the transport
        await self._transport.start()

        # Initialize the session
        await self._initialize()

        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        self._connected = False

        if self._transport:
            await self._transport.close()
            self._transport = None

        self._capabilities = None

    async def list_tools(self) -> list[dict[str, Any]]:
        """
        List available tools from the server.

        Returns:
            List of tool definitions.

        Raises:
            MCPSessionExpiredError: If session has expired.
            TransportError: If communication fails.
        """
        self._ensure_connected()

        try:
            result = await self._transport.send_request("tools/list")
            return result.get("tools", [])
        except TransportClosedError:
            self._connected = False
            raise MCPSessionExpiredError(self.server_name)

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Call a tool on the server.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            Tool call result.

        Raises:
            MCPSessionExpiredError: If session has expired.
            TransportError: If communication fails.
        """
        self._ensure_connected()

        try:
            result = await self._transport.send_request(
                "tools/call",
                {
                    "name": name,
                    "arguments": arguments,
                },
            )
            return result
        except TransportClosedError:
            self._connected = False
            raise MCPSessionExpiredError(self.server_name)

    async def list_resources(self) -> list[dict[str, Any]]:
        """
        List available resources from the server.

        Returns:
            List of resource definitions.

        Raises:
            MCPSessionExpiredError: If session has expired.
            TransportError: If communication fails.
        """
        self._ensure_connected()

        if not self._supports_resources():
            return []

        try:
            result = await self._transport.send_request("resources/list")
            return result.get("resources", [])
        except TransportClosedError:
            self._connected = False
            raise MCPSessionExpiredError(self.server_name)

    async def read_resource(self, uri: str) -> str | list[dict[str, Any]]:
        """
        Read a resource from the server.

        Args:
            uri: Resource URI.

        Returns:
            Resource content (string or content list).

        Raises:
            MCPSessionExpiredError: If session has expired.
            TransportError: If communication fails.
        """
        self._ensure_connected()

        if not self._supports_resources():
            raise TransportError("Server does not support resources")

        try:
            result = await self._transport.send_request(
                "resources/read",
                {"uri": uri},
            )
            contents = result.get("contents", [])
            if len(contents) == 1:
                return contents[0].get("text", "")
            return contents
        except TransportClosedError:
            self._connected = False
            raise MCPSessionExpiredError(self.server_name)

    async def list_prompts(self) -> list[dict[str, Any]]:
        """
        List available prompts from the server.

        Returns:
            List of prompt definitions.

        Raises:
            MCPSessionExpiredError: If session has expired.
            TransportError: If communication fails.
        """
        self._ensure_connected()

        if not self._supports_prompts():
            return []

        try:
            result = await self._transport.send_request("prompts/list")
            return result.get("prompts", [])
        except TransportClosedError:
            self._connected = False
            raise MCPSessionExpiredError(self.server_name)

    def _create_transport(self) -> Transport:
        """Create the appropriate transport for the server config."""
        if isinstance(self.config, McpStdioServerConfig):
            return StdioTransport(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
            )
        elif isinstance(self.config, McpSSEServerConfig):
            return SSETransport(
                url=self.config.url,
                headers=self.config.headers,
            )
        elif isinstance(self.config, McpHTTPServerConfig):
            return HTTPTransport(
                url=self.config.url,
                headers=self.config.headers,
            )
        elif isinstance(self.config, McpWebSocketServerConfig):
            return WebSocketTransport(
                url=self.config.url,
                headers=self.config.headers,
            )
        else:
            raise TransportError(f"Unsupported config type: {type(self.config)}")

    async def _initialize(self) -> None:
        """Initialize the MCP session."""
        try:
            result = await self._transport.send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                },
                "clientInfo": {
                    "name": "auracode-mcp-client",
                    "version": "1.0.0",
                },
            })
            self._capabilities = result.get("capabilities", {})

            # Send initialized notification
            await self._transport.send_notification("notifications/initialized")

        except TransportClosedError:
            self._connected = False
            raise MCPSessionExpiredError(self.server_name)

    def _ensure_connected(self) -> None:
        """Ensure the client is connected."""
        if not self._connected or self._transport is None:
            raise MCPSessionExpiredError(self.server_name)

    def _supports_resources(self) -> bool:
        """Check if server supports resources."""
        return bool(self._capabilities and self._capabilities.get("resources"))

    def _supports_prompts(self) -> bool:
        """Check if server supports prompts."""
        return bool(self._capabilities and self._capabilities.get("prompts"))

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
