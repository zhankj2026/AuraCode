# 插件系统

auracode 的插件系统允许通过插件扩展工具、钩子和行为。插件可以从四个来源加载，并通过统一的 `plugin_id` 进行管理。

---

## 架构概览

```
plugins/
├── base.py         # ToolPlugin 抽象基类（接口定义）
├── builtin.py      # 内置插件注册表（程序化注册）
├── loader.py       # 插件加载器（四源扫描 + 统一加载）
└── registry.py     # 插件注册中心（清单 + 查询）
```

三层架构：
- **定义层** — `base.py` 定义插件接口（`ToolPlugin`）
- **注册层** — `builtin.py` 管理内置插件的程序化注册
- **加载层** — `loader.py` + `registry.py` 负责扫描、加载、清单管理

---

## 插件来源

| 来源 | 路径 / 方式 | plugin_id 后缀 | 说明 |
|------|------------|----------------|------|
| **builtin** | `register_builtin_plugin()` 代码注册 | `@builtin` | 随 auracode 发布，不可删除 |
| **目录** | `auracode/plugins/*.py` 文件扫描 | `@user` | 项目自带插件 |
| **项目级** | `.auracode/plugins/` 目录 | `@project` | 跟随项目仓库 |
| **用户级** | `~/.auracode/plugins/` 目录 | `@user` | 全局个人插件 |

加载顺序：builtin → 目录 → 项目级 → 用户级。同名插件后加载的覆盖先加载的。

---

## Plugin ID 规范

每个插件都有唯一标识，格式为 `{name}@{source}`：

```
auto-format@builtin       # 内置自动格式化插件
my-tool@project           # 项目级自定义插件
web-search@user           # 用户级插件
```

Plugin ID 用于：
- 启用/禁用操作的唯一键
- 用户设置持久化的索引
- 日志和调试输出

---

## 编写插件

### 基类接口

所有插件必须继承 `ToolPlugin` 并实现抽象方法：

```python
from plugins.base import ToolPlugin

class MyPlugin(ToolPlugin):

    @property
    def name(self) -> str:
        return "my-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "我的自定义插件"

    def get_tools(self):
        """返回工具定义列表"""
        return [{
            "name": "my_tool",
            "description": "自定义工具",
            "parameters": { ... },
            "handler": self._handle_my_tool,
            "permission_level": "read",
        }]

    def get_hooks(self):
        """返回钩子定义列表"""
        return [{
            "event": "PreToolUse",
            "handler": self._pre_tool_check,
            "matcher": "run_command",  # 可选，匹配特定工具
        }]

    def is_available(self) -> bool:
        """检查插件依赖是否满足"""
        return True
```

### 可选属性

| 属性 | 默认值 | 说明 |
|------|--------|------|
| `default_enabled` | `True` | 默认启用状态（三级回退链第二级） |
| `source` | `"user"` | 插件来源标识 |
| `mcp_servers` | `[]` | 携带的 MCP Server 配置列表 |
| `plugin_id` | `{name}@{source}` | 自动计算，通常无需覆盖 |

---

## 内置插件注册

内置插件通过代码硬编码注册（而非目录扫描），适用于随 auracode 发布的核心扩展：

```python
from plugins.builtin import register_builtin_plugin, BuiltinPluginDefinition

register_builtin_plugin(BuiltinPluginDefinition(
    name="auto-format",
    description="自动格式化代码",
    version="1.0.0",
    plugin_class=AutoFormatPlugin,
    default_enabled=True,
    is_available_fn=lambda: shutil.which("black") is not None,
))
```

### 启用状态三级回退

```
用户设置 (plugins_settings.json) > default_enabled 属性 > True
```

| 场景 | 用户设置 | default_enabled | 最终状态 |
|------|----------|-----------------|----------|
| 全新安装 | 无 | `True` | 启用 |
| 全新安装 | 无 | `False` | 禁用 |
| 用户禁用 | `false` | `True` | 禁用 |
| 用户启用 | `true` | `False` | 启用 |

### is_available 隐藏

当 `is_available_fn` 返回 `False` 时，插件完全隐藏：
- 不出现在启用列表
- 不出现在禁用列表
- 不占用用户设置空间

典型场景：依赖外部工具（如 `black`、`prettier`）的插件，未安装时自动隐藏。

---

## 用户设置持久化

用户启用/禁用操作持久化到 `~/.auracode/plugins_settings.json`：

```json
{
  "auto-format@builtin": true,
  "lint-check@builtin": false,
  "my-tool@project": true
}
```

管理命令：

```python
from plugins.builtin import enable_plugin, disable_plugin

enable_plugin("auto-format@builtin")   # 启用
disable_plugin("lint-check@builtin")   # 禁用
```

---

## 插件清单

`PluginLoader` 在加载时生成 `PluginManifest`，包含：

| 字段 | 说明 |
|------|------|
| `name` | 插件名称 |
| `version` | 版本号 |
| `description` | 描述 |
| `plugin_id` | 规范 ID (`{name}@{source}`) |
| `source` | 来源标识 |
| `default_enabled` | 默认启用状态 |
| `tools` | 提供的工具列表 |
| `hooks` | 提供的钩子列表 |

查询 API：

```python
from plugins.registry import PluginRegistry

registry = PluginRegistry()
# 列出所有已注册插件
all_plugins = registry.list_plugins()
# 仅启用/禁用的插件
enabled = registry.get_enabled_plugins()
disabled = registry.get_disabled_plugins()
```

---

## 插件工具注册

插件的 `get_tools()` 返回的工具会在 `AgentLoop.__init__` 中自动注册到全局 `TOOL_REGISTRY`：

```
PluginLoader.load_all_plugins()
    → get_all_tools()
        → TOOL_REGISTRY.register_tool(name, definition)
```

插件工具与内置工具在使用上完全一致，LLM 不感知工具来源。

---

## 项目级插件

在项目根目录创建 `.auracode/plugins/` 目录，放入 `.py` 文件即可：

```
my-project/
├── .auracode/
│   └── plugins/
│       └── custom_lint.py
├── src/
│   └── ...
└── README.md
```

项目级插件随项目仓库分发，团队成员克隆项目后自动加载。

---

## 用户级插件

放入 `~/.auracode/plugins/` 目录，全局生效：

```
~/.auracode/
├── plugins/
│   └── my_global_tool.py
├── config.yaml
└── plugins_settings.json
```

适用于个人常用但与项目无关的扩展。
