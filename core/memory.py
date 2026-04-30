"""
记忆系统 - 仿 Claude Code 设计

提供持久化记忆存储,支持多种记忆类型:
- user: 用户信息(角色、目标、偏好、知识)
- feedback: 用户反馈(方法指导、确认有效的方法)
- project: 项目信息(正在进行的工作、目标、截止日期)
- reference: 外部系统参考(Bug跟踪、文档等)
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# 记忆类型定义
MEMORY_TYPES = {
    "user": {
        "description": "用户信息",
        "when_to_save": "了解用户角色、偏好、职责、知识时",
        "how_to_use": "根据用户画像定制响应风格和协作方式",
        "examples": [
            "用户是数据科学家,专注于可观测性和日志",
            "十年 Go 经验,第一次接触 React",
        ]
    },
    "feedback": {
        "description": "用户反馈",
        "when_to_save": "用户纠正或确认某种方法时",
        "how_to_use": "避免重复接受相同指导",
        "examples": [
            "集成测试必须使用真实数据库,不要 mock",
            "用户希望响应简洁,不需要结尾总结",
        ]
    },
    "project": {
        "description": "项目信息",
        "when_to_save": "了解谁在做什么、为什么、何时完成",
        "how_to_use": "理解任务背景,做出更好的建议",
        "examples": [
            "2026-03-05 后合并冻结,为移动版本发布",
            "重构由法律/合规要求驱动",
        ]
    },
    "reference": {
        "description": "外部系统参考",
        "when_to_save": "了解外部资源在哪里时",
        "how_to_use": "用户引用外部系统时参考",
        "examples": [
            "Bug 追踪在 Linear INGEST 项目",
            "Oncall 监控看板: grafana.internal/d/api-latency",
        ]
    }
}


class Memory:
    """记忆对象"""

    def __init__(
        self,
        memory_type: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None
    ):
        self.memory_type = memory_type
        self.title = title
        self.content = content
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "memory_type": self.memory_type,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """从字典创建"""
        return cls(
            memory_type=data["memory_type"],
            title=data["title"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )


class MemoryManager:
    """
    记忆管理器

    管理所有类型的记忆,提供增删改查功能。
    记忆存储在 {project_root}/memory/ 目录下。
    """

    def __init__(self, project_root: str = "."):
        """
        初始化记忆管理器

        Args:
            project_root: 项目根目录
        """
        self.project_root = Path(project_root).resolve()
        self.memory_dir = self.project_root / ".opencode" / "memory"

        # 确保记忆目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # MEMORY.md 是索引文件
        self.memory_index_path = self.memory_dir / "MEMORY.md"

        logger.info(f"MemoryManager initialized with dir: {self.memory_dir}")

    def _get_memory_path(self, memory_type: str, title: str) -> Path:
        """获取记忆文件路径"""
        import hashlib

        # 将标题转换为安全的文件名
        # 对于包含中文或特殊字符的标题,使用 hash
        try:
            # 尝试创建安全的文件名(保留中文)
            safe_title = title.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
            # 移除 Windows 不允许的字符
            safe_title = "".join(c for c in safe_title if c not in '<>:"|?*')

            # 如果处理后标题为空或太短,使用 hash
            if len(safe_title) < 3:
                safe_title = hashlib.md5(title.encode('utf-8')).hexdigest()[:8]

        except Exception:
            # 出错时使用 hash
            safe_title = hashlib.md5(title.encode('utf-8')).hexdigest()[:8]

        filename = f"{memory_type}_{safe_title}.md"
        return self.memory_dir / filename

    def save_memory(
        self,
        memory_type: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        保存记忆

        Args:
            memory_type: 记忆类型
            title: 记忆标题
            content: 记忆内容
            metadata: 可选元数据

        Returns:
            是否保存成功
        """
        if memory_type not in MEMORY_TYPES:
            logger.warning(f"Unknown memory type: {memory_type}")
            return False

        try:
            memory = Memory(
                memory_type=memory_type,
                title=title,
                content=content,
                metadata=metadata
            )

            # 保存记忆文件
            memory_path = self._get_memory_path(memory_type, title)
            with open(memory_path, "w", encoding="utf-8") as f:
                # 写入 frontmatter
                f.write(f"---\n")
                f.write(f"name: {title}\n")
                f.write(f"description: {content[:100]}...\n")
                f.write(f"type: {memory_type}\n")
                f.write(f"created_at: {memory.created_at}\n")
                f.write(f"updated_at: {memory.updated_at}\n")
                if metadata:
                    f.write(f"metadata: {json.dumps(metadata, ensure_ascii=False)}\n")
                f.write(f"---\n\n")
                f.write(content)

            # 更新索引
            self._update_index(memory)

            logger.info(f"Saved memory: {memory_type}/{title}")
            return True

        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            return False

    def load_memory(self, memory_type: str, title: str) -> Optional[Memory]:
        """
        加载记忆

        Args:
            memory_type: 记忆类型
            title: 记忆标题

        Returns:
            记忆对象,不存在则返回 None
        """
        memory_path = self._get_memory_path(memory_type, title)
        if not memory_path.exists():
            return None

        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析 frontmatter (简化版)
            lines = content.split("\n")
            metadata = {}
            body_start = 0

            in_frontmatter = False
            for i, line in enumerate(lines):
                if line.strip() == "---":
                    if not in_frontmatter:
                        in_frontmatter = True
                    else:
                        body_start = i + 1
                        break
                elif in_frontmatter and ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()

            # 提取正文
            body = "\n".join(lines[body_start:]).strip()

            return Memory(
                memory_type=metadata.get("type", memory_type),
                title=metadata.get("name", title),
                content=body,
                metadata=metadata.get("metadata"),
                created_at=metadata.get("created_at"),
                updated_at=metadata.get("updated_at")
            )

        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
            return None

    def delete_memory(self, memory_type: str, title: str) -> bool:
        """
        删除记忆

        Args:
            memory_type: 记忆类型
            title: 记忆标题

        Returns:
            是否删除成功
        """
        memory_path = self._get_memory_path(memory_type, title)
        if not memory_path.exists():
            return False

        try:
            memory_path.unlink()
            self._update_index()  # 重建索引
            logger.info(f"Deleted memory: {memory_type}/{title}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    def list_memories(
        self,
        memory_type: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        列出所有记忆

        Args:
            memory_type: 可选,过滤特定类型

        Returns:
            记忆列表,每个包含 type, title, description
        """
        memories = []

        try:
            for memory_file in self.memory_dir.glob("*.md"):
                if memory_file.name == "MEMORY.md":
                    continue

                # 解析文件名
                parts = memory_file.stem.split("_", 1)
                if len(parts) != 2:
                    continue

                mem_type, _ = parts

                if memory_type and mem_type != memory_type:
                    continue

                # 读取完整记忆以获取正确信息
                try:
                    with open(memory_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    # 从 frontmatter 提取信息
                    title = None
                    description = ""
                    for line in content.split("\n"):
                        line = line.strip()
                        if line.startswith("name:"):
                            title = line.split(":", 1)[1].strip()
                        elif line.startswith("description:"):
                            description = line.split(":", 1)[1].strip()
                        elif title and description:
                            break

                    # 如果没有找到标题,使用文件名
                    if not title:
                        title = parts[1].replace("_", " ")

                    memories.append({
                        "type": mem_type,
                        "title": title,
                        "description": description,
                        "file": str(memory_file.relative_to(self.project_root))
                    })

                except Exception as e:
                    logger.warning(f"Failed to read memory file {memory_file}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to list memories: {e}")

        return memories

    def search_memories(self, query: str) -> List[Dict[str, str]]:
        """
        搜索记忆

        Args:
            query: 搜索关键词

        Returns:
            匹配的记忆列表
        """
        results = []
        query_lower = query.lower()

        for memory in self.list_memories():
            # 加载完整记忆
            mem = self.load_memory(memory["type"], memory["title"])
            if mem:
                # 搜索标题和内容
                if (query_lower in mem.title.lower() or
                    query_lower in mem.content.lower()):
                    results.append(memory)

        return results

    def get_relevant_memories(
        self,
        context: str,
        max_results: int = 5
    ) -> List[Memory]:
        """
        根据上下文获取相关记忆

        Args:
            context: 当前上下文
            max_results: 最大返回数量

        Returns:
            相关记忆列表
        """
        import re

        # 提取上下文中的关键词
        # 匹配英文单词(字母数字,长度>=2)和中文字符
        context_lower = context.lower()
        english_words = set(re.findall(r'[a-z0-9]{2,}', context_lower))
        # 提取所有连续的中文字符
        chinese_chars = set(re.findall(r'[\u4e00-\u9fff]+', context))

        context_words = english_words | set(chinese_chars)  # 合并英文和中文

        scored_memories = []

        for memory_info in self.list_memories():
            mem = self.load_memory(memory_info["type"], memory_info["title"])
            if not mem:
                continue

            # 计算相关性分数
            score = 0

            # 检查标题中的关键词匹配
            title_lower = mem.title.lower()
            title_english = set(re.findall(r'[a-z0-9]{2,}', title_lower))
            title_chinese = set(re.findall(r'[\u4e00-\u9fff]+', title_lower))
            title_words = title_english | set(title_chinese)

            # 标题关键词匹配权重高
            matched_title_words = context_words & title_words
            score += len(matched_title_words) * 5

            # 检查内容中的关键词匹配
            content_lower = mem.content.lower()
            content_english = set(re.findall(r'[a-z0-9]{2,}', content_lower))
            content_chinese = set(re.findall(r'[\u4e00-\u9fff]+', content_lower))
            content_words = content_english | set(content_chinese)

            matched_content_words = context_words & content_words
            score += len(matched_content_words)

            if score > 0:
                scored_memories.append((score, mem))

        # 按分数排序
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # 返回前 N 个
        return [mem for score, mem in scored_memories[:max_results]]

    def _update_index(self, new_memory: Optional[Memory] = None):
        """
        更新 MEMORY.md 索引文件

        Args:
            new_memory: 新添加的记忆(可选)
        """
        try:
            # 按类型组织记忆
            by_type: Dict[str, List[Dict]] = {t: [] for t in MEMORY_TYPES}

            for memory_info in self.list_memories():
                mem_type = memory_info["type"]
                if mem_type in by_type:
                    # 创建简短描述
                    desc = memory_info.get("description", "")
                    if len(desc) > 150:
                        desc = desc[:147] + "..."

                    by_type[mem_type].append({
                        "title": memory_info["title"],
                        "description": desc,
                        "file": memory_info["file"]
                    })

            # 写入索引文件
            with open(self.memory_index_path, "w", encoding="utf-8") as f:
                f.write("# 记忆索引\n\n")
                f.write("此文件由 MemoryManager 自动维护,包含所有记忆的索引。\n\n")
                f.write("---\n\n")

                for mem_type, memories in by_type.items():
                    if not memories:
                        continue

                    type_info = MEMORY_TYPES[mem_type]
                    f.write(f"## {mem_type.capitalize()} - {type_info['description']}\n\n")
                    f.write(f"{type_info['when_to_save']}\n\n")

                    for mem in memories:
                        file_name = Path(mem["file"]).stem
                        f.write(f"- [{mem['title']}]({file_name}.md) — {mem['description']}\n")

                    f.write("\n")

        except Exception as e:
            logger.error(f"Failed to update memory index: {e}")

    def get_memory_summary(self) -> str:
        """
        获取记忆系统摘要

        Returns:
            摘要文本
        """
        memories = self.list_memories()
        if not memories:
            return "暂无记忆"

        lines = ["# 记忆摘要\n\n"]

        # 按类型分组
        by_type: Dict[str, List[Dict]] = {t: [] for t in MEMORY_TYPES}
        for mem in memories:
            by_type[mem["type"]].append(mem)

        for mem_type, type_memories in by_type.items():
            if not type_memories:
                continue

            type_info = MEMORY_TYPES[mem_type]
            lines.append(f"## {mem_type.capitalize()} ({len(type_memories)})\n")
            lines.append(f"{type_info['description']}\n\n")

            for mem in type_memories[:10]:  # 每种类型最多显示 10 个
                lines.append(f"- **{mem['title']}**: {mem.get('description', '')[:80]}...\n")

            if len(type_memories) > 10:
                lines.append(f"  ... 还有 {len(type_memories) - 10} 个\n")

            lines.append("\n")

        return "".join(lines)

    def export_memories(self, output_path: str) -> bool:
        """
        导出所有记忆

        Args:
            output_path: 输出文件路径

        Returns:
            是否成功
        """
        try:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            with open(output, "w", encoding="utf-8") as f:
                f.write(self.get_memory_summary())
                f.write("\n---\n\n")
                f.write("# 详细内容\n\n")

                for memory_info in self.list_memories():
                    mem = self.load_memory(memory_info["type"], memory_info["title"])
                    if mem:
                        f.write(f"## {mem.title}\n\n")
                        f.write(f"**类型**: {mem.memory_type}\n")
                        f.write(f"**创建时间**: {mem.created_at}\n")
                        f.write(f"**更新时间**: {mem.updated_at}\n\n")
                        f.write(mem.content)
                        f.write("\n\n---\n\n")

            logger.info(f"Exported memories to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export memories: {e}")
            return False


# 全局记忆管理器实例
_global_memory_manager: Optional[MemoryManager] = None


def get_memory_manager(project_root: str = ".") -> MemoryManager:
    """
    获取全局记忆管理器实例

    Args:
        project_root: 项目根目录

    Returns:
        MemoryManager 实例
    """
    global _global_memory_manager

    if _global_memory_manager is None:
        _global_memory_manager = MemoryManager(project_root)

    return _global_memory_manager
