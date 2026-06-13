"""
Skill 管理器 - 领域知识注入系统

基于 code.md Phase 5 实现
参考: 第 6.3 节
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """
    Skill 数据结构
    
    Attributes:
        name: Skill 名称
        description: Skill 描述
        trigger: 触发条件描述
        prompt_content: 完整提示词内容(激活后加载)
        is_active: 是否已激活
    """
    name: str
    description: str
    trigger: str
    prompt_content: Optional[str] = None
    is_active: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'description': self.description,
            'trigger': self.trigger,
            'is_active': self.is_active
        }


class SkillManager:
    """
    Skill 管理器
    
    设计理念: 渐进式披露
    - 启动时只加载 Skill 元数据(名称、描述)
    - 激活后才加载完整提示词内容
    - 节省 token,按需注入
    
    增强功能:
    - 用户自定义 Skill 创建/删除
    - 多源自动发现 (builtin + 项目级 .opencode/skills/ + 用户级 ~/.opencode/skills/)
    - 元数据索引与搜索
    """
    
    def __init__(self, skills_dir: str = None, project_root: str = "."):
        """
        初始化 Skill 管理器
        
        Args:
            skills_dir: 内置 Skill 目录路径,默认为 skills/
            project_root: 项目根目录（用于查找项目级自定义 Skill）
        """
        if skills_dir is None:
            # 默认为 opencode/skills/
            skills_dir = os.path.join(os.path.dirname(__file__), '..', 'skills')
        
        self.builtin_skills_dir = os.path.abspath(skills_dir)
        self.project_root = os.path.abspath(project_root)
        
        # 用户自定义 Skill 目录
        self.project_skills_dir = os.path.join(self.project_root, '.opencode', 'skills')
        self.user_skills_dir = os.path.join(os.path.expanduser('~'), '.opencode', 'skills')
        
        self.skills: Dict[str, Skill] = {}
        self.active_skills: List[str] = []
        self._skill_sources: Dict[str, str] = {}  # name -> source_dir 映射
        
        # 加载所有 Skill 元数据（多源）
        self._load_all_skills()
    
    def _parse_frontmatter(self, content: str) -> Dict[str, str]:
        """
        解析 YAML frontmatter
        
        Args:
            content: 文件内容
        
        Returns:
            元数据字典
        """
        metadata = {}
        
        # 匹配 frontmatter: --- ... ---
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
        
        if match:
            frontmatter = match.group(1)
            # 解析 YAML 键值对
            for line in frontmatter.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()
        
        return metadata
    
    def _load_all_skills(self):
        """加载所有 Skill 元数据（多源: 内置 + 项目级 + 用户级）"""
        total = 0
        # 1. 内置 skills
        total += self._load_skills_from_dir(self.builtin_skills_dir, 'builtin')
        # 2. 项目级自定义 skills
        total += self._load_skills_from_dir(self.project_skills_dir, 'project')
        # 3. 用户级自定义 skills
        total += self._load_skills_from_dir(self.user_skills_dir, 'user')
        logger.info(f"成功加载 {total} 个 Skill (builtin + project + user)")

    def _load_skills_from_dir(self, skills_dir: str, source: str) -> int:
        """从指定目录加载 Skill"""
        if not os.path.exists(skills_dir):
            logger.debug(f"Skill 目录不存在: {skills_dir}")
            return 0

        skill_count = 0

        for skill_name in os.listdir(skills_dir):
            if skill_name.startswith('__'):
                continue

            skill_path = os.path.join(skills_dir, skill_name)
            if not os.path.isdir(skill_path):
                continue

            skill_md = os.path.join(skill_path, 'SKILL.md')
            if not os.path.exists(skill_md):
                logger.debug(f"Skill {skill_name} 缺少 SKILL.md，跳过")
                continue

            try:
                with open(skill_md, 'r', encoding='utf-8') as f:
                    content = f.read()

                metadata = self._parse_frontmatter(content)

                if 'name' not in metadata:
                    metadata['name'] = skill_name
                if 'description' not in metadata:
                    metadata['description'] = '无描述'
                if 'trigger' not in metadata:
                    metadata['trigger'] = '手动激活'

                skill = Skill(
                    name=metadata['name'],
                    description=metadata['description'],
                    trigger=metadata['trigger']
                )

                # 避免重复（内置优先）
                if skill_name not in self.skills:
                    self.skills[skill_name] = skill
                    self._skill_sources[skill_name] = source
                    skill_count += 1
                    logger.info(f"加载 Skill [{source}]: {skill.name} - {skill.description}")

            except Exception as e:
                logger.error(f"加载 Skill {skill_name} 失败: {e}")

        return skill_count
    
    def get_available_skills(self) -> List[Dict[str, str]]:
        """
        获取可用 Skill 列表(轻量,只返回元数据)
        
        Returns:
            Skill 元数据列表
        """
        return [
            skill.to_dict()
            for skill in self.skills.values()
        ]
    
    def activate_skill(self, name: str) -> str:
        """
        激活 Skill,加载完整提示词
        
        Args:
            name: Skill 名称
        
        Returns:
            完整提示词内容
        
        Raises:
            ValueError: 如果 Skill 不存在
        """
        # 查找 Skill
        skill = None
        for s in self.skills.values():
            if s.name == name:
                skill = s
                break
        
        if not skill:
            raise ValueError(f"Skill 不存在: {name}")
        
        # 如果已激活,直接返回
        if skill.is_active and skill.prompt_content:
            return skill.prompt_content
        
        # 根据来源查找目录
        source = self._skill_sources.get(name, 'builtin')
        if source == 'project':
            skill_dir = os.path.join(self.project_skills_dir, name)
        elif source == 'user':
            skill_dir = os.path.join(self.user_skills_dir, name)
        else:
            skill_dir = os.path.join(self.builtin_skills_dir, name)

        # 加载 prompt.md
        prompt_file = os.path.join(skill_dir, 'prompt.md')
        
        if not os.path.exists(prompt_file):
            # 尝试从 SKILL.md 提取正文
            skill_md = os.path.join(skill_dir, 'SKILL.md')
            if os.path.exists(skill_md):
                with open(skill_md, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 去掉 frontmatter,保留正文
                    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
                    if match:
                        skill.prompt_content = match.group(2).strip()
                    else:
                        skill.prompt_content = content
            else:
                raise ValueError(f"Skill {name} 缺少 prompt.md 或 SKILL.md")
        else:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                skill.prompt_content = f.read()
        
        # 标记为已激活
        skill.is_active = True
        if name not in self.active_skills:
            self.active_skills.append(name)
        
        logger.info(f"激活 Skill: {skill.name}")
        
        return skill.prompt_content
    
    def deactivate_skill(self, name: str) -> bool:
        """
        停用 Skill
        
        Args:
            name: Skill 名称
        
        Returns:
            True 如果成功停用,False 否则
        """
        if name in self.active_skills:
            self.active_skills.remove(name)
            
            if name in self.skills:
                self.skills[name].is_active = False
                # 可选:释放 prompt_content 以节省内存
                # self.skills[name].prompt_content = None
            
            logger.info(f"停用 Skill: {name}")
            return True
        
        return False
    
    def get_active_skills(self) -> List[str]:
        """
        获取已激活的 Skill 列表
        
        Returns:
            已激活的 Skill 名称列表
        """
        return self.active_skills.copy()
    
    def get_active_prompts(self) -> str:
        """
        获取所有已激活 Skill 的提示词
        
        Returns:
            合并后的提示词
        """
        prompts = []
        
        for name in self.active_skills:
            if name in self.skills and self.skills[name].prompt_content:
                prompts.append(f"# Skill: {self.skills[name].name}\n")
                prompts.append(self.skills[name].prompt_content)
                prompts.append("")
        
        return "\n\n".join(prompts)
    
    def is_skill_active(self, name: str) -> bool:
        """
        检查 Skill 是否已激活
        
        Args:
            name: Skill 名称
        
        Returns:
            True 如果已激活,False 否则
        """
        return name in self.active_skills
    
    def list_skills(self, detailed: bool = False) -> str:
        """
        列出所有 Skill
        
        Args:
            detailed: 是否显示详细信息
        
        Returns:
            格式化的 Skill 列表
        """
        if not self.skills:
            return "没有可用的 Skill"
        
        lines = [f"可用 Skill (共 {len(self.skills)} 个):", ""]
        
        # 按来源分组
        by_source = {'builtin': [], 'project': [], 'user': []}
        for name, skill in self.skills.items():
            src = self._skill_sources.get(name, 'builtin')
            by_source.setdefault(src, []).append((name, skill))

        source_labels = {
            'builtin': '📦 内置',
            'project': '📁 项目级',
            'user': '👤 用户级',
        }
        for src in ['builtin', 'project', 'user']:
            skills_list = by_source.get(src, [])
            if not skills_list:
                continue
            lines.append(f"  {source_labels.get(src, src)} ({len(skills_list)} 个):")
            for name, skill in skills_list:
                status = "✅" if skill.is_active else "⏸️"
                lines.append(f"    {status} {skill.name}")
                lines.append(f"      描述: {skill.description}")
                lines.append(f"      触发: {skill.trigger}")
                if detailed and skill.prompt_content:
                    preview = skill.prompt_content[:100]
                    lines.append(f"      预览: {preview}...")
                lines.append("")
        
        return "\n".join(lines)
    
    def get_skill_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取 Skill 详细信息
        
        Args:
            name: Skill 名称
        
        Returns:
            Skill 信息字典,如果不存在返回 None
        """
        if name not in self.skills:
            return None
        
        skill = self.skills[name]
        info = skill.to_dict()
        info['source'] = self._skill_sources.get(name, 'builtin')
        
        if skill.is_active:
            info['prompt_length'] = len(skill.prompt_content) if skill.prompt_content else 0
        
        return info

    # ========== 用户自定义 Skill 管理 ==========

    def create_skill(
        self,
        name: str,
        description: str,
        trigger: str,
        prompt_content: str,
        scope: str = "project",
    ) -> str:
        """
        创建用户自定义 Skill

        Args:
            name: Skill 名称（目录名）
            description: 描述
            trigger: 触发条件
            prompt_content: 提示词内容
            scope: 'project' (项目级) 或 'user' (用户级)

        Returns:
            创建结果信息
        """
        if scope == "project":
            base_dir = self.project_skills_dir
        elif scope == "user":
            base_dir = self.user_skills_dir
        else:
            return f"❌ 无效作用域: {scope}，可选: project/user"

        skill_dir = os.path.join(base_dir, name)
        if os.path.exists(skill_dir):
            return f"⚠️ Skill 已存在: {name} ({skill_dir})"

        try:
            os.makedirs(skill_dir, exist_ok=True)

            # 写入 SKILL.md
            skill_md = os.path.join(skill_dir, 'SKILL.md')
            with open(skill_md, 'w', encoding='utf-8') as f:
                f.write("---\n")
                f.write(f"name: {name}\n")
                f.write(f"description: {description}\n")
                f.write(f"trigger: {trigger}\n")
                f.write("---\n\n")
                f.write(f"# {name}\n\n")
                f.write(description)

            # 写入 prompt.md
            prompt_file = os.path.join(skill_dir, 'prompt.md')
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt_content)

            # 注册到内存
            skill = Skill(
                name=name,
                description=description,
                trigger=trigger,
                prompt_content=prompt_content,
            )
            self.skills[name] = skill
            self._skill_sources[name] = scope

            return f"✅ Skill 已创建: {name} ({skill_dir})"

        except Exception as e:
            logger.error(f"创建 Skill 失败: {e}")
            return f"❌ 创建失败: {e}"

    def delete_skill(self, name: str) -> str:
        """删除用户自定义 Skill（不能删除内置 Skill）"""
        source = self._skill_sources.get(name, 'builtin')
        if source == 'builtin':
            return f"❌ 不能删除内置 Skill: {name}"

        if source == 'project':
            skill_dir = os.path.join(self.project_skills_dir, name)
        else:
            skill_dir = os.path.join(self.user_skills_dir, name)

        if not os.path.exists(skill_dir):
            return f"❌ Skill 目录不存在: {skill_dir}"

        try:
            import shutil
            shutil.rmtree(skill_dir)
            # 从内存移除
            self.deactivate_skill(name)
            self.skills.pop(name, None)
            self._skill_sources.pop(name, None)
            return f"🗑️ Skill 已删除: {name}"
        except Exception as e:
            return f"❌ 删除失败: {e}"

    def search_skills(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索 Skill（名称+描述+触发条件）"""
        keyword_lower = keyword.lower()
        results = []
        for name, skill in self.skills.items():
            if (keyword_lower in name.lower() or
                keyword_lower in skill.description.lower() or
                keyword_lower in skill.trigger.lower()):
                info = skill.to_dict()
                info['source'] = self._skill_sources.get(name, 'builtin')
                results.append(info)
        return results

    def list_by_source(self, source: str = None) -> List[Dict[str, Any]]:
        """按来源列出 Skill"""
        results = []
        for name, skill in self.skills.items():
            src = self._skill_sources.get(name, 'builtin')
            if source and src != source:
                continue
            info = skill.to_dict()
            info['source'] = src
            results.append(info)
        return results

    def reload_skills(self) -> int:
        """重新加载所有 Skill"""
        self.skills.clear()
        self._skill_sources.clear()
        self.active_skills.clear()
        self._load_all_skills()
        return len(self.skills)
