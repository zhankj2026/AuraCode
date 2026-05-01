# MCP Integration

This module provides Model Context Protocol (MCP) integration for opencode.

## Overview

MCP (Model Context Protocol) is a protocol for connecting AI assistants to external data sources and tools. This integration allows opencode to communicate with MCP servers, exposing their tools and resources as native tools in the opencode tool registry.

## Architecture

```
mcp/
├── auth/           # OAuth 2.0 authentication
├── client/         # MCP client implementations
├── config/         # Configuration management
├── plugins/        # Plugin integration
├── skills/         # Skill discovery and integration
├── tools/          # Tool, resource, and prompt adaptation
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

### Advanced Features

- **OAuth Authentication**: OAuth 2.0 flow for secure server access
- **Resource Tools**: Access MCP server resources (files, data, etc.)
- **Prompt Tools**: Use pre-defined prompts from MCP servers
- **Skill Discovery**: Auto-discover MCP servers as skills

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

## Advanced Features

### OAuth Authentication

MCP servers that require OAuth 2.0 authentication can be configured with OAuth settings:

```json
{
  "type": "sse",
  "url": "https://api.example.com/mcp",
  "oauth": {
    "clientId": "your-client-id",
    "callbackPort": 3000,
    "authServerMetadataUrl": "https://auth.example.com/.well-known/oauth-authorization-server"
  }
}
```

#### Programmatic OAuth Authentication

```python
from mcp.auth import authenticate_oauth, OAuthClient

# Automatic OAuth flow with local callback server
client = await authenticate_oauth(
    client_id="your-client-id",
    auth_server_metadata_url="https://auth.example.com/.well-known/oauth-authorization-server",
    scope="read write",
)

# Use the authenticated client
access_token = await client.get_access_token()
print(f"Access token: {access_token}")
```

#### Manual OAuth Flow

```python
from mcp.auth import OAuthClient

client = OAuthClient(
    client_id="your-client-id",
    auth_server_metadata_url="https://auth.example.com/.well-known/oauth-authorization-server",
)

# Generate authorization URL
code_verifier = client.generate_code_verifier()
auth_url = client.build_authorization_url(
    code_verifier=code_verifier,
    scope="read write",
)

# User visits auth_url and authorizes...

# Exchange code for token
await client.exchange_code_for_token(code, code_verifier)

# Get access token
token = await client.get_access_token()
```

### Resource Access

MCP servers can expose resources (files, database records, API endpoints) that can be accessed.

#### Listing Resources

```python
from mcp.tools.resources import ListMcpResourcesTool, register_resource_tools

# Register resource tools
await register_resource_tools("server-name", client)

# List resources
list_tool = ListMcpResourcesTool("server-name", client)
result = await list_tool.execute()

print(f"Found {result['count']} resources:")
for resource in result['resources']:
    print(f"  - {resource['uri']}: {resource.get('name', 'No name')}")
```

#### Reading Resources

```python
from mcp.tools.resources import ReadMcpResourceTool

read_tool = ReadMcpResourceTool("server-name", client)
result = await read_tool.execute(uri="file:///path/to/file.txt")

content = result.get('content')
print(f"Content: {content}")
```

### Prompt Tools

MCP servers can provide pre-defined prompts that can be used to generate specific types of messages.

#### Listing Prompts

```python
from mcp.tools.prompts import ListMcpPromptsTool, register_prompt_tools

# Register prompt tools
await register_prompt_tools("server-name", client)

# List prompts
list_tool = ListMcpPromptsTool("server-name", client)
result = await list_tool.execute()

print(f"Found {result['count']} prompts:")
for prompt in result['prompts']:
    print(f"  - {prompt['name']}: {prompt.get('description', 'No description')}")
```

#### Getting Prompts

```python
from mcp.tools.prompts import GetMcpPromptTool

get_tool = GetMcpPromptTool("server-name", client)
result = await get_tool.execute(
    name="summarize",
    arguments={"text": "Long text to summarize..."}
)

prompt = result.get('prompt')
print(f"Generated prompt: {prompt}")
```

### Skill Discovery

MCP servers can be automatically discovered and exposed as skills in the opencode skill system.

```python
from mcp.skills import discover_mcp_skills, McpSkillDiscoverer

# Discover all MCP servers as skills
discoverer = McpSkillDiscoverer()
skills = await discoverer.discover_all_skills()

for skill_name, skill_def in skills.items():
    print(f"Skill: {skill_name}")
    print(f"  Description: {skill_def.description}")
    print(f"  Has tools: {skill_def.has_tools}")
    print(f"  Has resources: {skill_def.has_resources}")
    print(f"  Has prompts: {skill_def.has_prompts}")
```

#### Skill Execution

```python
from mcp.skills import McpSkillExecutor

executor = McpSkillExecutor()

# Execute a tool via skill
result = await executor.execute_tool(
    server_name="github",
    server_config=config,
    tool_name="create_issue",
    arguments={"title": "Bug fix", "body": "Fixes issue #123"}
)

# Read a resource via skill
content = await executor.read_resource(
    server_name="filesystem",
    server_config=config,
    uri="file:///path/to/file.txt"
)

# Get a prompt via skill
prompt = await executor.get_prompt(
    server_name="my-server",
    server_config=config,
    prompt_name="summarize",
    arguments={"text": "Summary text"}
)

# Clean up
await executor.close_all()
```

### Skill Registry Integration

MCP skills can be integrated with the opencode skill registry:

```python
from mcp.skills.registry import (
    register_mcp_skill_builders,
    discover_and_create_mcp_skills,
    load_mcp_skills_to_registry,
)

# Register skill builders (do this during initialization)
from skills.loader import create_skill_command, parse_skill_frontmatter
register_mcp_skill_builders(create_skill_command, parse_skill_frontmatter)

# Load MCP skills into the skill registry
skill_names = await load_mcp_skills_to_registry(
    skill_registry=SKILL_REGISTRY,
    skills_dir=Path("./skills/mcp"),
)

print(f"Loaded {len(skill_names)} MCP skills")
```
