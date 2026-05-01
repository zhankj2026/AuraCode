"""
Environment variable resolution for MCP plugins.

This module provides functionality to expand and resolve environment
variables in MCP server configurations.
"""

import os
import re
from typing import Any


class EnvExpansionError(Exception):
    """Raised when environment variable expansion fails."""

    def __init__(self, message: str, missing_vars: list[str] | None = None):
        self.message = message
        self.missing_vars = missing_vars or []
        super().__init__(message)


def expand_env_vars(value: str) -> tuple[str, list[str]]:
    """
    Expand environment variables in a string.

    Supports ${VAR} and $VAR syntax.

    Args:
        value: The string to expand.

    Returns:
        Tuple of (expanded_value, list_of_missing_vars).
    """
    if not isinstance(value, str):
        return value, []

    missing_vars = []

    def replace_var(match: re.Match) -> str:
        var_name = match.group(1) or match.group(2)
        if var_name in os.environ:
            return os.environ[var_name]
        else:
            missing_vars.append(var_name)
            return match.group(0)

    # Replace ${VAR} first
    result = re.sub(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}", replace_var, value)

    # Then replace $VAR
    result = re.sub(r"\$([a-zA-Z_][a-zA-Z0-9_]*)", replace_var, result)

    return result, missing_vars


def substitute_plugin_vars(value: str, plugin: Any) -> str:
    """
    Substitute plugin-specific variables.

    Supported variables:
    - ${CLAUDE_PLUGIN_ROOT}: Plugin directory path
    - ${CLAUDE_PLUGIN_DATA}: Plugin data directory path

    Args:
        value: The string to substitute.
        plugin: Plugin object with 'path' and 'source' attributes.

    Returns:
        String with plugin variables substituted.
    """
    if not isinstance(value, str):
        return value

    plugin_root = getattr(plugin, "path", "")
    plugin_source = getattr(plugin, "source", "")

    # Replace plugin root
    value = value.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root)

    # Replace plugin data directory
    if plugin_source:
        import os
        plugin_data = os.path.expanduser(
            f"~/.config/opencode/plugins/{plugin_source}"
        )
        value = value.replace("${CLAUDE_PLUGIN_DATA}", plugin_data)

    return value


def substitute_user_config_vars(value: str, user_config: dict[str, str]) -> str:
    """
    Substitute user configuration variables.

    Supports ${user_config.KEY} syntax.

    Args:
        value: The string to substitute.
        user_config: Dictionary of user configuration values.

    Returns:
        String with user config variables substituted.

    Raises:
        EnvExpansionError: If a required user config key is missing.
    """
    if not isinstance(value, str):
        return value

    missing_vars = []

    def replace_config_var(match: re.Match) -> str:
        config_key = match.group(1)
        if config_key in user_config:
            return str(user_config[config_key])
        else:
            missing_vars.append(config_key)
            return match.group(0)

    # Replace ${user_config.KEY}
    result = re.sub(
        r"\$\{user_config\.([a-zA-Z_][a-zA-Z0-9_]*)\}",
        replace_config_var,
        value,
    )

    if missing_vars:
        raise EnvExpansionError(
            f"Missing user configuration variables: {', '.join(missing_vars)}",
            missing_vars=missing_vars,
        )

    return result


def resolve_mcp_env(
    config: Any,
    plugin: Any = None,
    user_config: dict[str, str] | None = None,
) -> Any:
    """
    Resolve environment variables in an MCP configuration.

    Resolution order:
    1. Plugin-specific variables (${CLAUDE_PLUGIN_ROOT}, ${CLAUDE_PLUGIN_DATA})
    2. User config variables (${user_config.KEY})
    3. System environment variables (${VAR}, $VAR)

    Args:
        config: The configuration to resolve.
        plugin: Optional plugin object.
        user_config: Optional user configuration values.

    Returns:
        Resolved configuration.

    Raises:
        EnvExpansionError: If required variables are missing.
    """
    if isinstance(config, str):
        # Step 1: Plugin variables
        if plugin:
            config = substitute_plugin_vars(config, plugin)

        # Step 2: User config variables
        if user_config:
            config = substitute_user_config_vars(config, user_config)

        # Step 3: Environment variables
        config, missing = expand_env_vars(config)

        return config

    elif isinstance(config, dict):
        result = {}
        for key, value in config.items():
            if key == "env" and isinstance(value, dict):
                # Environment variables need special handling
                result[key] = {}
                for env_key, env_value in value.items():
                    result[key][env_key] = resolve_mcp_env(
                        env_value, plugin, user_config
                    )
            else:
                result[key] = resolve_mcp_env(value, plugin, user_config)
        return result

    elif isinstance(config, list):
        return [resolve_mcp_env(item, plugin, user_config) for item in config]

    else:
        return config
