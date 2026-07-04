# WorkflowScriptGenerator 使用指南

> **版本**: v1.0  
> **最后更新**: 2026-06-02  
> **状态**: ✅ 完整实现

---

## 概述

`WorkflowScriptGenerator` 是 Dynamic Workflows 的核心组件，负责**使用 LLM 动态生成工作流脚本**。

### 核心能力

1. **任务分析** - 自动识别任务复杂度和关键领域
2. **阶段规划** - 生成 DAG 结构的多阶段工作流
3. **提示词工程** - 为每个 Agent 生成高质量提示词
4. **脚本验证** - 自动检查依赖关系和完整性
5. **脚本优化** - 支持基于反馈的迭代优化

---

## 架构设计

```
用户任务
   ↓
┌─────────────────────────────────┐
│  WorkflowScriptGenerator        │
│                                 │
│  Phase 1: 任务分析              │
│  - 复杂度评估                   │
│  - 关键领域识别                 │
│  - 执行阶段判断                 │
└─────────────────────────────────┘
   ↓
┌─────────────────────────────────┐
│  Phase 2: 阶段规划              │
│  - 生成 DAG 结构                │
│  - 分配 Agent 类型              │
│  - 设置依赖关系                 │
└─────────────────────────────────┘
   ↓
┌─────────────────────────────────┐
│  Phase 3: 提示词生成            │
│  - 研究阶段提示词               │
│  - 实现阶段提示词               │
│  - 验证阶段提示词               │
└─────────────────────────────────┘
   ↓
┌─────────────────────────────────┐
│  Phase 4: 脚本验证              │
│  - 名称唯一性检查               │
│  - 依赖关系验证                 │
│  - 循环依赖检测                 │
│  - 任务完整性检查               │
└─────────────────────────────────┘
   ↓
WorkflowScript 对象
```

---

## 使用方式

### 方式 1: 通过工具调用

```python
# 使用 dynamic_workflow 工具
result = dynamic_workflow(
    task="审计所有 API endpoint 的认证检查",
    auto_approve=False,
    save_script=True
)
```

### 方式 2: 直接调用生成器

```python
from core.workflow_generator import generate_workflow_script

# 生成工作流脚本
script = generate_workflow_script(
    task="审计所有 API endpoint 的认证检查",
    context={"project_type": "web_api"}
)

# 查看生成的脚本
print(script.to_dict())

# 验证脚本
errors = script.validate()
if errors:
    print(f"脚本错误: {errors}")

# 获取执行顺序
execution_order = script.get_execution_order()
print(f"执行顺序: {execution_order}")
```

---

## 任务分析引擎

### 复杂度评估

自动生成器会根据任务描述评估复杂度：

| 关键词 | 复杂度 | 预估阶段数 |
|--------|--------|------------|
| "所有"、"全部"、"整个" | complex | 3 |
| "一些"、"部分"、"几个" | moderate | 2 |
| 其他 | simple | 1 |

### 关键领域识别

自动识别任务涉及的关键领域：

```python
# 示例 1: API 审计
task = "审计所有 API endpoint 的认证检查"
# 识别结果: key_areas = ["api", "security"]

# 示例 2: 数据库迁移
task = "迁移数据库从 MySQL 到 PostgreSQL"
# 识别结果: key_areas = ["database"]

# 示例 3: 测试覆盖率
task = "提高测试覆盖率到 80%"
# 识别结果: key_areas = ["testing"]
```

### 执行阶段判断

根据任务特征自动决定需要的阶段：

| 阶段 | 触发条件 | Agent 类型 |
|------|----------|-----------|
| 研究阶段 | 包含"审计"、"分析"、"检查"等词 | explore |
| 实现阶段 | 包含"修改"、"更新"、"重构"等词 | general |
| 验证阶段 | 包含"验证"、"测试"、"确认"等词 | review |

---

## 提示词工程

### 研究阶段提示词模板

```
研究任务：{task}

你的任务：
1. 分析项目结构，识别与任务相关的关键文件和目录
2. 理解现有代码的实现方式
3. 评估任务的影响范围和复杂度
4. 列出需要修改的文件清单

重点关注：{key_areas}

输出格式：
## 研究发现

### 关键文件
- 文件路径: 作用描述

### 影响范围
- 受影响的模块/组件

### 复杂度评估
- 预估工作量：低/中/高

### 建议方案
- 推荐的实施步骤
```

### 实现阶段提示词模板

```
实施任务：{task}

基于研究发现，执行以下操作：
1. 按照建议方案逐步实施修改
2. 确保代码质量和一致性
3. 添加必要的注释和文档
4. 遵循项目的编码规范

注意事项：
- 保持代码可读性
- 避免引入新的问题
- 考虑边界情况

输出格式：
## 实施结果

### 已完成的修改
- 文件路径: 修改描述

### 新增功能
- 功能描述

### 注意事项
- 需要后续关注的问题
```

### 验证阶段提示词模板

```
验证任务：{task}

你的任务：
1. 检查实施结果是否符合要求
2. 验证代码的正确性和完整性
3. 检查是否遗漏了重要方面
4. 评估整体质量

验证清单：
- [ ] 所有要求的修改都已完成
- [ ] 代码质量符合标准
- [ ] 没有引入新的问题
- [ ] 文档和注释完整

输出格式：
## 验证结果

### 通过项
- 验证项: 状态

### 问题项
- 问题描述: 建议修复方式

### 总体评价
- 质量评分：1-10
- 建议：后续改进方向
```

---

## 脚本验证

### 验证规则

1. **名称唯一性** - 阶段名称必须唯一
2. **依赖关系** - 依赖的阶段必须存在
3. **循环依赖** - 不能存在循环依赖
4. **任务完整性** - 每个阶段必须包含至少一个 Agent
5. **提示词非空** - Agent 的提示词不能为空

### 验证示例

```python
from core.workflow_types import WorkflowScript, WorkflowStage, AgentTask

script = WorkflowScript(
    name="test-workflow",
    stages=[
        WorkflowStage(
            name="stage1",
            agents=[AgentTask(prompt="任务1")]
        ),
        WorkflowStage(
            name="stage2",
            agents=[AgentTask(prompt="任务2")],
            depends=["stage1"]  # ✅ 正确依赖
        )
    ]
)

errors = script.validate()
if errors:
    print(f"验证失败: {errors}")
else:
    print("验证通过")
```

---

## 高级功能

### 脚本优化

```python
from core.workflow_generator import WorkflowScriptGenerator

generator = WorkflowScriptGenerator()

# 生成初始脚本
script = generator.generate(task="审计 API 认证")

# 根据反馈优化
optimized_script = generator.optimize_script(
    script=script,
    feedback="研究阶段需要更详细的文件分析"
)
```

### 生成历史

```python
# 查看生成历史
history = generator.generation_history
for item in history:
    print(f"任务: {item['task']}")
    print(f"脚本: {item['script']}")
```

---

## 最佳实践

### 1. 任务描述要具体

```python
# ❌ 不好的描述
task = "修改代码"

# ✅ 好的描述
task = "将 src/api/ 下所有 endpoint 的认证检查从 JWT 改为 OAuth2"
```

### 2. 提供上下文信息

```python
script = generate_workflow_script(
    task="优化数据库查询性能",
    context={
        "project_type": "web_api",
        "database": "PostgreSQL",
        "orm": "SQLAlchemy",
        "target_files": ["src/models/", "src/queries/"]
    }
)
```

### 3. 验证生成的脚本

```python
script = generate_workflow_script(task="...")

# 验证脚本
errors = script.validate()
if errors:
    print(f"脚本存在错误: {errors}")
    # 可以选择重新生成或手动修复
else:
    # 执行脚本
    coordinator.load_workflow_script(script.to_dict())
```

### 4. 保存常用脚本

```python
# 生成脚本
script = generate_workflow_script(
    task="审计所有 API 的认证检查"
)

# 保存供后续复用
with open(".auracode/workflows/api-audit.json", "w") as f:
    json.dump(script.to_dict(), f, indent=2)

# 后续可以直接加载执行
coordinator.load_workflow_script_from_file(
    ".auracode/workflows/api-audit.json"
)
```

---

## 故障排查

### 问题 1: 生成的脚本阶段太少

**原因**: 任务描述过于简单

**解决**: 提供更详细的任务描述

```python
# ❌ 阶段太少
task = "检查代码"  # 可能只生成 1 个阶段

# ✅ 阶段丰富
task = "审计所有 API 的认证检查，修改不符合要求的地方，并验证修复结果"
# 会生成: 研究 → 实现 → 验证
```

### 问题 2: 提示词质量不高

**原因**: 缺少上下文信息

**解决**: 使用 `context` 参数提供更多信息

```python
script = generate_workflow_script(
    task="优化数据库查询",
    context={
        "database": "PostgreSQL",
        "orm": "SQLAlchemy",
        "slow_queries_file": "logs/slow_queries.log"
    }
)
```

### 问题 3: 脚本验证失败

**原因**: 可能存在循环依赖或任务不完整

**解决**: 检查生成的脚本并手动修复

```python
script = generate_workflow_script(task="...")
errors = script.validate()

if errors:
    print(f"错误: {errors}")
    # 查看具体哪个阶段有问题
    for stage in script.stages:
        print(f"阶段: {stage.name}")
        print(f"  依赖: {stage.depends}")
        print(f"  Agent 数: {len(stage.agents)}")
```

---

## API 参考

### WorkflowScriptGenerator

```python
class WorkflowScriptGenerator:
    def __init__(self, llm_client=None):
        """初始化生成器"""
    
    def generate(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> WorkflowScript:
        """生成工作流脚本"""
    
    def optimize_script(
        self,
        script: WorkflowScript,
        feedback: str
    ) -> WorkflowScript:
        """优化脚本"""
```

### 便捷函数

```python
def generate_workflow_script(
    task: str,
    context: Optional[Dict[str, Any]] = None
) -> WorkflowScript:
    """生成工作流脚本（全局实例）"""
```

---

## 相关文档

- [Dynamic Workflows 完整指南](batch-workflow.md)
- [Coordinator 模式](../development/architecture.md#coordinator-模式)
- [子代理系统](subagent-usage.md)

---

**最后更新**: 2026-06-02  
**版本**: v1.0  
**状态**: ✅ 完整实现
