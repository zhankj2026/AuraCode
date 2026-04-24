# Skill 激活机制完整方案

## 问题的解决

### 原始问题
用户提到之前会话讨论过 `tools\builtin\skill_tools.py`，实际上：
1. 我之前创建了这个文件，但后来删除了
2. 这导致 LLM **无法自己激活技能**
3. LLM 只能看到可用技能列表，但没有工具来激活它们

### 解决方案
创建完整的技能工具系统，让 LLM 能够自主管理技能。

## 架构设计

### 组件关系

```
┌─────────────────────────────────────────────────────────┐
│                    AgentLoop                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │  _init_extensions()                              │  │
│  │    ↓                                              │  │
│  │  SkillManager()                                   │  │
│  │    ↓                                              │  │
│  │  SkillContext.set_skill_manager(skill_manager)   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  SkillContext (单例)                     │
│  - set_skill_manager()                                 │
│  - activate_skill()                                    │
│  - deactivate_skill()                                  │
│  - list_skills()                                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              Skill Tools (5 个工具)                      │
│  - list_skills()                                       │
│  - show_available_skills()                             │
│  - activate_skill()                                    │
│  - deactivate_skill()                                  │
│  - get_active_skills()                                 │
└─────────────────────────────────────────────────────────┘
```

### 核心优势

**解耦设计**:
- 工具不直接依赖 AgentLoop 实例
- 通过 SkillContext 单例间接访问
- 避免循环依赖问题

## 激活时机

### 1. 用户手动激活

```python
loop = AgentLoop(config)
loop.activate_skill("python-standards")
```

**使用场景**:
- 用户明确知道需要某个技能
- 长期会话中预设技能

### 2. 配置默认激活

```python
config = {
    "active_skills": ["python-standards", "git-workflow"]
}
loop = AgentLoop(config)
```

**使用场景**:
- 特定项目的默认技能
- 工作流程标准化

### 3. LLM 自主激活 ⭐ **新增**

```python
# LLM 调用工具
activate_skill(skill_name="python-standards")
```

**使用场景**:
- LLM 分析任务后主动建议激活技能
- 根据上下文自动激活相关技能
- 提供更好的用户体验

**示例对话**:
```
用户: 帮我写一个 Python 函数来处理数据

LLM: 我注意到这个任务涉及 Python 编码。
让我先激活 python-standards 技能来确保代码质量...

[调用 activate_skill(skill_name="python-standards")]

python-standards 技能已激活！现在我将遵循
Python 编码规范来编写这个函数...
```

### 4. 未来：基于任务自动激活

```python
# 未来可扩展的功能
def auto_activate_skills(task: str):
    """根据任务类型自动激活相关技能"""
    if "python" in task.lower():
        activate_skill("python-standards")
    if "git" in task.lower():
        activate_skill("git-workflow")
```

## 工具详解

### 1. show_available_skills()
**用途**: 让 LLM 了解有哪些技能可用

```python
# 返回
**python-standards** [未激活]
  描述: Python 编码规范和最佳实践
  触发: 编写或修改 Python 代码时

**git-workflow** [未激活]
  描述: Git 工作流和提交规范
  触发: 执行 Git 操作或提交时
```

### 2. activate_skill()
**用途**: LLM 激活需要的技能

```python
# 调用
activate_skill(skill_name="python-standards")

# 返回
技能 'python-standards' 已激活

当前已激活的技能: python-standards

注意: 技能激活后将在下一次 LLM 调用时生效。
```

### 3. get_active_skills()
**用途**: LLM 查询当前激活的技能

```python
# 返回
当前已激活的技能:

- python-standards
- git-workflow

使用 deactivate_skill 工具来停用不需要的技能。
```

### 4. deactivate_skill()
**用途**: LLM 停用不需要的技能

```python
# 调用
deactivate_skill(skill_name="git-workflow")

# 返回
技能 'git-workflow' 已停用

当前仍激活的技能: python-standards
```

### 5. list_skills()
**用途**: 获取详细的技能列表

```python
# 调用
list_skills(detailed=True)

# 返回包含提示词预览的详细信息
```

## 系统提示词的演变

### 改进前
```
第 3 层: 技能提示词
└── [只有已激活技能的完整内容]
    └── LLM 不知道有哪些其他技能可用
```

### 改进后
```
第 3 层: 技能系统
├── 可用技能列表（元数据，始终存在）
│   ├── python-standards: ... [状态]
│   └── git-workflow: ... [状态]
│
└── 已激活技能的详细内容（按需加载）
    └── LLM 看到可用技能，可以通过工具激活
```

## 验证结果

### 测试数据
```
无激活技能的系统提示词: 1,772 字符
两个激活技能的系统提示词: 7,718 字符
差异: 5,946 字符（只为激活的技能付费）
```

### 功能验证
✅ 5 个技能工具已正确注册
✅ 工具可以激活/停用技能
✅ 工具可以查询技能状态
✅ 激活后技能内容注入到系统提示词
✅ Token 使用符合渐进式披露原则

## 使用场景示例

### 场景 1: LLM 主动建议激活技能

```
用户: 帮我重构这个 Python 代码

LLM: 我注意到这个任务涉及 Python 代码重构。
根据可用技能列表，我有 python-standards 技能，
它包含了 Python 编码规范和最佳实践。

[调用 activate_skill(skill_name="python-standards")]

已激活！现在我将遵循 PEP 8 规范来重构代码...
```

### 场景 2: 多技能协作

```
用户: 完成开发并提交代码

LLM: 这个任务涉及代码编写和 Git 提交。
我将激活相关技能：

1. [调用 activate_skill(skill_name="python-standards")]
2. [调用 activate_skill(skill_name="git-workflow")]

两个技能已激活！现在我将：
- 遵循 Python 编码规范编写代码
- 按照规范撰写 Git 提交信息
```

### 场景 3: 技能切换

```
用户: 现在开始处理 API 设计

LLM: 之前的 git-workflow 技能不再需要了。
让我先停用它，然后查看是否有 API 相关的技能...

[调用 deactivate_skill(skill_name="git-workflow")]
[调用 show_available_skills()]

我目前没有专门的 API 设计技能，
但我可以基于通用的最佳实践来设计...
```

## 总结

| 方面 | 改进前 | 改进后 |
|------|--------|--------|
| 激活方式 | 用户手动 | 用户 + LLM 自主 |
| 可发现性 | ❌ 低 | ✅ 高 |
| 智能化 | ❌ 无 | ✅ LLM 可主动激活 |
| 用户体验 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**现在 LLM 真正成为了技能系统的主动管理者！**

---

**相关文件**:
- `skills/context.py` - 技能上下文（单例）
- `tools/builtin/skill_tools.py` - 5 个技能工具
- `core/agent_loop.py` - 集成代码
- `test_skill_tools.py` - 测试验证
