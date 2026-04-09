"""
Subagent 管理器 - 并行任务执行

基于 code.md Phase 6 实现
参考: 第 6.4 节
"""

import uuid
import threading
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SubagentHandle:
    """
    Subagent 句柄
    
    Attributes:
        agent_id: 唯一标识符
        thread: 执行线程
        task: 任务描述
        model: 使用的模型
        result: 执行结果
        status: 状态(running/completed/failed)
        created_at: 创建时间
        completed_at: 完成时间
        error: 错误信息
    """
    agent_id: str
    thread: threading.Thread
    task: str
    model: str
    result: Optional[str] = None
    status: str = "running"  # running/completed/failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'agent_id': self.agent_id,
            'task': self.task,
            'model': self.model,
            'status': self.status,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'result_preview': self.result[:200] if self.result else None
        }


class SubagentManager:
    """
    Subagent 管理器
    
    支持创建和管理多个并行执行的子 Agent
    每个 Subagent 拥有独立的线程和上下文
    """
    
    def __init__(self, max_concurrent: int = 5):
        """
        初始化 Subagent 管理器
        
        Args:
            max_concurrent: 最大并发数,默认 5
        """
        self.agents: Dict[str, SubagentHandle] = {}
        self.max_concurrent = max_concurrent
        self._lock = threading.Lock()
    
    def _execute_task(
        self,
        agent_id: str,
        task: str,
        model: str,
        output_file: str,
        progress_callback: Optional[Callable] = None
    ):
        """
        在独立线程中执行任务
        
        Args:
            agent_id: Agent ID
            task: 任务描述
            model: 模型名称
            output_file: 输出文件路径
            progress_callback: 进度回调函数
        """
        try:
            logger.info(f"Subagent {agent_id} 开始执行任务")
            
            # 模拟任务执行(实际应该调用 LLM API)
            # 这里创建一个简化的执行环境
            result_lines = [
                f"# Subagent 执行报告",
                f"",
                f"**Agent ID**: {agent_id}",
                f"**任务**: {task}",
                f"**模型**: {model}",
                f"**开始时间**: {datetime.now().isoformat()}",
                f"",
                f"## 执行过程",
                f"",
            ]
            
            # 模拟多步骤执行
            steps = [
                "分析任务需求",
                "收集相关信息",
                "制定执行计划",
                "执行具体操作",
                "验证结果",
            ]
            
            for i, step in enumerate(steps, 1):
                if progress_callback:
                    progress_callback(agent_id, i, len(steps), step)
                
                result_lines.append(f"{i}. {step} ✓")
            
            result_lines.extend([
                f"",
                f"## 执行结果",
                f"",
                f"任务执行完成。",
                f"",
                f"**完成时间**: {datetime.now().isoformat()}",
            ])
            
            result = "\n".join(result_lines)
            
            # 保存结果到文件
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            
            # 更新状态
            with self._lock:
                if agent_id in self.agents:
                    self.agents[agent_id].result = result
                    self.agents[agent_id].status = "completed"
                    self.agents[agent_id].completed_at = datetime.now().isoformat()
            
            logger.info(f"Subagent {agent_id} 执行完成")
            
        except Exception as e:
            error_msg = f"Subagent {agent_id} 执行失败: {str(e)}"
            logger.error(error_msg)
            
            with self._lock:
                if agent_id in self.agents:
                    self.agents[agent_id].result = error_msg
                    self.agents[agent_id].status = "failed"
                    self.agents[agent_id].completed_at = datetime.now().isoformat()
                    self.agents[agent_id].error = str(e)
    
    def spawn_subagent(
        self,
        task: str,
        model: str = "glm-4-plus",
        tools: List[str] = None,
        run_in_background: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> SubagentHandle:
        """
        创建子 Agent 执行任务
        
        Args:
            task: 任务描述
            model: 使用的模型名称
            tools: 可用的工具列表
            run_in_background: 是否后台运行
            progress_callback: 进度回调函数,签名: callback(agent_id, current, total, step)
        
        Returns:
            SubagentHandle 句柄
        """
        # 生成唯一 ID
        agent_id = str(uuid.uuid4())[:8]
        
        # 创建输出文件路径
        output_dir = os.path.join(os.getcwd(), '.subagent_output')
        output_file = os.path.join(output_dir, f"{agent_id}.md")
        
        # 创建线程
        thread = threading.Thread(
            target=self._execute_task,
            args=(agent_id, task, model, output_file, progress_callback),
            daemon=True
        )
        
        # 创建句柄
        handle = SubagentHandle(
            agent_id=agent_id,
            thread=thread,
            task=task,
            model=model
        )
        
        # 在同一个锁内检查并发数并注册
        with self._lock:
            running_count = sum(
                1 for agent in self.agents.values()
                if agent.status == "running"
            )
            
            if running_count >= self.max_concurrent:
                raise RuntimeError(
                    f"达到最大并发数限制: {self.max_concurrent}\n"
                    f"请等待部分任务完成后再提交新任务"
                )
            
            # 注册
            self.agents[agent_id] = handle
        
        # 启动线程
        thread.start()
        
        logger.info(f"创建 Subagent: {agent_id}, 任务: {task[:50]}...")
        
        # 如果不同步运行,返回句柄
        if run_in_background:
            return handle
        
        # 同步运行:等待完成
        thread.join()
        return handle
    
    def join_subagent(self, agent_id: str, timeout: float = None) -> str:
        """
        等待 Subagent 完成并获取结果
        
        Args:
            agent_id: Agent ID
            timeout: 超时时间(秒),None 表示无限等待
        
        Returns:
            执行结果
        
        Raises:
            KeyError: 如果 Agent 不存在
            TimeoutError: 如果超时
        """
        if agent_id not in self.agents:
            raise KeyError(f"Subagent 不存在: {agent_id}")
        
        handle = self.agents[agent_id]
        
        # 等待线程完成
        handle.thread.join(timeout=timeout)
        
        if handle.thread.is_alive():
            raise TimeoutError(f"Subagent {agent_id} 执行超时({timeout}秒)")
        
        if handle.status == "failed":
            return f"❌ Subagent 执行失败\n\n{handle.result}"
        
        return handle.result
    
    def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """
        获取 Subagent 状态
        
        Args:
            agent_id: Agent ID
        
        Returns:
            状态信息字典
        
        Raises:
            KeyError: 如果 Agent 不存在
        """
        if agent_id not in self.agents:
            raise KeyError(f"Subagent 不存在: {agent_id}")
        
        handle = self.agents[agent_id]
        return handle.to_dict()
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """
        列出所有 Subagent
        
        Returns:
            Subagent 信息列表
        """
        return [
            handle.to_dict()
            for handle in self.agents.values()
        ]
    
    def get_running_agents(self) -> List[Dict[str, Any]]:
        """
        获取正在运行的 Subagent
        
        Returns:
            运行中的 Subagent 列表
        """
        return [
            handle.to_dict()
            for handle in self.agents.values()
            if handle.status == "running"
        ]
    
    def cancel_agent(self, agent_id: str) -> bool:
        """
        取消 Subagent(不推荐,可能导致资源泄漏)
        
        Args:
            agent_id: Agent ID
        
        Returns:
            True 如果成功取消
        """
        if agent_id not in self.agents:
            return False
        
        handle = self.agents[agent_id]
        
        if handle.status != "running":
            return False
        
        # 注意: Python 不支持强制终止线程
        # 这里只是标记状态,实际线程会继续运行直到完成
        handle.status = "cancelled"
        logger.warning(f"Subagent {agent_id} 标记为取消(线程仍会继续运行)")
        
        return True
    
    def cleanup_finished(self, max_age_hours: float = 24):
        """
        清理已完成的 Subagent 记录
        
        Args:
            max_age_hours: 保留时间(小时),默认 24 小时
        """
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            to_remove = []
            
            for agent_id, handle in self.agents.items():
                if handle.status in ['completed', 'failed', 'cancelled']:
                    if handle.completed_at:
                        completed_time = datetime.fromisoformat(handle.completed_at)
                        if completed_time < cutoff_time:
                            to_remove.append(agent_id)
            
            for agent_id in to_remove:
                del self.agents[agent_id]
            
            if to_remove:
                logger.info(f"清理 {len(to_remove)} 个已完成的 Subagent")
    
    def get_stats(self) -> Dict[str, int]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            'total': len(self.agents),
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }
        
        for handle in self.agents.values():
            if handle.status in stats:
                stats[handle.status] += 1
        
        return stats


# 全局 Subagent 管理器实例
subagent_manager = SubagentManager(max_concurrent=5)
