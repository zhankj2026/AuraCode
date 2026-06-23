# Dynamic Workflows 快速入门

## 📋 概述

Dynamic Workflows 是 Claude Code 的高级编排功能，现已通过**渐进增强**方式集成到 OpenCode。

**核心能力**:
- ✅ 阶段化 Pipeline 执行（DAG 依赖）
- ✅ 大规模并行（50-100+ Agent）
- ✅ 中间结果存储（上下文卸载）
- ✅ 脚本可保存和复用

---

## 🚀 快速开始

### 示例 1: API 认证审计

```python
from core.subagent import SubagentOrchestrator
from core.workflow_types import create_simple_workflow

# 1. 创建工作流脚本
workflow = create_simple_workflow(
    name="api-auth-audit",
    description="审计 API endpoint 的认证检查",
    stages=[
        {
            "name": "scan",
            "agents": [
                {"prompt": "扫描 src/routes/ 下所有 API endpoint，检查是否有认证检查", "agent_type": "explore"},
                {"prompt": "分析认证中间件的实现", "agent_type": "explore"},
            ],
            "depends": [],
            "synthesize": True,
            "synthesize_prompt": "汇总扫描结果，列出缺少认证检查的 endpoint"
        },
        {
            "name": "verify",
            "agents": [
                {"prompt": "验证扫描发现的缺少认证的 endpoint，确认真实性", "agent_type": "review"},
            ],
            "depends": ["scan"],
            "synthesize": True,
        },
        {
            "name": "report",
            "agents": [
                {"prompt": "生成审计报告，包含 endpoint 列表、风险等级、修复建议", "agent_type": "general"},
            ],
            "depends": ["verify"],
            "synthesize": False,
        }
    ]
)

# 2. 执行工作流
orchestrator = SubagentOrchestrator()
result = orchestrator.run_workflow(workflow)

# 3. 查看结果
print(f"工作流: {result['workflow_name']}")
print(f"收敛: {result['converged']}")
print(f"最终结果: {result['final_result'][:500]}")
```

### 示例 2: 深度研究（交叉验证）

```python
from core.workflow_types import create_simple_workflow

workflow = create_simple_workflow(
    name="deep-research",
    description="深度研究（交叉验证多个来源）",
    stages=[
        {
            "name": "search",
            "agents": [
                {"prompt": "搜索 Node.js v20 权限模型", "agent_type": "explore"},
                {"prompt": "搜索 Node.js v22 权限模型", "agent_type": "explore"},
                {"prompt": "搜索 v20 到 v22 的破坏性变更", "agent_type": "explore"},
            ],
            "depends": [],
            "synthesize": False,
        },
        {
            "name": "fetch",
            "agents": [
                {"prompt": "获取并提取搜索结果的关键信息（来源 1-5）", "agent_type": "explore"},
                {"prompt": "获取并提取搜索结果的关键信息（来源 6-10）", "agent_type": "explore"},
            ],
            "depends": ["search"],
            "synthesize": False,
        },
        {
            "name": "cross-check",
            "agents": [
                {"prompt": "交叉检查不同来源的声明，识别矛盾", "agent_type": "review"},
                {"prompt": "根据 Node.js 官方文档验证声明", "agent_type": "review"},
            ],
            "depends": ["fetch"],
            "synthesize": True,
            "synthesize_prompt": "综合交叉检查结果，过滤未通过验证的声明，生成可信结论列表"
        },
        {
            "name": "report",
            "agents": [
                {"prompt": "编写引用报告，仅包含已验证的声明", "agent_type": "general"},
            ],
            "depends": ["cross-check"],
            "synthesize": False,
        }
    ]
)

# 执行
orchestrator = SubagentOrchestrator()
result = orchestrator.run_workflow(workflow)
```

---

## 📖 使用手册

### 1. 创建工作流脚本

#### 方法 A: 使用辅助函数（推荐）

```python
from core.workflow_types import create_simple_workflow

workflow = create_simple_workflow(
    name="my-workflow",
    description="描述",
    stages=[
        {
            "name": "阶段名",
            "agents": [
                {"prompt": "任务", "agent_type": "explore"}
            ],
            "depends": [],  # 依赖的阶段（可选）
            "synthesize": True,  # 是否综合结果（可选，默认 True）
            "synthesize_prompt": "综合提示词"  # 可选
        }
    ]
)
```

#### 方法 B: 直接创建对象

```python
from core.workflow_types import WorkflowScript, WorkflowStage, AgentTask, AgentType

workflow = WorkflowScript(
    name="my-workflow",
    description="描述",
    stages=[
        WorkflowStage(
            name="stage1",
            agents=[
                AgentTask(
                    prompt="任务",
                    agent_type=AgentType.EXPLORE
                )
            ],
            depends=[],
            synthesize=True
        )
    ]
)
```

#### 方法 C: 从 JSON 加载

```python
from core.workflow_types import workflow_from_json

json_str = """
{
    "name": "my-workflow",
    "stages": [
        {
            "name": "stage1",
            "agents": [
                {"prompt": "任务", "agent_type": "explore"}
            ]
        }
    ]
}
"""

workflow = workflow_from_json(json_str)
```

### 2. 验证脚本

```python
errors = workflow.validate()
if errors:
    print("脚本验证失败:")
    for error in errors:
        print(f"  - {error}")
else:
    print("✅ 脚本验证通过")
```

### 3. 查看执行顺序

```python
order = workflow.get_execution_order()
print(f"执行顺序: {' -> '.join(order)}")
# 输出: 执行顺序: scan -> verify -> report
```

### 4. 执行工作流

```python
from core.subagent import SubagentOrchestrator

orchestrator = SubagentOrchestrator()
result = orchestrator.run_workflow(workflow)
```

### 5. 查看结果

```python
# 基本信息
print(f"工作流: {result['workflow_name']}")
print(f"收敛: {result['converged']}")
print(f"迭代次数: {result['iterations']}")

# 阶段结果
for stage_name, stage_result in result['stages'].items():
    print(f"\n阶段: {stage_name}")
    print(f"  Agent 数: {len(stage_result)}")
    for agent_result in stage_result:
        print(f"  - {agent_result['agent_id']}: {agent_result['status']}")

# 中间存储（上下文卸载）
print(f"\n中间结果:")
for stage_name, content in result['intermediate_store'].items():
    print(f"  {stage_name}: {content[:100]}...")

# 最终结果
print(f"\n最终结果:\n{result['final_result']}")
```

### 6. 序列化/反序列化

```python
from core.workflow_types import workflow_to_json, workflow_from_json

# 序列化为 JSON
json_str = workflow_to_json(workflow, indent=2)

# 保存到文件
with open("my_workflow.json", "w") as f:
    f.write(json_str)

# 从文件加载
with open("my_workflow.json") as f:
    workflow = workflow_from_json(f.read())
```

---

## 🎯 Agent 类型

| 类型 | 用途 | 系统提示词 |
|------|------|-----------|
| `explore` | 探索、调研、信息收集 | 强调全面性和深度 |
| `plan` | 规划、设计方案 | 强调结构化和可行性 |
| `review` | 审查、验证、找问题 | 强调批判性思维 |
| `impact` | 影响分析 | 强调全面评估影响 |
| `diagnose` | 诊断问题 | 强调根因分析 |
| `general` | 通用任务 | 标准提示词 |

---

## 💡 最佳实践

### 1. 阶段设计原则

- **独立性**: 每个阶段应有明确的输入和输出
- **并行性**: 阶段内的 Agent 任务应可并行执行
- **依赖清晰**: 明确声明阶段间的依赖关系
- **综合必要**: 只在需要时使用 `synthesize=True`

### 2. Prompt 设计原则

- **自包含**: 每个 Agent 的 prompt 必须自包含（Agent 无法看到其他对话）
- **具体**: 明确指定要做什么、怎么做、输出格式
- **上下文**: 如需访问之前阶段结果，在 prompt 中引用

### 3. 中间结果管理

```python
# 查看中间存储
store = orchestrator.get_intermediate_store()

# 清空中间存储（释放内存）
orchestrator.clear_intermediate_store()
```

### 4. 错误处理

```python
try:
    result = orchestrator.run_workflow(workflow)
except ValueError as e:
    print(f"脚本错误: {e}")
except RuntimeError as e:
    print(f"执行错误: {e}")
```

---

## 🔧 高级功能

### 收敛检查（TODO）

```python
workflow = create_simple_workflow(
    name="iterative-workflow",
    stages=[...],
    convergence_check="检查是否所有声明都通过交叉验证",
    max_iterations=3
)
```

### 对抗性验证（TODO）

```python
workflow = create_simple_workflow(
    name="adversarial-review",
    stages=[
        {"name": "implement", "agents": [...]},
        {"name": "challenge", "agents": [...]},  # 反驳实现
        {"name": "vote", "agents": [...]},  # 投票过滤
    ]
)
```

---

## 📊 与现有编排方式对比

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 简单并行查询（<5 个 Agent） | Subagent 并行 | 最简单 |
| 需要多轮迭代 | Coordinator | 结果综合 |
| 多角色长期协作 | Team | 自主认领 |
| 大规模批量变更 | Batch Skill | worktree 隔离 |
| 代码质量审查 | Simplify Skill | 三路审查 |
| **复杂端到端任务** | **Dynamic Workflows** | **阶段化 + 上下文卸载** |
| **需要交叉验证** | **Dynamic Workflows** | **多阶段验证** |
| **可重复执行** | **Dynamic Workflows** | **脚本可保存** |

---

## 🎓 示例场景

### 场景 1: 代码库安全审计

```python
workflow = create_simple_workflow(
    name="security-audit",
    description="全面安全审计",
    stages=[
        {"name": "scan-auth", "agents": [{"prompt": "扫描认证逻辑", "agent_type": "explore"}]},
        {"name": "scan-input", "agents": [{"prompt": "扫描输入验证", "agent_type": "explore"}]},
        {"name": "scan-crypto", "agents": [{"prompt": "扫描加密实现", "agent_type": "explore"}]},
        {"name": "verify", "agents": [{"prompt": "验证所有发现", "agent_type": "review"}], "depends": ["scan-auth", "scan-input", "scan-crypto"]},
        {"name": "report", "agents": [{"prompt": "生成安全报告", "agent_type": "general"}], "depends": ["verify"]}
    ]
)
```

### 场景 2: 大规模重构规划

```python
workflow = create_simple_workflow(
    name="refactor-plan",
    description="重构规划（多方案对比）",
    stages=[
        {"name": "analyze", "agents": [
            {"prompt": "分析当前架构", "agent_type": "explore"},
            {"prompt": "识别技术债", "agent_type": "diagnose"}
        ]},
        {"name": "design-a", "agents": [{"prompt": "设计方案 A（保守）", "agent_type": "plan"}], "depends": ["analyze"]},
        {"name": "design-b", "agents": [{"prompt": "设计方案 B（激进）", "agent_type": "plan"}], "depends": ["analyze"]},
        {"name": "compare", "agents": [{"prompt": "对比方案 A 和 B", "agent_type": "review"}], "depends": ["design-a", "design-b"]},
        {"name": "recommend", "agents": [{"prompt": "给出推荐方案", "agent_type": "general"}], "depends": ["compare"]}
    ]
)
```

---

## 📝 总结

Dynamic Workflows 通过**渐进增强**方式集成到 OpenCode，核心优势：

1. **上下文卸载**: 中间结果存储在脚本变量，不占 LLM 上下文
2. **阶段化执行**: 支持复杂的多阶段 Pipeline（DAG 依赖）
3. **可重复性**: 脚本可保存、复用、版本控制
4. **向后兼容**: 100% 兼容现有 Subagent/Coordinator/Team 功能

**下一步**: Phase 2 - 增强 CoordinatorMode 支持 LLM 生成脚本
