#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
Workflow Script Generator - 使用 LLM 动态生成工作流脚本

核心能力：
1. 分析用户任务描述
2. 生成多阶段工作流脚本（DAG 结构）
3. 验证脚本正确性
4. 支持脚本优化和迭代

参考标准 Dynamic Workflows 的脚本生成机制。
"""
import json
import logging
from typing import Dict, Any, List, Optional
from core.workflow_types import (
    WorkflowScript, 
    WorkflowStage, 
    AgentTask, 
    AgentType
)

logger = logging.getLogger(__name__)


class WorkflowScriptGenerator:
    """
    工作流脚本生成器
    
    使用 LLM 分析用户任务，自动生成多阶段工作流脚本。
    
    核心流程：
    1. 任务分析 - 理解用户意图和复杂度
    2. 阶段规划 - 确定工作流阶段和依赖关系
    3. Agent 分配 - 为每个阶段分配适当的 Agent 类型
    4. 提示词生成 - 为每个 Agent 生成自包含的提示词
    5. 脚本验证 - 验证生成的脚本正确性
    """
    
    def __init__(self, llm_client=None):
        """
        初始化生成器
        
        Args:
            llm_client: LLM 客户端（用于生成脚本）
        """
        self.llm_client = llm_client
        self.generation_history: List[Dict[str, Any]] = []
    
    def generate(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> WorkflowScript:
        """
        生成工作流脚本
        
        Args:
            task: 用户任务描述
            context: 上下文信息（项目结构、技术栈等）
        
        Returns:
            WorkflowScript 对象
        
        示例：
            generator = WorkflowScriptGenerator()
            script = generator.generate(
                task="审计所有 API endpoint 的认证检查",
                context={"project_type": "web_api"}
            )
        """
        logger.info(f"Generating workflow for task: {task[:50]}...")
        
        # Phase 1: 任务分析
        task_analysis = self._analyze_task(task, context)
        
        # Phase 2: 生成阶段规划
        stage_plan = self._plan_stages(task, task_analysis)
        
        # Phase 3: 构建完整脚本
        workflow_script = self._build_script(task, stage_plan)
        
        # Phase 4: 验证脚本
        errors = workflow_script.validate()
        if errors:
            logger.warning(f"Generated script has validation errors: {errors}")
            # 尝试修复
            workflow_script = self._fix_script(workflow_script, errors)
        
        # 记录生成历史
        self.generation_history.append({
            "task": task,
            "script": workflow_script.to_dict(),
            "timestamp": len(self.generation_history)
        })
        
        logger.info(f"Workflow generated: {workflow_script.name}")
        return workflow_script
    
    def _analyze_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析任务特征
        
        Returns:
            {
                "complexity": "simple" | "moderate" | "complex",
                "requires_research": bool,
                "requires_implementation": bool,
                "requires_verification": bool,
                "estimated_stages": int,
                "key_areas": List[str]
            }
        """
        # 简化版：基于规则的任务分析
        # 实际实现应该调用 LLM
        
        task_lower = task.lower()
        
        # 判断复杂度
        if any(word in task_lower for word in ["所有", "全部", "整个", "all", "entire"]):
            complexity = "complex"
            estimated_stages = 3
        elif any(word in task_lower for word in ["一些", "部分", "几个", "some", "few"]):
            complexity = "moderate"
            estimated_stages = 2
        else:
            complexity = "simple"
            estimated_stages = 1
        
        # 判断是否需要研究阶段
        requires_research = any(word in task_lower for word in [
            "审计", "分析", "检查", "扫描", "audit", "analyze", "check", "scan"
        ])
        
        # 判断是否需要实现阶段
        requires_implementation = any(word in task_lower for word in [
            "修改", "更新", "重构", "迁移", "modify", "update", "refactor", "migrate"
        ])
        
        # 判断是否需要验证阶段
        requires_verification = any(word in task_lower for word in [
            "验证", "测试", "确认", "validate", "test", "verify"
        ])
        
        # 识别关键领域
        key_areas = []
        if "api" in task_lower:
            key_areas.append("api")
        if "security" in task_lower or "认证" in task_lower or "auth" in task_lower:
            key_areas.append("security")
        if "database" in task_lower or "数据库" in task_lower:
            key_areas.append("database")
        if "test" in task_lower or "测试" in task_lower:
            key_areas.append("testing")
        
        return {
            "complexity": complexity,
            "requires_research": requires_research,
            "requires_implementation": requires_implementation,
            "requires_verification": requires_verification or requires_research,
            "estimated_stages": estimated_stages,
            "key_areas": key_areas
        }
    
    def _plan_stages(
        self,
        task: str,
        task_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        规划工作流阶段
        
        Returns:
            [
                {
                    "name": "阶段名",
                    "agent_type": "agent 类型",
                    "prompt_template": "提示词模板",
                    "depends": []
                }
            ]
        """
        stages = []
        
        # 研究阶段
        if task_analysis["requires_research"]:
            stages.append({
                "name": "research",
                "agent_type": "explore",
                "prompt_template": self._get_research_prompt(task, task_analysis),
                "depends": [],
                "synthesize": True,
                "synthesize_prompt": "总结研究发现，列出关键发现和影响范围。"
            })
        
        # 实现阶段
        if task_analysis["requires_implementation"]:
            depends = ["research"] if task_analysis["requires_research"] else []
            stages.append({
                "name": "implementation",
                "agent_type": "general",
                "prompt_template": self._get_implementation_prompt(task, task_analysis),
                "depends": depends,
                "synthesize": True
            })
        
        # 验证阶段
        if task_analysis["requires_verification"]:
            if task_analysis["requires_implementation"]:
                depends = ["implementation"]
            elif task_analysis["requires_research"]:
                depends = ["research"]
            else:
                depends = []
            
            stages.append({
                "name": "verification",
                "agent_type": "review",
                "prompt_template": self._get_verification_prompt(task, task_analysis),
                "depends": depends,
                "synthesize": False
            })
        
        # 如果没有明确的阶段，创建一个通用阶段
        if not stages:
            stages.append({
                "name": "execution",
                "agent_type": "general",
                "prompt_template": f"执行任务：{task}",
                "depends": [],
                "synthesize": True
            })
        
        return stages
    
    def _build_script(
        self,
        task: str,
        stage_plan: List[Dict[str, Any]]
    ) -> WorkflowScript:
        """构建完整的工作流脚本"""
        # 生成工作流名称
        workflow_name = self._generate_workflow_name(task)
        
        # 构建阶段
        workflow_stages = []
        for stage_data in stage_plan:
            agent_task = AgentTask(
                prompt=stage_data["prompt_template"],
                agent_type=AgentType(stage_data["agent_type"]),
                timeout=300,
                retry_on_failure=False
            )
            
            stage = WorkflowStage(
                name=stage_data["name"],
                agents=[agent_task],
                depends=stage_data["depends"],
                synthesize=stage_data.get("synthesize", True),
                synthesize_prompt=stage_data.get("synthesize_prompt", "")
            )
            workflow_stages.append(stage)
        
        # 创建完整脚本
        script = WorkflowScript(
            name=workflow_name,
            description=task,
            stages=workflow_stages,
            max_iterations=3,
            metadata={
                "generated_by": "WorkflowScriptGenerator",
                "task_complexity": "auto-detected",
                "version": "1.0"
            }
        )
        
        return script
    
    def _generate_workflow_name(self, task: str) -> str:
        """生成工作流名称"""
        # 提取关键词
        task_words = task.split()[:5]
        name = "-".join([w.lower() for w in task_words if len(w) > 3])
        
        # 清理特殊字符
        name = name.replace(",", "").replace(".", "").replace(":", "")
        
        # 限制长度
        if len(name) > 40:
            name = name[:40]
        
        return f"workflow-{name}" if name else "workflow-auto-generated"
    
    def _get_research_prompt(
        self,
        task: str,
        task_analysis: Dict[str, Any]
    ) -> str:
        """生成研究阶段的提示词"""
        key_areas = ", ".join(task_analysis["key_areas"]) if task_analysis["key_areas"] else "相关领域"
        
        return f"""研究任务：{task}

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
"""
    
    def _get_implementation_prompt(
        self,
        task: str,
        task_analysis: Dict[str, Any]
    ) -> str:
        """生成实现阶段的提示词"""
        return f"""实施任务：{task}

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
"""
    
    def _get_verification_prompt(
        self,
        task: str,
        task_analysis: Dict[str, Any]
    ) -> str:
        """生成验证阶段的提示词"""
        return f"""验证任务：{task}

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
"""
    
    def _fix_script(
        self,
        script: WorkflowScript,
        errors: List[str]
    ) -> WorkflowScript:
        """
        尝试修复脚本错误
        
        简化版：直接返回原脚本
        实际实现应该调用 LLM 修复
        """
        logger.warning(f"Script validation failed with {len(errors)} errors")
        # TODO: 实现 LLM 驱动的脚本修复
        return script
    
    def optimize_script(
        self,
        script: WorkflowScript,
        feedback: str
    ) -> WorkflowScript:
        """
        根据反馈优化脚本
        
        Args:
            script: 原始脚本
            feedback: 用户反馈或执行结果
        
        Returns:
            优化后的脚本
        """
        # TODO: 实现 LLM 驱动的脚本优化
        logger.info("Script optimization not yet implemented")
        return script


# ── 全局实例 ──

_workflow_generator = WorkflowScriptGenerator()


def generate_workflow_script(
    task: str,
    context: Optional[Dict[str, Any]] = None
) -> WorkflowScript:
    """
    便捷函数：生成工作流脚本
    
    Args:
        task: 任务描述
        context: 上下文信息
    
    Returns:
        WorkflowScript 对象
    
    示例：
        script = generate_workflow_script(
            task="审计所有 API 的认证检查"
        )
    """
    return _workflow_generator.generate(task, context)
