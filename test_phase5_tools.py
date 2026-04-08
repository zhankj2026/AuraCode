"""Phase 5 工具测试 - Skill 系统"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skills.loader import SkillManager, Skill

print("="*60)
print("Phase 5 工具测试 (Skill 系统)")
print("="*60)

# ========== 测试 Skill 管理器 ==========
print("\n" + "="*60)
print("测试 1: Skill 管理器")
print("="*60)

# 测试 1.1: 初始化
print("\n[测试 1.1] Skill 管理器初始化")
skill_manager = SkillManager()
print(f"Skill 目录: {skill_manager.skills_dir}")
assert os.path.exists(skill_manager.skills_dir)
print("✅ 管理器初始化成功")

# 测试 1.2: 加载 Skill
print("\n[测试 1.2] 加载 Skill 元数据")
print(f"加载的 Skill 数: {len(skill_manager.skills)}")
for name in skill_manager.skills:
    skill = skill_manager.skills[name]
    print(f"  - {skill.name}: {skill.description}")
assert len(skill_manager.skills) >= 2  # 至少有 2 个示例 Skill
print("✅ Skill 加载成功")

# 测试 1.3: 获取可用 Skill 列表
print("\n[测试 1.3] 获取可用 Skill 列表")
available = skill_manager.get_available_skills()
print(f"可用 Skill 数: {len(available)}")
for s in available:
    print(f"  • {s['name']}: {s['description']} (激活: {s['is_active']})")
assert len(available) >= 2
assert all('name' in s and 'description' in s for s in available)
print("✅ 列表获取成功")

# 测试 1.4: 激活 Skill
print("\n[测试 1.4] 激活 Skill")
prompt = skill_manager.activate_skill('python-standards')
print(f"激活 python-standards")
print(f"提示词长度: {len(prompt)} 字符")
assert len(prompt) > 100  # 应该有实际内容
assert skill_manager.is_skill_active('python-standards')
print("✅ Skill 激活成功")

# 测试 1.5: 重复激活
print("\n[测试 1.5] 重复激活同一 Skill")
prompt2 = skill_manager.activate_skill('python-standards')
assert prompt == prompt2  # 应该返回相同内容
print("✅ 重复激活正确处理")

# 测试 1.6: 激活多个 Skill
print("\n[测试 1.6] 激活多个 Skill")
prompt_git = skill_manager.activate_skill('git-workflow')
print(f"激活 git-workflow")
print(f"提示词长度: {len(prompt_git)} 字符")
assert skill_manager.is_skill_active('git-workflow')
print("✅ 多 Skill 激活成功")

# 测试 1.7: 获取已激活 Skill
print("\n[测试 1.7] 获取已激活 Skill 列表")
active = skill_manager.get_active_skills()
print(f"已激活: {active}")
assert 'python-standards' in active
assert 'git-workflow' in active
assert len(active) == 2
print("✅ 激活列表正确")

# 测试 1.8: 获取所有激活提示词
print("\n[测试 1.8] 获取所有激活提示词")
all_prompts = skill_manager.get_active_prompts()
print(f"合并提示词长度: {len(all_prompts)} 字符")
assert 'Python 编码规范' in all_prompts
assert 'Git 工作流规范' in all_prompts
print("✅ 合并提示词正确")

# 测试 1.9: 停用 Skill
print("\n[测试 1.9] 停用 Skill")
success = skill_manager.deactivate_skill('git-workflow')
assert success == True
assert not skill_manager.is_skill_active('git-workflow')
active = skill_manager.get_active_skills()
assert 'git-workflow' not in active
print("✅ Skill 停用成功")

# 测试 1.10: 停用未激活的 Skill
print("\n[测试 1.10] 停用未激活的 Skill")
success = skill_manager.deactivate_skill('non-existent')
assert success == False
print("✅ 未激活 Skill 处理正确")

# 测试 1.11: 列显 Skill
print("\n[测试 1.11] 列出 Skill")
skill_list = skill_manager.list_skills()
print(skill_list)
assert 'python-standards' in skill_list
assert 'git-workflow' in skill_list
print("✅ Skill 列表正确")

# 测试 1.12: 获取 Skill 信息
print("\n[测试 1.12] 获取 Skill 详细信息")
info = skill_manager.get_skill_info('python-standards')
print(f"Skill 信息: {info}")
assert info is not None
assert info['name'] == 'python-standards'
assert 'prompt_length' in info  # 已激活的应该有长度
print("✅ Skill 信息正确")

# 测试 1.13: 获取不存在的 Skill
print("\n[测试 1.13] 获取不存在的 Skill")
info = skill_manager.get_skill_info('non-existent')
assert info is None
print("✅ 不存在 Skill 处理正确")

# 测试 1.14: 激活不存在的 Skill
print("\n[测试 1.14] 激活不存在的 Skill")
try:
    skill_manager.activate_skill('non-existent')
    assert False, "应该抛出异常"
except ValueError as e:
    print(f"正确抛出异常: {e}")
    assert '不存在' in str(e)
print("✅ 异常处理正确")

# 测试 1.15: 渐进式披露验证
print("\n[测试 1.15] 验证渐进式披露")
# 创建新管理器
skill_manager2 = SkillManager()

# 初始状态:所有 Skill 未激活
for skill in skill_manager2.skills.values():
    assert not skill.is_active
    assert skill.prompt_content is None

print("初始状态: 所有 Skill 未激活,prompt_content 为 None")

# 获取可用列表(轻量操作)
available = skill_manager2.get_available_skills()
print(f"获取列表: {len(available)} 个 Skill")

# 验证仍未加载 prompt_content
for skill in skill_manager2.skills.values():
    assert skill.prompt_content is None

print("✅ 渐进式披露验证通过: 列表查询不加载完整内容")

# ========== 总结 ==========
print("\n" + "="*60)
print("✅ 所有 Phase 5 测试通过!")
print("="*60)
print("\nPhase 5 完成功能:")
print("  1. Skill 管理器 (334行)")
print("     - 加载和管理 Skill 元数据")
print("     - 渐进式披露: 按需加载提示词")
print("     - 激活/停用 Skill")
print("     - 合并多个激活的提示词")
print("  2. 示例 Skill (2个)")
print("     - python-standards: Python 编码规范 (240行)")
print("     - git-workflow: Git 工作流规范 (202行)")
print("\n设计理念:")
print("  • 启动时只加载元数据(名称、描述)")
print("  • 激活后才加载完整提示词")
print("  • 节省 token,按需注入")
