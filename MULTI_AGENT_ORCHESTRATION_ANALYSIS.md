# Claude Code vs OpenCode 多智能体编排协作对比分析

## 一、Claude Code 的多智能体编排协作方式

Claude Code 实现了 **5 种核心编排模式**，覆盖从简单并行到大规模协作的完整场景：

---

### 1. **Subagent 并行模式** (基础并行)

**文件**: `src/tools/AgentTool/AgentTool.tsx`, `src/tools/AgentTool/forkSubagent.ts`

**核心机制**:
- 通过 `Agent` 工具创建子代理（Subagent）
- 支持多种专业类型：`explore`, `plan`, `review`, `impact`, `diagnose`, `general-purpose`
- 支持 **Fork 模式**（继承父会话上下文）和 **Fresh 模式**（独立上下文）
- 后台异步执行（`run_in_background: true`）或同步等待
- 结果自动通知（`<task-notification>` XML 格式）

**协作流程**:
```
用户请求
  ↓
主 Agent 分析任务
  ↓
并行启动多个 Subagent（单次消息中多次工具调用）
  ├─ Subagent A: 研究模块 X
  ├─ Subagent B: 研究模块 Y
  └─ Subagent C: 检查测试模式
  ↓
每个 Subagent 独立执行，完成后发送 <task-notification>
  ↓
主 Agent 接收通知，汇总结果
  ↓
继续下一步工作（或使用 SendMessage 继续某个 Subagent）
```

**关键特性**:
- **并发控制**: 系统自动管理并发数
- **上下文隔离**: 每个 Subagent 有独立上下文窗口
- **结果通知**: 异步通知机制，不阻塞主循环
- **Fork 继承**: Fork 模式可继承完整对话历史

---

### 2. **Coordinator 协调者模式** (主从编排)

**文件**: `src/coordinator/coordinatorMode.ts`

**核心机制**:
- 主 Agent 转变为 **Coordinator（协调者）** 角色
- 专门负责任务分解、Worker 调度、结果综合
- Worker 使用 `subagent_type: "worker"`
- 支持 **SendMessage** 工具继续已完成的 Worker 对话

**协作流程**:
```
用户请求
  ↓
Coordinator 启动（CLAUDE_CODE_COORDINATOR_MODE=1）
  ↓
Phase 1: Research（研究阶段）
  ├─ 并行启动 Worker A: 调查 bug 根源
  └─ 并行启动 Worker B: 研究相关测试
  ↓
Worker 完成后发送 <task-notification>
  ↓
Coordinator 综合发现（关键步骤！）
  - 阅读所有 Worker 结果
  - 理解问题本质
  - 编写具体的实施规范（含文件路径、行号）
  ↓
Phase 2: Implementation（实施阶段）
  ├─ 继续 Worker A（SendMessage）: 修复 null pointer at validate.ts:42
  └─ 启动新 Worker C: 验证修改
  ↓
Phase 3: Verification（验证阶段）
  └─ Worker C 运行测试、类型检查
  ↓
Coordinator 向用户报告最终结果
```

**关键设计原则**:
1. **Coordinator 必须综合**: 禁止 "based on your findings" 这种懒惰委托
2. **Continue vs Spawn 决策**:
   - 高上下文重叠 → Continue（SendMessage）
   - 低上下文重叠 → Spawn fresh（新 Agent）
3. **Worker 无法看到 Coordinator 对话**: 每个 prompt 必须自包含
4. **并行是超能力**: Worker 是异步的，尽可能并发

**可用工具**:
- `Agent` - 启动新 Worker
- `SendMessage` - 继续现有 Worker
- `TaskStop` - 停止运行中的 Worker

---

### 3. **Team 团队模式** (多智能体协作)

**文件**: 
- `src/tools/TeamCreateTool/TeamCreateTool.ts`
- `src/tools/TeamCreateTool/prompt.ts`
- `src/utils/swarm/teamHelpers.ts`
- `src/utils/swarm/inProcessRunner.ts`

**核心机制**:
- 创建 **Team**（团队），包含 Team Lead + 多个 Teammate
- Team 与 TaskList 1:1 对应
- 支持 **In-Process**（进程内）和 **Out-of-Process**（tmux/iTerm2 面板）两种执行模式
- 团队成员通过 **Mailbox** 和 **TaskList** 协作

**协作流程**:
```
用户请求复杂任务
  ↓
Phase 1: 创建团队
  ├─ TeamCreate 工具 → 创建团队配置文件 (~/.claude/teams/{name}/config.json)
  └─ 自动创建对应的 TaskList (~/.claude/tasks/{name}/)
  ↓
Phase 2: 创建任务
  ├─ TaskCreate: 任务 1 - 研究现有实现
  ├─ TaskCreate: 任务 2 - 实现新功能
  ├─ TaskCreate: 任务 3 - 编写测试
  └─ 设置依赖关系（blocks/blocked_by）
  ↓
Phase 3: 启动队友
  ├─ Agent 工具 + team_name + name 参数 → 创建队友
  ├─ 队友自动读取团队配置发现其他成员
  └─ 队友通过 TaskList 自主认领任务
  ↓
Phase 4: 协作执行
  ├─ Team Lead 分配任务（TaskUpdate owner=队友名称）
  ├─ 队友完成任务后标记完成（TaskUpdate status=completed）
  ├─ 队友间通过 SendMessage 直接通信（Peer DM）
  └─ 空闲队友自动发送 idle 通知
  ↓
Phase 5: 完成与清理
  ├─ 所有任务完成后，Team Lead 发送 shutdown_request
  └─ TeamDelete 清理团队
```

**关键特性**:
- **自主认领**: 队友按 ID 顺序自主认领可用任务
- **依赖管理**: 任务可设置 blocks/blocked_by 关系
- **Peer DM**: 队友间可直接通信，摘要显示给 Team Lead
- **持久化**: 团队配置和任务状态持久化到文件系统
- **跨进程**: 支持 tmux/iTerm2 面板作为独立队友

**团队配置示例**:
```json
{
  "team_name": "feature-auth",
  "description": "实现 JWT 认证",
  "members": [
    {
      "agentId": "agent-abc",
      "name": "team-lead",
      "agentType": "general-purpose"
    },
    {
      "agentId": "agent-xyz",
      "name": "researcher",
      "agentType": "explore"
    },
    {
      "agentId": "agent-123",
      "name": "implementer",
      "agentType": "general-purpose"
    }
  ]
}
```

---

### 4. **Batch 批处理模式** (大规模并行变更)

**文件**: `src/skills/bundled/batch.ts`

**核心机制**:
- 通过 `/batch` 命令触发
- 适用于大规模重构、迁移（5-30 个并行 Worker）
- 每个 Worker 在 **隔离的 git worktree** 中工作
- 自动创建 PR

**协作流程**:
```
用户: /batch migrate from react to vue
  ↓
Phase 1: Research & Plan（计划模式）
  ├─ 进入 Plan Mode
  ├─ 启动 Subagent 深入研究影响范围
  ├─ 分解为 5-30 个独立工作单元
  │   - 每个单元可独立在 git worktree 中实施
  │   - 每个单元的 PR 可独立合并不依赖其他
  │   - 规模均匀（拆分大的，合并小的）
  ├─ 确定 e2e 测试验证方案
  └─ 退出 Plan Mode，提交计划供审批
  ↓
用户审批计划
  ↓
Phase 2: Spawn Workers（并行执行）
  ├─ 单次消息中启动所有 Worker（全部并行）
  ├─ 每个 Worker 配置:
  │   - isolation: "worktree" (隔离的 git worktree)
  │   - run_in_background: true
  │   - 自包含的 prompt（目标 + 具体任务 + 约定 + 测试方案）
  └─ Worker 指令:
      1. 实施变更
      2. 调用 simplify skill 审查代码
      3. 运行单元测试
      4. 执行 e2e 测试
      5. 提交、推送、创建 PR
      6. 报告 PR URL
  ↓
Phase 3: Track Progress（进度跟踪）
  ├─ 渲染初始状态表格
  │   | # | Unit | Status | PR |
  │   |---|------|--------|----|
  │   | 1 | xxx | running | — |
  ├─ 接收 Worker 完成通知
  ├─ 解析 PR URL，更新表格
  └─ 全部完成后渲染最终总结
```

**关键特性**:
- **Git Worktree 隔离**: 每个 Worker 在独立 worktree，无共享状态
- **PR 自动化**: Worker 自动创建 PR，Coordinator 跟踪
- **Plan Mode 集成**: 必须先规划再执行，用户审批
- **e2e 测试**: 强制要求端到端验证

---

### 5. **Simplify 三路并行审查模式** (代码质量保障)

**文件**: `src/skills/bundled/simplify.ts`

**核心机制**:
- 通过 `/simplify` 命令触发
- 并行启动 **3 个审查 Agent**，各有不同视角
- 覆盖代码复用、代码质量、性能效率三个维度

**协作流程**:
```
用户: /simplify（或修改代码后自动触发）
  ↓
Phase 1: 识别变更
  └─ 运行 git diff 获取修改内容
  ↓
Phase 2: 三路并行审查
  ├─ Agent 1: Code Reuse Review（代码复用审查）
  │   - 检查是否有现有函数/模式可复用
  │   - 识别重复代码
  │   - 建议抽象和提取
  │
  ├─ Agent 2: Code Quality Review（代码质量审查）
  │   - 检查代码风格、最佳实践
  │   - 识别潜在 bug、边界情况
  │   - 建议改进可读性和可维护性
  │
  └─ Agent 3: Performance Review（性能审查）
      - 识别性能瓶颈
      - 检查算法复杂度
      - 建议优化方案
  ↓
Phase 3: 综合报告
  └─ 汇总三个 Agent 的发现，生成改进建议
```

**关键特性**:
- **多视角审查**: 三个独立维度，互不干扰
- **并行执行**: 单次消息中启动所有审查 Agent
- **自动化触发**: 可在代码修改后自动建议

---

## 二、OpenCode 当前实现状态

### ✅ 已实现功能

**文件**: `opencode/core/subagent.py`, `opencode/tools/builtin/subagent.py`, `opencode/tools/builtin/task_manager.py`

1. **Subagent 管理器** (`SubagentManager`)
   - ✅ 创建和管理并行子代理
   - ✅ 支持 agent_type（explore/plan/review/impact/diagnose/general）
   - ✅ Fork 模式支持（继承父会话上下文）
   - ✅ 结果自动压缩
   - ✅ Agent 定义文件解析（`.claude/agents/*.md`）
   - ✅ 并发数限制
   - ✅ 后台/同步执行模式

2. **Agent 邮箱** (`AgentMailbox`)
   - ✅ 代理间消息传递
   - ✅ 广播和点对点通信
   - ✅ 消息类型过滤
   - ✅ 对话历史查询

3. **编排器** (`SubagentOrchestrator`)
   - ✅ 串行任务链（前序结果自动注入）
   - ✅ 并行任务执行
   - ✅ 共享上下文传递
   - ✅ 结果聚合分析（summary/merge/vote 策略）

4. **Task 任务管理** (`task_manager.py`)
   - ✅ task_create - 创建任务
   - ✅ task_get - 获取任务详情
   - ✅ task_update - 更新任务状态/内容
   - ✅ task_list - 列出所有任务
   - ✅ task_stop - 停止运行中的任务
   - ✅ 依赖关系管理（blocks/blocked_by）
   - ✅ 进度追踪（0-100%）
   - ✅ 任务层级（parent_id/subtasks）
   - ✅ 团队关联（team_name）
   - ✅ 任务认领（owner）
   - ✅ 可认领任务过滤（show_available）

5. **Team 团队管理** (`team_manager.py`)
   - ✅ team_create - 创建团队和 TaskList
   - ✅ team_delete - 删除团队
   - ✅ team_spawn - 启动队友
   - ✅ team_list - 列出团队信息
   - ✅ team_discover - 发现团队成员
   - ✅ team_notify_idle - 空闲通知
   - ✅ 团队配置持久化（~/.opencode/teams/）

---

### ❌ 缺失的核心功能

| 功能 | Claude Code 实现 | OpenCode 状态 | 缺失程度 |
|------|------------------|---------------|----------|
| **Coordinator 模式** | 完整的协调者角色、System Prompt、工作流指导 | ✅ 已实现 | ✅ 完成 |
| **SendMessage 工具** | 继续已完成的 Subagent 对话 | ✅ 已实现 | ✅ 完成 |
| **TaskStop 工具** | 停止运行中的 Worker | ✅ 已实现 (task_manager.py) | ✅ 完成 |
| **Team 团队模式** | TeamCreate、TaskList、Teammate、Mailbox | ✅ 已实现 | ✅ 完成 |
| **Task 依赖管理** | blocks/blocked_by、自主认领、空闲通知 | ✅ 已实现 | ✅ 完成 |
| **Batch Skill** | `/batch` 命令、git worktree 隔离、PR 自动化 | ❌ 未实现 | 🟡 中等 |
| **Simplify Skill** | 三路并行审查 | ❌ 未实现 | 🟢 可选 |
| **Fork 完整实现** | 继承完整对话历史 + 工具调用状态 | ⚠️ 部分实现 | 🟡 中等 |
| **进度摘要** | 30s 定时生成 Subagent 进度摘要 | ❌ 未实现 | 🟢 可选 |
| **Worktree 隔离** | git worktree 独立工作目录 | ❌ 未实现 | 🟡 中等 |

---

## 三、关键差距分析

### 1. **Coordinator 模式缺失** 🔴

**问题**: 
- OpenCode 没有协调者角色，无法实现"分解-综合-再分解"的高级工作流
- 主 Agent 和 Subagent 是简单的"启动-等待-获取结果"关系

**影响**:
- 无法实现 Claude Code 的 Research → Synthesis → Implementation → Verification 四阶段工作流
- Subagent 结果无法被深度综合后指导下一步行动

**需要实现**:
```python
class CoordinatorMode:
    """协调者模式"""
    
    def get_system_prompt(self) -> str:
        """返回协调者系统提示词"""
        # 包含角色定义、工具说明、工作流指导
        pass
    
    def handle_task_notification(self, notification: dict):
        """处理 Worker 完成通知"""
        # 解析 <task-notification> XML
        # 更新 Worker 状态
        # 触发 Coordinator 下一轮决策
        pass
    
    def synthesize_findings(self, worker_results: list) -> str:
        """综合多个 Worker 的发现"""
        # 禁止懒惰委托
        # 必须生成具体的实施规范
        pass
```

---

### 2. **SendMessage 工具缺失** 🔴

**问题**:
- 无法继续已完成的 Subagent 对话
- 每次启动 Subagent 都是全新的上下文

**影响**:
- 无法实现 Claude Code 的 Continue vs Spawn 决策
- Worker 完成后无法给予后续指令（如"修复发现的问题"）
- 上下文浪费（重新加载相同文件）

**需要实现**:
```python
def send_message_handler(
    to: str,           # 目标 agent_id 或 name
    message: str,      # 消息内容
    summary: str = ""  # 简短摘要
) -> str:
    """
    继续已存在的 Subagent 对话
    
    流程:
    1. 查找目标 Subagent
    2. 将消息追加到其对话历史
    3. 重新激活 Subagent（如果已完成）
    4. 返回执行状态
    """
    pass
```

---

### 3. **Team 团队模式完全缺失** 🔴

**问题**:
- 没有团队概念，无法实现多 Agent 协作
- 没有 TaskList，无法跟踪和管理多步骤任务
- 没有队友自主认领任务的机制

**影响**:
- 无法实现 Claude Code 的 Team 工作流（创建团队 → 创建任务 → 分配 → 协作 → 完成）
- 无法实现复杂项目的多角色协作（研究、实施、测试分工）
- 缺少任务依赖管理（blocks/blocked_by）

**需要实现的核心组件**:

#### 3.1 Team 管理
```python
class TeamManager:
    """团队管理器"""
    
    def create_team(self, team_name: str, description: str) -> TeamConfig:
        """创建团队及对应的 TaskList"""
        pass
    
    def spawn_teammate(self, team_name: str, name: str, 
                      agent_type: str, prompt: str) -> Teammate:
        """启动队友加入团队"""
        pass
    
    def shutdown_team(self, team_name: str):
        """关闭团队"""
        pass
```

#### 3.2 TaskList 管理
```python
class TaskListManager:
    """任务列表管理器"""
    
    def create_task(self, team_name: str, subject: str, 
                   description: str, blocks: list = None,
                   blocked_by: list = None) -> Task:
        """创建任务，支持依赖关系"""
        pass
    
    def claim_task(self, team_name: str, task_id: str, owner: str):
        """认领任务"""
        pass
    
    def complete_task(self, team_name: str, task_id: str):
        """完成任务"""
        pass
    
    def get_available_tasks(self, team_name: str) -> list[Task]:
        """获取可认领的任务（未阻塞、未分配）"""
        pass
```

#### 3.3 队友协作
```python
class TeammateCollaboration:
    """队友协作机制"""
    
    def send_peer_dm(self, from_name: str, to_name: str, 
                    message: str, team_name: str):
        """队友间直接通信"""
        pass
    
    def notify_idle(self, teammate_name: str, team_name: str):
        """通知队友空闲"""
        pass
    
    def auto_claim_next_task(self, teammate_name: str, team_name: str):
        """队友自动认领下一个可用任务"""
        pass
```

---

### 4. **Batch Skill 缺失** 🟡

**问题**:
- 没有 `/batch` 命令支持大规模并行变更
- 没有 git worktree 隔离机制
- 没有 PR 自动化

**影响**:
- 无法处理大规模重构（如 React → Vue 迁移）
- 无法实现 5-30 个 Worker 并行在独立 worktree 中工作

**需要实现**:
```python
class BatchSkill:
    """批处理 Skill"""
    
    def execute(self, instruction: str):
        """
        执行批处理
        
        Phase 1: 研究规划
        Phase 2: 生成 worktree 并启动 Worker
        Phase 3: 跟踪进度，渲染状态表格
        """
        pass
    
    def create_worktree(self, branch_name: str) -> str:
        """创建隔离的 git worktree"""
        pass
    
    def auto_create_pr(self, worktree_path: str, branch_name: str) -> str:
        """自动创建 PR"""
        pass
```

---

## 四、完整协作流程对比

### Claude Code 完整协作流程示例

```
用户: "修复认证模块的 null pointer bug，并确保测试通过"

┌─────────────────────────────────────────────────────────┐
│ Phase 1: Coordinator 模式启动                             │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 2: Research（并行）                                 │
│ Agent({subagent_type: "worker", prompt: "调查 auth bug"})│
│ Agent({subagent_type: "worker", prompt: "研究 auth 测试"})│
└─────────────────────────────────────────────────────────┘
  ↓ [Worker 完成后发送 <task-notification>]
┌─────────────────────────────────────────────────────────┐
│ Phase 3: Synthesis（Coordinator 必须综合）                │
│ 阅读发现: "validate.ts:42 的 user 字段在 session 过期时为 undefined" │
│ 编写规范: "在 validate.ts:42 添加 null check..."         │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 4: Implementation（Continue Worker）               │
│ SendMessage({to: "agent-a1b", message: "修复 null pointer..."}) │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 5: Verification（Spawn fresh Worker）              │
│ Agent({subagent_type: "worker", prompt: "验证修复..."})  │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 6: 向用户报告结果                                   │
└─────────────────────────────────────────────────────────┘
```

### OpenCode 当前流程（简化）

```
用户: "修复认证模块的 null pointer bug，并确保测试通过"

┌─────────────────────────────────────────────────────────┐
│ Phase 1: 主 Agent 分析任务                                │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 2: 启动 Subagent（并行）                            │
│ spawn_subagent(task="调查 auth bug")                     │
│ spawn_subagent(task="研究 auth 测试")                    │
└─────────────────────────────────────────────────────────┘
  ↓ [等待完成]
┌─────────────────────────────────────────────────────────┐
│ Phase 3: 获取结果（无综合机制）                           │
│ join_subagent(agent_id) → 获取压缩后的摘要                │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 4: 主 Agent 自己执行修复                            │
│ 或启动新的 Subagent（无法继续之前的对话）                   │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────🤣
│ Phase 5: 主 Agent 向用户报告                              │
└─────────────────────────────────────────────────────────┘
```

**关键差距**:
1. ❌ 缺少 Coordinator 综合阶段
2. ❌ 无法 Continue Worker（SendMessage）
3. ❌ 无法实现 Research → Implementation → Verification 的完整分工
4. ❌ 无法实现 Team 协作（多角色、多任务、依赖管理）
5. ⚠️ TaskStop 已实现，但缺少与 Subagent 的生命周期联动

---

## 五、实现优先级建议

### ✅ P0 - 已完成

1. ✅ **SendMessage 工具** - 实现继续 Subagent 对话的能力
2. ✅ **Coordinator 模式** - 实现协调者角色和系统提示词
3. ✅ **TaskStop 工具** - 已在 task_manager.py 中实现

### ✅ P1 - 已完成

3. ✅ **Team 团队模式（基础）** - 完整的团队管理系统
4. ✅ **Team 协作机制** - 队友间协作和任务认领
5. ✅ **Task 依赖管理完善** - 自主认领、空闲通知、团队过滤

### 🟢 P2 - 高级功能（按需实现）

6. **Batch Skill**
   - `/batch` 命令
   - git worktree 隔离
   - PR 自动化

7. **Simplify Skill**
   - 三路并行审查

8. **进度摘要**
   - 定时生成 Subagent 进度摘要

---

## 六、总结

Claude Code 的多智能体编排是一个 **分层递进** 的系统：

```
Level 1: Subagent 并行     ← OpenCode 已实现 ✅
         ↓
Level 2: Coordinator 模式   ← OpenCode 缺失 ❌
         ↓
Level 3: Team 团队协作      ← OpenCode 缺失 ❌
         ↓
Level 4: Batch 大规模变更   ← OpenCode 缺失 ❌
```

**核心差距在于**:
1. ✅ **编排能力**: Coordinator 模式已实现，支持"分解-综合-再分解"工作流
2. ✅ **上下文复用**: SendMessage 已实现，支持继续 Subagent 对话
3. ✅ **协作机制**: Team 模式已实现，支持多角色协作和任务认领
4. ❌ **自动化**: Claude Code 支持 git worktree 隔离和 PR 自动化，OpenCode 无此能力
5. ✅ **任务管理**: 完整的 Task 管理和 Team 协作机制

**下一步建议**: 实现 P2 高级功能（Batch Skill、Simplify Skill）
