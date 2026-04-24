# Skill 使用场景分析

## 两个关键方法的区别

### `get_available_skills()` - 可用技能
```python
[
    {
        'name': 'python-standards',
        'description': 'Python 编码规范和最佳实践',
        'trigger': '在编写或修改 Python 代码时激活',
        'is_active': False
    },
    {
        'name': 'git-workflow',
        'description': 'Git 工作流和提交规范',
        'trigger': '执行 Git 操作或提交时激活',
        'is_active': True
    }
]
```
- **返回内容**: 元数据（名称、描述、触发条件、激活状态）
- **不包含**: 完整的提示词内容
- **用途**: 让 LLM 知道有哪些技能可用

### `get_active_skills()` - 已激活技能
```python
['python-standards', 'git-workflow']
```
- **返回内容**: 已激活技能的名称列表
- **配合**: `get_active_prompts()` 获取完整内容
- **用途**: 构建系统提示词时注入激活的技能

## 当前实现的问题

### 当前 `_build_system_prompt()` 的逻辑

```python
# 第 3 层: 技能提示词
if self.skill_manager and self.skills_enabled:
    active_skills = self.skill_manager.get_active_skills()
    if active_skills:
        skill_prompts = self.skill_manager.get_active_prompts()
        if skill_prompts:
            parts.append(f"## 激活的技能\n\n{skill_prompts}")
```

**问题**: LLM 不知道有哪些技能可用，无法主动选择激活！

### 三种设计方案对比

| 方案 | 系统提示词内容 | Token 使用 | LLM 能力 | 推荐度 |
|------|----------------|------------|----------|--------|
| **方案 1: 当前** | 只注入已激活技能的完整内容 | 少 | ❌ 不知道有哪些技能可用 | ⭐⭐ |
| **方案 2: 全部注入** | 注入所有技能的完整内容 | 多 | ✅ 知道所有技能内容 | ⭐ |
| **方案 3: 元数据注入** | 所有技能元数据 + 已激活技能的完整内容 | 中 | ✅ 知道可用技能，可根据需要激活 | ⭐⭐⭐⭐⭐ |

## 推荐方案 3: 元数据注入

### 设计理念

```
系统提示词结构:

┌─────────────────────────────────────────────────┐
│ 第 3 层: 技能系统                                │
├─────────────────────────────────────────────────┤
│ ## 可用技能                                      │
│                                                  │
│ 以下技能可用于增强特定任务的专业性:               │
│                                                  │
│ - **python-standards**: Python 编码规范          │
│   触发: 编写或修改 Python 代码时                 │
│   状态: ✅ 已激活                                │
│                                                  │
│ - **git-workflow**: Git 工作流规范               │
│   触发: 执行 Git 操作或提交时                    │
│   状态: ⏸️ 未激活                               │
│                                                  │
│ - **api-design**: API 设计最佳实践               │
│   触发: 设计或修改 API 时                        │
│   状态: ⏸️ 未激活                               │
│                                                  │
├─────────────────────────────────────────────────┤
│ ## 已激活技能的详细内容                          │
│                                                  │
│ # Skill: python-standards                       │
│ [完整的 python-standards 提示词内容...]         │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 优势

1. **LLM 知道有哪些技能可用**
   - 可以根据任务类型主动建议激活相关技能
   - 提供更好的用户体验

2. **Token 使用可控**
   - 只注入已激活技能的完整内容
   - 可用技能只显示元数据（轻量）

3. **灵活性**
   - 用户可以手动激活技能
   - LLM 可以建议激活技能
   - 未来可以实现自动激活

### 实现改进

```python
def _build_system_prompt(self) -> str:
    """构建系统提示词(增强版 5 层)"""
    parts = []

    # 第 1 层: 基础角色定义
    parts.append(self._base_role())

    # 第 2 层: 项目上下文(CLAUDE.md)
    project_context = load_project_context()
    if project_context:
        parts.append(project_context)

    # 第 3 层: 技能系统（改进版）
    if self.skill_manager and self.skills_enabled:
        # 3.1 可用技能列表（元数据）
        available = self.skill_manager.get_available_skills()
        if available:
            skill_list = []
            skill_list.append("## 可用技能\n\n")
            skill_list.append("以下技能可用于增强特定任务的专业性:\n\n")

            for skill_info in available:
                status = "✅ 已激活" if skill_info['is_active'] else "⏸️ 未激活"
                skill_list.append(f"- **{skill_info['name']}**: {skill_info['description']}\n")
                skill_list.append(f"  触发: {skill_info['trigger']}\n")
                skill_list.append(f"  状态: {status}\n\n")

            parts.append("".join(skill_list))

        # 3.2 已激活技能的完整内容
        active_skills = self.skill_manager.get_active_skills()
        if active_skills:
            skill_prompts = self.skill_manager.get_active_prompts()
            if skill_prompts:
                parts.append(f"\n## 已激活技能的详细内容\n\n{skill_prompts}")
                logger.debug(f"包含 {len(active_skills)} 个激活的技能提示词")

    # 第 4 层: 工具说明
    parts.append(self._tools_description())

    # 第 5 层: 安全规则
    parts.append(self._security_rules())

    return "\n\n".join(parts)
```

## 使用场景对比

### 场景 1: 用户编写 Python 代码

**当前实现**:
```
LLM 不知道有 python-standards 技能，可能不会遵循最佳实践
```

**改进后**:
```
LLM 看到可用技能列表，发现 python-standards 相关
如果已激活，直接应用规范
如果未激活，可以建议用户激活
```

### 场景 2: 用户进行 Git 提交

**当前实现**:
```
LLM 可能不知道有 git-workflow 技能
```

**改进后**:
```
LLM 看到可用技能中有 git-workflow
可以提示用户: "建议激活 git-workflow 技能以确保提交符合规范"
```

### 场景 3: 复杂任务需要多个技能

**当前实现**:
```
用户需要手动知道有哪些技能可用
```

**改进后**:
```
LLM 可以根据任务自动建议: "这个任务涉及 API 设计，建议激活 api-design 技能"
```

## 总结

| 方面 | 当前实现 | 改进方案 |
|------|----------|----------|
| 可发现性 | ❌ 低 | ✅ 高 |
| Token 效率 | ✅ 高 | ✅ 高 |
| 用户体验 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 智能化 | ❌ 无 | ✅ LLM 可建议 |

**推荐采用方案 3**，在系统提示词中同时展示:
1. 所有可用技能的元数据（轻量）
2. 已激活技能的完整内容（重量）
