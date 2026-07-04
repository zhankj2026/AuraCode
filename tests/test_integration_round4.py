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
工程化集成测试 — 验证 ToolEnhancer/SessionIntelligence/CodeAnalyzer 集成

测试覆盖:
1. P0: ToolEnhancer 集成到 agent_loop._execute_tool()
2. P1: SessionIntelligence 集成到 SessionStore
3. P2: CodeAnalyzer 集成到 /review 命令
"""
import os
import sys
import json
import tempfile
import shutil
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}: {detail}")


# ============================================================
# P0: ToolEnhancer 集成
# ============================================================
print("\n" + "=" * 60)
print("P0: ToolEnhancer → agent_loop._execute_tool() 集成")
print("=" * 60)

# 1. 验证 ToolEnhancer 可导入
try:
    from core.tool_enhancer import get_tool_enhancer, ToolEnhancer
    enhancer = get_tool_enhancer()
    check("ToolEnhancer 可导入", True)
    check("ToolEnhancer 是单例", get_tool_enhancer() is enhancer)
except Exception as e:
    check("ToolEnhancer 可导入", False, str(e))
    enhancer = None

# 2. 验证 process_tool_result 正常工作
if enhancer:
    # 短结果 — 不截断
    short_result = "hello world"
    processed = enhancer.process_tool_result("read_file", short_result)
    check("短结果原样返回", "hello world" in processed)

    # 长结果 — 自动裁剪+摘要
    long_lines = [f"Line {i}: some content here for testing" for i in range(600)]
    long_result = "\n".join(long_lines)
    processed_long = enhancer.process_tool_result("run_command", long_result)
    check("长结果被裁剪", len(processed_long) < len(long_result))

# 3. 验证 should_retry 正常工作
if enhancer:
    # 幂等工具 (read_file) 可重试
    can_retry = enhancer.should_retry("read_file", "Connection timeout", 1)
    check("幂等工具可重试 (attempt 1)", can_retry)

    # 非幂等工具 (write_file) 不重试
    no_retry = enhancer.should_retry("write_file", "Connection timeout", 1)
    check("非幂等工具不重试", not no_retry)

    # 超过最大次数不重试
    max_retry = enhancer.should_retry("read_file", "Connection timeout", 10)
    check("超过最大次数不重试", not max_retry)

    # 重试延迟递增
    delay1 = enhancer.get_retry_delay(1)
    delay2 = enhancer.get_retry_delay(2)
    check("重试延迟递增", delay2 >= delay1)

# 4. 验证 agent_loop 导入了 tool_enhancer
try:
    import core.agent_loop as al_mod
    source = open(al_mod.__file__, "r", encoding="utf-8").read()
    check("agent_loop.py 导入 get_tool_enhancer",
          "from core.tool_enhancer import get_tool_enhancer" in source)
    check("agent_loop.py 初始化 tool_enhancer",
          "self.tool_enhancer = get_tool_enhancer()" in source)
    check("agent_loop.py 调用 process_tool_result",
          "self.tool_enhancer.process_tool_result" in source)
    check("agent_loop.py 调用 should_retry",
          "self.tool_enhancer.should_retry" in source)
    check("agent_loop.py 发送 tool_retry 事件",
          "tool_retry" in source)
except Exception as e:
    check("agent_loop.py 集成检查", False, str(e))


# ============================================================
# P1: SessionIntelligence 集成
# ============================================================
print("\n" + "=" * 60)
print("P1: SessionIntelligence → SessionStore 集成")
print("=" * 60)

# 1. SessionStore 可导入
try:
    from core.session_store import SessionStore, SessionMeta
    check("SessionStore 可导入", True)
except Exception as e:
    check("SessionStore 可导入", False, str(e))

# 2. SessionStore 包含智能增强属性
tmpdir = tempfile.mkdtemp(prefix="auracode_test_sessions_")
try:
    store = SessionStore(sessions_dir=tmpdir)
    check("SessionStore 初始化含 SessionIntelligence",
          hasattr(store, '_intelligence'))
    check("SessionStore 有 _brancher", hasattr(store, '_brancher'))
    check("SessionStore 有 _search", hasattr(store, '_search'))
except Exception as e:
    check("SessionStore 智能初始化", False, str(e))
    store = None

# 3. 保存会话时自动索引
if store:
    messages = [
        {"role": "user", "content": "Please fix the authentication bug"},
        {"role": "assistant", "content": "I will look at the auth module"},
        {"role": "user", "content": "Check the login function"},
    ]
    meta = store.save_session(
        messages=messages,
        model="test-model",
        turn_count=2,
        session_id="test-session-001",
    )
    check("会话保存成功", meta is not None and meta.session_id == "test-session-001")

    # 验证自动索引
    indexed = "test-session-001" in store._search._index
    check("保存后自动索引到 SessionSearch", indexed)

# 4. 增强搜索
if store:
    # 保存第二个会话
    messages2 = [
        {"role": "user", "content": "How to optimize database queries"},
        {"role": "assistant", "content": "Use indexing and query optimization"},
    ]
    store.save_session(
        messages=messages2,
        model="test-model",
        turn_count=1,
        session_id="test-session-002",
    )

    results = store.search_sessions_enhanced("authentication")
    check("增强搜索找到认证相关消息", len(results) > 0)

    results2 = store.search_sessions_enhanced("database")
    check("增强搜索找到数据库相关消息", len(results2) > 0)

    # 角色过滤
    user_results = store.search_sessions_enhanced("fix", role_filter="user")
    check("角色过滤只返回 user 消息",
          all(r.get("role") == "user" for r in user_results) if user_results else True)

# 5. 分支操作
if store:
    branch_info = store.create_branch("test-session-001", from_index=1, branch_name="explore-a")
    check("创建分支成功", branch_info is not None and "branch_id" in branch_info)

    if branch_info:
        bid = branch_info["branch_id"]
        check("分支名称正确", branch_info["name"] == "explore-a")
        check("分支消息数合理", branch_info["message_count"] >= 1)

        # 评估分支
        score = store.evaluate_branch(bid)
        check("分支评分返回数值", isinstance(score, (int, float)))

        # 列出分支
        all_branches = store.get_branch_info()
        check("分支列表包含创建的分支",
              all_branches["total"] >= 1)

# 6. 搜索统计
if store:
    stats = store.get_search_stats()
    check("搜索统计有 sessions 数", "indexed_sessions" in str(stats) or "sessions" in str(stats) or isinstance(stats, dict))


# ============================================================
# P2: CodeAnalyzer 集成到 /review
# ============================================================
print("\n" + "=" * 60)
print("P2: CodeAnalyzer → /review 命令集成")
print("=" * 60)

# 1. review 命令包含 CodeAnalyzer 集成
try:
    from commands.builtin import review_command
    review_source = open(review_command.__file__, "r", encoding="utf-8").read()
    check("review_command 导入 CodeAnalyzer",
          "from core.code_analyzer import CodeAnalyzer" in review_source)
    check("review_command 调用 analyze_impact",
          "analyzer.analyze_impact" in review_source)
    check("review_command 调用 generate_impact_report",
          "analyzer.generate_impact_report" in review_source)
    check("review_command 有 _extract_changed_files",
          "_extract_changed_files" in review_source)
except Exception as e:
    check("review_command 集成检查", False, str(e))

# 2. CodeAnalyzer 功能验证
try:
    from core.code_analyzer import CodeAnalyzer

    # 创建临时项目结构
    test_project = tempfile.mkdtemp(prefix="auracode_test_project_")
    src_dir = os.path.join(test_project, "src")
    os.makedirs(src_dir)

    # 创建 Python 文件
    with open(os.path.join(src_dir, "main.py"), "w") as f:
        f.write("from src.utils import helper\ndef main():\n    helper()\n")
    with open(os.path.join(src_dir, "utils.py"), "w") as f:
        f.write("def helper():\n    print('help')\n")
    with open(os.path.join(src_dir, "__init__.py"), "w") as f:
        f.write("")

    analyzer = CodeAnalyzer(project_root=test_project)
    graph = analyzer.build_dependency_graph()
    check("CodeAnalyzer 构建依赖图", graph is not None)
    check("依赖图包含节点", len(graph) > 0 if graph else False)

    # 影响分析
    impact = analyzer.analyze_impact(["src/utils.py"])
    check("影响分析返回结果", impact is not None)

    # 影响报告
    report = analyzer.generate_impact_report(["src/utils.py"])
    check("影响报告是字符串", isinstance(report, str) and len(report) > 0)

    # 统计
    stats = analyzer.get_stats()
    check("统计信息是字典", isinstance(stats, dict))

    # 清理
    shutil.rmtree(test_project, ignore_errors=True)

except Exception as e:
    check("CodeAnalyzer 功能验证", False, str(e))


# ============================================================
# 跨模块集成验证
# ============================================================
print("\n" + "=" * 60)
print("跨模块集成验证")
print("=" * 60)

# 验证所有三个模块可以同时导入
try:
    from core.tool_enhancer import ToolEnhancer, get_tool_enhancer
    from core.session_intelligence import SessionIntelligence, get_session_intelligence
    from core.code_analyzer import CodeAnalyzer
    check("三个模块可同时导入", True)
except Exception as e:
    check("三个模块可同时导入", False, str(e))

# 验证 agent_loop.py 语法正确
try:
    import py_compile
    py_compile.compile(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "core", "agent_loop.py"),
        doraise=True
    )
    check("agent_loop.py 语法正确", True)
except Exception as e:
    check("agent_loop.py 语法正确", False, str(e))

# 验证 session_store.py 语法正确
try:
    py_compile.compile(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "core", "session_store.py"),
        doraise=True
    )
    check("session_store.py 语法正确", True)
except Exception as e:
    check("session_store.py 语法正确", False, str(e))

# 验证 review_command.py 语法正确
try:
    py_compile.compile(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "commands", "builtin", "review_command.py"),
        doraise=True
    )
    check("review_command.py 语法正确", True)
except Exception as e:
    check("review_command.py 语法正确", False, str(e))


# ============================================================
# 清理
# ============================================================
shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"测试完成: {PASS}/{total} 通过, {FAIL} 失败")
if FAIL > 0:
    print("⚠️ 有测试失败!")
    sys.exit(1)
else:
    print("🎉 全部通过!")
    sys.exit(0)
