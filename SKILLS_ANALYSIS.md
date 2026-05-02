# Skills 系统分析与完善计划

## 一、现状对比

### 本工程 (opencode) 能力
- ✅ 基础的技能加载（单目录）
- ✅ 激活/停用机制
- ✅ 懒加载提示词
- ✅ 命令行工具
- ✅ SkillContext 单例模式

### ../src (TypeScript) 能力
- ✅ 多层技能来源（managed/user/project/bundled/MCP）
- ✅ 动态技能发现
- ✅ 参数传递和替换
- ✅ 条件激活（paths frontmatter）
- ✅ Hooks 集成
- ✅ allowed-tools 白名单
- ✅ inline/fork 执行上下文
- ✅ Shell 命令注入
- ✅ 别名系统
- ✅ 基于 realpath 的去重
- ✅ React UI 组件
- ✅ MCP 技能支持

## 二、核心差异

### 1. 技能加载机制
**本工程**: 单一静态目录加载
**../src**: 多层来源 + 动态发现 + 智能去重

### 2. 条件激活
**本工程**: 不存在
**../src**: 支持 paths frontmatter 自动激活

### 3. 参数系统
**本工程**: 不存在
**../src**: `${ARG1}`, `${CLAUDE_SKILL_DIR}`, `${CLAUDE_SESSION_ID}`

### 4. 执行能力
**本工程**: 纯文本提示词
**../src**: Shell 命令执行 (`!cmd`) + 工具限制

## 三、完善计划

### Phase 1: 增强基础能力（优先级：高）

#### 1.1 参数支持
```python
# loader.py
class Skill:
    argument_names: List[str] = []
    argument_hint: Optional[str] = None

class SkillManager:
    def substitute_arguments(self, content: str, args: str) -> str:
        """替换 ${ARG1}, ${ARG2} 等参数占位符"""
```

**SKILL.md 格式扩展**:
```yaml
---
name: example-skill
description: 示例技能
arguments: [pattern, output_file]
argument-hint: "<pattern> <output_file>"
---
```

#### 1.2 条件激活（paths）
```python
# loader.py
class Skill:
    paths: Optional[List[str]] = None  # gitignore 风格模式

class SkillManager:
    def activate_for_paths(self, file_paths: List[str]) -> List[str]:
        """根据文件路径自动激活匹配的技能"""
```

**SKILL.md 格式扩展**:
```yaml
---
name: typescript-standards
paths: ["src/**/*.ts", "tests/**/*.test.ts"]
---
```

#### 1.3 变量替换
```python
# 支持的变量
${CLAUDE_SKILL_DIR}   # 技能目录
${CLAUDE_SESSION_ID}  # 会话 ID
${ARG1}, ${ARG2}      # 参数
${PWD}                # 工作目录
```

### Phase 2: 高级特性（优先级：中）

#### 2.1 Hooks 支持
```python
# loader.py
@dataclass
class Skill:
    hooks: Optional[Dict[str, Any]] = None

# SKILL.md
---
hooks:
  pre_tool_use:
    - tool: Bash
      command: "echo 'About to run bash'"
---
```

#### 2.2 工具白名单
```python
# SKILL.md
---
allowed-tools: [Read, Write, Edit, Bash]
---
```

#### 2.3 别名系统
```python
# SKILL.md
---
name: python-standards
aliases: [py, python, py-style]
---
```

#### 2.4 Shell 命令注入
```python
# SKILL.md 内容
---
name: setup-project
---

执行以下初始化命令：

!`npm install -g typescript`
!`python -m venv .venv`
```

### Phase 3: 架构增强（优先级：中）

#### 3.1 多层技能来源
```python
class SkillManager:
    def __init__(self):
        # 按优先级加载
        self.sources = [
            'managed',    # ~/.claude/skills (managed)
            'user',       # ~/.claude/skills (user)
            'project',    # ./.claude/skills
            'bundled',    # 内置技能
        ]
```

#### 3.2 动态技能发现
```python
# 动态发现嵌套的 .claude/skills 目录
class SkillManager:
    async def discover_skills_for_paths(self, file_paths: List[str]) -> None:
        """为给定路径发现并加载嵌套的技能目录"""
```

#### 3.3 智能去重
```python
# 基于 realpath 去重
async def get_file_identity(self, file_path: str) -> Optional[str]:
    """解析符号链接，返回真实路径"""
    return await os.path.realpath(file_path)
```

### Phase 4: 集成能力（优先级：低）

#### 4.1 MCP 技能支持
```python
# 从 MCP 服务器加载技能
class MCPSkillLoader:
    async def load_skills_from_server(self, server_name: str) -> List[Skill]:
        """从 MCP 服务器获取技能定义"""
```

#### 4.2 执行上下文
```python
# SKILL.md
---
context: fork  # inline | fork
---
```

## 四、实施建议

### 优先级排序
1. **立即实施**: 参数支持、变量替换
2. **短期**: 条件激活、工具白名单
3. **中期**: Hooks、Shell 注入、别名
4. **长期**: MCP 集成、动态发现

### 兼容性策略
- 保持现有 SKILL.md 格式向后兼容
- 新增字段均为可选
- 渐进式增强，不破坏现有技能

### 测试策略
```python
# tests/test_skills_enhanced.py
class TestEnhancedSkills:
    def test_argument_substitution(self)
    def test_conditional_activation(self)
    def test_hooks_integration(self)
    def test_deduplication(self)
```

## 五、参考文件位置

### 本工程需要修改的文件
```
opencode/
├── skills/
│   ├── loader.py          # 核心加载逻辑
│   ├── context.py         # 上下文管理
│   └── __init__.py
├── tools/builtin/
│   └── skill_tools.py     # 工具集成
└── commands/builtin/
    └── skills_command.py  # 命令行
```

### 参考实现位置
```
src/
├── skills/
│   ├── loadSkillsDir.ts   # 主要参考
│   ├── bundledSkills.ts   # 内置技能
│   └── mcpSkillBuilders.ts
└── components/skills/
    └── SkillsMenu.tsx     # UI 参考
```
