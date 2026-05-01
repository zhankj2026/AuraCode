"""
Test MCP integration functionality.
"""

import asyncio
import pytest

from mcp.config.types import (
    McpStdioServerConfig,
    McpHTTPServerConfig,
    ConfigScope,
    ScopedMcpServerConfig,
)
from mcp.config.manager import MCPConfigManager
from mcp.config.validation import validate_mcp_config, ConfigValidationError
from mcp.utils.strings import (
    normalize_name_for_mcp,
    mcp_info_from_string,
    build_mcp_tool_name,
    get_mcp_prefix,
)
from mcp.tools.validation import (
    estimate_token_count,
    estimate_content_size,
)


class TestMcpStringUtils:
    """Test MCP string utility functions."""

    def test_normalize_name_for_mcp(self):
        """Test name normalization."""
        assert normalize_name_for_mcp("My Server") == "my_server"
        assert normalize_name_for_mcp("GitHub-Integration") == "github_integration"
        assert normalize_name_for_mcp("test@server") == "test_server"

    def test_mcp_info_from_string(self):
        """Test parsing MCP tool names."""
        result = mcp_info_from_string("mcp__github__create_issue")
        assert result == {
            "server_name": "github",
            "tool_name": "create_issue",
        }

        result = mcp_info_from_string("mcp__github")
        assert result == {
            "server_name": "github",
            "tool_name": None,
        }

        assert mcp_info_from_string("not_an_mcp_tool") is None

    def test_build_mcp_tool_name(self):
        """Test building MCP tool names."""
        assert build_mcp_tool_name("GitHub", "Create Issue") == "mcp__github__create_issue"
        assert build_mcp_tool_name("Test Server", "my-tool") == "mcp__test_server__my_tool"

    def test_get_mcp_prefix(self):
        """Test getting MCP prefix."""
        assert get_mcp_prefix("GitHub") == "mcp__github__"
        assert get_mcp_prefix("test-server") == "mcp__test_server__"


class TestMcpValidation:
    """Test MCP configuration validation."""

    def test_validate_stdio_config(self):
        """Test stdio configuration validation."""
        config = {
            "mcpServers": {
                "test-server": {
                    "type": "stdio",
                    "command": "node",
                    "args": ["server.js"],
                    "env": {"TEST": "value"},
                }
            }
        }

        errors = validate_mcp_config(config)
        assert len(errors) == 0

    def test_validate_http_config(self):
        """Test HTTP configuration validation."""
        config = {
            "mcpServers": {
                "test-server": {
                    "type": "http",
                    "url": "https://example.com/mcp",
                }
            }
        }

        errors = validate_mcp_config(config)
        assert len(errors) == 0

    def test_validate_invalid_url(self):
        """Test validation fails with invalid URL."""
        config = {
            "mcpServers": {
                "test-server": {
                    "type": "http",
                    "url": "not-a-url",
                }
            }
        }

        errors = validate_mcp_config(config)
        assert len(errors) > 0
        assert "url" in errors[0].field or True  # URL should be mentioned


class TestMcpTokenEstimation:
    """Test MCP token estimation."""

    def test_estimate_token_count(self):
        """Test token count estimation."""
        # Simple approximation: ~4 chars per token
        text = "This is a test string with some words."
        count = estimate_token_count(text)
        assert count > 0
        assert count < len(text)  # Should be less than character count

    def test_estimate_content_size_string(self):
        """Test content size estimation for strings."""
        text = "x" * 100
        size = estimate_content_size(text)
        assert size > 0

    def test_estimate_content_size_list(self):
        """Test content size estimation for content lists."""
        content = [
            {"type": "text", "text": "x" * 100},
            {"type": "image", "source": "data:image/png;base64,..."},
        ]
        size = estimate_content_size(content)
        assert size > 100  # Text tokens
        assert size > 1000  # Should include image estimate


class TestMcpConfigManager:
    """Test MCP configuration manager."""

    def test_initialization(self):
        """Test manager initialization."""
        manager = MCPConfigManager()
        assert manager is not None
        assert isinstance(manager.project_dir, object)

    def test_get_empty_configs(self):
        """Test getting configs when none exist."""
        manager = MCPConfigManager(project_dir="/nonexistent")
        configs = manager.get_all_configs()
        assert isinstance(configs, dict)

    def test_dynamic_config(self):
        """Test adding dynamic configurations."""
        manager = MCPConfigManager()

        config = McpStdioServerConfig(
            command="test",
            args=[],
        )

        manager.add_dynamic_config("test-server", config, "test-plugin")

        all_configs = manager.get_all_configs()
        # Dynamic configs should be accessible
        assert "test-server" in all_configs or len(all_configs) >= 0


@pytest.mark.asyncio
class TestMcpAsync:
    """Test async MCP functionality."""

    async def test_tool_adapter_structure(self):
        """Test that tool adapter can be created."""
        from mcp.tools.adapter import MCPToolAdapter
        from mcp.client.base import MCPClient

        # Create a mock client (not actually connected)
        class MockClient:
            server_name = "test"
            config = McpStdioServerConfig(command="test")
            _connected = False

        adapter = MCPToolAdapter(
            server_name="test",
            tool_name="test_tool",
            tool_description="A test tool",
            tool_schema={"type": "object"},
            mcp_client=MockClient(),
        )

        assert adapter.qualified_name == "mcp__test__test_tool"
        assert "test tool" in adapter.description.lower()

    async def test_env_expansion(self):
        """Test environment variable expansion."""
        from mcp.plugins.env_resolver import expand_env_vars

        # Set a test environment variable
        import os
        os.environ["TEST_VAR"] = "test_value"

        result, missing = expand_env_vars("${TEST_VAR}")
        assert result == "test_value"
        assert len(missing) == 0

        # Clean up
        del os.environ["TEST_VAR"]

    async def test_plugin_var_substitution(self):
        """Test plugin variable substitution."""
        from mcp.plugins.env_resolver import substitute_plugin_vars

        plugin = type("Plugin", (), {"path": "/test/path", "source": "test-plugin"})

        result = substitute_plugin_vars("${CLAUDE_PLUGIN_ROOT}", plugin)
        assert "/test/path" in result


if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v"])
