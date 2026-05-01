"""
MCP configuration validation.

This module provides validation functions for MCP configurations.
"""

import re
from typing import Any


class ConfigValidationError(Exception):
    """Raised when MCP configuration validation fails."""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(message)


def validate_url(url: str) -> bool:
    """Validate that a string is a valid URL."""
    if not url:
        return False
    # Basic URL validation
    url_pattern = re.compile(
        r"^(https?|wss?)://"  # http://, https://, ws://, or wss://
        r"([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}"  # domain
        r"(:\d+)?"  # optional port
        r"(/.*)?$",  # optional path
        re.IGNORECASE,
    )
    return bool(url_pattern.match(url))


def validate_command(command: str) -> bool:
    """Validate that a command string is not empty and looks valid."""
    if not command or not command.strip():
        return False
    # Check for obviously dangerous commands
    dangerous = ["rm -rf", "del /f", "format", "shutdown"]
    command_lower = command.lower()
    for dangerous_cmd in dangerous:
        if dangerous_cmd in command_lower:
            return False
    return True


def validate_mcp_config(config: dict[str, Any]) -> list[ConfigValidationError]:
    """
    Validate an MCP configuration dictionary.

    Returns a list of validation errors (empty if valid).
    """
    errors = []

    if not isinstance(config, dict):
        errors.append(ConfigValidationError("Configuration must be a dictionary"))
        return errors

    # Check for mcpServers key
    if "mcpServers" not in config:
        errors.append(ConfigValidationError("Missing 'mcpServers' key"))
        return errors

    mcp_servers = config.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        errors.append(ConfigValidationError("'mcpServers' must be a dictionary"))
        return errors

    # Validate each server config
    for server_name, server_config in mcp_servers.items():
        if not isinstance(server_config, dict):
            errors.append(
                ConfigValidationError(
                    f"Server '{server_name}' config must be a dictionary",
                    field=server_name,
                )
            )
            continue

        # Check for type field
        server_type = server_config.get("type")
        if server_type is None:
            # Default to stdio
            server_type = "stdio"

        # Validate based on type
        if server_type == "stdio":
            errors.extend(_validate_stdio_config(server_name, server_config))
        elif server_type in ("sse", "http", "ws"):
            errors.extend(_validate_remote_config(server_name, server_config, server_type))
        elif server_type == "sdk":
            errors.extend(_validate_sdk_config(server_name, server_config))
        else:
            errors.append(
                ConfigValidationError(
                    f"Unknown server type '{server_type}' for '{server_name}'",
                    field=server_name,
                )
            )

    return errors


def _validate_stdio_config(
    server_name: str, config: dict[str, Any]
) -> list[ConfigValidationError]:
    """Validate a stdio server configuration."""
    errors = []

    command = config.get("command")
    if not command:
        errors.append(
            ConfigValidationError(
                f"stdio server '{server_name}' missing 'command' field",
                field=f"{server_name}.command",
            )
        )
    elif not validate_command(command):
        errors.append(
            ConfigValidationError(
                f"Invalid command '{command}' for server '{server_name}'",
                field=f"{server_name}.command",
            )
        )

    # Validate args if present
    args = config.get("args")
    if args is not None:
        if not isinstance(args, list):
            errors.append(
                ConfigValidationError(
                    f"'args' must be a list for server '{server_name}'",
                    field=f"{server_name}.args",
                )
            )
        else:
            for i, arg in enumerate(args):
                if not isinstance(arg, str):
                    errors.append(
                        ConfigValidationError(
                            f"Arg {i} must be a string for server '{server_name}'",
                            field=f"{server_name}.args.{i}",
                        )
                    )

    # Validate env if present
    env = config.get("env")
    if env is not None:
        if not isinstance(env, dict):
            errors.append(
                ConfigValidationError(
                    f"'env' must be a dictionary for server '{server_name}'",
                    field=f"{server_name}.env",
                )
            )
        else:
            for key, value in env.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    errors.append(
                        ConfigValidationError(
                            f"Environment variables must be strings for server '{server_name}'",
                            field=f"{server_name}.env",
                        )
                    )

    return errors


def _validate_remote_config(
    server_name: str, config: dict[str, Any], server_type: str
) -> list[ConfigValidationError]:
    """Validate a remote (SSE/HTTP/WS) server configuration."""
    errors = []

    url = config.get("url")
    if not url:
        errors.append(
            ConfigValidationError(
                f"{server_type} server '{server_name}' missing 'url' field",
                field=f"{server_name}.url",
            )
        )
    elif not validate_url(url):
        errors.append(
            ConfigValidationError(
                f"Invalid URL '{url}' for server '{server_name}'",
                field=f"{server_name}.url",
            )
        )

    # Validate headers if present
    headers = config.get("headers")
    if headers is not None:
        if not isinstance(headers, dict):
            errors.append(
                ConfigValidationError(
                    f"'headers' must be a dictionary for server '{server_name}'",
                    field=f"{server_name}.headers",
                )
            )

    return errors


def _validate_sdk_config(
    server_name: str, config: dict[str, Any]
) -> list[ConfigValidationError]:
    """Validate an SDK server configuration."""
    errors = []

    name = config.get("name")
    if not name:
        errors.append(
            ConfigValidationError(
                f"SDK server '{server_name}' missing 'name' field",
                field=f"{server_name}.name",
            )
        )

    return errors


def validate_and_raise(config: dict[str, Any]) -> None:
    """
    Validate configuration and raise exception if invalid.

    Raises:
        ConfigValidationError: If configuration is invalid.
    """
    errors = validate_mcp_config(config)
    if errors:
        raise ConfigValidationError(
            f"Configuration validation failed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {e.message}" for e in errors)
        )
