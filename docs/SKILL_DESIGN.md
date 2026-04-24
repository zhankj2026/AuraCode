# Skill 系统渐进式披露设计

## 设计理念

**渐进式披露 (Progressive Disclosure)** 是一种用户体验设计模式，核心思想是：

> 只在需要时才展示复杂或详细信息，初始状态下只展示必要的元数据。

## 在 Skill 系统中的应用

### 问题背景

如果每次初始化都加载所有技能的完整提示词：
- **内存浪费**: 加载可能不需要的内容
- **Token 浪费**: 注入到系统提示词增加成本
- **启动慢**: 大量文件 I/O 操作

### 解决方案

```
初始化阶段（轻量）
    ↓
只加载元数据（名称、描述、触发条件）
    ↓
需要时激活
    ↓
加载完整提示词内容
    ↓
注入到系统提示词
```

## 技术实现

### 1. 数据结构

```python
@dataclass
class Skill:
    name: str                    # 技能名称
    description: str             # 技能描述
    trigger: str                 # 触发条件
    prompt_content: Optional[str] = None  # 完整内容（激活时加载）
    is_active: bool = False      # 是否已激活
```

### 2. 初始化流程

```python
# AgentLoop.__init__()
config = {
    "enable_skills": True,
    "active_skills": []  # 可选：指定默认激活的技能
}

loop = AgentLoop(config)
# ↓
# SkillManager._load_skills()
#   - 只解析 SKILL.md 的 frontmatter（元数据）
#   - prompt_content 保持为 None
#   - is_active = False
```

### 3. 激活流程

```python
# 用户激活技能
loop.activate_skill("python-standards")
# ↓
# SkillManager.activate_skill()
#   - 读取 prompt.md 或 SKILL.md 正文
#   - 设置 prompt_content
#   - 设置 is_active = True
```

### 4. 注入流程

```python
# 构建系统提示词时
system_prompt = loop._build_system_prompt()
# ↓
# 获取已激活技能的提示词
active_prompts = skill_manager.get_active_prompts()
#   - 遍历 active_skills
#   - 拼接 prompt_content
#   - 注入到系统提示词的第 3 层
```

## 验证结果

### 内存使用

| 阶段 | python-standards | git-workflow |
|------|------------------|--------------|
| 初始化后 | 0 字节 | 0 字节 |
| 激活后 | 3451 字符 | 2419 字符 |

### Token 节省

假设有 10 个技能，每个平均 3000 字符：
- **全量加载**: ~30,000 字符注入到系统提示词
- **按需激活**: 只注入激活的技能，如激活 2 个则 ~6,000 字符
- **节省**: ~80% 的 token

## 使用方式

### 方式 1: 手动激活

```python
loop = AgentLoop(config)

# 查看可用技能
available = loop.skill_manager.get_available_skills()
# [{'name': 'python-standards', 'description': '...', ...}]

# 激活需要的技能
loop.activate_skill("python-standards")

# 停用不需要的技能
loop.deactivate_skill("git-workflow")
```

### 方式 2: 配置默认激活

```python
config = {
    "active_skills": ["python-standards", "git-workflow"]
}

loop = AgentLoop(config)
# 指定的技能会在初始化时自动激活
```

### 方式 3: 动态激活（未来）

可以基于任务类型自动激活相关技能：

```python
# 未来可扩展的功能
loop.auto_activate_skills(task="refactor python code")
# 自动激活 python-standards
```

## 设计原则

1. **轻量启动**: 初始化时只加载元数据
2. **按需加载**: 激活时才加载完整内容
3. **灵活控制**: 支持手动/配置/自动激活
4. **Token 优化**: 只注入激活的技能

## 相关文件

- `skills/loader.py` - SkillManager 实现
- `core/agent_loop.py` - 集成到主流程
- `demo_skills.py` - 渐进式披露演示
- `skills/python-standards/` - 示例技能
- `skills/git-workflow/` - 示例技能

---

**验证状态**: ✅ 通过
**演示文件**: `demo_skills.py`
