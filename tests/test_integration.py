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
Extension System Integration Test

Verify Hooks, Skills, Plugins are properly integrated into AgentLoop
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent_loop import AgentLoop


def test_integration():
    """Test extension system integration"""
    print("="*60)
    print("Extension System Integration Test")
    print("="*60)

    # 1. Initialize AgentLoop (without actually running)
    print("\n[Test 1] Initialize AgentLoop")
    config = {
        "api_key": "test_key",
        "model": "glm-4-plus",
        "max_iterations": 1,
        "permission_mode": "bypass",
        "enable_plugins": True,
        "enable_hooks": True,
        "enable_skills": True
    }

    loop = AgentLoop(config)
    print("[OK] AgentLoop initialized successfully")

    # 2. Check if extension systems are initialized
    print("\n[Test 2] Check extension systems")

    # Plugin system
    assert loop.plugin_loader is not None, "Plugin loader should exist"
    print(f"[OK] Plugin system initialized")

    # Hook system
    assert loop.hook_manager is not None, "Hook manager should exist"
    print(f"[OK] Hook system initialized")

    # Skill system
    assert loop.skill_manager is not None, "Skill manager should exist"
    print(f"[OK] Skill system initialized")

    # 3. Test skill system
    print("\n[Test 3] Test skill system")
    skills_list = loop.list_skills()
    # Don't print directly due to encoding issues
    assert "python-standards" in skills_list, "Should have python-standards skill"
    assert "git-workflow" in skills_list, "Should have git-workflow skill"
    print("[OK] Skill list retrieved successfully")
    print(f"     Found skills: python-standards, git-workflow")

    # Activate skill
    success = loop.activate_skill("python-standards")
    assert success, "Skill activation should succeed"
    active = loop.list_active_skills()
    assert "python-standards" in active, "python-standards should be in active list"
    print(f"[OK] Skill activated successfully: {active}")

    # 4. Test hook system
    print("\n[Test 4] Test hook system")
    hooks_list = loop.list_hooks()
    # Don't print directly due to encoding issues
    print("[OK] Hook list retrieved successfully")

    # Manually register hook
    def test_hook(**kwargs):
        from hooks.manager import HookResult
        return HookResult(allow=True)

    hook_id = loop.register_hook("PreToolUse", test_hook)
    assert hook_id >= 0, "Hook registration should succeed"
    print(f"[OK] Manual hook registration successful: ID={hook_id}")

    # 5. Test plugin system
    print("\n[Test 5] Test plugin system")
    plugins_list = loop.list_plugins()
    # Don't print directly due to encoding issues
    assert "auto-format" in plugins_list or "auto" in plugins_list.lower(), "Should have auto-format plugin"
    print("[OK] Plugin list retrieved successfully")
    print("     Found plugin: auto-format")

    # 6. Get system status
    print("\n[Test 6] Get system status")
    status = loop.get_system_status()
    print(f"Plugins: {status['plugins']['loaded']} loaded")
    print(f"Hooks: {status['hooks']['registered']} registered")
    print(f"Skills: {status['skills']['active']}/{status['skills']['total']} active")
    print(f"Tools: {status['tools']['total']} total")

    assert status['plugins']['loaded'] >= 1, "At least 1 plugin should be loaded"
    assert status['skills']['total'] >= 2, "At least 2 skills should exist"
    assert status['tools']['total'] >= 10, "At least 10 tools should exist"
    print("[OK] System status is correct")

    # 7. Test system prompt includes skills
    print("\n[Test 7] Test system prompt")
    system_prompt = loop._build_system_prompt()
    assert "激活的技能" in system_prompt or "Python 编码规范" in system_prompt, \
        "System prompt should include activated skills"
    print("[OK] System prompt correctly includes skill prompts")

    print("\n" + "="*60)
    print("[OK] All integration tests passed!")
    print("="*60)
    print("\nIntegration verified:")
    print("  - Plugin system loaded and integrated")
    print("  - Hook system initialized and functional")
    print("  - Skill system loaded and activatable")
    print("  - Skill prompts injected into system prompt")
    print("  - All extension system control methods available")


if __name__ == "__main__":
    test_integration()
