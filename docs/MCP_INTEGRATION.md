# MCP Integration

This module provides Model Context Protocol (MCP) integration for opencode.

## Overview

MCP (Model Context Protocol) is a protocol for connecting AI assistants to external data sources and tools. This integration allows opencode to communicate with MCP servers, exposing their tools and resources as native tools in the opencode tool registry.

## Architecture

```
mcp/
├── client/         # MCP client implementations
├── config/         # Configuration management
├── tools/          # Tool adaptation layer
├── plugins/        # Plugin integration
├── transport/      # Transport protocols (stdio, HTTP, WebSocket)
└── utils/          # Utility functions
```

## Features

### High Priority (Core Functionality)

- **MCP Client**: Core client for communicating with MCP servers
- **Transport Support**: stdio, HTTP, and WebSocket transports
- **Configuration Management**: Load and manage MCP server configurations
- **Tool Adaptation**: Adapt MCP tools to the opencode tool registry

### Medium Priority (Enhanced Features)

- **WebSocket Transport**: Real-time bidirectional communication
- **Plugin Integration**: Load MCP servers from plugins
- **Output Validation**: Token counting and truncation for large outputs

## Quick Start

### 1. Define MCP Servers

Create a `.mcp.json` file in your project directory:

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"]
    }
  }
}
```

### 2. Load Configuration and Connect

```python
import asyncio
from mcp.config.manager import MCPConfigManager
from mcp.client.base import MCPClient

async def main():
    # Load configuration
    manager = MCPConfigManager()
    configs = manager.get_all_configs()

    # Connect to a server
    if "github" in configs:
        client = MCPClient("github", configs["github"].config)
        await client.connect()

        # List available tools
        tools = await client.list_tools()
        for tool in tools:
            print(f"Tool: {tool['name']} - {tool.get('description', '')}")

        await client.disconnect()

asyncio.run(main())
```

### 3. Register MCP Tools

```python
from mcp.tools.adapter import register_mcp_tools

async def register_tools():
    client = MCPClient("github", config)
    await client.connect()

    # Register all tools from the server
    registered = await register_mcp_tools("github", client)
    print(f"Registered {len(registered)} tools")

    # Tools are now available in the tool registry
    # They can be called using the standard tool interface

    await client.disconnect()
```

## Configuration

### Configuration Scopes

MCP configurations are loaded from multiple sources in priority order:

1. **Enterprise**: Managed enterprise configurations
2. **Managed**: Managed service configurations
3. **User**: User-level configurations (`~/.config/opencode/mcp.json`)
4. **Project**: Project-level configurations (`./.mcp.json`)
5. **Dynamic**: Dynamically loaded from plugins

### Server Configuration Types

#### stdio (Local Process)

```json
{
  "type": "stdio",
  "command": "node",
  "args": ["server.js"],
  "env": {
    "API_KEY": "${API_KEY}"
  }
}
```

#### HTTP/SSE

```json
{
  "type": "sse",
  "url": "https://example.com/mcp",
  "headers": {
    "Authorization": "Bearer ${TOKEN}"
  }
}
```

#### WebSocket

```json
{
  "type": "ws",
  "url": "wss://example.com/mcp",
  "headers": {
    "Authorization": "Bearer ${TOKEN}"
  }
}
```

## Environment Variables

### Configuration Variables

You can use environment variables in your MCP configurations:

- `${VAR}` or `$VAR`: System environment variables
- `${user_config.KEY}`: User configuration values
- `${CLAUDE_PLUGIN_ROOT}`: Plugin directory (in plugins)
- `${CLAUDE_PLUGIN_DATA}`: Plugin data directory (in plugins)

### MCP Limits

- `MAX_MCP_OUTPUT_TOKENS`: Maximum tokens for MCP tool output (default: 25000)

## Plugin Integration

### Loading MCP Servers from Plugins

Plugins can define MCP servers in their `manifest.json`:

```json
{
  "name": "my-plugin",
  "mcpServers": ".mcp.json"
}
```

Or inline:

```json
{
  "name": "my-plugin",
  "mcpServers": {
    "my-server": {
      "type": "stdio",
      "command": "node",
      "args": ["server.js"]
    }
  }
}
```

### User Configuration in Plugins

Plugins can require user configuration:

```json
{
  "name": "my-plugin",
  "userConfig": {
    "apiKey": {
      "type": "string",
      "description": "API key for the service",
      "required": true
    }
  },
  "mcpServers": {
    "my-server": {
      "type": "http",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${user_config.apiKey}"
      }
    }
  }
}
```

## Tool Naming

MCP tools are named using the following pattern:

```
mcp__<server_name>__<tool_name>
```

For example, a tool called `create_issue` from the `github` server would be named:

```
mcp__github__create_issue
```

## Error Handling

### Session Expired

When an MCP session expires, a `MCPSessionExpiredError` is raised:

```python
from mcp.client.base import MCPSessionExpiredError

try:
    result = await client.call_tool("tool_name", {})
except MCPSessionExpiredError:
    # Reconnect and retry
    await client.connect()
    result = await client.call_tool("tool_name", {})
```

### Transport Errors

Transport errors can occur when:

- Server is not reachable
- Invalid configuration
- Network issues

Always handle `TransportError` exceptions:

```python
from mcp.transport.base import TransportError

try:
    await client.connect()
except TransportError as e:
    print(f"Failed to connect: {e}")
```

## Output Truncation

MCP tool outputs are automatically truncated if they exceed the token limit:

```python
from mcp.tools.validation import validate_and_truncate_output

result = await client.call_tool("tool_name", {})
# Result is automatically truncated if needed
```

You can configure the limit:

```python
import os
os.environ["MAX_MCP_OUTPUT_TOKENS"] = "50000"
```

## Examples

See the `examples/` directory for complete examples:

- `mcp_usage_example.py`: Comprehensive usage examples

## Testing

Run the MCP integration tests:

```bash
pytest tests/test_mcp_integration.py -v
```

## License

This MCP integration is part of opencode and follows the same license.
