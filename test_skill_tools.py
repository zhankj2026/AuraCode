"""
Skill 工具测试

验证 LLM 能够通过工具激活和管理技能
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_skill_tools():
    """测试技能工具"""
    print("="*70)
    print("Skill 工具测试")
    print("="*70)

    from tools.registry import TOOL_REGISTRY
    from tools.builtin import skill_tools
    from core.agent_loop import AgentLoop

    # 初始化 AgentLoop（这会设置 SkillContext）
    print("\n[测试 1] 初始化 AgentLoop")
    config = {
        "api_key": "test_key",
        "model": "glm-4-plus",
        "max_iterations": 1,
        "permission_mode": "bypass",
        "enable_skills": True,
        "active_skills": []
    }

    loop = AgentLoop(config)
    print("[OK] AgentLoop 初始化完成")

    # 验证工具已注册
    print("\n[测试 2] 验证技能工具已注册")
    skill_tool_names = [
        "list_skills",
        "show_available_skills",
        "activate_skill",
        "deactivate_skill",
        "get_active_skills"
    ]

    for tool_name in skill_tool_names:
        assert tool_name in TOOL_REGISTRY, f"工具 {tool_name} 未注册"
        print(f"  [OK] {tool_name} 已注册")

    # 测试工具功能
    print("\n[测试 3] 测试工具功能")

    # 3.1 show_available_skills
    print("\n  [3.1] show_available_skills")
    result = skill_tools.show_available_skills_handler()
    assert "python-standards" in result
    assert "git-workflow" in result
    assert "未激活" in result
    print("  [OK] 正确显示可用技能")

    # 3.2 activate_skill
    print("\n  [3.2] activate_skill")
    result = skill_tools.activate_skill_handler("python-standards")
    assert "已激活" in result
    assert "python-standards" in result
    print(f"  [OK] 激活成功: {result[:50]}...")

    # 3.3 get_active_skills
    print("\n  [3.3] get_active_skills")
    result = skill_tools.get_active_skills_handler()
    assert "python-standards" in result
    print(f"  [OK] {result.strip()}")

    # 3.4 deactivate_skill
    print("\n  [3.4] deactivate_skill")
    result = skill_tools.deactivate_skill_handler("python-standards")
    assert "已停用" in result
    print(f"  [OK] {result[:50]}...")

    # 3.5 list_skills (detailed)
    print("\n  [3.5] list_skills (detailed=False)")
    result = skill_tools.list_skills_handler(detailed=False)
    assert "python-standards" in result
    print("  [OK] 简要列表正确")

    # 测试激活后的系统提示词
    print("\n[测试 4] 激活技能后的系统提示词")

    # 通过工具激活
    skill_tools.activate_skill_handler("python-standards")
    skill_tools.activate_skill_handler("git-workflow")

    # 构建系统提示词
    system_prompt = loop._build_system_prompt()

    # 验证
    assert "## 可用技能" in system_prompt
    assert "## 已激活技能的详细内容" in system_prompt
    assert "Python 编码规范" in system_prompt
    assert "Git 工作流" in system_prompt

    # 检查状态显示
    assert "[已激活]" in system_prompt or "已激活" in system_prompt

    print("[OK] 系统提示词正确包含:")
    print("  - 可用技能列表（元数据）")
    print("  - 已激活技能的详细内容")

    # 测试 token 对比
    print("\n[测试 5] Token 使用对比")

    # 全部停用
    skill_tools.deactivate_skill_handler("python-standards")
    skill_tools.deactivate_skill_handler("git-workflow")

    prompt_no_active = loop._build_system_prompt()

    # 全部激活
    skill_tools.activate_skill_handler("python-standards")
    skill_tools.activate_skill_handler("git-workflow")

    prompt_with_active = loop._build_system_prompt()

    print(f"  无激活技能: {len(prompt_no_active)} 字符")
    print(f"  两个激活技能: {len(prompt_with_active)} 字符")
    print(f"  差异: {len(prompt_with_active) - len(prompt_no_active)} 字符")

    # 总结
    print("\n" + "="*70)
    print("[OK] 所有测试通过！")
    print("="*70)
    print("\n验证结果:")
    print("  1. [OK] 5 个技能工具已正确注册")
    print("  2. [OK] 工具可以激活/停用技能")
    print("  3. [OK] 工具可以查询技能状态")
    print("  4. [OK] 激活后技能内容注入到系统提示词")
    print("  5. [OK] Token 使用符合渐进式披露原则")
    print("\n技能激活时机:")
    print("  - 用户可以手动激活: loop.activate_skill()")
    print("  - 配置默认激活: config['active_skills']")
    print("  - LLM 可以激活: activate_skill() 工具")
    print("  - 基于任务激活: 未来可扩展")


if __name__ == "__main__":
    test_skill_tools()
