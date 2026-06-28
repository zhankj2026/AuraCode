# -*- coding: utf-8 -*-
"""
Subagent Enhanced Feature Tests

Tests:
1. Agent definition file loading
2. Fork mode
3. Result compression
4. Specialist Agent types
"""

import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.subagent import SubagentManager, AgentDefinition


def test_agent_definition_parsing():
    """Test Agent definition file parsing"""
    print("\n=== Test Agent Definition File Parsing ===")

    # Create temporary directory and test file
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir) / "agents"
        agents_dir.mkdir()

        # Create test agent definition
        test_agent = agents_dir / "test_agent.md"
        with open(test_agent, 'w', encoding='utf-8') as f:
            f.write("""---
name: test
description: Test Agent
tools: Read, Grep, Glob
model: sonnet
---

This is a test agent prompt.
""")

        # Parse file
        result = AgentDefinition.parse_file(str(test_agent))

        assert result is not None, "Parsing failed"
        assert result['name'] == 'test', f"Wrong name: {result['name']}"
        assert result['description'] == 'Test Agent', f"Wrong description: {result['description']}"
        assert 'Read' in result['tools'], f"Wrong tools: {result['tools']}"
        assert result['model'] == 'sonnet', f"Wrong model: {result['model']}"

        print("[PASS] Agent definition parsing test passed")


def test_agent_directory_loading():
    """Test directory loading"""
    print("\n=== Test Agent Directory Loading ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir) / "agents"
        agents_dir.mkdir(exist_ok=True)

        # Create multiple agent files
        with open(agents_dir / "agent1.md", 'w', encoding='utf-8') as f:
            f.write("---\nname: agent1\ndescription: First\n---\nPrompt 1")
        with open(agents_dir / "agent2.md", 'w', encoding='utf-8') as f:
            f.write("---\nname: agent2\ndescription: Second\n---\nPrompt 2")
        with open(agents_dir / "readme.txt", 'w', encoding='utf-8') as f:
            f.write("Not an agent")

        agents = AgentDefinition.load_agents_directory(str(agents_dir))

        assert len(agents) == 2, f"Should load 2 agents, got: {len(agents)}"
        assert 'agent1' in agents, "Missing agent1"
        assert 'agent2' in agents, "Missing agent2"

        print("[PASS] Agent directory loading test passed")


def test_result_compression():
    """Test result compression"""
    print("\n=== Test Result Compression ===")

    # Set API key for real call (if available)
    os.environ.setdefault('OPENAI_API_KEY', 'test-key')

    manager = SubagentManager(max_concurrent=2)

    # Create long text (simulate large output)
    long_text = []
    for i in range(1000):
        long_text.append(f"Line {i}: Some search result content")
        if i % 100 == 0:
            long_text.append(f"## Key Finding {i//100}")
            long_text.append(f"Important discovery at line {i}")

    raw_result = "\n".join(long_text)

    # Test compression
    compressed = manager._compress_result(raw_result, "Test task")

    # Verify compression
    compression_ratio = 100 * (1 - len(compressed) / len(raw_result))

    print(f"Original length: {len(raw_result)} chars")
    print(f"Compressed: {len(compressed)} chars")
    print(f"Compression ratio: {compression_ratio:.1f}%")

    assert len(compressed) < len(raw_result), "Result should be compressed"
    assert "## Key Finding" in compressed, "Key content should be preserved"

    print("[PASS] Result compression test passed")


def test_subagent_spawn():
    """Test Subagent creation"""
    print("\n=== Test Subagent Creation ===")

    os.environ.setdefault('OPENAI_API_KEY', 'test-key')

    manager = SubagentManager(max_concurrent=2)

    # Test creation
    handle = manager.spawn_subagent(
        task="Test task",
        model="glm-4-plus",
        agent_type="general",
        run_in_background=True
    )

    assert handle.agent_id is not None, "Should have agent_id"
    assert handle.status == "running", "Initial status should be running"
    assert handle.agent_type == "general", "Wrong agent type"

    print(f"[PASS] Subagent creation test passed (ID: {handle.agent_id})")

    # Wait for completion
    handle.thread.join(timeout=5)

    # Get status
    status = manager.get_agent_status(handle.agent_id)
    print(f"Final status: {status['status']}")


def test_available_agent_types():
    """Test available Agent types"""
    print("\n=== Test Available Agent Types ===")

    os.environ.setdefault('OPENAI_API_KEY', 'test-key')

    manager = SubagentManager()

    # Switch to project directory to load .auracode/agents
    original_dir = os.getcwd()
    try:
        os.chdir(project_root)
        manager = SubagentManager()
    finally:
        os.chdir(original_dir)

    types = manager.get_available_agent_types()

    print(f"Available agent types: {types}")

    # Should at least have general
    assert 'general' in types, "Should have general type"

    # Check built-in types
    expected_types = ['explore', 'plan', 'review', 'impact', 'diagnose']
    for expected in expected_types:
        if expected in types:
            agent_def = manager.get_agent_definition(expected)
            assert agent_def is not None, f"{expected} definition should not be None"
            print(f"  - {expected}: {agent_def['description'][:50]}...")

    print("[PASS] Available agent types test passed")


def test_concurrent_limit():
    """Test concurrent limit"""
    print("\n=== Test Concurrent Limit ===")

    os.environ.setdefault('OPENAI_API_KEY', 'test-key')

    manager = SubagentManager(max_concurrent=2)

    # Create 2 subagents (should succeed)
    handle1 = manager.spawn_subagent("Task 1", run_in_background=True)
    handle2 = manager.spawn_subagent("Task 2", run_in_background=True)

    # Create 3rd (should be rejected)
    try:
        handle3 = manager.spawn_subagent("Task 3", run_in_background=True)
        assert False, "Should raise exception"
    except RuntimeError as e:
        assert "max concurrent" in str(e) or "并发" in str(e), f"Wrong error message: {e}"
        print("[PASS] Concurrent limit triggered correctly")

    # Cleanup
    handle1.thread.join(timeout=5)
    handle2.thread.join(timeout=5)

    print("[PASS] Concurrent limit test passed")


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Subagent Enhanced Feature Test Suite")
    print("=" * 60)

    tests = [
        test_agent_definition_parsing,
        test_agent_directory_loading,
        test_result_compression,
        test_subagent_spawn,
        test_available_agent_types,
        test_concurrent_limit,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] Test failed: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] Test error: {test.__name__}")
            print(f"   Exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
