# MCP 功能对比分析 & 外部服务注册指南

## 📊 Claude Code vs OpenCode MCP 功能对比

### 核心功能对比表

| 功能模块 | Claude Code | OpenCode | 状态 | 说明 |
|---------|-------------|----------|------|------|
| **传输协议** | | | | |
| stdio | ✅ | ✅ | ✅ 完整 | 本地进程通信 |
| SSE | ✅ | ✅ | ✅ 完整 | Server-Sent Events |
| HTTP | ✅ | ✅ | ✅ 完整 | HTTP POST 请求 |
| WebSocket | ✅ | ✅ | ✅ 完整 | 双向实时通信 |
| SDK | ✅ | ✅ | ✅ 完整 | 进程内集成 |
| | | | | |
| **配置管理** | | | | |
| 项目级配置 (.mcp.json) | ✅ | ✅ | ✅ 完整 | 项目根目录 |
| 用户级配置 | ✅ | ✅ | ✅ 完整 | ~/.config/opencode |
| 企业级配置 | ✅ | ⚠️ 部分 | 🟡 待完善 | 企业策略控制 |
| 插件配置 | ✅ | ✅ | ✅ 完整 | 插件 MCP 集成 |
| 动态配置 (CLI) | ✅ | ✅ | ✅ 完整 | 运行时添加 |
| | | | | |
| **认证与安全** | | | | |
| OAuth 2.0 | ✅ | ✅ | ✅ 完整 | 标准 OAuth 流程 |
| 客户端注册 (DCR) | ✅ | ⚠️ 基础 | 🟡 待完善 | 动态客户端注册 |
| 安全存储 | ✅ | ⚠️ 基础 | 🟡 待完善 | 密钥安全存储 |
| 允许列表 (Allowlist) | ✅ | ❌ | 🔴 缺失 | 企业策略控制 |
| 拒绝列表 (Denylist) | ✅ | ❌ | 🔴 缺失 | 黑名单控制 |
| 命令匹配 | ✅ | ❌ | 🔴 缺失 | 精确命令控制 |
| URL 模式匹配 | ✅ | ❌ | 🔴 缺失 | 通配符 URL 控制 |
| | | | | |
| **服务器管理** | | | | |
| 热加载 | ✅ | ✅ | ✅ 完整 | 运行时添加 |
| 热卸载 | ✅ | ✅ | ✅ 完整 | 运行时移除 |
| 自动重连 | ✅ | ✅ | ✅ 完整 | 连接恢复 |
| 健康检查 | ✅ | ⚠️ 基础 | 🟡 待完善 | 服务器状态监控 |
| 会话过期处理 | ✅ | ✅ | ✅ 完整 | SessionExpiredError |
| 配置变更检测 | ✅ | ⚠️ 基础 | 🟡 待完善 | 自动重新连接 |
| | | | | |
| **工具集成** | | | | |
| 自动发现 | ✅ | ✅ | ✅ 完整 | 工具列表发现 |
| 自动注册 | ✅ | ✅ | ✅ 完整 | 注册到工具系统 |
| 工具调用 | ✅ | ✅ | ✅ 完整 | 统一工具接口 |
| 结果验证 | ✅ | ✅ | ✅ 完整 | 输出验证和截断 |
| 结果缓存 (TTL) | ✅ | ✅ | ✅ 完整 | 缓存机制 |
| Schema 转换 | ✅ | ⚠️ 基础 | 🟡 待完善 | Zod → JSON Schema |
| | | | | |
| **资源支持** | | | | |
| 资源列表 | ✅ | ✅ | ✅ 完整 | List Resources |
| 资源读取 | ✅ | ✅ | ✅ 完整 | Read Resource |
| 资源模板 | ✅ | ⚠️ 基础 | 🟡 待完善 | 资源 URI 模板 |
| | | | | |
| **提示词支持** | | | | |
| 提示词列表 | ✅ | ✅ | ✅ 完整 | List Prompts |
| 提示词获取 | ✅ | ✅ | ✅ 完整 | Get Prompt |
| 提示词参数 | ✅ | ⚠️ 基础 | 🟡 待完善 | 参数验证 |
| | | | | |
| **Skill 集成** | | | | |
| Skill 发现 | ✅ | ✅ | ✅ 完整 | 从 MCP 发现 Skill |
| Skill 执行 | ✅ | ✅ | ✅ 完整 | Skill 执行器 |
| Skill 构建器 | ✅ | ✅ | ✅ 完整 | 预定义 Skill 模板 |
| | | | | |
| **高级功能** | | | | |
| MCP Server 模式 | ✅ | ❌ | 🔴 缺失 | 作为 MCP Server 运行 |
| MCPB 文件支持 | ✅ | ❌ | 🔴 缺失 | MCP Bundle 格式 |
| 环境变量扩展 | ✅ | ✅ | ✅ 完整 | ${VAR} 语法 |
| 插件变量扩展 | ✅ | ✅ | ✅ 完整 | ${PLUGIN:VAR} 语法 |
| 计算机使用 (Computer Use) | ✅ | ❌ | 🔴 缺失 | 专用 MCP 服务器 |
| Chrome 集成 | ✅ | ❌ | 🔴 缺失 | Claude in Chrome |
| 配置优先级管理 | ✅ | ⚠️ 基础 | 🟡 待完善 | 多配置冲突解决 |
| 遥测和监控 | ✅ | ❌ | 🔴 缺失 | 使用统计 |

---

## 🔴 缺失的重要功能（按优先级排序）

### P0: 核心缺失功能

#### 1. **MCP Server 模式**（对标 `src/entrypoints/mcp.ts`）

**Claude Code 实现**：
```typescript
// 作为 MCP Server 运行，对外暴露 OpenCode 的工具
export async function startMCPServer(cwd: string, debug: boolean, verbose: boolean): Promise<void> {
  const server = new Server(
    { name: 'claude/tengu', version: MACRO.VERSION },
    { capabilities: { tools: {} } }
  )
  
  // 暴露所有工具给外部 MCP 客户端
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    const tools = getTools(getEmptyToolPermissionContext())
    return { tools: tools.map(tool => convertToMcpTool(tool)) }
  })
  
  server.setRequestHandler(CallToolRequestSchema, async ({ params }) => {
    const tool = findToolByName(tools, params.name)
    return await tool.call(params.arguments, context)
  })
  
  await server.connect(new StdioServerTransport())
}
```

**OpenCode 缺失**：
- ❌ 无法作为 MCP Server 运行
- ❌ 无法将内置工具暴露给外部系统
- ❌ 无法被其他 AI 代理调用

**影响**：无法实现工具链集成、无法被外部系统调用

---

#### 2. **允许列表/拒绝列表策略**（企业级安全）

**Claude Code 实现**：
```typescript
// 企业级策略控制
function isMcpServerAllowedByPolicy(serverName: string, config?: McpServerConfig): boolean {
  // 1. 拒绝列表优先
  if (isMcpServerDenied(serverName, config)) return false
  
  // 2. 允许列表检查
  const settings = getMcpAllowlistSettings()
  if (!settings.allowedMcpServers) return true
  
  // 3. 支持三种匹配方式
  // - serverName: 按名称匹配
  // - serverCommand: 按命令数组精确匹配 [command, ...args]
  // - serverUrl: 按 URL 模式匹配（支持通配符）
}
```

**OpenCode 缺失**：
- ❌ 无允许列表控制
- ❌ 无拒绝列表控制
- ❌ 无命令级别权限控制
- ❌ 无 URL 模式匹配

**影响**：企业环境无法控制哪些 MCP 服务器可以被加载

---

#### 3. **MCPB 文件格式支持**（MCP Bundle）

**Claude Code 支持**：
```json
// .mcpb 文件 - 打包的 MCP 服务器配置
{
  "name": "database-tools",
  "version": "1.0.0",
  "servers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "${user:DATABASE_URL}"
      }
    }
  }
}
```

**OpenCode 缺失**：
- ❌ 不支持 .mcpb 文件格式
- ❌ 不支持打包分发 MCP 配置

**影响**：无法实现 MCP 配置的打包和分发

---

### P1: 重要功能缺失

#### 4. **动态客户端注册 (DCR) 完善**

**Claude Code 实现**：
```typescript
// OAuth 2.0 动态客户端注册
async registerClient(metadata: OAuthClientMetadata): Promise<OAuthClientInformationFull> {
  // 1. 从授权服务器获取注册端点
  const registrationEndpoint = await this.getRegistrationEndpoint()
  
  // 2. 发送注册请求
  const response = await fetch(registrationEndpoint, {
    method: 'POST',
    body: JSON.stringify(metadata)
  })
  
  // 3. 存储客户端凭证
  await this.saveClientInformation(response.json())
}
```

**OpenCode 现状**：
- ✅ 基础 OAuth 支持
- ⚠️ DCR 实现不完整
- ⚠️ 客户端凭证存储不完善

---

#### 5. **配置优先级和冲突解决**

**Claude Code 优先级**：
```
1. CLI 动态配置 (--mcp-config)        [最高]
2. 企业级配置 (exclusive control)
3. 插件配置 (plugin:namespace:name)
4. 用户级配置 (~/.config/opencode)
5. 项目级配置 (.mcp.json)
6. 本地配置 (local)                   [最低]
```

**OpenCode 现状**：
- ⚠️ 基础优先级支持
- ❌ 无完整的冲突解决逻辑
- ❌ 无配置合并策略

---

#### 6. **健康检查和监控**

**Claude Code 实现**：
```typescript
// 服务器健康状态
type MCPServerConnection =
  | ConnectedMCPServer    // ✅ 已连接
  | FailedMCPServer       // ❌ 连接失败
  | NeedsAuthMCPServer    // 🔐 需要认证
  | PendingMCPServer      // ⏳ 重连中
  | DisabledMCPServer     // ⛔ 已禁用
```

**OpenCode 现状**：
- ✅ 基础连接状态
- ⚠️ 无详细状态分类
- ❌ 无健康检查机制

---

### P2: 可选功能

#### 7. **计算机使用 (Computer Use) MCP**
- 专用 MCP 服务器控制浏览器/桌面
- Claude Code 特殊集成

#### 8. **Claude in Chrome 集成**
- 浏览器 MCP 服务器
- reserved server name: "claude-in-chrome"

#### 9. **遥测和监控**
- MCP 服务器使用统计
- 工具调用频率
- 性能指标

---

## 📝 如何注册外部 MCP 服务

### 方法 1: 配置文件注册（推荐）

#### 1.1 项目级配置

创建 `.mcp.json` 在项目根目录：

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost/mydb"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${user:GITHUB_TOKEN}"
      }
    }
  }
}
```

#### 1.2 用户级配置

创建 `~/.config/opencode/mcp.json`：

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "${user:SLACK_TOKEN}"
      }
    }
  }
}
```

#### 1.3 YAML 配置（config.yaml）

```yaml
mcp:
  servers:
    database:
      command: "python"
      args: ["-m", "mcp_server_postgres"]
      transport: stdio
      env:
        DATABASE_URL: "postgresql://localhost/db"
    
    remote-api:
      url: "http://localhost:3000"
      transport: sse
      headers:
        Authorization: "Bearer ${user:API_TOKEN}"
    
    realtime-service:
      url: "ws://localhost:4000"
      transport: websocket
      auto_reconnect: true
```

---

### 方法 2: 命令行动态注册

```bash
# 进入 opencode 目录
cd opencode

# 添加 stdio 服务器
python -c "
from mcp.manager import McpManager
from mcp.config.types import McpStdioServerConfig
import asyncio

async def add_server():
    mgr = McpManager()
    config = McpStdioServerConfig(
        command='npx',
        args=['-y', '@modelcontextprotocol/server-postgres'],
        env={'DATABASE_URL': 'postgresql://localhost/db'}
    )
    state = await mgr.add_server('postgres', config)
    print(f'Connected: {state.connected}')
    print(f'Tools: {state.tools}')

asyncio.run(add_server())
"

# 添加 SSE 服务器
python -c "
from mcp.manager import McpManager
from mcp.config.types import McpSSEServerConfig
import asyncio

async def add_sse_server():
    mgr = McpManager()
    config = McpSSEServerConfig(
        url='http://localhost:3000',
        headers={'Authorization': 'Bearer token123'}
    )
    state = await mgr.add_server('remote-api', config)
    print(f'Connected: {state.connected}')

asyncio.run(add_sse_server())
"
```

---

### 方法 3: 编程方式注册

```python
"""注册外部 MCP 服务"""
import asyncio
from mcp.manager import McpManager
from mcp.config.types import (
    McpStdioServerConfig,
    McpSSEServerConfig,
    McpHTTPServerConfig,
    McpWebSocketServerConfig
)

async def register_mcp_servers():
    mgr = McpManager()
    
    # 1. 注册 stdio 服务器（本地进程）
    postgres_config = McpStdioServerConfig(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres"],
        env={
            "DATABASE_URL": "postgresql://user:pass@localhost/mydb"
        }
    )
    await mgr.add_server("postgres", postgres_config)
    
    # 2. 注册 SSE 服务器（HTTP 流）
    filesystem_config = McpSSEServerConfig(
        url="http://localhost:3001",
        headers={
            "Authorization": "Bearer token123"
        }
    )
    await mgr.add_server("filesystem", filesystem_config)
    
    # 3. 注册 HTTP 服务器
    api_config = McpHTTPServerConfig(
        url="http://localhost:3002/mcp",
        headers={
            "Content-Type": "application/json"
        }
    )
    await mgr.add_server("api", api_config)
    
    # 4. 注册 WebSocket 服务器（实时双向）
    ws_config = McpWebSocketServerConfig(
        url="ws://localhost:4000",
        headers={}
    )
    await mgr.add_server("realtime", ws_config)
    
    # 查看已注册的服务器
    for name, state in mgr.servers.items():
        print(f"服务器: {name}")
        print(f"  连接状态: {state.connected}")
        print(f"  工具数: {len(state.tools)}")
        print(f"  工具列表: {state.tools}")

# 运行
asyncio.run(register_mcp_servers())
```

---

### 方法 4: 插件方式注册

创建插件目录结构：

```
my-plugin/
├── manifest.json
├── .mcp.json
└── servers/
    └── custom-server.py
```

**manifest.json**：
```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "mcpServers": {
    "custom-tools": {
      "command": "python",
      "args": ["servers/custom-server.py"]
    }
  }
}
```

**.mcp.json**：
```json
{
  "mcpServers": {
    "database": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "${PLUGIN:DATABASE_URL}"
      }
    }
  }
}
```

**加载插件**：
```python
from mcp.plugins.integration import load_mcp_from_plugin

async def load_plugin():
    servers = await load_mcp_from_plugin(
        plugin_path="./my-plugin",
        plugin_name="my-plugin",
        plugin_source="local"
    )
    
    print(f"从插件加载了 {len(servers)} 个 MCP 服务器")
    for name, config in servers.items():
        print(f"  - {name}: {config}")
```

---

### 方法 5: 自动发现注册

OpenCode 启动时自动扫描以下路径：

```python
from mcp.manager import McpManager

mgr = McpManager()

# 自动发现并注册
search_paths = [
    "./mcp-servers",
    "~/.config/opencode/mcp-servers",
    "/opt/mcp-servers"
]

registered = await mgr.auto_register_discovered(search_paths)

print(f"自动发现并注册了 {len(registered)} 个 MCP 服务器")
for name, state in registered.items():
    print(f"  - {name}: {state.connected}")
```

在 `mcp-servers/` 目录放置配置文件：

```
mcp-servers/
├── postgres.json
├── filesystem.yaml
└── github.json
```

**postgres.json**：
```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-postgres"],
  "env": {
    "DATABASE_URL": "postgresql://localhost/db"
  }
}
```

---

## 🔧 完整使用示例

### 示例：注册 PostgreSQL MCP 服务器

```python
"""
完整示例：注册并使用 PostgreSQL MCP 服务器
"""
import asyncio
from mcp.manager import McpManager
from mcp.config.types import McpStdioServerConfig

async def main():
    # 1. 创建管理器
    mgr = McpManager()
    
    # 2. 配置 PostgreSQL 服务器
    config = McpStdioServerConfig(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres"],
        env={
            "DATABASE_URL": "postgresql://user:password@localhost:5432/mydb"
        }
    )
    
    # 3. 添加服务器
    print("📡 连接 PostgreSQL MCP 服务器...")
    state = await mgr.add_server("postgres", config)
    
    if state.connected:
        print(f"✅ 连接成功！")
        print(f"📦 发现 {len(state.tools)} 个工具:")
        for tool_name in state.tools:
            print(f"   - {tool_name}")
        
        # 4. 工具已自动注册到全局工具系统
        # 现在可以通过 AI 代理调用这些工具
        print("\n🎯 工具已注册，可以被 AI 代理调用")
        
        # 5. 查看缓存统计
        stats = mgr.get_cache_stats()
        print(f"\n📊 缓存统计:")
        print(f"   - 命中: {stats['hits']}")
        print(f"   - 未命中: {stats['misses']}")
        print(f"   - 大小: {stats['size']}")
    else:
        print(f"❌ 连接失败: {state.error}")
    
    # 6. 保持运行
    print("\n⏸️  按 Ctrl+C 停止...")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 正在清理...")
        await mgr.shutdown()
        print("✅ 已清理")

# 运行
asyncio.run(main())
```

---

## 📋 配置参数参考

### stdio 服务器

```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-xxx"],
  "env": {
    "KEY": "value",
    "TOKEN": "${user:TOKEN_VAR}"
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 否 | 固定 "stdio"（默认） |
| command | string | 是 | 可执行文件路径 |
| args | array | 否 | 命令行参数 |
| env | object | 否 | 环境变量（支持 ${user:VAR} 和 ${PLUGIN:VAR}） |

---

### SSE 服务器

```json
{
  "type": "sse",
  "url": "http://localhost:3000",
  "headers": {
    "Authorization": "Bearer token"
  },
  "oauth": {
    "client_id": "your-client-id",
    "callback_port": 3000,
    "auth_server_metadata_url": "https://auth.example.com/.well-known/oauth-authorization-server"
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 固定 "sse" |
| url | string | 是 | SSE 端点 URL |
| headers | object | 否 | HTTP 请求头 |
| oauth | object | 否 | OAuth 配置 |

---

### HTTP 服务器

```json
{
  "type": "http",
  "url": "http://localhost:3001/mcp",
  "headers": {
    "Content-Type": "application/json"
  }
}
```

---

### WebSocket 服务器

```json
{
  "type": "ws",
  "url": "ws://localhost:4000",
  "headers": {}
}
```

---

## 🎯 总结

### OpenCode MCP 优势

✅ **完整的传输协议支持**：stdio/SSE/HTTP/WebSocket/SDK  
✅ **热加载/热卸载**：运行时动态管理  
✅ **自动工具发现**：自动注册到工具系统  
✅ **工具结果缓存**：TTL 缓存机制  
✅ **OAuth 认证**：标准 OAuth 2.0 支持  
✅ **插件集成**：支持从插件加载 MCP 服务器  
✅ **Skill 发现**：从 MCP 服务器发现 Skill  
✅ **多配置源**：项目/用户/插件/动态配置  

### 需要补齐的功能

🔴 **P0（核心缺失）**：
1. MCP Server 模式（对外暴露工具）
2. 允许列表/拒绝列表（企业安全）
3. MCPB 文件格式支持

🟡 **P1（重要功能）**：
4. DCR 完善
5. 配置优先级和冲突解决
6. 健康检查和监控

🟢 **P2（可选功能）**：
7. 计算机使用 MCP
8. Claude in Chrome 集成
9. 遥测和监控

### 推荐实施路线

```
Phase 1 (1-2 周): MCP Server 模式
  - 实现 StdioServerTransport
  - 暴露内置工具给外部客户端
  - 工具调用代理

Phase 2 (1 周): 企业安全策略
  - 允许列表/拒绝列表
  - 命令匹配和 URL 模式匹配
  - 配置验证

Phase 3 (1-2 周): 高级功能
  - MCPB 文件格式
  - DCR 完善
  - 健康检查机制
```

---

**文档版本**: v1.0  
**创建日期**: 2026-06-02  
**状态**: 完整对比分析
