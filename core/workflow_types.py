"""
Workflow Types - Dynamic Workflows 类型定义

定义工作流脚本的数据结构，支持：
- 阶段化 Pipeline（DAG 依赖）
- 阶段内并行执行
- 中间结果存储
- 收敛检查

参考标准 Dynamic Workflows 的脚本 Schema。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class AgentType(Enum):
    """Agent 类型"""
    EXPLORE = "explore"
    PLAN = "plan"
    REVIEW = "review"
    IMPACT = "impact"
    DIAGNOSE = "diagnose"
    GENERAL = "general"


@dataclass
class AgentTask:
    """
    单个 Agent 任务定义
    
    属性:
        prompt: 任务提示词（必须自包含，Agent 无法看到其他对话）
        agent_type: Agent 类型（决定系统提示词和工具集）
        timeout: 超时时间（秒）
        retry_on_failure: 失败时是否重试
        max_retries: 最大重试次数
    """
    prompt: str
    agent_type: AgentType = AgentType.GENERAL
    timeout: int = 300  # 5 分钟
    retry_on_failure: bool = False
    max_retries: int = 2
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "prompt": self.prompt,
            "agent_type": self.agent_type.value,
            "timeout": self.timeout,
            "retry_on_failure": self.retry_on_failure,
            "max_retries": self.max_retries,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTask":
        """从字典创建"""
        return cls(
            prompt=data["prompt"],
            agent_type=AgentType(data.get("agent_type", "general")),
            timeout=data.get("timeout", 300),
            retry_on_failure=data.get("retry_on_failure", False),
            max_retries=data.get("max_retries", 2),
        )


@dataclass
class WorkflowStage:
    """
    工作流阶段定义
    
    属性:
        name: 阶段名称（唯一标识）
        agents: 该阶段并行执行的 Agent 任务列表
        depends: 依赖的阶段名称列表（DAG 依赖）
        synthesize: 是否需要综合该阶段的结果
        synthesize_prompt: 综合提示词（为空时使用默认提示）
        description: 阶段描述（可选）
    """
    name: str
    agents: List[AgentTask]
    depends: List[str] = field(default_factory=list)
    synthesize: bool = True
    synthesize_prompt: str = ""
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "agents": [agent.to_dict() for agent in self.agents],
            "depends": self.depends,
            "synthesize": self.synthesize,
            "synthesize_prompt": self.synthesize_prompt,
            "description": self.description,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStage":
        """从字典创建"""
        return cls(
            name=data["name"],
            agents=[AgentTask.from_dict(a) for a in data.get("agents", [])],
            depends=data.get("depends", []),
            synthesize=data.get("synthesize", True),
            synthesize_prompt=data.get("synthesize_prompt", ""),
            description=data.get("description", ""),
        )


@dataclass
class WorkflowScript:
    """
    完整工作流脚本定义
    
    参考标准 Dynamic Workflows 的脚本结构。
    
    属性:
        name: 工作流名称（唯一标识）
        description: 工作流描述
        stages: 阶段列表（DAG 结构）
        validation: 验证规则（可选）
        convergence_check: 收敛检查脚本/prompt
        max_iterations: 最大迭代次数（防止无限循环）
        metadata: 元数据（创建时间、版本等）
    """
    name: str
    description: str = ""
    stages: List[WorkflowStage] = field(default_factory=list)
    validation: Dict[str, Any] = field(default_factory=dict)
    convergence_check: str = ""
    max_iterations: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化和 LLM 生成）"""
        return {
            "name": self.name,
            "description": self.description,
            "stages": [stage.to_dict() for stage in self.stages],
            "validation": self.validation,
            "convergence_check": self.convergence_check,
            "max_iterations": self.max_iterations,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowScript":
        """从字典创建（用于加载脚本）"""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            stages=[WorkflowStage.from_dict(s) for s in data.get("stages", [])],
            validation=data.get("validation", {}),
            convergence_check=data.get("convergence_check", ""),
            max_iterations=data.get("max_iterations", 3),
            metadata=data.get("metadata", {}),
        )
    
    def validate(self) -> List[str]:
        """
        验证脚本正确性
        
        Returns:
            错误列表（为空表示验证通过）
        """
        errors = []
        
        # 检查基本信息
        if not self.name:
            errors.append("工作流名称不能为空")
        
        if not self.stages:
            errors.append("工作流必须包含至少一个阶段")
        
        # 检查阶段名称唯一性
        stage_names = [s.name for s in self.stages]
        if len(stage_names) != len(set(stage_names)):
            errors.append("阶段名称必须唯一")
        
        # 检查依赖关系
        for stage in self.stages:
            for dep in stage.depends:
                if dep not in stage_names:
                    errors.append(f"阶段 '{stage.name}' 依赖不存在的阶段 '{dep}'")
            
            # 检查循环依赖（简化版）
            if stage.name in stage.depends:
                errors.append(f"阶段 '{stage.name}' 不能依赖自己")
        
        # 检查 Agent 任务
        for stage in self.stages:
            if not stage.agents:
                errors.append(f"阶段 '{stage.name}' 必须包含至少一个 Agent 任务")
            
            for i, agent in enumerate(stage.agents):
                if not agent.prompt:
                    errors.append(f"阶段 '{stage.name}' 的 Agent {i+1} 提示词不能为空")
        
        return errors
    
    def get_execution_order(self) -> List[str]:
        """
        获取阶段的执行顺序（拓扑排序）
        
        Returns:
            阶段名称列表（按执行顺序）
            
        Raises:
            ValueError: 存在循环依赖
        """
        # 构建邻接表
        graph = {stage.name: [] for stage in self.stages}
        in_degree = {stage.name: 0 for stage in self.stages}
        
        for stage in self.stages:
            for dep in stage.depends:
                graph[dep].append(stage.name)
                in_degree[stage.name] += 1
        
        # Kahn 算法拓扑排序
        queue = [name for name, degree in in_degree.items() if degree == 0]
        order = []
        
        while queue:
            # 选择入度为 0 的节点
            node = queue.pop(0)
            order.append(node)
            
            # 减少后继节点的入度
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 检查是否有循环依赖
        if len(order) != len(self.stages):
            raise ValueError("存在循环依赖，无法拓扑排序")
        
        return order


# ── 辅助函数 ──

def create_simple_workflow(
    name: str,
    description: str,
    stages: List[Dict[str, Any]]
) -> WorkflowScript:
    """
    快速创建简单工作流
    
    Args:
        name: 工作流名称
        description: 工作流描述
        stages: 阶段列表（简化格式）
            [
                {
                    "name": "阶段名",
                    "agents": [
                        {"prompt": "任务", "agent_type": "explore"}
                    ],
                    "depends": [],  # 可选
                    "synthesize": True  # 可选
                }
            ]
    
    Returns:
        WorkflowScript 对象
    
    示例:
        workflow = create_simple_workflow(
            name="api-audit",
            description="审计 API 认证",
            stages=[
                {
                    "name": "scan",
                    "agents": [
                        {"prompt": "扫描认证检查", "agent_type": "explore"}
                    ]
                },
                {
                    "name": "verify",
                    "agents": [
                        {"prompt": "验证发现", "agent_type": "review"}
                    ],
                    "depends": ["scan"]
                }
            ]
        )
    """
    workflow_stages = []
    for stage_data in stages:
        agents = [
            AgentTask(
                prompt=a["prompt"],
                agent_type=AgentType(a.get("agent_type", "general"))
            )
            for a in stage_data.get("agents", [])
        ]
        
        workflow_stages.append(WorkflowStage(
            name=stage_data["name"],
            agents=agents,
            depends=stage_data.get("depends", []),
            synthesize=stage_data.get("synthesize", True),
        ))
    
    return WorkflowScript(
        name=name,
        description=description,
        stages=workflow_stages,
    )


def workflow_from_json(json_str: str) -> WorkflowScript:
    """
    从 JSON 字符串加载工作流脚本
    
    Args:
        json_str: JSON 格式的脚本
    
    Returns:
        WorkflowScript 对象
    """
    import json
    data = json.loads(json_str)
    return WorkflowScript.from_dict(data)


def workflow_to_json(script: WorkflowScript, indent: int = 2) -> str:
    """
    将工作流脚本转换为 JSON 字符串
    
    Args:
        script: WorkflowScript 对象
        indent: JSON 缩进
    
    Returns:
        JSON 字符串
    """
    import json
    return json.dumps(script.to_dict(), indent=indent, ensure_ascii=False)
