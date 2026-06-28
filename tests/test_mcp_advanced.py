"""
Test MCP advanced features.

Tests for OAuth authentication, resource access, prompts, and skill discovery.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
class TestOAuthAuthentication:
    """Test OAuth authentication functionality."""

    def test_oauth_client_initialization(self):
        """Test OAuth client initialization."""
        from mcp.auth import OAuthClient

        client = OAuthClient(
            client_id="test-client",
            auth_server_metadata_url="https://auth.example.com/metadata",
        )

        assert client.client_id == "test-client"
        assert client.auth_server_metadata_url == "https://auth.example.com/metadata"

    def test_code_verifier_generation(self):
        """Test PKCE code verifier generation."""
        from mcp.auth import OAuthClient

        client = OAuthClient(client_id="test")

        verifier1 = client.generate_code_verifier()
        verifier2 = client.generate_code_verifier()

        # Verifiers should be unique
        assert verifier1 != verifier2
        # Should be reasonable length
        assert len(verifier1) > 32

    def test_code_challenge_generation(self):
        """Test PKCE code challenge generation."""
        from mcp.auth import OAuthClient

        client = OAuthClient(client_id="test")

        verifier = client.generate_code_verifier()
        challenge = client.generate_code_challenge(verifier)

        # Challenge should be different from verifier
        assert challenge != verifier
        # Challenge should be base64-like
        assert "=" not in challenge or challenge.endswith("=")

    def test_build_authorization_url(self):
        """Test building authorization URL."""
        from mcp.auth import OAuthClient

        client = OAuthClient(
            client_id="test-client",
            authorization_endpoint="https://auth.example.com/authorize",
        )

        verifier = client.generate_code_verifier()
        url = client.build_authorization_url(
            code_verifier=verifier,
            scope="read write",
        )

        assert "https://auth.example.com/authorize" in url
        assert "client_id=test-client" in url
        assert "scope=read+write" in url
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url


@pytest.mark.asyncio
class TestResourceTools:
    """Test resource access tools."""

    async def test_list_resources_tool_creation(self):
        """Test creating a list resources tool."""
        from mcp.tools.resources import ListMcpResourcesTool
        from mcp.client.base import MCPClient

        mock_client = MagicMock(spec=MCPClient)
        mock_client._supports_resources.return_value = True

        tool = ListMcpResourcesTool("test-server", mock_client)

        assert tool.name == "mcp__test-server__list_resources"
        assert "test-server" in tool.description
        assert tool.get_parameters() == {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def test_read_resource_tool_creation(self):
        """Test creating a read resource tool."""
        from mcp.tools.resources import ReadMcpResourceTool
        from mcp.client.base import MCPClient

        mock_client = MagicMock(spec=MCPClient)
        mock_client._supports_resources.return_value = True

        tool = ReadMcpResourceTool("test-server", mock_client)

        assert tool.name == "mcp__test-server__read_resource"
        assert "test-server" in tool.description
        params = tool.get_parameters()
        assert "uri" in params["properties"]
        assert "uri" in params["required"]


@pytest.mark.asyncio
class TestPromptTools:
    """Test prompt tools."""

    async def test_list_prompts_tool_creation(self):
        """Test creating a list prompts tool."""
        from mcp.tools.prompts import ListMcpPromptsTool
        from mcp.client.base import MCPClient

        mock_client = MagicMock(spec=MCPClient)
        mock_client._supports_prompts.return_value = True

        tool = ListMcpPromptsTool("test-server", mock_client)

        assert tool.name == "mcp__test-server__list_prompts"
        assert "test-server" in tool.description
        assert tool.get_parameters() == {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def test_get_prompt_tool_creation(self):
        """Test creating a get prompt tool."""
        from mcp.tools.prompts import GetMcpPromptTool
        from mcp.client.base import MCPClient

        mock_client = MagicMock(spec=MCPClient)
        mock_client._supports_prompts.return_value = True

        tool = GetMcpPromptTool("test-server", mock_client)

        assert tool.name == "mcp__test-server__get_prompt"
        assert "test-server" in tool.description
        params = tool.get_parameters()
        assert "name" in params["properties"]
        assert "name" in params["required"]


@pytest.mark.asyncio
class TestSkillDiscovery:
    """Test MCP skill discovery."""

    async def test_skill_definition_creation(self):
        """Test creating MCP skill definition."""
        from mcp.skills import McpSkillDefinition
        from mcp.config.types import McpStdioServerConfig

        config = McpStdioServerConfig(command="test")
        skill = McpSkillDefinition(
            server_name="test-server",
            server_config=config,
            description="Test MCP server",
        )

        assert skill.name == "mcp_test-server"
        assert skill.server_name == "test-server"
        assert skill.description == "Test MCP server"

    async def test_skill_definition_capabilities(self):
        """Test skill definition with capabilities."""
        from mcp.skills import McpSkillDefinition
        from mcp.config.types import McpStdioServerConfig

        config = McpStdioServerConfig(command="test")
        skill = McpSkillDefinition(
            server_name="test-server",
            server_config=config,
            capabilities={
                "tools": {"available": True},
                "resources": {"available": False},
                "prompts": {"available": True},
            },
        )

        assert skill.has_tools is True
        assert skill.has_resources is False
        assert skill.has_prompts is True

    async def test_skill_discoverer_initialization(self):
        """Test skill discoverer initialization."""
        from mcp.skills import McpSkillDiscoverer
        from mcp.config.manager import MCPConfigManager

        manager = MCPConfigManager()
        discoverer = McpSkillDiscoverer(manager)

        assert discoverer.config_manager is manager

    async def test_skill_executor(self):
        """Test skill executor."""
        from mcp.skills import McpSkillExecutor
        from mcp.config.types import McpStdioServerConfig

        executor = McpSkillExecutor()
        config = McpStdioServerConfig(command="test")

        # Mock the client
        with patch("mcp.skills.MCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client.call_tool = AsyncMock(return_value={"result": "test"})
            mock_client_class.return_value = mock_client

            # Execute a tool
            result = await executor.execute_tool(
                "test-server",
                config,
                "test_tool",
                {"arg": "value"},
            )

            assert result == {"result": "test"}

        # Clean up
        await executor.close_all()


@pytest.mark.asyncio
class TestSkillRegistry:
    """Test MCP skill registry integration."""

    def test_skill_builders_registration(self):
        """Test registering skill builders."""
        from mcp.skills.registry import McpSkillBuilders

        async def create_skill(*args, **kwargs):
            return lambda: "skill"

        def parse_frontmatter(data):
            return data

        McpSkillBuilders.register_builders(create_skill, parse_frontmatter)

        retrieved_create, retrieved_parse = McpSkillBuilders.get_builders()

        assert retrieved_create is create_skill
        assert retrieved_parse is parse_frontmatter

    def test_skill_builders_not_registered(self):
        """Test error when builders not registered."""
        from mcp.skills.registry import McpSkillBuilders

        # Reset to test error case
        McpSkillBuilders._create_skill_command = None
        McpSkillBuilders._parse_skill_frontmatter = None

        with pytest.raises(RuntimeError, match="not registered"):
            McpSkillBuilders.get_builders()

    def test_frontmatter_parser_validation(self):
        """Test frontmatter validation."""
        from mcp.skills.registry import McpSkillFrontmatterParser

        # Valid frontmatter
        valid = {
            "name": "test_skill",
            "type": "mcp",
            "server_name": "test-server",
        }

        errors = McpSkillFrontmatterParser.validate(valid)
        assert len(errors) == 0

        # Invalid frontmatter
        invalid = {
            "name": "test_skill",
            "type": "invalid",
        }

        errors = McpSkillFrontmatterParser.validate(invalid)
        assert len(errors) > 0


@pytest.mark.asyncio
class TestEnvironmentExpansion:
    """Test environment variable expansion in various contexts."""

    def test_plugin_variable_substitution(self):
        """Test plugin-specific variable substitution."""
        from mcp.plugins.env_resolver import substitute_plugin_vars

        plugin = type("Plugin", (), {
            "path": "/test/plugin/path",
            "source": "test-plugin"
        })

        result = substitute_plugin_vars("${AURACODE_PLUGIN_ROOT}", plugin)
        assert result == "/test/plugin/path"

        result = substitute_plugin_vars("${AURACODE_PLUGIN_DATA}", plugin)
        assert "test-plugin" in result

    def test_user_config_variable_substitution(self):
        """Test user config variable substitution."""
        from mcp.plugins.env_resolver import substitute_user_config_vars
        from mcp.plugins.env_resolver import EnvExpansionError

        user_config = {"API_KEY": "test-key"}

        result = substitute_user_config_vars("${user_config.API_KEY}", user_config)
        assert result == "test-key"

        # Test missing variable
        with pytest.raises(EnvExpansionError):
            substitute_user_config_vars("${user_config.MISSING}", user_config)

    def test_combined_env_resolution(self):
        """Test combined environment variable resolution."""
        from mcp.plugins.env_resolver import resolve_mcp_env
        import os

        # Set test environment variable
        os.environ["TEST_VAR"] = "test_value"

        config = {
            "command": "${TEST_VAR}",
            "args": ["${TEST_VAR}"],
            "env": {
                "KEY": "${TEST_VAR}",
            },
        }

        plugin = type("Plugin", (), {
            "path": "/test",
            "source": "test"
        })

        resolved = resolve_mcp_env(config, plugin)

        assert resolved["command"] == "test_value"
        assert resolved["args"] == ["test_value"]
        assert resolved["env"]["KEY"] == "test_value"

        # Clean up
        del os.environ["TEST_VAR"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
