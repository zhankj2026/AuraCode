# Dynamic Workflows 迁移方案

## 📋 概述

**Claude Code Dynamic Workflows** 是 2026 年 5 月 28 日随 Claude Opus 4.8 发布的新功能，核心能力是：

> **让 Claude 为复杂任务动态生成编排脚本，在后台执行数十到数百个并行子代理，并将编排逻辑写入代码而非依赖上下文窗口。**

本文档评估将该功能迁移到 OpenCode 的可行性、差距分析和实施方案。

---

## 一、Dynamic Workflows 核心机制

### 1.1 工作流程

```
用户提出复杂任务
  ↓
Claude 动态规划任务
  ↓
生成编排脚本（JavaScript）
  ↓
运行时执行脚本，后台启动多阶段并行子代理
  ↓
交叉验证 → 结果收敛
  ↓
输出协调后的结果
```

### 1.2 核心特性

| 特性 | Claude Code 实现 | 说明 |
|------|-----------------|------|
| **动态脚本生成** | Claude 生成 JavaScript 脚本 | 脚本持有循环、分支、中间结果 |
| **阶段化执行** | 多阶段 pipeline | 每阶段可包含数十个并行 Agent |
| **大规模并行** | 50-100+ 并行子代理 | 远超 Subagent 并行的几个 |
| **上下文卸载** | 中间结果存脚本变量 | Claude 上下文只持有最终答案 |
| **对抗性审查** | 独立 Agent 相互反驳 | 提高结果可信度 |
| **后台执行** | 会话保持响应 | `/workflows` 查看进度 |
| **可恢复性** | 中断后可继续 | 保存进度到会话 |
| **可重复性** | 脚本可保存和重新运行 | 保存为自定义命令 |
| **权限控制** | 运行前审批计划 | 可查看/编辑原始脚本 |

### 1.3 典型应用场景

1. **代码库审计**：扫描所有 API endpoint 的认证检查
2. **大规模迁移**：500 文件迁移（如 Bun Zig → Rust，75 万行代码）
3. **深度研究**：交叉检查多个来源的研究问题
4. **安全审计**：多 Agent 从不同角度检查安全问题
5. **困难规划**：从多个独立角度起草方案并相互权衡

---

## 二、OpenCode 现有能力对比

### 2.1 已具备的基础

| 能力 | OpenCode 实现 | 文件 |
|------|--------------|------|
| Subagent 并行 | ✅ SubagentManager | `core/subagent.py` |
| 后台执行 | ✅ run_in_background | `core/subagent.py` |
| 任务管理 | ✅ TaskManager | `tools/builtin/task_manager.py` |
| 定时任务 | ✅ CronScheduler | `tools/builtin/cron_tool.py` |
| 协调者模式 | ✅ CoordinatorMode | `core/coordinator.py` |
| 团队协作 | ✅ TeamManager | `tools/builtin/team_manager.py` |
| 批量变更 | ✅ Batch Skill | `skills/batch.py` |
| 代码审查 | ✅ Simplify Skill | `skills/simplify.py` |

### 2.2 核心差距

| 差距维度 | Claude Code | OpenCode | 差距程度 |
|---------|-------------|----------|---------|
| **动态脚本生成** | LLM 生成可执行脚本 | ❌ 无 | 🔴 核心缺失 |
| **阶段化 Pipeline** | 多阶段编排，阶段间传递数据 | ⚠️ 部分（Orchestrator 串行/并行） | 🟡 需增强 |
| **大规模并发** | 50-100+ Agent | ⚠️ 受并发数限制 | 🟡 需调整 |
| **中间结果存储** | 脚本变量，不占上下文 | ❌ 结果在上下文窗口 | 🔴 核心缺失 |
| **对抗性验证** | Agent 相互审查/反驳 | ❌ 无 | 🟡 可实现 |
| **进度可视化** | `/workflows` 交互式 UI | ❌ 无 | 🟢 可选 |
| **可恢复性** | 中断后继续 | ❌ 无 | 🟡 可实现 |
| **脚本持久化** | 保存为可重复命令 | ❌ 无 | 🟡 可实现 |
| **运行前审批** | 显示计划供审批 | ❌ 无 | 🟢 可选 |

---

## 三、迁移可行性分析

### 3.1 技术可行性：✅ 高度可行

**理由**:
1. ✅ **Python 可动态生成和执行代码**
   - `exec()` / `eval()` 支持动态执行
   - `ast` 模块支持 AST 解析和生成
   - 可使用模板引擎生成脚本

2. ✅ **现有 SubagentManager 可作为执行引擎**
   - 已支持并行、后台、Fork 模式
   - 只需增加并发数上限和队列管理

3. ✅ **已有编排基础**
   - `SubagentOrchestrator` 提供串行/并行执行
   - `CoordinatorMode` 提供结果综合
   - 可扩展为阶段化 Pipeline

4. ✅ **持久化和恢复有基础**
   - `CronScheduler` 实现持久化
   - `TeamManager` 实现配置持久化
   - 可复用到 Workflow 状态保存

### 3.2 架构适配性：✅ 可适配

**Claude Code 的 JavaScript 脚本方案**：
```javascript
// Claude Code 生成的脚本示例
const workflow = {
  stages: [
    {
      name: "research",
      agents: [
        { prompt: "扫描 src/routes/ 认证检查", type: "explore" },
        { prompt: "分析权限模型", type: "analyze" },
      ]
    },
    {
      name: "cross-check",
      depends: ["research"],
      agents: [
        { prompt: "验证研究发现的漏洞", type: "review" },
      ]
    }
  ]
}
```

**OpenCode 的 Python 适配方案**：
```python
# OpenCode 生成的脚本（Python dict 或 YAML）
workflow = {
    "stages": [
        {
            "name": "research",
            "agents": [
                {"prompt": "扫描 src/routes/ 认证检查", "agent_type": "explore"},
                {"prompt": "分析权限模型", "agent_type": "impact"},
            ]
        },
        {
            "name": "cross-check",
            "depends": ["research"],
            "agents": [
                {"prompt": "验证研究发现的漏洞", "agent_type": "review"},
            ]
        }
    ]
}
```

**或者使用 DSL（领域特定语言）**：
```yaml
# workflow.yaml
name: "auth-audit"
stages:
  - name: research
    parallel: true
    agents:
      - prompt: "扫描 src/routes/ 认证检查"
        type: explore
      - prompt: "分析权限模型"
        type: impact
  
  - name: cross-check
    depends: [research]
    parallel: true
    agents:
      - prompt: "验证研究发现的漏洞"
        type: review
```

### 3.3 实现复杂度：🟡 中等

**核心挑战**:
1. 🟡 **LLM 生成可执行脚本**
   - 需要设计脚本 Schema 和验证机制
   - 需要 prompt engineering 确保生成正确脚本
   - 复杂度：中等

2. 🟡 **大规模并发管理**
   - 需要并发队列和限流
   - 需要资源监控（内存、线程数）
   - 复杂度：中等

3. 🟡 **中间结果存储和传递**
   - 需要设计阶段间数据传递机制
   - 需要避免上下文膨胀
   - 复杂度：中等

4. 🟢 **进度跟踪和恢复**
   - 基于现有持久化机制扩展
   - 复杂度：低

---

## 四、迁移方案设计

### 4.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Dynamic Workflow Engine                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Script Generator │  │ Script Validator │                │
│  │                  │  │                  │                │
│  │ LLM 生成脚本     │→ │ 验证 Schema      │                │
│  │ (Python/YAML)    │  │ 安全性检查       │                │
│  └──────────────────┘  └────────┬─────────┘                │
│                                 │                           │
│                    ┌────────────▼────────────┐             │
│                    │   Workflow Executor     │             │
│                    │                         │             │
│                    │  Stage 1 (Parallel)     │             │
│                    │    ├─ Agent 1           │             │
│                    │    ├─ Agent 2           │             │
│                    │    └─ Agent N           │             │
│                    │         ↓               │             │
│                    │  Stage 2 (Depends: 1)   │             │
│                    │    ├─ Agent 1           │             │
│                    │    └─ Agent M           │             │
│                    │         ↓               │             │
│                    │  Synthesize Results     │             │
│                    └────────────┬────────────┘             │
│                                 │                           │
│         ┌───────────────────────┼───────────────────────┐  │
│         │                       │                       │  │
│  ┌──────▼──────┐  ┌────────────▼─────────┐  ┌─────────▼──┐│
│  │Result Store │  │ Progress Tracker     │  │Recovery Mgr││
│  │             │  │                      │  │            ││
│  │ 中间结果存储 │  │ 进度/状态跟踪        │  │ 中断恢复   ││
│  └─────────────┘  └──────────────────────┘  └────────────┘│
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ↓
    SubagentManager (执行引擎)
```

### 4.2 核心组件设计

#### 4.2.1 Workflow Script Schema

```python
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

class AgentType(Enum):
    EXPLORE = "explore"
    PLAN = "plan"
    REVIEW = "review"
    IMPACT = "impact"
    DIAGNOSE = "diagnose"
    GENERAL = "general"

@dataclass
class AgentTask:
    """单个 Agent 任务定义"""
    prompt: str                          # 任务提示词
    agent_type: AgentType = AgentType.GENERAL
    timeout: int = 300                   # 超时时间（秒）
    retry_on_failure: bool = False       # 失败重试
    max_retries: int = 2                 # 最大重试次数

@dataclass
class WorkflowStage:
    """工作流阶段"""
    name: str                            # 阶段名称
    agents: List[AgentTask]              # 并行 Agent 列表
    depends: List[str] = field(default_factory=list)  # 依赖的阶段
    synthesize: bool = True              # 是否需要综合结果
    synthesize_prompt: str = ""          # 综合提示词（可选）

@dataclass
class WorkflowScript:
    """完整工作流脚本"""
    name: str                            # 工作流名称
    description: str = ""                # 描述
    stages: List[WorkflowStage]          # 阶段列表
    validation: Dict[str, Any] = field(default_factory=dict)  # 验证规则
    convergence_check: str = ""          # 收敛检查脚本
    max_iterations: int = 3              # 最大迭代次数
```

#### 4.2.2 Script Generator

```python
class WorkflowScriptGenerator:
    """
    使用 LLM 生成工作流脚本
    
    流程:
    1. 分析用户任务
    2. 规划阶段和 Agent
    3. 生成 WorkflowScript 对象
    4. 验证脚本正确性
    """
    
    def generate(self, task_description: str) -> WorkflowScript:
        """
        生成工作流脚本
        
        Args:
            task_description: 用户任务描述
        
        Returns:
            WorkflowScript 对象
        """
        # Prompt LLM 生成脚本
        prompt = self._build_generation_prompt(task_description)
        llm_response = self._call_llm(prompt)
        
        # 解析 LLM 输出为 WorkflowScript
        script = self._parse_response(llm_response)
        
        # 验证脚本
        self._validate_script(script)
        
        return script
    
    def _build_generation_prompt(self, task: str) -> str:
        return f"""
你是一个工作流编排专家。请为以下任务生成工作流脚本：

任务: {task}

要求:
1. 将任务分解为多个阶段（通常 2-5 个阶段）
2. 每个阶段包含多个可并行执行的 Agent 任务
3. 设置阶段间的依赖关系
4. 为需要综合结果的阶段编写综合提示词
5. 设置收敛检查机制（如何判断结果已收敛）

输出格式（Python dict）:
```python
{{
    "name": "工作流名称",
    "description": "描述",
    "stages": [
        {{
            "name": "阶段1名称",
            "agents": [
                {{"prompt": "任务1", "agent_type": "explore"}},
                {{"prompt": "任务2", "agent_type": "review"}}
            ],
            "depends": [],
            "synthesize": true,
            "synthesize_prompt": "综合所有发现，..."
        }},
        {{
            "name": "阶段2名称",
            "agents": [...],
            "depends": ["阶段1名称"],
            ...
        }}
    ],
    "convergence_check": "如何判断收敛",
    "max_iterations": 3
}}
```
"""
```

#### 4.2.3 Workflow Executor

```python
class WorkflowExecutor:
    """
    工作流执行引擎
    
    功能:
    - 按阶段执行（支持依赖）
    - 阶段内并行执行
    - 结果综合
    - 进度跟踪
    - 中断恢复
    """
    
    def __init__(self, script: WorkflowScript):
        self.script = script
        self.stage_results: Dict[str, Dict] = {}
        self.progress: Dict[str, str] = {}  # stage_name -> status
        self.intermediate_store: Dict[str, Any] = {}  # 中间结果存储
        
    async def execute(self) -> Dict:
        """
        执行工作流
        
        Returns:
            最终结果
        """
        # 构建 DAG（依赖图）
        dag = self._build_dag()
        
        # 拓扑排序执行
        execution_order = self._topological_sort(dag)
        
        for stage_name in execution_order:
            stage = self._get_stage(stage_name)
            
            # 等待依赖完成
            await self._wait_for_dependencies(stage)
            
            # 执行阶段
            self.progress[stage_name] = "running"
            stage_results = await self._execute_stage(stage)
            
            # 综合结果（如果需要）
            if stage.synthesize:
                synthesized = await self._synthesize_stage(
                    stage, stage_results
                )
                self.intermediate_store[stage_name] = synthesized
            else:
                self.intermediate_store[stage_name] = stage_results
            
            self.stage_results[stage_name] = stage_results
            self.progress[stage_name] = "completed"
        
        # 收敛检查
        final_result = await self._check_convergence()
        
        return final_result
    
    async def _execute_stage(self, stage: WorkflowStage) -> List[Dict]:
        """
        并行执行阶段内的所有 Agent
        
        Args:
            stage: 阶段定义
        
        Returns:
            Agent 结果列表
        """
        handles = []
        
        # 启动所有 Agent（并行）
        for agent_task in stage.agents:
            handle = subagent_manager.spawn_subagent(
                task=agent_task.prompt,
                agent_type=agent_task.agent_type.value,
                run_in_background=True
            )
            handles.append(handle)
        
        # 等待所有完成
        results = []
        for handle in handles:
            result = handle.join(timeout=handle_timeout)
            results.append({
                "agent_id": handle.agent_id,
                "status": handle.status,
                "result": handle.result
            })
        
        return results
    
    async def _synthesize_stage(
        self, 
        stage: WorkflowStage, 
        results: List[Dict]
    ) -> str:
        """
        综合阶段结果
        
        Args:
            stage: 阶段定义
            results: Agent 结果列表
        
        Returns:
            综合后的结果
        """
        # 收集所有发现
        all_findings = "\n\n".join([
            f"### Agent {r['agent_id']}\n{r['result']}"
            for r in results if r['status'] == 'completed'
        ])
        
        # 使用综合提示词或默认提示词
        synthesize_prompt = stage.synthesize_prompt or (
            "综合以上所有发现，提取关键信息，消除矛盾，"
            "生成一致的结论。如果有相互矛盾的发现，请标注出来。"
        )
        
        # 启动综合 Agent
        synthesis_handle = subagent_manager.spawn_subagent(
            task=f"{synthesize_prompt}\n\n---\n\n所有发现:\n{all_findings}",
            agent_type="general",
            run_in_background=False  # 同步等待
        )
        
        return synthesis_handle.result or ""
```

#### 4.2.4 Progress Tracker & Recovery

```python
class WorkflowProgressTracker:
    """
    工作流进度跟踪和恢复
    
    功能:
    - 持久化进度到文件
    - 中断后恢复
    - 实时进度查询
    """
    
    def __init__(self, workflow_id: str, persist_path: str = ".opencode/workflows/"):
        self.workflow_id = workflow_id
        self.persist_path = Path(persist_path)
        self.state_file = self.persist_path / f"{workflow_id}.json"
        
    def save_state(self, state: Dict):
        """保存进度状态"""
        self.persist_path.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self) -> Optional[Dict]:
        """加载进度状态"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return None
    
    def delete_state(self):
        """删除进度状态（工作流完成后）"""
        if self.state_file.exists():
            self.state_file.unlink()
    
    def get_progress_summary(self) -> str:
        """获取进度摘要"""
        state = self.load_state()
        if not state:
            return "No workflow state found"
        
        stages = state.get('progress', {})
        lines = [f"Workflow: {state.get('name', 'Unknown')}"]
        lines.append(f"Status: {state.get('status', 'unknown')}")
        lines.append("")
        lines.append("Stages:")
        for stage_name, status in stages.items():
            icon = "✅" if status == "completed" else "🔄" if status == "running" else "⏸️"
            lines.append(f"  {icon} {stage_name}: {status}")
        
        return "\n".join(lines)
```

### 4.3 工具注册

```python
from tools.registry import register_tool

# 1. 动态生成并执行工作流
register_tool("dynamic_workflow", {
    "description": (
        "Generate and execute a dynamic workflow for complex tasks. "
        "Claude will analyze the task, create a multi-stage workflow script, "
        "and execute it with parallel agents. Use for large-scale audits, "
        "migrations, research, and security reviews."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Task description (e.g., 'audit all API endpoints for auth checks')"
            },
            "auto_approve": {
                "type": "boolean",
                "description": "Auto-approve the generated script without review",
                "default": False
            },
            "save_script": {
                "type": "boolean",
                "description": "Save the script for future reuse",
                "default": False
            }
        },
        "required": ["task"]
    },
    "handler": dynamic_workflow_handler
})

# 2. 执行已保存的工作流脚本
register_tool("execute_workflow", {
    "description": (
        "Execute a saved workflow script by name or path. "
        "Use for repeating previously defined workflows."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Workflow name or script path"
            }
        },
        "required": ["name"]
    },
    "handler": execute_workflow_handler
})

# 3. 查看工作流进度
register_tool("workflow_status", {
    "description": (
        "Check the progress of running or completed workflows. "
        "Shows stage status, agent status, and intermediate results."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_id": {
                "type": "string",
                "description": "Workflow ID (optional, shows all if not specified)"
            }
        }
    },
    "handler": workflow_status_handler
})

# 4. 保存工作流脚本
register_tool("save_workflow", {
    "description": (
        "Save a generated workflow script for future reuse. "
        "Converts the script into a reusable command."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Workflow name"
            },
            "description": {
                "type": "string",
                "description": "Workflow description"
            }
        },
        "required": ["name"]
    },
    "handler": save_workflow_handler
})
```

---

## 五、实施计划

### Phase 1: 基础框架（1-2 天）

**目标**: 实现 WorkflowScript Schema 和执行引擎

**任务**:
1. ✅ 定义 `WorkflowScript`、`WorkflowStage`、`AgentTask` 数据类
2. ✅ 实现 `WorkflowExecutor` 基础框架
3. ✅ 实现阶段依赖解析（DAG + 拓扑排序）
4. ✅ 实现阶段内并行执行
5. ✅ 集成 SubagentManager

**产出**:
- `core/workflow_engine.py` - 工作流引擎核心
- 可手动编写脚本并执行

### Phase 2: 脚本生成（2-3 天）

**目标**: 实现 LLM 自动生成工作流脚本

**任务**:
1. ✅ 设计 Script Generator prompt
2. ✅ 实现 `WorkflowScriptGenerator`
3. ✅ 实现脚本验证（Schema 校验）
4. ✅ 实现安全性检查（禁止危险操作）
5. ✅ 测试生成质量

**产出**:
- `core/workflow_generator.py` - 脚本生成器
- prompt templates

### Phase 3: 进度与恢复（1-2 天）

**目标**: 实现进度跟踪和中断恢复

**任务**:
1. ✅ 实现 `WorkflowProgressTracker`
2. ✅ 实现状态持久化
3. ✅ 实现中断恢复逻辑
4. ✅ 实现进度查询工具

**产出**:
- `core/workflow_tracker.py` - 进度跟踪器
- 持久化存储

### Phase 4: 工具集成（1 天）

**目标**: 注册工具并集成到系统

**任务**:
1. ✅ 注册 `dynamic_workflow` 工具
2. ✅ 注册 `execute_workflow` 工具
3. ✅ 注册 `workflow_status` 工具
4. ✅ 注册 `save_workflow` 工具
5. ✅ 编写工具文档

**产出**:
- `tools/builtin/workflow_tools.py` - 工具集

### Phase 5: 高级功能（2-3 天）

**目标**: 实现对抗性验证和收敛检查

**任务**:
1. ✅ 实现对抗性审查（Agent 相互反驳）
2. ✅ 实现收敛检查机制
3. ✅ 实现迭代优化（不收敛则重新执行）
4. ✅ 实现中间结果优化存储

**产出**:
- 完整的 Dynamic Workflows 功能

### Phase 6: 测试与优化（2 天）

**目标**: 测试和性能优化

**任务**:
1. ✅ 编写单元测试
2. ✅ 编写集成测试
3. ✅ 性能优化（大规模并发）
4. ✅ 内存优化（中间结果管理）

**产出**:
- 测试套件
- 性能报告

---

## 六、与现有功能的关系

### 6.1 互补关系

| 现有功能 | Dynamic Workflows | 关系 |
|---------|------------------|------|
| Subagent 并行 | 建立在 Subagent 之上 | **依赖** |
| Coordinator 模式 | 更通用的编排 | **扩展** |
| Team 模式 | 临时团队 vs 持久团队 | **互补** |
| Batch Skill | 通用框架 vs 专用场景 | **泛化** |
| Simplify Skill | 可作为 Workflow 阶段 | **集成** |

### 6.2 使用场景选择指南

```
任务特征                     推荐方案
───────────────────────────────────────
简单并行查询（<5个Agent）      → Subagent 并行
需要多轮迭代和结果综合         → Coordinator 模式
多角色长期协作                 → Team 模式
大规模批量变更（5-30单元）     → Batch Skill
代码质量审查                   → Simplify Skill
复杂端到端任务（动态编排）     → Dynamic Workflows ⭐
需要交叉验证和收敛             → Dynamic Workflows ⭐
可重复的复杂工作流             → Dynamic Workflows ⭐
```

---

## 七、技术风险与缓解

### 7.1 风险清单

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| LLM 生成脚本错误 | 执行失败 | 中 | Schema 验证 + 自动重试 |
| 大规模并发资源耗尽 | 系统崩溃 | 低 | 并发限流 + 资源监控 |
| 中间结果内存占用过高 | OOM | 中 | 结果压缩 + 磁盘缓存 |
| 收敛检查不准确 | 无限循环 | 低 | max_iterations 限制 |
| 脚本安全性问题 | 执行恶意代码 | 低 | 沙箱执行 + 权限控制 |

### 7.2 安全措施

1. **脚本验证**:
   - Schema 校验（类型、必填字段）
   - 静态分析（禁止危险操作）
   - 用户审批（auto_approve=False 时）

2. **执行沙箱**:
   - 工具允许列表（继承系统配置）
   - 资源限制（内存、CPU、时间）
   - 文件系统隔离（可选）

3. **权限控制**:
   - 首次运行必须审批
   - 可配置信任列表
   - 审计日志

---

## 八、预期收益

### 8.1 能力提升

| 能力维度 | 提升幅度 | 说明 |
|---------|---------|------|
| **编排规模** | 5-10x | 从几个 Agent 到 50-100+ Agent |
| **可重复性** | 新增 | 脚本可保存和重新运行 |
| **上下文效率** | 显著提升 | 中间结果不占上下文 |
| **结果可信度** | 显著提升 | 对抗性验证 + 收敛检查 |
| **适用范围** | 扩展 | 复杂端到端任务、大规模迁移 |

### 8.2 典型场景收益

**场景 1: 代码库安全审计**
```
Before: 手动启动几个 Subagent，手动汇总结果
After:  自动生成 4 阶段工作流（扫描→分析→交叉验证→报告）
        20+ 并行 Agent，对抗性验证，收敛检查
收益:   结果更全面、更可信，可重复执行
```

**场景 2: 大规模框架迁移**
```
Before: Batch Skill 处理 5-30 个单元
After:  Dynamic Workflow 处理 50-100+ 单元
        多阶段验证（迁移→测试→审查→修复循环）
收益:   规模 10x 提升，自动化验证和修复
```

**场景 3: 深度研究**
```
Before: 手动启动 Subagent 研究，手动交叉检查
After:  自动生成研究流程（搜索→获取→交叉检查→综合）
        多来源验证，过滤未通过交叉检查的声明
收益:   研究质量显著提升，引用可追溯
```

---

## 九、总结与建议

### 9.1 迁移可行性结论

**✅ 高度可行，采用渐进增强方案**

**理由**:
1. ✅ **技术基础完备**: OpenCode 已有 Subagent、Coordinator、Team 等核心组件
2. ✅ **架构适配性好**: Python 可完美替代 JavaScript 脚本方案
3. ✅ **渐进增强可行**: 在现有编排基础上增强，无需推倒重来
4. ✅ **实现难度可控**: 分 3 个 Phase，每阶段 2-3 天，总计 6-8 天
5. ✅ **价值显著**: 填补 Claude Code 最新核心能力，提升编排规模 10x

### 9.2 实施策略：渐进增强（强烈推荐⭐⭐⭐）

**核心思路**: 在现有 5 种编排方式上增强，而非新建引擎

**增强目标**:
1. ✅ **增强 SubagentOrchestrator**（核心执行引擎）
   - 新增 `run_workflow()` 方法
   - 支持阶段化 Pipeline（DAG 依赖）
   - 支持中间结果存储（`intermediate_store`）

2. ✅ **增强 CoordinatorMode**（智能编排）
   - 新增 `load_workflow_script()` 方法
   - 支持 LLM 动态生成脚本
   - 支持进度跟踪和恢复

3. ✅ **新增工具集**（用户接口）
   - `dynamic_workflow` 工具
   - `workflow_status` 工具
   - `save_workflow` 工具

**优势**:
- ✅ 向后兼容 100%（不影响现有功能）
- ✅ 代码改动量小（600-900 行 vs 新建 2000+ 行）
- ✅ 实施时间短（6-8 天 vs 9-13 天）
- ✅ 实施风险低（渐进交付）
- ✅ 用户学习成本低（统一接口）

### 9.3 渐进增强实施计划

#### Phase 1: 增强 SubagentOrchestrator（2-3 天）

**目标**: 让 Orchestrator 支持阶段化工作流执行

**任务**:
1. ✅ 定义 `WorkflowScript`、`WorkflowStage`、`AgentTask` 数据类
2. ✅ 在 `SubagentOrchestrator` 中新增 `run_workflow()` 方法
3. ✅ 实现 DAG 依赖解析和拓扑排序
4. ✅ 实现阶段内并行执行
5. ✅ 实现中间结果存储（`intermediate_store`）
6. ✅ 实现阶段间数据传递

**产出**:
- `core/workflow_types.py` - 工作流类型定义（新增，~150 行）
- `core/subagent.py` - 增强 SubagentOrchestrator（修改，+300 行）

**交付物**: 可手动编写脚本并执行的工作流引擎

#### Phase 2: 增强 CoordinatorMode（2-3 天）

**目标**: 让 Coordinator 支持脚本化编排和 LLM 生成

**任务**:
1. ✅ 在 `CoordinatorMode` 中新增 `load_workflow_script()` 方法
2. ✅ 设计 Script Generator prompt
3. ✅ 实现 `WorkflowScriptGenerator`（LLM 生成脚本）
4. ✅ 实现脚本验证（Schema 校验 + 安全检查）
5. ✅ 实现进度跟踪（复用 CronScheduler 持久化机制）
6. ✅ 实现中断恢复逻辑

**产出**:
- `core/workflow_generator.py` - 脚本生成器（新增，~250 行）
- `core/coordinator.py` - 增强 CoordinatorMode（修改，+250 行）
- `core/workflow_tracker.py` - 进度跟踪器（新增，~150 行）

**交付物**: 支持 LLM 生成脚本和进度跟踪的完整编排

#### Phase 3: 工具集成与高级功能（2 天）

**目标**: 注册工具并实现收敛检查

**任务**:
1. ✅ 注册 `dynamic_workflow` 工具
2. ✅ 注册 `workflow_status` 工具
3. ✅ 注册 `save_workflow` 工具
4. ✅ 实现收敛检查机制
5. ✅ 实现对抗性验证（可选）
6. ✅ 编写工具文档和测试

**产出**:
- `tools/builtin/workflow_tools.py` - 工具集（新增，~200 行）
- 测试套件

**交付物**: 完整的 Dynamic Workflows 用户接口

---

## 附录 A: Claude Code 案例参考

### Bun Zig → Rust 迁移

**规模**: 75 万行 Rust 代码
**时间**: 11 天
**工作流**:
- Workflow 1: 为每个 Zig struct 字段映射 Rust lifetime
- Workflow 2: 将每个 .zig 文件移植为 .rs 文件
- 每个文件有 2 个 reviewer
- 持续驱动构建和测试，直到干净运行

**测试通过率**: 99.8%

### 深度研究

**命令**: `/deep-research What changed in Node.js permission model between v20 and v22?`

**流程**:
1. 多角度扇出网络搜索
2. 获取并交叉检查来源
3. 对每个声明投票
4. 过滤未通过交叉检查的声明
5. 生成引用报告

---

## 附录 B: 脚本示例

### 示例 1: API 认证审计

```python
{
    "name": "api-auth-audit",
    "description": "Audit all API endpoints for missing auth checks",
    "stages": [
        {
            "name": "scan-endpoints",
            "agents": [
                {"prompt": "Scan src/routes/user/ for auth checks", "agent_type": "explore"},
                {"prompt": "Scan src/routes/payment/ for auth checks", "agent_type": "explore"},
                {"prompt": "Scan src/routes/admin/ for auth checks", "agent_type": "explore"},
                {"prompt": "Scan src/routes/public/ for auth checks", "agent_type": "explore"}
            ],
            "depends": [],
            "synthesize": true,
            "synthesize_prompt": "汇总所有扫描结果，列出缺少认证检查的 endpoint"
        },
        {
            "name": "verify-findings",
            "agents": [
                {"prompt": "验证扫描发现的缺少认证的 endpoint，确认真实性", "agent_type": "review"},
                {"prompt": "检查是否有隐式认证机制（如中间件）被遗漏", "agent_type": "review"}
            ],
            "depends": ["scan-endpoints"],
            "synthesize": true,
            "synthesize_prompt": "综合验证结果，过滤误报，生成最终报告"
        },
        {
            "name": "generate-report",
            "agents": [
                {"prompt": "生成审计报告，包含 endpoint 列表、风险等级、修复建议", "agent_type": "general"}
            ],
            "depends": ["verify-findings"],
            "synthesize": false
        }
    ],
    "max_iterations": 2
}
```

### 示例 2: 深度研究

```python
{
    "name": "deep-research",
    "description": "Research question with cross-validation",
    "stages": [
        {
            "name": "search",
            "agents": [
                {"prompt": "Search for Node.js v20 permission model documentation", "agent_type": "explore"},
                {"prompt": "Search for Node.js v22 permission model documentation", "agent_type": "explore"},
                {"prompt": "Search for breaking changes between v20 and v22", "agent_type": "explore"}
            ],
            "depends": [],
            "synthesize": false
        },
        {
            "name": "fetch-sources",
            "agents": [
                {"prompt": "Fetch and extract key info from search results (sources 1-5)", "agent_type": "explore"},
                {"prompt": "Fetch and extract key info from search results (sources 6-10)", "agent_type": "explore"}
            ],
            "depends": ["search"],
            "synthesize": false
        },
        {
            "name": "cross-check",
            "agents": [
                {"prompt": "Cross-check claims from different sources, identify contradictions", "agent_type": "review"},
                {"prompt": "Verify claims against official Node.js documentation", "agent_type": "review"}
            ],
            "depends": ["fetch-sources"],
            "synthesize": true,
            "synthesize_prompt": "综合交叉检查结果，过滤未通过验证的声明，生成可信结论列表"
        },
        {
            "name": "synthesis",
            "agents": [
                {"prompt": "Write a cited report with verified claims only", "agent_type": "general"}
            ],
            "depends": ["cross-check"],
            "synthesize": false
        }
    ],
    "max_iterations": 1
}
```

---

**文档版本**: v1.0
**创建日期**: 2026-06-02
**状态**: 待评审
