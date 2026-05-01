"""
MCP skill discovery and integration.

This module provides functionality to discover and integrate
MCP servers as skills in the opencode skill system.
"""

import asyncio
from pathlib import Path
from typing import Any

from mcp.client.base import MCPClient, MCPSessionExpiredError
from mcp.config.types import McpServerConfig, ScopedMcpServerConfig
from mcp.config.manager import MCPConfigManager


class McpSkillDefinition:
    """
    Definition of a skill discovered from an MCP server.

    An MCP server can be exposed as a skill that provides access
    to all of its tools, resources, and prompts.
    """

    def __init__(
        self,
        server_name: str,
        server_config: McpServerConfig,
        description: str = "",
        capabilities: dict[str, Any] | None = None,
    ):
        """
        Initialize the MCP skill definition.

        Args:
            server_name: Name of the MCP server.
            server_config: Server configuration.
            description: Optional skill description.
            capabilities: Server capabilities (tools, resources, prompts).
        """
        self.server_name = server_name
        self.server_config = server_config
        self.description = description or f"MCP server: {server_name}"
        self.capabilities = capabilities or {}

    @property
    def name(self) -> str:
        """Get the skill name."""
        return f"mcp_{self.server_name}"

    @property
    def has_tools(self) -> bool:
        """Check if server provides tools."""
        return bool(self.capabilities.get("tools"))

    @property
    def has_resources(self) -> bool:
        """Check if server provides resources."""
        return bool(self.capabilities.get("resources"))

    @property
    def has_prompts(self) -> bool:
        """Check if server provides prompts."""
        return bool(self.capabilities.get("prompts"))

    def to_skill_definition(self) -> dict[str, Any]:
        """
        Convert to skill definition format.

        Returns:
            Skill definition compatible with the skill system.
        """
        return {
            "name": self.name,
            "description": self.description,
            "type": "mcp",
            "server_name": self.server_name,
            "server_config": self.server_config,
            "capabilities": self.capabilities,
        }


class McpSkillDiscoverer:
    """
    Discovers MCP servers and creates skill definitions.

    This class handles the discovery of MCP servers from various
    sources and converts them to skill definitions.
    """

    def __init__(self, config_manager: MCPConfigManager | None = None):
        """
        Initialize the MCP skill discoverer.

        Args:
            config_manager: Optional configuration manager.
        """
        self.config_manager = config_manager or MCPConfigManager()
        self._discovered_skills: dict[str, McpSkillDefinition] = {}

    async def discover_all_skills(
        self,
        include_disabled: bool = False,
    ) -> dict[str, McpSkillDefinition]:
        """
        Discover all MCP servers as skills.

        Args:
            include_disabled: Whether to include disabled servers.

        Returns:
            Dictionary mapping skill names to skill definitions.
        """
        configs = self.config_manager.get_all_configs(
            include_disabled=include_disabled
        )

        skills: dict[str, McpSkillDefinition] = {}

        for name, scoped_config in configs.items():
            if scoped_config.disabled:
                continue

            # Try to connect and discover capabilities
            skill = await self._discover_skill(name, scoped_config)
            if skill:
                skills[skill.name] = skill

        self._discovered_skills = skills
        return skills

    async def discover_skill(
        self,
        server_name: str,
    ) -> McpSkillDefinition | None:
        """
        Discover a specific MCP server as a skill.

        Args:
            server_name: Name of the MCP server.

        Returns:
            Skill definition or None if discovery fails.
        """
        configs = self.config_manager.get_all_configs()
        if server_name not in configs:
            return None

        scoped_config = configs[server_name]
        return await self._discover_skill(server_name, scoped_config)

    async def _discover_skill(
        self,
        server_name: str,
        scoped_config: ScopedMcpServerConfig,
    ) -> McpSkillDefinition | None:
        """
        Discover an MCP server's capabilities.

        Args:
            server_name: Name of the server.
            scoped_config: Scoped server configuration.

        Returns:
            Skill definition with capabilities, or None if connection fails.
        """
        client = MCPClient(server_name, scoped_config.config)

        try:
            # Connect to discover capabilities
            await client.connect()

            # Gather information
            capabilities: dict[str, Any] = {}

            # Check for tools
            try:
                tools = await client.list_tools()
                capabilities["tools"] = {
                    "available": True,
                    "count": len(tools),
                    "tools": tools,
                }
            except Exception:
                capabilities["tools"] = {"available": False}

            # Check for resources
            try:
                resources = await client.list_resources()
                capabilities["resources"] = {
                    "available": True,
                    "count": len(resources),
                    "resources": resources,
                }
            except Exception:
                capabilities["resources"] = {"available": False}

            # Check for prompts
            try:
                prompts = await client.list_prompts()
                capabilities["prompts"] = {
                    "available": True,
                    "count": len(prompts),
                    "prompts": prompts,
                }
            except Exception:
                capabilities["prompts"] = {"available": False}

            # Create skill definition
            description = f"MCP server providing"
            if capabilities["tools"]["available"]:
                description += f" {capabilities['tools']['count']} tools"
            if capabilities["resources"]["available"]:
                if capabilities["tools"]["available"]:
                    description += ","
                description += f" {capabilities['resources']['count']} resources"
            if capabilities["prompts"]["available"]:
                if capabilities["tools"]["available"] or capabilities["resources"]["available"]:
                    description += ","
                description += f" {capabilities['prompts']['count']} prompts"

            skill = McpSkillDefinition(
                server_name=server_name,
                server_config=scoped_config.config,
                description=description,
                capabilities=capabilities,
            )

            return skill

        except (MCPSessionExpiredError, Exception):
            # Connection failed, return None
            return None

        finally:
            await client.disconnect()

    def get_discovered_skills(self) -> dict[str, McpSkillDefinition]:
        """Get all previously discovered skills."""
        return self._discovered_skills.copy()

    def clear_cache(self) -> None:
        """Clear the discovered skills cache."""
        self._discovered_skills.clear()


class McpSkillExecutor:
    """
    Executes MCP skills by managing server connections.

    This class provides the execution layer for MCP skills,
    handling connection lifecycle and tool/resource/prompt access.
    """

    def __init__(self):
        """Initialize the MCP skill executor."""
        self._active_clients: dict[str, MCPClient] = {}

    async def execute_tool(
        self,
        server_name: str,
        server_config: McpServerConfig,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """
        Execute a tool on an MCP server.

        Args:
            server_name: Name of the MCP server.
            server_config: Server configuration.
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.

        Returns:
            Tool execution result.
        """
        client = await self._get_client(server_name, server_config)
        return await client.call_tool(tool_name, arguments)

    async def read_resource(
        self,
        server_name: str,
        server_config: McpServerConfig,
        uri: str,
    ) -> Any:
        """
        Read a resource from an MCP server.

        Args:
            server_name: Name of the MCP server.
            server_config: Server configuration.
            uri: Resource URI.

        Returns:
            Resource content.
        """
        client = await self._get_client(server_name, server_config)
        return await client.read_resource(uri)

    async def get_prompt(
        self,
        server_name: str,
        server_config: McpServerConfig,
        prompt_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Get a prompt from an MCP server.

        Args:
            server_name: Name of the MCP server.
            server_config: Server configuration.
            prompt_name: Name of the prompt.
            arguments: Optional prompt arguments.

        Returns:
            Prompt content.
        """
        client = await self._get_client(server_name, server_config)
        return await client._transport.send_request(
            "prompts/get",
            {
                "name": prompt_name,
                "arguments": arguments or {},
            },
        )

    async def close_server(self, server_name: str) -> None:
        """
        Close connection to an MCP server.

        Args:
            server_name: Name of the server to close.
        """
        if server_name in self._active_clients:
            await self._active_clients[server_name].disconnect()
            del self._active_clients[server_name]

    async def close_all(self) -> None:
        """Close all active server connections."""
        for client in self._active_clients.values():
            await client.disconnect()
        self._active_clients.clear()

    async def _get_client(
        self,
        server_name: str,
        server_config: McpServerConfig,
    ) -> MCPClient:
        """Get or create a client for the server."""
        if server_name not in self._active_clients:
            client = MCPClient(server_name, server_config)
            await client.connect()
            self._active_clients[server_name] = client

        return self._active_clients[server_name]


async def discover_mcp_skills(
    config_manager: MCPConfigManager | None = None,
) -> list[dict[str, Any]]:
    """
    Discover all MCP servers and return skill definitions.

    This is a convenience function for skill discovery.

    Args:
        config_manager: Optional configuration manager.

    Returns:
        List of skill definition dictionaries.
    """
    discoverer = McpSkillDiscoverer(config_manager)
    skills = await discoverer.discover_all_skills()

    return [skill.to_skill_definition() for skill in skills.values()]


async def register_mcp_skill_tools(
    server_name: str,
    server_config: McpServerConfig,
    tool_registry: dict = None,
) -> list[str]:
    """
    Register all tools, resources, and prompts from an MCP server.

    Args:
        server_name: Name of the MCP server.
        server_config: Server configuration.
        tool_registry: Optional tool registry.

    Returns:
        List of registered tool names.
    """
    from tools.registry import TOOL_REGISTRY

    if tool_registry is None:
        tool_registry = TOOL_REGISTRY

    client = MCPClient(server_name, server_config)
    registered_names = []

    try:
        await client.connect()

        # Register tools
        from mcp.tools.adapter import register_mcp_tools
        tool_names = await register_mcp_tools(server_name, client, tool_registry)
        registered_names.extend(tool_names)

        # Register resource tools
        from mcp.tools.resources import register_resource_tools
        resource_names = await register_resource_tools(
            server_name, client, tool_registry
        )
        registered_names.extend(resource_names)

        # Register prompt tools
        from mcp.tools.prompts import register_prompt_tools
        prompt_names = await register_prompt_tools(server_name, client, tool_registry)
        registered_names.extend(prompt_names)

    except Exception:
        pass

    finally:
        await client.disconnect()

    return registered_names
