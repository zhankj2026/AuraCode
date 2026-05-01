"""
MCP resource tools.

This module provides tools for accessing MCP server resources,
including listing and reading resources.
"""

import asyncio
from typing import Any

from mcp.client.base import MCPClient, MCPSessionExpiredError


class ListMcpResourcesTool:
    """
    Tool for listing available resources from an MCP server.

    Resources represent data sources that the MCP server can provide
    access to, such as files, database records, or API endpoints.
    """

    def __init__(self, server_name: str, mcp_client: MCPClient):
        """
        Initialize the resource listing tool.

        Args:
            server_name: Name of the MCP server.
            mcp_client: Connected MCP client.
        """
        self.server_name = server_name
        self.mcp_client = mcp_client

    @property
    def name(self) -> str:
        """Get the tool name."""
        return f"mcp__{self.server_name}__list_resources"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return f"List available resources from {self.server_name} MCP server"

    def get_parameters(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self) -> dict[str, Any]:
        """
        Execute the resource listing.

        Returns:
            Dictionary with list of resources.

        Raises:
            MCPSessionExpiredError: If session has expired.
        """
        try:
            resources = await self.mcp_client.list_resources()

            return {
                "server": self.server_name,
                "count": len(resources),
                "resources": resources,
            }

        except MCPSessionExpiredError:
            raise
        except Exception as e:
            return {
                "server": self.server_name,
                "error": str(e),
                "resources": [],
            }

    def to_tool_definition(self) -> dict[str, Any]:
        """Convert to tool registry definition format."""
        return {
            "description": self.description,
            "parameters": self.get_parameters(),
            "handler": self._create_handler(),
            "permission_level": "read",
            "mcp_server": self.server_name,
            "mcp_resource_tool": "list",
        }

    def _create_handler(self) -> callable:
        """Create an async handler for the tool."""
        async def handler(**kwargs):
            return await self.execute()
        return handler


class ReadMcpResourceTool:
    """
    Tool for reading a specific resource from an MCP server.

    This tool retrieves the actual content of a resource by its URI.
    """

    def __init__(self, server_name: str, mcp_client: MCPClient):
        """
        Initialize the resource reading tool.

        Args:
            server_name: Name of the MCP server.
            mcp_client: Connected MCP client.
        """
        self.server_name = server_name
        self.mcp_client = mcp_client

    @property
    def name(self) -> str:
        """Get the tool name."""
        return f"mcp__{self.server_name}__read_resource"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return f"Read a resource from {self.server_name} MCP server by URI"

    def get_parameters(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "URI of the resource to read",
                },
            },
            "required": ["uri"],
        }

    async def execute(self, uri: str) -> dict[str, Any]:
        """
        Execute the resource reading.

        Args:
            uri: Resource URI to read.

        Returns:
            Dictionary with resource content.

        Raises:
            MCPSessionExpiredError: If session has expired.
        """
        try:
            content = await self.mcp_client.read_resource(uri)

            # Handle different content formats
            if isinstance(content, str):
                return {
                    "server": self.server_name,
                    "uri": uri,
                    "content": content,
                    "type": "text",
                }
            elif isinstance(content, list):
                # Multiple content blocks
                return {
                    "server": self.server_name,
                    "uri": uri,
                    "content": content,
                    "type": "multipart",
                }
            else:
                return {
                    "server": self.server_name,
                    "uri": uri,
                    "content": str(content),
                    "type": "unknown",
                }

        except MCPSessionExpiredError:
            raise
        except Exception as e:
            return {
                "server": self.server_name,
                "uri": uri,
                "error": str(e),
            }

    def to_tool_definition(self) -> dict[str, Any]:
        """Convert to tool registry definition format."""
        return {
            "description": self.description,
            "parameters": self.get_parameters(),
            "handler": self._create_handler(),
            "permission_level": "read",
            "mcp_server": self.server_name,
            "mcp_resource_tool": "read",
        }

    def _create_handler(self) -> callable:
        """Create an async handler for the tool."""
        async def handler(**kwargs):
            uri = kwargs.get("uri", "")
            return await self.execute(uri)
        return handler


async def register_resource_tools(
    server_name: str,
    mcp_client: MCPClient,
    tool_registry: dict = None,
) -> list[str]:
    """
    Register resource access tools for an MCP server.

    Args:
        server_name: Name of the MCP server.
        mcp_client: Connected MCP client.
        tool_registry: Optional tool registry (defaults to global).

    Returns:
        List of registered tool names.
    """
    if tool_registry is None:
        from tools.registry import TOOL_REGISTRY, register_tool
        tool_registry = TOOL_REGISTRY

    registered_names = []

    # Only register if server supports resources
    if not mcp_client._supports_resources():
        return registered_names

    # Register list tool
    list_tool = ListMcpResourcesTool(server_name, mcp_client)
    try:
        from tools.registry import register_tool
        register_tool(list_tool.name, list_tool.to_tool_definition())
        registered_names.append(list_tool.name)
    except ValueError:
        pass

    # Register read tool
    read_tool = ReadMcpResourceTool(server_name, mcp_client)
    try:
        from tools.registry import register_tool
        register_tool(read_tool.name, read_tool.to_tool_definition())
        registered_names.append(read_tool.name)
    except ValueError:
        pass

    return registered_names


async def unregister_resource_tools(
    server_name: str,
    tool_registry: dict = None,
) -> None:
    """
    Unregister resource tools for an MCP server.

    Args:
        server_name: Name of the MCP server.
        tool_registry: Optional tool registry (defaults to global).
    """
    if tool_registry is None:
        from tools.registry import TOOL_REGISTRY
        tool_registry = TOOL_REGISTRY

    # Resource tools to remove
    resource_tools = [
        f"mcp__{server_name}__list_resources",
        f"mcp__{server_name}__read_resource",
    ]

    for name in resource_tools:
        tool_registry.pop(name, None)
