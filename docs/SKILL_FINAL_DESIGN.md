# Skill 系统最终设计方案

## 问题分析

### `get_available_skills()` vs `get_active_skills()`

| 方法 | 返回内容 | 用途 | Token |
|------|----------|------|-------|
| `get_available_skills()` | 所有技能的元数据 | 让 LLM 知道有哪些技能可用 | 少 |
| `get_active_skills()` | 已激活技能的名称列表 | 获取当前激活的技能 | 极少 |
| `get_active_prompts()` | 已激活技能的完整内容 | 注入到系统提示词 | 多 |

### 原始实现的问题

```python
# 原始实现: 只注入已激活技能的完整内容
if active_skills:
    skill_prompts = self.skill_manager.get_active_prompts()
    parts.append(f"## 激活的技能\n\n{skill_prompts}")
```

**问题**: LLM 不知道有哪些技能可用，无法主动建议激活相关技能

## 最终方案

### 设计理念

```
系统提示词结构:

┌─────────────────────────────────────────────────┐
│ 第 3 层: 技能系统                                │
├─────────────────────────────────────────────────┤
│ ## 可用技能（元数据，始终存在）                  │
│                                                  │
│ - **python-standards**: Python 编码规范          │
│   触发: 编写或修改 Python 代码时                 │
│   状态: [已激活]                                 │
│                                                  │
│ - **git-workflow**: Git 工作流规范               │
│   触发: 执行 Git 操作或提交时                    │
│   状态: [未激活]                                 │
│                                                  │
├─────────────────────────────────────────────────┤
│ ## 已激活技能的详细内容（按需加载）              │
│                                                  │
│ # Skill: python-standards                       │
│ [完整的 python-standards 提示词内容...]         │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 核心改进

```python
def _build_system_prompt(self) -> str:
    # ... 其他层 ...

    # 第 3 层: 技能系统（改进版）
    if self.skill_manager and self.skills_enabled:
        # 3.1 可用技能列表（元数据，轻量）
        available = self.skill_manager.get_available_skills()
        if available:
            skill_list = ["## 可用技能\n\n"]
            skill_list.append("以下技能可用于增强特定任务的专业性:\n\n")

            for skill_info in available:
                status = "[已激活]" if skill_info['is_active'] else "[未激活]"
                skill_list.append(f"- **{skill_info['name']}**: {skill_info['description']}\n")
                skill_list.append(f"  触发: {skill_info['trigger']}\n")
                skill_list.append(f"  状态: {status}\n\n")

            parts.append("".join(skill_list))

        # 3.2 已激活技能的完整内容（按需加载）
        active_skills = self.skill_manager.get_active_skills()
        if active_skills:
            skill_prompts = self.skill_manager.get_active_prompts()
            if skill_prompts:
                parts.append(f"\n## 已激活技能的详细内容\n\n{skill_prompts}")
```

## 验证结果

### Token 使用对比

| 场景 | 系统提示词长度 | 说明 |
|------|----------------|------|
| 无激活技能 | 1,355 字符 | 只包含元数据 |
| 两个激活技能 | 7,300 字符 | 元数据 + 2 个技能的完整内容 |
| 增量 | +5,946 字符 | 只为激活的技能付费 |

### 功能验证

✅ **可发现性**: LLM 知道有哪些技能可用
✅ **Token 效率**: 只加载激活技能的完整内容
✅ **状态显示**: 清楚显示哪些技能已激活
✅ **渐进式披露**: 元数据始终轻量，完整内容按需加载

## 使用场景示例

### 场景 1: 用户编写 Python 代码

**LLM 的响应**（改进后）:
```
我注意到有 python-standards 技能可用。
该技能已激活，我将遵循 Python 编码规范来编写代码...
```

### 场景 2: 用户进行 Git 操作

**LLM 的响应**（改进后）:
```
我注意到有 git-workflow 技能可用。
该技能目前未激活，建议激活它以确保提交符合规范。
是否需要我激活 git-workflow 技能？
```

### 场景 3: 复杂任务涉及多个领域

**LLM 的响应**（改进后）:
```
根据任务分析，我建议激活以下技能：
- python-standards: 用于确保代码质量
- api-design: 用于设计 RESTful API

是否需要我激活这些技能？
```

## 渐进式披露的完整实现

### 初始化阶段
```python
SkillManager()
  ↓
_load_skills()
  ↓
只解析 SKILL.md 的 frontmatter（元数据）
  ↓
prompt_content = None  # ✅ 不加载完整内容
```

### 激活阶段
```python
activate_skill("python-standards")
  ↓
读取 prompt.md 或 SKILL.md 正文
  ↓
prompt_content = "..."  # ✅ 按需加载完整内容
```

### 注入阶段
```python
_build_system_prompt()
  ↓
1. 获取所有可用技能的元数据（始终轻量）
2. 获取已激活技能的完整内容（按需加载）
  ↓
注入到系统提示词
```

## 总结

| 方面 | 改进前 | 改进后 |
|------|--------|--------|
| 可发现性 | ❌ LLM 不知道有哪些技能 | ✅ LLM 看到所有可用技能 |
| Token 效率 | ✅ 只加载激活的技能 | ✅ 仍然高效（元数据轻量） |
| 用户体验 | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 智能化 | ❌ 无 | ✅ LLM 可建议激活技能 |
| 渐进式披露 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**最终方案同时实现了：**
1. ✅ 完全的渐进式披露
2. ✅ 高度的可发现性
3. ✅ 优秀的 Token 效率
4. ✅ 更好的用户体验

---

**相关文件**:
- `core/agent_loop.py` - 实现代码
- `test_skill_metadata.py` - 测试验证
- `docs/SKILL_USAGE_ANALYSIS.md` - 详细分析
