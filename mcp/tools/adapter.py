"""
MCP tool adapter for integration with the tool registry.

This module adapts MCP tools to work with the existing tool system.
"""

import asyncio
from typing import Any

from mcp.client.base import MCPClient
from mcp.tools.validation import validate_and_truncate_output


class MCPToolAdapter:
    """
    Adapter for MCP tools to work with the tool registry.

    This adapter wraps MCP tools to provide a consistent interface
    for the tool registry.
    """

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        tool_description: str,
        tool_schema: dict[str, Any],
        mcp_client: MCPClient,
    ):
        """
        Initialize the MCP tool adapter.

        Args:
            server_name: Name of the MCP server.
            tool_name: Name of the tool on the server.
            tool_description: Description of the tool.
            tool_schema: JSON schema for tool parameters.
            mcp_client: The MCP client instance.
        """
        self.server_name = server_name
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.tool_schema = tool_schema
        self.mcp_client = mcp_client

        # Create the qualified name for this tool
        self.qualified_name = f"mcp__{server_name}__{tool_name}"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return f"{self.tool_description} (MCP: {self.server_name})"

    def get_parameters(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return self.tool_schema

    async def execute(self, arguments: dict[str, Any]) -> Any:
        """
        Execute the tool via the MCP client.

        Args:
            arguments: Tool arguments.

        Returns:
            Tool execution result (truncated if needed).
        """
        # Call the tool via MCP client
        result = await self.mcp_client.call_tool(self.tool_name, arguments)

        # Extract content from result
        content = result.get("content", [])
        if isinstance(content, list) and len(content) > 0:
            # Get the first text content
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    # Validate and truncate if needed
                    return await validate_and_truncate_output(text)

        # Return raw result if no text content
        return result

    def to_tool_definition(self) -> dict[str, Any]:
        """
        Convert to tool registry definition format.

        Returns:
            Tool definition compatible with the tool registry.
        """
        return {
            "description": self.description,
            "parameters": self.get_parameters(),
            "handler": self._create_handler(),
            "permission_level": "execute",  # MCP tools execute on the server
            "mcp_server": self.server_name,
            "mcp_tool": self.tool_name,
        }

    def _create_handler(self) -> callable:
        """Create an async handler for the tool."""

        async def handler(**kwargs):
            """Async handler wrapper."""
            return await self.execute(kwargs)

        # Return the async function directly
        return handler


def create_mcp_tool(
    server_name: str,
    tool_def: dict[str, Any],
    mcp_client: MCPClient,
) -> MCPToolAdapter:
    """
    Create an MCP tool adapter from a tool definition.

    Args:
        server_name: Name of the MCP server.
        tool_def: Tool definition from the server.
        mcp_client: The MCP client instance.

    Returns:
        MCPToolAdapter instance.
    """
    return MCPToolAdapter(
        server_name=server_name,
        tool_name=tool_def.get("name", ""),
        tool_description=tool_def.get("description", ""),
        tool_schema=tool_def.get("inputSchema", {}),
        mcp_client=mcp_client,
    )


async def register_mcp_tools(
    server_name: str,
    mcp_client: MCPClient,
    tool_registry: dict = None,
) -> list[str]:
    """
    Discover and register all tools from an MCP server.

    Args:
        server_name: Name of the MCP server.
        mcp_client: Connected MCP client.
        tool_registry: Optional tool registry (defaults to global).

    Returns:
        List of registered tool names.
    """
    if tool_registry is None:
        # Import here to avoid circular dependency
        from tools.registry import TOOL_REGISTRY
        tool_registry = TOOL_REGISTRY

    # List available tools
    tools = await mcp_client.list_tools()

    registered_names = []

    for tool_def in tools:
        # Create adapter
        adapter = create_mcp_tool(server_name, tool_def, mcp_client)

        # Convert to tool definition
        definition = adapter.to_tool_definition()

        # Register the tool
        try:
            from tools.registry import register_tool
            register_tool(adapter.qualified_name, definition)
            registered_names.append(adapter.qualified_name)
        except ValueError:
            # Tool already registered, skip
            continue

    return registered_names


async def unregister_mcp_tools(
    server_name: str,
    tool_registry: dict = None,
) -> None:
    """
    Unregister all tools from an MCP server.

    Args:
        server_name: Name of the MCP server.
        tool_registry: Optional tool registry (defaults to global).
    """
    if tool_registry is None:
        # Import here to avoid circular dependency
        from tools.registry import TOOL_REGISTRY
        tool_registry = TOOL_REGISTRY

    # Find all tools for this server
    tools_to_remove = [
        name
        for name in tool_registry.keys()
        if name.startswith(f"mcp__{server_name}__")
    ]

    # Remove them
    for name in tools_to_remove:
        tool_registry.pop(name, None)
