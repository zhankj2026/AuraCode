"""
MCP prompt tools.

This module provides tools for accessing MCP server prompts,
including listing and getting prompts.
"""

import asyncio
from typing import Any

from mcp.client.base import MCPClient, MCPSessionExpiredError


class ListMcpPromptsTool:
    """
    Tool for listing available prompts from an MCP server.

    Prompts are pre-defined templates that the MCP server provides,
    which can be used to generate specific types of messages or queries.
    """

    def __init__(self, server_name: str, mcp_client: MCPClient):
        """
        Initialize the prompt listing tool.

        Args:
            server_name: Name of the MCP server.
            mcp_client: Connected MCP client.
        """
        self.server_name = server_name
        self.mcp_client = mcp_client

    @property
    def name(self) -> str:
        """Get the tool name."""
        return f"mcp__{self.server_name}__list_prompts"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return f"List available prompts from {self.server_name} MCP server"

    def get_parameters(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self) -> dict[str, Any]:
        """
        Execute the prompt listing.

        Returns:
            Dictionary with list of prompts.

        Raises:
            MCPSessionExpiredError: If session has expired.
        """
        try:
            prompts = await self.mcp_client.list_prompts()

            return {
                "server": self.server_name,
                "count": len(prompts),
                "prompts": prompts,
            }

        except MCPSessionExpiredError:
            raise
        except Exception as e:
            return {
                "server": self.server_name,
                "error": str(e),
                "prompts": [],
            }

    def to_tool_definition(self) -> dict[str, Any]:
        """Convert to tool registry definition format."""
        return {
            "description": self.description,
            "parameters": self.get_parameters(),
            "handler": self._create_handler(),
            "permission_level": "read",
            "mcp_server": self.server_name,
            "mcp_prompt_tool": "list",
        }

    def _create_handler(self) -> callable:
        """Create an async handler for the tool."""
        async def handler(**kwargs):
            return await self.execute()
        return handler


class GetMcpPromptTool:
    """
    Tool for getting a specific prompt from an MCP server.

    This tool retrieves a prompt template and optionally fills it
    with provided arguments.
    """

    def __init__(self, server_name: str, mcp_client: MCPClient):
        """
        Initialize the prompt getting tool.

        Args:
            server_name: Name of the MCP server.
            mcp_client: Connected MCP client.
        """
        self.server_name = server_name
        self.mcp_client = mcp_client

    @property
    def name(self) -> str:
        """Get the tool name."""
        return f"mcp__{self.server_name}__get_prompt"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return f"Get a prompt from {self.server_name} MCP server by name"

    def get_parameters(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the prompt to get",
                },
                "arguments": {
                    "type": "object",
                    "description": "Optional arguments to fill the prompt template",
                },
            },
            "required": ["name"],
        }

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute the prompt getting.

        Args:
            name: Prompt name to get.
            arguments: Optional arguments for the prompt template.

        Returns:
            Dictionary with prompt content.

        Raises:
            MCPSessionExpiredError: If session has expired.
        """
        try:
            # Get the prompt
            result = await self.mcp_client._transport.send_request(
                "prompts/get",
                {
                    "name": name,
                    "arguments": arguments or {},
                },
            )

            return {
                "server": self.server_name,
                "name": name,
                "prompt": result,
            }

        except MCPSessionExpiredError:
            raise
        except Exception as e:
            return {
                "server": self.server_name,
                "name": name,
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
            "mcp_prompt_tool": "get",
        }

    def _create_handler(self) -> callable:
        """Create an async handler for the tool."""
        async def handler(**kwargs):
            name = kwargs.get("name", "")
            arguments = kwargs.get("arguments")
            return await self.execute(name, arguments)
        return handler


async def register_prompt_tools(
    server_name: str,
    mcp_client: MCPClient,
    tool_registry: dict = None,
) -> list[str]:
    """
    Register prompt tools for an MCP server.

    Args:
        server_name: Name of the MCP server.
        mcp_client: Connected MCP client.
        tool_registry: Optional tool registry (defaults to global).

    Returns:
        List of registered tool names.
    """
    if tool_registry is None:
        from tools.registry import TOOL_REGISTRY
        tool_registry = TOOL_REGISTRY

    registered_names = []

    # Only register if server supports prompts
    if not mcp_client._supports_prompts():
        return registered_names

    # Register list tool
    list_tool = ListMcpPromptsTool(server_name, mcp_client)
    try:
        from tools.registry import register_tool
        register_tool(list_tool.name, list_tool.to_tool_definition())
        registered_names.append(list_tool.name)
    except ValueError:
        pass

    # Register get tool
    get_tool = GetMcpPromptTool(server_name, mcp_client)
    try:
        from tools.registry import register_tool
        register_tool(get_tool.name, get_tool.to_tool_definition())
        registered_names.append(get_tool.name)
    except ValueError:
        pass

    return registered_names


async def unregister_prompt_tools(
    server_name: str,
    tool_registry: dict = None,
) -> None:
    """
    Unregister prompt tools for an MCP server.

    Args:
        server_name: Name of the MCP server.
        tool_registry: Optional tool registry (defaults to global).
    """
    if tool_registry is None:
        from tools.registry import TOOL_REGISTRY
        tool_registry = TOOL_REGISTRY

    # Prompt tools to remove
    prompt_tools = [
        f"mcp__{server_name}__list_prompts",
        f"mcp__{server_name}__get_prompt",
    ]

    for name in prompt_tools:
        tool_registry.pop(name, None)
