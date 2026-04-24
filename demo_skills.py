"""
Skill 系统渐进式披露演示

展示正确的 Skill 使用流程：
1. 初始化时只加载元数据（轻量）
2. 需要时激活技能（加载完整内容）
3. 激活的技能注入到系统提示词
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent_loop import AgentLoop


def demo_progressive_disclosure():
    """演示渐进式披露"""
    print("="*70)
    print("Skill 系统渐进式披露演示")
    print("="*70)

    # ========== 第 1 步: 初始化（只加载元数据） ==========
    print("\n[第 1 步] 初始化 AgentLoop")
    print("-" * 70)

    config = {
        "api_key": "test_key",
        "model": "glm-4-plus",
        "max_iterations": 1,
        "permission_mode": "bypass",
        "enable_skills": True,
        # 可以在配置中指定默认激活的技能
        "active_skills": []  # 初始不激活任何技能
    }

    loop = AgentLoop(config)

    # 验证：此时只加载了元数据，没有加载完整内容
    print("\n验证渐进式披露:")
    for skill_name, skill in loop.skill_manager.skills.items():
        is_active = skill.is_active
        has_content = skill.prompt_content is not None
        print(f"  {skill.name}:")
        print(f"    - 已激活: {is_active}")
        print(f"    - 已加载内容: {has_content}")
        assert not has_content, "初始化时不应加载完整内容！"

    print("\n[OK] 初始化完成，只加载了元数据，未加载任何完整内容")

    # ========== 第 2 步: 查看可用技能（轻量操作） ==========
    print("\n[第 2 步] 查看可用技能（轻量操作）")
    print("-" * 70)

    available = loop.skill_manager.get_available_skills()
    print(f"可用技能数量: {len(available)}")
    print("\n技能列表:")
    for skill_info in available:
        print(f"  - {skill_info['name']}: {skill_info['description']}")
        print(f"    触发条件: {skill_info['trigger']}")

    # 验证：仍然没有加载完整内容
    for skill_name, skill in loop.skill_manager.skills.items():
        assert skill.prompt_content is None, "查看列表不应加载完整内容！"

    print("\n[OK] 列表查询完成，仍未加载完整内容")

    # ========== 第 3 步: 激活技能（按需加载） ==========
    print("\n[第 3 步] 激活技能（按需加载完整内容）")
    print("-" * 70)

    # 激活第一个技能
    skill_name = "python-standards"
    print(f"\n激活技能: {skill_name}")

    before_content_len = 0
    if loop.skill_manager.skills[skill_name].prompt_content:
        before_content_len = len(loop.skill_manager.skills[skill_name].prompt_content)

    # 激活
    loop.activate_skill(skill_name)

    after_content_len = len(loop.skill_manager.skills[skill_name].prompt_content)

    print(f"  激活前内容长度: {before_content_len}")
    print(f"  激活后内容长度: {after_content_len}")
    print(f"  [OK] 技能 '{skill_name}' 已激活，完整内容已加载")

    # 激活第二个技能
    skill_name2 = "git-workflow"
    print(f"\n激活技能: {skill_name2}")
    loop.activate_skill(skill_name2)
    print(f"  [OK] 技能 '{skill_name2}' 已激活")

    # ========== 第 4 步: 构建系统提示词（注入激活的技能） ==========
    print("\n[第 4 步] 构建系统提示词")
    print("-" * 70)

    system_prompt = loop._build_system_prompt()

    # 检查激活的技能是否在系统提示词中
    active_skills = loop.skill_manager.get_active_skills()
    print(f"\n已激活的技能: {active_skills}")

    for skill_name in active_skills:
        skill = loop.skill_manager.skills[skill_name]
        if skill.prompt_content:
            # 检查是否在系统提示词中
            if skill_name == "python-standards":
                assert "Python 编码规范" in system_prompt
                print(f"  [OK] {skill_name} 的提示词已注入到系统提示词")
            elif skill_name == "git-workflow":
                assert "Git 工作流" in system_prompt
                print(f"  [OK] {skill_name} 的提示词已注入到系统提示词")

    # 显示系统提示词中技能部分的内容
    if "## 激活的技能" in system_prompt:
        skill_section = system_prompt.split("## 激活的技能")[1].split("##")[0]
        print(f"\n系统提示词中的技能部分:")
        print(skill_section[:200] + "...")

    # ========== 第 5 步: 停用技能 ==========
    print("\n[第 5 步] 停用技能")
    print("-" * 70)

    loop.deactivate_skill("git-workflow")
    remaining_active = loop.list_active_skills()
    print(f"停用后激活的技能: {remaining_active}")
    assert "git-workflow" not in remaining_active
    print("[OK] 技能停用成功")

    # ========== 总结 ==========
    print("\n" + "="*70)
    print("渐进式披露验证完成")
    print("="*70)
    print("\n设计原则:")
    print("  1. 初始化时只加载元数据（名称、描述）")
    print("  2. 查询可用技能时不加载完整内容")
    print("  3. 激活时才加载完整的提示词内容")
    print("  4. 只有激活的技能才注入到系统提示词")
    print("\n优势:")
    print("  - 节省初始化时间和内存")
    print("  - 减少 token 使用（只加载需要的技能）")
    print("  - 按需注入，灵活控制 AI 行为")


def demo_config_with_active_skills():
    """演示在配置中指定默认激活的技能"""
    print("\n\n" + "="*70)
    print("演示 2: 在配置中指定默认激活的技能")
    print("="*70)

    config = {
        "api_key": "test_key",
        "model": "glm-4-plus",
        "max_iterations": 1,
        "permission_mode": "bypass",
        "enable_skills": True,
        # 在配置中指定默认激活的技能
        "active_skills": ["python-standards", "git-workflow"]
    }

    print("\n配置中指定激活的技能:")
    print(f"  active_skills = {config['active_skills']}")

    loop = AgentLoop(config)

    # 验证技能已自动激活
    active = loop.list_active_skills()
    print(f"\n初始化后自动激活的技能: {active}")

    assert "python-standards" in active
    assert "git-workflow" in active

    for skill_name in active:
        skill = loop.skill_manager.skills[skill_name]
        assert skill.is_active
        assert skill.prompt_content is not None
        print(f"  [OK] {skill_name}: 已激活，内容已加载 ({len(skill.prompt_content)} 字符)")

    print("\n[OK] 配置中的技能已自动激活")


if __name__ == "__main__":
    demo_progressive_disclosure()
    demo_config_with_active_skills()
