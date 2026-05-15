# Tasks 目录功能分析与集成计划

## 一、Tasks 目录功能概述

### 1.1 架构设计

Claude Code 的 `tasks/` 目录实现了一个**统一任务管理系统**，用于跟踪和管理各种后台任务的执行状态、输出和生命周期。

核心组件：
```
src/tasks/
├── types.ts                    # 任务类型联合定义
├── pillLabel.ts                # UI 显示标签生成
├── stopTask.ts                 # 任务停止逻辑
├── LocalMainSessionTask.ts     # 主会话后台任务
├── DreamTask/                  # 内存整合任务
├── InProcessTeammateTask/      # 进程内队友任务
├── LocalAgentTask/             # 本地代理任务
├── LocalShellTask/             # 本地 Shell 命令任务
└── RemoteAgentTask/            # 远程代理任务（云会话）
```

### 1.2 支持的任务类型

| 任务类型 | 说明 | 使用场景 |
|---------|------|---------|
| `local_bash` | 本地 shell 命令执行 | Bash 工具、监控脚本 |
| `local_agent` | 本地代理（子智能体） | Agent 工具、规划模式 |
| `remote_agent` | 远程云会话代理 | Ultraplan、代码审查 |
| `in_process_teammate` | 进程内队友 | Swarm 团队协作 |
| `local_workflow` | 本地工作流 | 自定义脚本工作流 |
| `monitor_mcp` | MCP 服务器监控 | MCP 连接监控 |
| `dream` | 内存整合后台任务 | 自动记忆整合 |

### 1.3 核心功能

1. **任务生命周期管理**
   - 状态转换: pending → running → completed/failed/killed
   - 任务注册、更新、清理
   - 终止任务和资源释放

2. **输出管理**
   - 独立输出文件（symlink 到任务 transcript）
   - 增量输出追踪（outputOffset）
   - 任务完成后输出清理

3. **进度追踪**
   - Token 计数
   - 工具使用计数
   - 最近活动列表

4. **通知系统**
   - 任务完成通知
   - 任务失败通知
   - XML 格式通知消息

5. **UI 集成**
   - 底部状态栏显示（pill label）
   - 后台任务面板
   - Shift+Down 快捷键查看

## 二、与 opencode 项目对比

### 2.1 opencode 现有功能

| 功能 | opencode 现状 | Claude Code 对应 |
|------|--------------|-----------------|
| Subagent 管理 | ✅ `core/subagent.py` | LocalAgentTask |
| 工具执行 | ✅ 工具注册表 | LocalShellTask (部分) |
| 状态管理 | ⚠️ 简单状态 | 完整任务状态机 |
| 通知系统 | ❌ 缺失 | XML 通知队列 |
| 进度追踪 | ⚠️ 部分 | Token/工具计数 |
| 输出管理 | ⚠️ 简单 | 独立输出文件 |
| 远程代理 | ❌ 缺失 | RemoteAgentTask |
| 任务面板 | ❌ 缺失 | CoordinatorTaskPanel |

### 2.2 差距分析

**opencode 缺少的关键功能：**

1. **统一的任务状态管理** - 没有中央化的任务注册表
2. **任务生命周期管理** - 缺少完整的任务状态转换
3. **进度追踪** - 没有 token 计数和工具使用追踪
4. **通知系统** - 没有任务完成通知机制
5. **输出隔离** - 没有独立的任务输出文件
6. **远程任务支持** - 没有云会话集成

## 三、集成必要性评估

### 3.1 集成价值

| 价值维度 | 评分 | 说明 |
|---------|------|------|
| 功能完整性 | ⭐⭐⭐⭐⭐ | 填补任务管理核心空白 |
| 用户体验 | ⭐⭐⭐⭐⭐ | 提供可见的任务状态和进度 |
| 系统可维护性 | ⭐⭐⭐⭐ | 统一管理减少代码分散 |
| 扩展性 | ⭐⭐⭐⭐⭐ | 为新任务类型提供框架 |

### 3.2 集成复杂度

| 复杂度维度 | 评分 | 说明 |
|-----------|------|------|
| 语言差异 | ⭐⭐⭐⭐⭐ | TypeScript → Python 需要完全重写 |
| 依赖关系 | ⭐⭐⭐ | 与 React/Ink UI 深度耦合 |
| 状态管理 | ⭐⭐⭐ | AppState 需要重新设计 |
| 输出系统 | ⭐⭐ | 相对独立，易于移植 |

### 3.3 最终结论

**✅ 建议集成**，但需要**适配性重新设计**，而非直接移植。

理由：
1. opencode 的 Subagent 系统需要统一管理
2. 任务进度追踪对用户体验至关重要
3. 通知系统是完整 AI 助手的必备功能
4. 为未来功能（远程代理、工作流）奠定基础

## 四、集成方案设计

### 4.1 整体架构

```python
opencode/
├── core/
│   ├── task_manager.py       # 新增：任务管理器
│   ├── task_base.py          # 新增：任务基类
│   └── task_types/           # 新增：任务类型目录
│       ├── __init__.py
│       ├── subagent_task.py  # Subagent 任务
│       ├── command_task.py   # 命令执行任务
│       └── workflow_task.py  # 工作流任务
├── utils/
│   └── task_output.py        # 新增：任务输出管理
└── cli.py                    # 更新：集成任务面板
```

### 4.2 核心类设计

#### TaskBase (任务基类)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"

class TaskType(Enum):
    """任务类型"""
    SUBAGENT = "subagent"
    COMMAND = "command"
    WORKFLOW = "workflow"

@dataclass
class TaskProgress:
    """任务进度"""
    token_count: int = 0
    tool_use_count: int = 0
    recent_activities: list = field(default_factory=list)
    last_activity: Optional[dict] = None

@dataclass
class TaskState:
    """任务状态基类"""
    id: str
    type: TaskType
    status: TaskStatus
    description: str
    start_time: datetime
    end_time: Optional[datetime] = None
    progress: Optional[TaskProgress] = None
    output_file: Optional[str] = None
    output_offset: int = 0
    notified: bool = False
    error: Optional[str] = None

class TaskBase(ABC):
    """任务基类"""
    
    def __init__(self, description: str):
        self.id = self._generate_id()
        self.description = description
        self.state = TaskState(
            id=self.id,
            type=self.get_type(),
            status=TaskStatus.PENDING,
            description=description,
            start_time=datetime.now()
        )
    
    @abstractmethod
    def get_type(self) -> TaskType:
        """获取任务类型"""
        pass
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Any:
        """执行任务"""
        pass
    
    @abstractmethod
    async def kill(self):
        """终止任务"""
        pass
    
    def _generate_id(self) -> str:
        """生成任务 ID"""
        prefix = self.get_type().value[0]
        unique = uuid.uuid4().hex[:8]
        return f"{prefix}{unique}"
```

#### TaskManager (任务管理器)

```python
from typing import Dict, List, Optional, Callable
import asyncio
import logging

logger = logging.getLogger(__name__)

class TaskManager:
    """
    任务管理器
    
    功能：
    1. 任务注册与追踪
    2. 状态更新
    3. 进度轮询
    4. 通知发送
    5. 任务清理
    """
    
    def __init__(self):
        self._tasks: Dict[str, TaskState] = {}
        self._task_instances: Dict[str, TaskBase] = {}
        self._poll_interval = 1.0  # 1秒轮询间隔
        self._polling = False
        self._notification_callbacks: List[Callable] = []
    
    def register_task(self, task: TaskBase) -> str:
        """注册任务"""
        task_id = task.id
        self._tasks[task_id] = task.state
        self._task_instances[task_id] = task
        logger.info(f"注册任务: {task_id} - {task.description}")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskState]:
        """获取任务状态"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[TaskState]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_running_tasks(self) -> List[TaskState]:
        """获取运行中的任务"""
        return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]
    
    def update_task_status(self, task_id: str, status: TaskStatus, **kwargs):
        """更新任务状态"""
        if task_id not in self._tasks:
            logger.warning(f"任务不存在: {task_id}")
            return
        
        task = self._tasks[task_id]
        task.status = status
        
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED]:
            task.end_time = datetime.now()
        
        for key, value in kwargs.items():
            setattr(task, key, value)
        
        logger.info(f"任务状态更新: {task_id} -> {status.value}")
    
    def update_task_progress(self, task_id: str, progress: TaskProgress):
        """更新任务进度"""
        if task_id in self._tasks:
            self._tasks[task_id].progress = progress
    
    async def kill_task(self, task_id: str):
        """终止任务"""
        if task_id not in self._task_instances:
            logger.warning(f"任务不存在: {task_id}")
            return
        
        task = self._task_instances[task_id]
        await task.kill()
        self.update_task_status(task_id, TaskStatus.KILLED)
        logger.info(f"任务已终止: {task_id}")
    
    def register_notification_callback(self, callback: Callable):
        """注册通知回调"""
        self._notification_callbacks.append(callback)
    
    async def start_polling(self):
        """启动轮询"""
        if self._polling:
            return
        
        self._polling = True
        logger.info("任务轮询已启动")
        
        while self._polling:
            await self._poll_once()
            await asyncio.sleep(self._poll_interval)
    
    def stop_polling(self):
        """停止轮询"""
        self._polling = False
        logger.info("任务轮询已停止")
    
    async def _poll_once(self):
        """单次轮询"""
        running_tasks = self.get_running_tasks()
        
        for task_state in running_tasks:
            # 检查任务状态变化
            await self._check_task_status(task_state)
            
            # 发送进度通知
            if task_state.progress:
                await self._send_progress_notification(task_state)
    
    async def _check_task_status(self, task_state: TaskState):
        """检查任务状态"""
        # 由具体任务类型实现
        pass
    
    async def _send_progress_notification(self, task_state: TaskState):
        """发送进度通知"""
        for callback in self._notification_callbacks:
            try:
                await callback(task_state)
            except Exception as e:
                logger.error(f"通知回调失败: {e}")
    
    def cleanup_completed_tasks(self, max_age_seconds: int = 300):
        """清理已完成的任务"""
        now = datetime.now()
        to_remove = []
        
        for task_id, task in self._tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED]:
                if task.end_time:
                    age = (now - task.end_time).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(task_id)
        
        for task_id in to_remove:
            del self._tasks[task_id]
            if task_id in self._task_instances:
                del self._task_instances[task_id]
            logger.info(f"清理任务: {task_id}")

# 全局单例
_task_manager: Optional[TaskManager] = None

def get_task_manager() -> TaskManager:
    """获取任务管理器单例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
```

### 4.3 具体任务类型实现

#### SubagentTask

```python
import asyncio
from typing import Dict, Any
from core.subagent import SubagentManager
from core.task_base import TaskBase, TaskType, TaskStatus, TaskProgress

class SubagentTask(TaskBase):
    """Subagent 任务"""
    
    def __init__(self, description: str, agent_type: str = "general"):
        super().__init__(description)
        self.agent_type = agent_type
        self.subagent_manager = None
        self.result = None
    
    def get_type(self) -> TaskType:
        return TaskType.SUBAGENT
    
    async def execute(self, context: Dict[str, Any]) -> Any:
        """执行 Subagent 任务"""
        self.state.status = TaskStatus.RUNNING
        
        try:
            # 创建 Subagent
            self.subagent_manager = SubagentManager(
                model=context.get("model", "glm-4-plus"),
                agent_type=self.agent_type
            )
            
            # 执行任务
            agent_id = await self.subagent_manager.spawn(
                task=self.description,
                context=context
            )
            
            # 等待完成
            self.result = await self.subagent_manager.join(agent_id)
            
            self.state.status = TaskStatus.COMPLETED
            return self.result
            
        except Exception as e:
            self.state.status = TaskStatus.FAILED
            self.state.error = str(e)
            raise
    
    async def kill(self):
        """终止任务"""
        if self.subagent_manager:
            await self.subagent_manager.cancel_all()
```

#### CommandTask

```python
import asyncio
import subprocess
from typing import Dict, Any
from core.task_base import TaskBase, TaskType, TaskStatus

class CommandTask(TaskBase):
    """命令执行任务"""
    
    def __init__(self, description: str, command: str, cwd: str = None):
        super().__init__(description)
        self.command = command
        self.cwd = cwd or "."
        self.process = None
    
    def get_type(self) -> TaskType:
        return TaskType.COMMAND
    
    async def execute(self, context: Dict[str, Any]) -> Any:
        """执行命令"""
        self.state.status = TaskStatus.RUNNING
        
        try:
            # 创建子进程
            self.process = await asyncio.create_subprocess_shell(
                self.command,
                cwd=self.cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 等待完成
            stdout, stderr = await self.process.communicate()
            
            if self.process.returncode == 0:
                self.state.status = TaskStatus.COMPLETED
                return stdout.decode()
            else:
                self.state.status = TaskStatus.FAILED
                self.state.error = stderr.decode()
                return None
                
        except Exception as e:
            self.state.status = TaskStatus.FAILED
            self.state.error = str(e)
            raise
    
    async def kill(self):
        """终止进程"""
        if self.process:
            self.process.kill()
            await self.process.wait()
```

### 4.4 集成到 CLI

```python
# cli.py 更新

from core.task_manager import get_task_manager

class OpenCodeCLI:
    def __init__(self, config):
        # ... 现有初始化 ...
        
        # 初始化任务管理器
        self.task_manager = get_task_manager()
        
        # 注册通知回调
        self.task_manager.register_notification_callback(
            self._on_task_notification
        )
    
    async def _on_task_notification(self, task_state):
        """任务通知处理"""
        print(f"\n[任务通知] {task_state.description}: {task_state.status.value}")
        
        if task_state.progress:
            print(f"  Token: {task_state.progress.token_count}, "
                  f"工具: {task_state.progress.tool_use_count}")
    
    async def show_tasks(self):
        """显示任务列表"""
        tasks = self.task_manager.get_all_tasks()
        
        if not tasks:
            print("没有活动任务")
            return
        
        print("\n活动任务:")
        for task in tasks:
            status_icon = {
                TaskStatus.RUNNING: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.PENDING: "⏳",
            }.get(task.status, "❓")
            
            print(f"  {status_icon} {task.id}: {task.description}")
            
            if task.progress:
                print(f"     Token: {task.progress.token_count}, "
                      f"工具: {task.progress.tool_use_count}")
```

### 4.5 工具集成

```python
# tools/builtin/subagent.py 更新

from core.task_manager import get_task_manager
from core.task_types.subagent_task import SubagentTask

async def spawn_subagent(tool_input: dict, context: dict) -> dict:
    """启动 Subagent（使用任务管理器）"""
    task_manager = get_task_manager()
    
    # 创建任务
    task = SubagentTask(
        description=tool_input.get("task", ""),
        agent_type=tool_input.get("agent_type", "general")
    )
    
    # 注册任务
    task_id = task_manager.register_task(task)
    
    # 异步执行
    asyncio.create_task(task.execute(context))
    
    return {
        "agent_id": task_id,
        "status": "started",
        "message": f"任务已启动: {task_id}"
    }
```

## 五、实施步骤

### Phase 1: 基础框架 (2-3 天)
1. ✅ 创建 `TaskBase` 基类和 `TaskState` 数据类
2. ✅ 创建 `TaskManager` 核心管理器
3. ✅ 实现任务注册、状态更新、查询接口
4. ✅ 添加基础测试

### Phase 2: 任务类型 (3-4 天)
1. ✅ 实现 `SubagentTask`（集成现有 Subagent）
2. ✅ 实现 `CommandTask`（替代简单命令执行）
3. ✅ 实现 `WorkflowTask`（为未来工作流做准备）
4. ✅ 添加任务类型测试

### Phase 3: 输出管理 (2-3 天)
1. ✅ 实现任务输出文件管理
2. ✅ 实现输出 offset 追踪
3. ✅ 添加输出读取 API
4. ✅ 集成到任务通知

### Phase 4: CLI 集成 (2-3 天)
1. ✅ 更新 CLI 集成任务管理器
2. ✅ 实现 `/tasks` 命令查看任务
3. ✅ 实现任务状态显示
4. ✅ 添加任务终止功能

### Phase 5: 通知系统 (2 天)
1. ✅ 实现任务完成通知
2. ✅ 实现任务失败通知
3. ✅ 实现进度通知
4. ✅ 添加通知配置

### Phase 6: 测试与优化 (2-3 天)
1. ✅ 端到端测试
2. ✅ 性能优化
3. ✅ 文档完善
4. ✅ 示例代码

**总计：15-20 天**

## 六、风险与注意事项

### 6.1 技术风险

| 风险 | 缓解措施 |
|------|---------|
| 语言差异导致移植困难 | 采用适配性重新设计，非直接移植 |
| 与现有 Subagent 系统冲突 | 逐步迁移，保持向后兼容 |
| UI 依赖难以实现 | 使用 CLI 替代方案（文本界面） |
| 状态管理复杂度增加 | 分阶段实施，充分测试 |

### 6.2 实施建议

1. **分阶段实施** - 按照 Phase 计划逐步推进
2. **保持兼容** - 现有功能继续工作，新功能可选
3. **充分测试** - 每个阶段完成后进行全面测试
4. **文档先行** - 先更新文档，再实现代码
5. **用户反馈** - 早期引入用户测试，收集反馈

## 七、总结

Claude Code 的任务系统是一个设计优秀的**后台任务管理框架**，为 opencode 项目提供了重要的参考价值。

**核心建议：**
1. ✅ **集成是必要的** - 任务管理是 AI 助手的核心功能
2. ⚠️ **需要适配性设计** - 直接移植不可行，需要重新设计
3. 🎯 **重点实现核心功能** - 优先实现任务状态管理和进度追踪
4. 📈 **为未来扩展留空间** - 设计时要考虑远程代理、工作流等未来功能

通过实施本计划，opencode 将获得：
- 统一的任务管理界面
- 完整的任务生命周期追踪
- 用户友好的进度显示
- 为高级功能奠定基础
