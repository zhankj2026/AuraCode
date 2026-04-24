"""
记忆系统演示

展示如何使用记忆系统来存储和检索信息。
"""

import tempfile
import shutil
from core.memory import MemoryManager
from tools.builtin.memory_tools import (
    save_memory_tool,
    load_memory_tool,
    list_memories_tool,
    search_memories_tool,
    get_relevant_memories_tool
)


def demo_memory_system():
    """演示记忆系统的基本功能"""

    print("=" * 60)
    print("记忆系统演示")
    print("=" * 60)

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    manager = MemoryManager(temp_dir)

    try:
        # 1. 保存不同类型的记忆
        print("\n1. 保存记忆...")

        memories = [
            {
                "type": "user",
                "title": "Python 专家",
                "content": "用户有 10 年 Python 开发经验,擅长后端开发和性能优化。"
            },
            {
                "type": "user",
                "title": "React 新手",
                "content": "用户刚开始学习 React,需要详细解释和示例。"
            },
            {
                "type": "feedback",
                "title": "简洁回复偏好",
                "content": "用户希望回复简洁明了,不需要冗长的总结。直接给出结果即可。"
            },
            {
                "type": "project",
                "title": "API 优化项目",
                "content": "正在进行 API 性能优化项目,截止日期是 2026-05-01。主要目标是降低响应时间。"
            },
            {
                "type": "reference",
                "title": "Bug 追踪系统",
                "content": "项目使用 Linear 跟踪 Bug,项目代号是 INGEST。"
            }
        ]

        for mem in memories:
            manager.save_memory(
                memory_type=mem["type"],
                title=mem["title"],
                content=mem["content"]
            )
            print(f"  [OK] 保存 {mem['type']}: {mem['title']}")

        # 2. 列出所有记忆
        print("\n2. 列出所有记忆...")
        all_memories = manager.list_memories()
        print(f"  共有 {len(all_memories)} 条记忆:")
        for mem in all_memories:
            print(f"    - [{mem['type']}] {mem['title']}")

        # 3. 按类型过滤
        print("\n3. 按 type 过滤记忆...")
        user_memories = manager.list_memories("user")
        print(f"  用户记忆: {len(user_memories)} 条")
        for mem in user_memories:
            print(f"    - {mem['title']}")

        # 4. 搜索记忆
        print("\n4. 搜索记忆...")
        search_results = manager.search_memories("Python")
        print(f"  搜索 'Python': 找到 {len(search_results)} 条")
        for mem in search_results:
            print(f"    - {mem['title']}")

        # 5. 获取相关记忆
        print("\n5. 获取相关记忆...")
        context = "如何优化 Python API 的性能?"
        relevant = manager.get_relevant_memories(context)
        print(f"  上下文: {context}")
        print(f"  找到 {len(relevant)} 条相关记忆:")
        for mem in relevant:
            print(f"    - {mem.title} (类型: {mem.memory_type})")

        # 6. 使用工具接口
        print("\n6. 使用工具接口...")
        result = save_memory_tool(
            memory_type="feedback",
            title="演示反馈",
            content="通过工具接口保存的记忆"
        )
        print(f"  保存结果: {result['success']}")

        # 7. 获取记忆摘要
        print("\n7. 记忆摘要...")
        summary = manager.get_memory_summary()
        lines = summary.split("\n")
        print("  " + "\n  ".join(lines[:10]))

        # 8. 导出记忆
        print("\n8. 导出记忆...")
        export_path = f"{temp_dir}/memories_export.md"
        manager.export_memories(export_path)
        print(f"  已导出到: {export_path}")

        print("\n" + "=" * 60)
        print("演示完成!")
        print("=" * 60)

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    demo_memory_system()
