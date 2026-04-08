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
    """
    
    def __init__(self, skills_dir: str = None):
        """
        初始化 Skill 管理器
        
        Args:
            skills_dir: Skill 目录路径,默认为 skills/
        """
        if skills_dir is None:
            # 默认为 opencode/skills/
            skills_dir = os.path.join(os.path.dirname(__file__), '..', 'skills')
        
        self.skills_dir = os.path.abspath(skills_dir)
        self.skills: Dict[str, Skill] = {}
        self.active_skills: List[str] = []
        
        # 加载所有 Skill 元数据
        self._load_skills()
    
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
    
    def _load_skills(self):
        """加载所有 Skill 元数据"""
        if not os.path.exists(self.skills_dir):
            logger.warning(f"Skill 目录不存在: {self.skills_dir}")
            return
        
        skill_count = 0
        
        # 遍历 skills 目录
        for skill_name in os.listdir(self.skills_dir):
            skill_path = os.path.join(self.skills_dir, skill_name)
            
            # 只处理目录
            if not os.path.isdir(skill_path):
                continue
            
            # 查找 SKILL.md
            skill_md = os.path.join(skill_path, 'SKILL.md')
            if not os.path.exists(skill_md):
                logger.warning(f"Skill {skill_name} 缺少 SKILL.md")
                continue
            
            try:
                # 读取并解析 SKILL.md
                with open(skill_md, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                metadata = self._parse_frontmatter(content)
                
                # 验证必需字段
                if 'name' not in metadata:
                    metadata['name'] = skill_name
                if 'description' not in metadata:
                    metadata['description'] = '无描述'
                if 'trigger' not in metadata:
                    metadata['trigger'] = '手动激活'
                
                # 创建 Skill 对象
                skill = Skill(
                    name=metadata['name'],
                    description=metadata['description'],
                    trigger=metadata['trigger']
                )
                
                self.skills[skill_name] = skill
                skill_count += 1
                
                logger.info(f"加载 Skill: {skill.name} - {skill.description}")
                
            except Exception as e:
                logger.error(f"加载 Skill {skill_name} 失败: {e}")
        
        logger.info(f"成功加载 {skill_count} 个 Skill")
    
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
        
        # 加载 prompt.md
        skill_dir = os.path.join(self.skills_dir, name)
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
        
        for skill in self.skills.values():
            status = "✅ 已激活" if skill.is_active else "⏸️  未激活"
            lines.append(f"• {skill.name}")
            lines.append(f"  描述: {skill.description}")
            lines.append(f"  触发: {skill.trigger}")
            lines.append(f"  状态: {status}")
            
            if detailed and skill.prompt_content:
                preview = skill.prompt_content[:100]
                lines.append(f"  预览: {preview}...")
            
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
        
        if skill.is_active:
            info['prompt_length'] = len(skill.prompt_content) if skill.prompt_content else 0
        
        return info
