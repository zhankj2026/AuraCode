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
MCP skill registry.

This module provides integration between MCP servers and the auracode
skill system, allowing MCP tools to be exposed as skills.
"""

import asyncio
from pathlib import Path
from typing import Any, Callable

from mcp.skills import McpSkillDiscoverer, McpSkillExecutor
from mcp.config.manager import MCPConfigManager


# Type aliases for skill system integration
CreateSkillCommandFunc = Callable[..., Any]
ParseSkillFrontmatterFunc = Callable[[dict[str, Any]], dict[str, Any]]


class McpSkillBuilders:
    """
    Registry for skill builder functions.

    This allows MCP skills to be created using the same mechanisms
    as file-based skills.
    """

    _create_skill_command: CreateSkillCommandFunc | None = None
    _parse_skill_frontmatter: ParseSkillFrontmatterFunc | None = None

    @classmethod
    def register_builders(
        cls,
        create_skill_command: CreateSkillCommandFunc,
        parse_skill_frontmatter: ParseSkillFrontmatterFunc,
    ) -> None:
        """
        Register the skill builder functions.

        Args:
            create_skill_command: Function to create a skill command.
            parse_skill_frontmatter: Function to parse skill frontmatter.
        """
        cls._create_skill_command = create_skill_command
        cls._parse_skill_frontmatter = parse_skill_frontmatter

    @classmethod
    def get_builders(cls) -> tuple[CreateSkillCommandFunc, ParseSkillFrontmatterFunc]:
        """Get the registered skill builder functions."""
        if cls._create_skill_command is None or cls._parse_skill_frontmatter is None:
            raise RuntimeError(
                "MCP skill builders not registered. "
                "Call register_builders() first."
            )
        return cls._create_skill_command, cls._parse_skill_frontmatter


async def create_mcp_skill_command(
    server_name: str,
    skill_file: Path,
    mcp_config_manager: MCPConfigManager | None = None,
):
    """
    Create a skill command from an MCP server.

    This function creates an auracode skill command that wraps
    an MCP server, exposing its tools as skill commands.

    Args:
        server_name: Name of the MCP server.
        skill_file: Path to the skill file (for metadata).
        mcp_config_manager: Optional config manager.

    Returns:
        Skill command function.
    """
    config_manager = mcp_config_manager or MCPConfigManager()
    configs = config_manager.get_all_configs()

    if server_name not in configs:
        raise ValueError(f"MCP server '{server_name}' not found in configuration")

    scoped_config = configs[server_name]

    # Get the skill builder functions
    create_skill_command, _ = McpSkillBuilders.get_builders()

    # Create skill metadata
    skill_metadata = {
        "name": f"mcp_{server_name}",
        "description": f"MCP server: {server_name}",
        "type": "mcp",
        "server_name": server_name,
        "server_config": scoped_config.config,
    }

    # Create the skill command using the registered builder
    skill_command = create_skill_command(
        skill_file=skill_file,
        metadata=skill_metadata,
    )

    # Wrap the skill command to add MCP-specific behavior
    async def mcp_skill_wrapper(*args, **kwargs):
        """Wrapper for MCP skill execution."""
        executor = McpSkillExecutor()

        try:
            # Execute the skill command
            result = await skill_command(*args, **kwargs)

            return result

        finally:
            # Clean up connections
            await executor.close_all()

    return mcp_skill_wrapper


async def discover_and_create_mcp_skills(
    skills_dir: Path,
    mcp_config_manager: MCPConfigManager | None = None,
) -> dict[str, Callable]:
    """
    Discover all MCP servers and create skill commands for them.

    Args:
        skills_dir: Directory to store MCP skill files.
        mcp_config_manager: Optional config manager.

    Returns:
        Dictionary mapping skill names to skill command functions.
    """
    from mcp.skills import discover_mcp_skills

    skills_dir = Path(skills_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)

    config_manager = mcp_config_manager or MCPConfigManager()

    # Discover all MCP skills
    skill_definitions = await discover_mcp_skills(config_manager)

    skill_commands: dict[str, Callable] = {}

    for skill_def in skill_definitions:
        server_name = skill_def.get("server_name")
        if not server_name:
            continue

        # Create a skill file for metadata
        skill_file = skills_dir / f"mcp_{server_name}.md"

        # Write skill metadata to file
        skill_file.write_text(
            f"""---
name: mcp_{server_name}
description: {skill_def.get('description', f'MCP server: {server_name}')}
type: mcp
server_name: {server_name}
---

MCP Skill: {server_name}

This skill provides access to the {server_name} MCP server.

**Capabilities:**
"""
        )

        capabilities = skill_def.get("capabilities", {})
        if capabilities.get("tools", {}).get("available"):
            tools_info = capabilities["tools"]
            skill_file.write_text(
                f"- Tools: {tools_info.get('count', 0)} available\n",
                append=True,
            )

        if capabilities.get("resources", {}).get("available"):
            resources_info = capabilities["resources"]
            skill_file.write_text(
                f"- Resources: {resources_info.get('count', 0)} available\n",
                append=True,
            )

        if capabilities.get("prompts", {}).get("available"):
            prompts_info = capabilities["prompts"]
            skill_file.write_text(
                f"- Prompts: {prompts_info.get('count', 0)} available\n",
                append=True,
            )

        # Create the skill command
        try:
            skill_command = await create_mcp_skill_command(
                server_name=server_name,
                skill_file=skill_file,
                mcp_config_manager=config_manager,
            )
            skill_commands[f"mcp_{server_name}"] = skill_command
        except Exception:
            # Skip servers that can't be connected to
            continue

    return skill_commands


def register_mcp_skill_builders(
    create_skill_command: CreateSkillCommandFunc,
    parse_skill_frontmatter: ParseSkillFrontmatterFunc,
) -> None:
    """
    Register the skill builder functions for MCP skill integration.

    This should be called during application initialization to enable
    MCP skill discovery and creation.

    Args:
        create_skill_command: Function to create a skill command.
        parse_skill_frontmatter: Function to parse skill frontmatter.

    Example:
        ```python
        from skills.loader import create_skill_command, parse_skill_frontmatter
        from mcp.skills.registry import register_mcp_skill_builders

        register_mcp_skill_builders(create_skill_command, parse_skill_frontmatter)
        ```
    """
    McpSkillBuilders.register_builders(
        create_skill_command,
        parse_skill_frontmatter,
    )


async def load_mcp_skills_to_registry(
    skill_registry: dict,
    skills_dir: Path,
    mcp_config_manager: MCPConfigManager | None = None,
) -> list[str]:
    """
    Load MCP skills into the skill registry.

    Args:
        skill_registry: The skill registry to update.
        skills_dir: Directory containing MCP skill files.
        mcp_config_manager: Optional config manager.

    Returns:
        List of loaded skill names.
    """
    skill_commands = await discover_and_create_mcp_skills(
        skills_dir=skills_dir,
        mcp_config_manager=mcp_config_manager,
    )

    loaded_names = []

    for skill_name, skill_command in skill_commands.items():
        try:
            skill_registry[skill_name] = skill_command
            loaded_names.append(skill_name)
        except Exception:
            continue

    return loaded_names


class McpSkillFrontmatterParser:
    """
    Parser for MCP skill frontmatter.

    This handles parsing the metadata from MCP skill files,
    which contain server configuration and capability information.
    """

    @staticmethod
    def parse(frontmatter: dict[str, Any]) -> dict[str, Any]:
        """
        Parse MCP skill frontmatter.

        Args:
            frontmatter: The frontmatter dictionary from the skill file.

        Returns:
            Parsed skill metadata with MCP-specific fields.
        """
        # Get the registered parser function
        _, parse_frontmatter = McpSkillBuilders.get_builders()

        # Use the base parser
        base_metadata = parse_frontmatter(frontmatter)

        # Add MCP-specific fields
        mcp_metadata = {
            **base_metadata,
            "mcp_server_name": frontmatter.get("server_name"),
            "mcp_server_config": frontmatter.get("server_config"),
            "mcp_capabilities": frontmatter.get("capabilities", {}),
        }

        return mcp_metadata

    @staticmethod
    def validate(frontmatter: dict[str, Any]) -> list[str]:
        """
        Validate MCP skill frontmatter.

        Args:
            frontmatter: The frontmatter dictionary to validate.

        Returns:
            List of validation errors (empty if valid).
        """
        errors = []

        # Check required fields
        if "server_name" not in frontmatter:
            errors.append("Missing required field: server_name")

        # Check type
        skill_type = frontmatter.get("type")
        if skill_type != "mcp":
            errors.append(f"Invalid type: {skill_type} (expected 'mcp')")

        return errors


# Export the registry functions
__all__ = [
    "McpSkillBuilders",
    "register_mcp_skill_builders",
    "create_mcp_skill_command",
    "discover_and_create_mcp_skills",
    "load_mcp_skills_to_registry",
    "McpSkillFrontmatterParser",
]
