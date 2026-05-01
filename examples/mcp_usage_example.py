"""
MCP Integration Usage Example

This example demonstrates how to use the MCP integration in opencode.

Usage:
    python examples/mcp_usage_example.py
"""

import asyncio
from pathlib import Path

from mcp.config.manager import MCPConfigManager
from mcp.config.types import McpStdioServerConfig, McpJsonConfig
from mcp.client.base import MCPClient
from mcp.tools.adapter import register_mcp_tools, unregister_mcp_tools


async def example_1_basic_client_usage():
    """Example 1: Basic MCP client usage."""
    print("\n=== Example 1: Basic MCP Client Usage ===\n")

    # Create a simple stdio server config
    config = McpStdioServerConfig(
        command="node",
        args=["path/to/server.js"],
    )

    # Create and connect client
    client = MCPClient("example-server", config)

    try:
        # Connect to the server
        print("Connecting to MCP server...")
        await client.connect()
        print("Connected!")

        # List available tools
        print("\nAvailable tools:")
        tools = await client.list_tools()
        for tool in tools:
            print(f"  - {tool.get('name')}: {tool.get('description', 'No description')}")

        # Call a tool (if available)
        if tools:
            tool_name = tools[0].get("name")
            print(f"\nCalling tool: {tool_name}")
            result = await client.call_tool(tool_name, {})
            print(f"Result: {result}")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        await client.disconnect()


async def example_2_config_manager():
    """Example 2: Using the configuration manager."""
    print("\n=== Example 2: Configuration Manager ===\n")

    # Create config manager for current project
    manager = MCPConfigManager()

    # Save a project configuration
    print("Saving project MCP configuration...")
    config = McpJsonConfig()
    config.mcp_servers["example-server"] = McpStdioServerConfig(
        command="node",
        args=["server.js"],
    )

    # Note: This would actually write to .mcp.json
    # manager.save_project_config(config)

    # Load all configurations
    print("\nLoading all MCP configurations...")
    all_configs = manager.get_all_configs()

    print(f"Found {len(all_configs)} server(s):")
    for name, scoped_config in all_configs.items():
        print(f"  - {name} (scope: {scoped_config.scope})")

    # Add a dynamic configuration (e.g., from plugin)
    print("\nAdding dynamic configuration...")
    manager.add_dynamic_config(
        "dynamic-server",
        McpStdioServerConfig(command="python", args=["-m", "mcp_server"]),
        plugin_source="example-plugin",
    )

    # Reload to see dynamic config
    all_configs = manager.get_all_configs()
    print(f"Now have {len(all_configs)} server(s)")


async def example_3_tool_registration():
    """Example 3: Registering MCP tools with the tool registry."""
    print("\n=== Example 3: Tool Registration ===\n")

    # Create a mock server config
    config = McpStdioServerConfig(
        command="echo",  # Simple echo command for testing
        args=[],
    )

    client = MCPClient("echo-server", config)

    try:
        await client.connect()

        # Register tools from this server
        print("Registering MCP tools...")
        registered = await register_mcp_tools("echo-server", client)

        print(f"Registered {len(registered)} tool(s):")
        for name in registered:
            print(f"  - {name}")

        # Tools can now be used via the tool registry
        print("\nTools are now available in the tool registry!")

        # Unregister when done
        print("\nUnregistering tools...")
        await unregister_mcp_tools("echo-server")
        print("Done!")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        await client.disconnect()


async def example_4_plugin_integration():
    """Example 4: Loading MCP servers from plugins."""
    print("\n=== Example 4: Plugin Integration ===\n")

    from mcp.plugins.integration import load_mcp_from_plugin

    # Load MCP servers from a plugin
    plugin_path = Path("./plugins/example-plugin")
    if plugin_path.exists():
        print(f"Loading MCP servers from plugin: {plugin_path}")

        servers = await load_mcp_from_plugin(
            plugin_path=str(plugin_path),
            plugin_name="example-plugin",
            plugin_source="local",
            user_config={"API_KEY": "test-key"},  # Optional user config
        )

        print(f"Found {len(servers)} MCP server(s) in plugin:")
        for name, scoped_config in servers.items():
            print(f"  - {name}")
            print(f"    Type: {type(scoped_config.config).__name__}")
    else:
        print(f"Plugin path does not exist: {plugin_path}")


async def example_5_string_utilities():
    """Example 5: Using string utility functions."""
    print("\n=== Example 5: String Utilities ===\n")

    from mcp.utils.strings import (
        normalize_name_for_mcp,
        build_mcp_tool_name,
        mcp_info_from_string,
        extract_mcp_tool_display_name,
    )

    # Normalize names
    server_name = "GitHub Integration"
    normalized = normalize_name_for_mcp(server_name)
    print(f"Normalized '{server_name}' -> '{normalized}'")

    # Build tool names
    tool_name = build_mcp_tool_name("GitHub", "Create Issue")
    print(f"Built tool name: {tool_name}")

    # Parse tool names
    info = mcp_info_from_string(tool_name)
    print(f"Parsed info: {info}")

    # Extract display names
    user_facing = "github - Add comment to issue (MCP)"
    display = extract_mcp_tool_display_name(user_facing)
    print(f"Display name: '{display}'")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("MCP Integration Usage Examples")
    print("=" * 60)

    # Run examples
    await example_1_basic_client_usage()
    await example_2_config_manager()
    await example_5_string_utilities()

    # Note: Examples 3 and 4 require actual MCP servers/plugins
    # await example_3_tool_registration()
    # await example_4_plugin_integration()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
