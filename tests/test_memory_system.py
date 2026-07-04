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
记忆系统测试
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path

from core.memory import Memory, MemoryManager, get_memory_manager, MEMORY_TYPES


class TestMemory:
    """测试 Memory 类"""

    def test_memory_creation(self):
        """测试创建记忆对象"""
        memory = Memory(
            memory_type="user",
            title="测试用户",
            content="这是一个测试用户"
        )

        assert memory.memory_type == "user"
        assert memory.title == "测试用户"
        assert memory.content == "这是一个测试用户"
        assert memory.created_at is not None
        assert memory.updated_at is not None

    def test_memory_to_dict(self):
        """测试记忆转换为字典"""
        memory = Memory(
            memory_type="feedback",
            title="测试反馈",
            content="用户希望简洁的回复",
            metadata={"source": "chat"}
        )

        data = memory.to_dict()
        assert data["memory_type"] == "feedback"
        assert data["title"] == "测试反馈"
        assert data["content"] == "用户希望简洁的回复"
        assert data["metadata"]["source"] == "chat"

    def test_memory_from_dict(self):
        """测试从字典创建记忆"""
        data = {
            "memory_type": "project",
            "title": "测试项目",
            "content": "项目截止日期: 2026-04-30",
            "metadata": {"deadline": "2026-04-30"},
            "created_at": "2026-04-24T10:00:00",
            "updated_at": "2026-04-24T10:00:00"
        }

        memory = Memory.from_dict(data)
        assert memory.memory_type == "project"
        assert memory.title == "测试项目"
        assert memory.metadata["deadline"] == "2026-04-30"


class TestMemoryManager:
    """测试 MemoryManager 类"""

    def setup_method(self):
        """每个测试前设置临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = MemoryManager(self.temp_dir)

    def teardown_method(self):
        """每个测试后清理临时目录"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_manager_initialization(self):
        """测试管理器初始化"""
        assert self.manager.memory_dir.exists()
        assert self.manager.memory_dir.name == "memory"

    def test_save_memory(self):
        """测试保存记忆"""
        success = self.manager.save_memory(
            memory_type="user",
            title="测试用户",
            content="这是一个测试用户"
        )

        assert success is True

        # 检查文件是否创建
        memory_path = self.manager._get_memory_path("user", "测试用户")
        assert memory_path.exists()

    def test_load_memory(self):
        """测试加载记忆"""
        # 先保存
        self.manager.save_memory(
            memory_type="feedback",
            title="测试反馈",
            content="用户希望简洁的回复"
        )

        # 再加载
        memory = self.manager.load_memory("feedback", "测试反馈")

        assert memory is not None
        assert memory.title == "测试反馈"
        assert memory.content == "用户希望简洁的回复"

    def test_delete_memory(self):
        """测试删除记忆"""
        # 先保存
        self.manager.save_memory(
            memory_type="user",
            title="待删除",
            content="这个记忆将被删除"
        )

        # 确认存在
        memory = self.manager.load_memory("user", "待删除")
        assert memory is not None

        # 删除
        success = self.manager.delete_memory("user", "待删除")
        assert success is True

        # 确认不存在
        memory = self.manager.load_memory("user", "待删除")
        assert memory is None

    def test_list_memories(self):
        """测试列出所有记忆"""
        # 保存多个记忆
        self.manager.save_memory("user", "用户1", "内容1")
        self.manager.save_memory("user", "用户2", "内容2")
        self.manager.save_memory("feedback", "反馈1", "反馈内容1")

        # 列出所有
        all_memories = self.manager.list_memories()
        assert len(all_memories) == 3

        # 按类型过滤
        user_memories = self.manager.list_memories("user")
        assert len(user_memories) == 2

        feedback_memories = self.manager.list_memories("feedback")
        assert len(feedback_memories) == 1

    def test_search_memories(self):
        """测试搜索记忆"""
        # 保存记忆
        self.manager.save_memory("user", "Python开发者", "用户擅长Python开发")
        self.manager.save_memory("user", "前端开发者", "用户擅长React")
        self.manager.save_memory("project", "Python项目", "使用Python的后端项目")

        # 搜索
        results = self.manager.search_memories("Python")
        assert len(results) == 2

    def test_get_relevant_memories(self):
        """测试获取相关记忆"""
        # 保存记忆
        self.manager.save_memory(
            "user",
            "Python专家",
            "用户是Python专家,有10年经验"
        )
        self.manager.save_memory(
            "user",
            "React新手",
            "用户刚学习React,需要帮助"
        )

        # 获取相关记忆
        relevant = self.manager.get_relevant_memories("如何优化Python代码")
        assert len(relevant) > 0
        # 应该优先匹配 Python专家
        assert relevant[0].title == "Python专家"

    def test_memory_index(self):
        """测试记忆索引文件"""
        # 保存一些记忆
        self.manager.save_memory("user", "用户A", "内容A")
        self.manager.save_memory("feedback", "反馈A", "内容A")

        # 检查索引文件
        index_path = self.manager.memory_index_path
        assert index_path.exists()

        content = index_path.read_text(encoding="utf-8")
        assert "用户A" in content
        assert "反馈A" in content

    def test_get_memory_summary(self):
        """测试获取记忆摘要"""
        # 保存记忆
        self.manager.save_memory("user", "用户1", "内容1")
        self.manager.save_memory("feedback", "反馈1", "内容1")

        # 获取摘要
        summary = self.manager.get_memory_summary()

        assert "用户1" in summary
        assert "反馈1" in summary
        assert "# 记忆摘要" in summary

    def test_export_memories(self):
        """测试导出记忆"""
        # 保存记忆
        self.manager.save_memory("user", "导出测试", "测试内容")

        # 导出
        export_path = os.path.join(self.temp_dir, "export.md")
        success = self.manager.export_memories(export_path)

        assert success is True
        assert os.path.exists(export_path)

        # 检查内容
        content = Path(export_path).read_text(encoding="utf-8")
        assert "导出测试" in content


class TestMemoryTools:
    """测试记忆工具"""

    def setup_method(self):
        """每个测试前设置临时目录"""
        self.temp_dir = tempfile.mkdtemp()

        # 修改全局项目根目录
        import core.memory
        core.memory._global_memory_manager = None
        self.manager = get_memory_manager(self.temp_dir)

    def teardown_method(self):
        """每个测试后清理临时目录"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        # 清理全局管理器
        import core.memory
        core.memory._global_memory_manager = None

    def test_save_memory_tool(self):
        """测试保存记忆工具"""
        from tools.builtin.memory_tools import save_memory_tool

        result = save_memory_tool(
            memory_type="user",
            title="工具测试",
            content="通过工具保存的记忆"
        )

        assert result["success"] is True

        # 验证记忆已保存
        memory = self.manager.load_memory("user", "工具测试")
        assert memory is not None
        assert memory.content == "通过工具保存的记忆"

    def test_load_memory_tool(self):
        """测试加载记忆工具"""
        from tools.builtin.memory_tools import load_memory_tool, save_memory_tool

        # 先保存
        save_memory_tool(
            memory_type="feedback",
            title="工具反馈",
            content="通过工具保存的反馈"
        )

        # 再加载
        result = load_memory_tool("feedback", "工具反馈")

        assert result["success"] is True
        assert result["memory"]["content"] == "通过工具保存的反馈"

    def test_list_memories_tool(self):
        """测试列出记忆工具"""
        from tools.builtin.memory_tools import list_memories_tool, save_memory_tool

        # 保存一些记忆
        save_memory_tool("user", "用户1", "内容1")
        save_memory_tool("user", "用户2", "内容2")

        # 列出
        result = list_memories_tool()

        assert result["success"] is True
        assert result["count"] == 2

    def test_search_memories_tool(self):
        """测试搜索记忆工具"""
        from tools.builtin.memory_tools import search_memories_tool, save_memory_tool

        # 保存记忆
        save_memory_tool("user", "Python专家", "擅长Python")
        save_memory_tool("user", "React新手", "学习React")

        # 搜索
        result = search_memories_tool("Python")

        assert result["success"] is True
        assert result["count"] == 1

    def test_delete_memory_tool(self):
        """测试删除记忆工具"""
        from tools.builtin.memory_tools import delete_memory_tool, save_memory_tool

        # 先保存
        save_memory_tool("user", "待删除", "内容")

        # 删除
        result = delete_memory_tool("user", "待删除")

        assert result["success"] is True

    def test_get_memory_summary_tool(self):
        """测试获取摘要工具"""
        from tools.builtin.memory_tools import get_memory_summary_tool, save_memory_tool

        # 保存记忆
        save_memory_tool("user", "用户1", "内容1")

        # 获取摘要
        result = get_memory_summary_tool()

        assert result["success"] is True
        assert "用户1" in result["summary"]

    def test_get_relevant_memories_tool(self):
        """测试获取相关记忆工具"""
        from tools.builtin.memory_tools import get_relevant_memories_tool, save_memory_tool

        # 保存记忆
        save_memory_tool(
            "user",
            "Python专家",
            "用户有十年Python经验"
        )

        # 获取相关记忆
        result = get_relevant_memories_tool(
            context="如何优化Python代码性能"
        )

        assert result["success"] is True
        assert result["count"] > 0


class TestMemoryIntegration:
    """测试记忆系统集成"""

    def test_memory_in_agent_loop(self):
        """测试记忆在 Agent Loop 中的集成"""
        # 这个测试需要完整的 Agent Loop 环境
        # 这里只测试导入是否正常
        try:
            from core.agent_loop import AgentLoop
            from core.memory import get_memory_manager

            # 创建临时项目根目录
            temp_dir = tempfile.mkdtemp()

            try:
                # 初始化 Agent Loop(启用记忆)
                config = {
                    "api_key": "test",
                    "base_url": "https://test.com",
                    "model": "test-model",
                    "enable_memory": True,
                    "project_root": temp_dir
                }

                # 注意: 这会因为缺少 API key 而失败,但可以验证初始化流程
                # 我们只测试到记忆管理器初始化
                manager = get_memory_manager(temp_dir)
                assert manager is not None

            finally:
                shutil.rmtree(temp_dir)

        except ImportError as e:
            pytest.skip(f"AgentLoop 导入失败: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
