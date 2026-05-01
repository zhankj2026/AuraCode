"""
MCP string utility functions.

This module provides utility functions for parsing and manipulating
MCP server and tool name strings.
"""

import re


def normalize_name_for_mcp(name: str) -> str:
    """
    Normalize a name for use in MCP tool names.

    Converts to lowercase and replaces non-alphanumeric characters
    with underscores.

    Args:
        name: The name to normalize.

    Returns:
        Normalized name.
    """
    # Replace non-alphanumeric characters with underscores
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    # Remove leading/trailing underscores
    normalized = normalized.strip("_")
    # Convert to lowercase
    return normalized.lower()


def mcp_info_from_string(
    tool_string: str,
) -> dict[str, str] | None:
    """
    Extract MCP server information from a tool name string.

    Expected format: "mcp__serverName__toolName"

    Args:
        tool_string: The string to parse.

    Returns:
        Dict with 'server_name' and optional 'tool_name', or None if not a valid MCP name.

    Examples:
        >>> mcp_info_from_string("mcp__github__create_issue")
        {'server_name': 'github', 'tool_name': 'create_issue'}

        >>> mcp_info_from_string("mcp__github")
        {'server_name': 'github', 'tool_name': None}
    """
    parts = tool_string.split("__")
    if len(parts) < 2 or parts[0] != "mcp":
        return None

    server_name = parts[1]
    tool_name = parts[2] if len(parts) > 2 else None

    return {
        "server_name": server_name,
        "tool_name": tool_name,
    }


def get_mcp_prefix(server_name: str) -> str:
    """
    Get the MCP tool/command name prefix for a server.

    Args:
        server_name: Name of the MCP server.

    Returns:
        The prefix string (e.g., "mcp__github__").

    Examples:
        >>> get_mcp_prefix("GitHub")
        'mcp__github__'
    """
    normalized = normalize_name_for_mcp(server_name)
    return f"mcp__{normalized}__"


def build_mcp_tool_name(server_name: str, tool_name: str) -> str:
    """
    Build a fully qualified MCP tool name.

    Inverse of mcp_info_from_string().

    Args:
        server_name: Name of the MCP server (unnormalized).
        tool_name: Name of the tool (unnormalized).

    Returns:
        The fully qualified name (e.g., "mcp__server__tool").

    Examples:
        >>> build_mcp_tool_name("GitHub", "Create Issue")
        'mcp__github__create_issue'
    """
    prefix = get_mcp_prefix(server_name)
    normalized_tool = normalize_name_for_mcp(tool_name)
    return f"{prefix}{normalized_tool}"


def get_mcp_display_name(full_name: str, server_name: str) -> str:
    """
    Extract the display name from an MCP tool/command name.

    Args:
        full_name: The full MCP tool/command name (e.g., "mcp__server_name__tool_name").
        server_name: The server name to remove from the prefix.

    Returns:
        The display name without the MCP prefix.

    Examples:
        >>> get_mcp_display_name("mcp__github__create_issue", "github")
        'create_issue'
    """
    prefix = get_mcp_prefix(server_name)
    return full_name.replace(prefix, "")


def extract_mcp_tool_display_name(user_facing_name: str) -> str:
    """
    Extract just the tool display name from a user-facing name.

    Args:
        user_facing_name: The full user-facing name
            (e.g., "github - Add comment to issue (MCP)").

    Returns:
        The display name without server prefix and (MCP) suffix.

    Examples:
        >>> extract_mcp_tool_display_name("github - Add comment to issue (MCP)")
        'Add comment to issue'
    """
    # Remove the (MCP) suffix if present
    without_suffix = re.sub(r"\s*\(MCP\)\s*$", "", user_facing_name).strip()

    # Remove the server prefix (everything before " - ")
    dash_index = without_suffix.find(" - ")
    if dash_index != -1:
        return without_suffix[dash_index + 3 :].strip()

    # If no dash found, return the string without (MCP)
    return without_suffix


def get_tool_name_for_permission_check(
    tool: dict[str, any],
) -> str:
    """
    Get the name to use for permission rule matching.

    For MCP tools, uses the fully qualified mcp__server__tool name
    so that deny rules targeting builtins (e.g., "Write") don't
    match unprefixed MCP replacements that share the same display name.

    Args:
        tool: Tool dictionary with 'name' and optional 'mcp_info'.

    Returns:
        The name to use for permission checking.
    """
    mcp_info = tool.get("mcp_info")
    if mcp_info:
        server_name = mcp_info.get("server_name", "")
        tool_name = mcp_info.get("tool_name", "")
        if tool_name:
            return build_mcp_tool_name(server_name, tool_name)

    return tool.get("name", "")
