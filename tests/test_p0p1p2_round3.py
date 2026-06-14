"""P0/P1/P2 功能验证测试 — 工具智能+会话智能+代码理解"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("P0: 工具智能增强测试")
print("=" * 60)

from core.tool_enhancer import (
    ToolEnhancer, ToolResultSummarizer, ToolRetryPolicy,
    ToolOutputTrimmer, RetryConfig, get_tool_enhancer
)

# 摘要器
summarizer = ToolResultSummarizer(threshold=200)
# 短结果不摘要
short = "Hello World"
assert not summarizer.should_summarize("run_command", short)
print("  [PASS] 短结果不摘要")

# 长命令输出摘要
long_output = "\n".join([f"line {i}: output data" for i in range(100)])
long_output += "\nError: something failed at line 50\n"
assert summarizer.should_summarize("run_command", long_output)
summary = summarizer.summarize("run_command", long_output)
assert len(summary) < len(long_output), "Summary should be shorter"
assert "Error" in summary or "error" in summary.lower(), "Should keep error lines"
print(f"  [PASS] 命令摘要: {len(long_output)} → {len(summary)} 字符")

# 文件内容摘要
file_content = "\n".join([f"# line {i}" for i in range(100)])
file_content = "class MyClass:\n" + file_content + "\ndef main():\n    pass\n"
summary_file = summarizer.summarize("read_file", file_content)
assert len(summary_file) < len(file_content)
print(f"  [PASS] 文件摘要: {len(file_content)} → {len(summary_file)} 字符")

# 搜索结果摘要
search_result = "\n".join([f"file{i}.py: match at line {i}" for i in range(80)])
summary_search = summarizer.summarize("grep_search", search_result)
assert "匹配" in summary_search or "match" in summary_search.lower()
print(f"  [PASS] 搜索摘要: {len(search_result)} → {len(summary_search)} 字符")

# 重试策略
retry = ToolRetryPolicy()
assert retry.is_retryable_tool("read_file") == True
assert retry.is_retryable_tool("write_file") == False
assert retry.is_retryable_tool("grep_search") == True
print("  [PASS] 幂等工具判断")

assert retry.is_retryable_error("Connection timeout") == True
assert retry.is_retryable_error("File not found") == False
print("  [PASS] 可重试错误判断")

assert retry.should_retry("read_file", "connection timeout", 0) == True
assert retry.should_retry("read_file", "connection timeout", 2) == False  # max_retries
assert retry.should_retry("write_file", "connection timeout", 0) == False  # 非幂等
print("  [PASS] 重试决策")

delay0 = retry.get_retry_delay(0)
delay1 = retry.get_retry_delay(1)
assert delay1 > delay0, "Exponential backoff"
print(f"  [PASS] 指数退避: {delay0}s → {delay1}s")

# 输出裁剪
trimmer = ToolOutputTrimmer(max_lines=50)
big_output = "\n".join([f"line {i}" for i in range(200)])
trimmed = trimmer.trim(big_output)
assert len(trimmed.splitlines()) < 200
print(f"  [PASS] 输出裁剪: 200 → {len(trimmed.splitlines())} 行")

# 统一增强器
enhancer = get_tool_enhancer()
result = enhancer.process_tool_result("run_command", long_output)
assert len(result) < len(long_output)
print(f"  [PASS] 统一增强器: process_tool_result")

retry_result = enhancer.should_retry("read_file", "timeout error", 0)
assert retry_result == True
print(f"  [PASS] 统一增强器: should_retry")

stats = enhancer.get_stats()
assert "summarizer_cache" in stats
assert "retry_stats" in stats
print(f"  [PASS] 增强器统计: {stats}")

print()
print("=" * 60)
print("P1: 会话智能增强测试")
print("=" * 60)

from core.session_intelligence import (
    SessionBrancher, SessionSearch, SessionIntelligence,
    get_session_intelligence
)

# 会话分支
brancher = SessionBrancher()
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "分析代码"},
    {"role": "assistant", "content": "好的，让我来分析"},
    {"role": "tool", "content": "文件内容..."},
    {"role": "assistant", "content": "分析结果..."},
    {"role": "user", "content": "继续深入"},
    {"role": "assistant", "content": "深入分析..."},
]

# 创建分支
b1 = brancher.create_branch(messages, from_index=4, name="explore-a")
assert b1.name == "explore-a"
assert len(b1.messages) == 5  # 0..4
print(f"  [PASS] 创建分支: {b1.name}, {len(b1.messages)} 消息")

b2 = brancher.create_branch(messages, from_index=4, name="explore-b")
b2.messages.extend([
    {"role": "user", "content": "探索另一条路"},
    {"role": "assistant", "content": "另一条路的分析..."},
])
print(f"  [PASS] 创建第二个分支: {b2.name}")

# 评估
score1 = brancher.evaluate_branch(b1.branch_id)
score2 = brancher.evaluate_branch(b2.branch_id)
assert 0 <= score1 <= 1
assert 0 <= score2 <= 1
print(f"  [PASS] 分支评估: {b1.name}={score1:.2f}, {b2.name}={score2:.2f}")

# 合并 (best)
merged = brancher.merge_branches([b1.branch_id, b2.branch_id], strategy="best")
assert merged is not None
assert len(merged) > 0
print(f"  [PASS] 合并(best): {len(merged)} 消息")

# 合并 (concat)
merged_concat = brancher.merge_branches([b1.branch_id, b2.branch_id], strategy="concat")
assert len(merged_concat) >= len(merged)
print(f"  [PASS] 合并(concat): {len(merged_concat)} 消息")

# 列出分支
branches = brancher.list_branches()
assert len(branches) == 2
print(f"  [PASS] 列出分支: {len(branches)} 个")

# 跨会话搜索
search = SessionSearch()
search.index_session("session-1", messages)
search.index_session("session-2", [
    {"role": "user", "content": "帮我分析认证模块"},
    {"role": "assistant", "content": "认证模块使用了JWT token"},
    {"role": "tool", "content": "Error: authentication failed"},
])

results = search.query("分析")
assert len(results) > 0
print(f"  [PASS] 搜索 '分析': {len(results)} 条结果")

results2 = search.query("authentication error", role_filter="tool")
assert len(results2) >= 1
assert results2[0]["role"] == "tool"
print(f"  [PASS] 搜索(过滤tool): {len(results2)} 条")

# 索引统计
s_stats = search.get_stats()
assert s_stats["indexed_sessions"] == 2
assert s_stats["indexed_messages"] > 0
print(f"  [PASS] 搜索统计: {s_stats}")

# 统一入口
intel = get_session_intelligence()
assert intel.brancher is not None
assert intel.search is not None
print(f"  [PASS] 会话智能统一入口")

print()
print("=" * 60)
print("P2: 代码理解深化测试")
print("=" * 60)

from core.code_analyzer import (
    DependencyGraph, ImpactAnalyzer, CodeAnalyzer
)

# 依赖图
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
graph = DependencyGraph(project_root)
nodes = graph.build([os.path.join(project_root, "core"), os.path.join(project_root, "tools")])

assert len(nodes) > 0, f"Should find nodes, got {len(nodes)}"
print(f"  [PASS] 构建依赖图: {len(nodes)} 个文件")

# 循环依赖检测
cycles = graph.detect_cycles()
print(f"  [PASS] 循环依赖检测: {len(cycles)} 个循环")

# 统计
g_stats = graph.get_stats()
assert g_stats["total_files"] > 0
print(f"  [PASS] 图统计: {g_stats}")

# 变更影响分析
analyzer = ImpactAnalyzer(graph)

# 模拟修改 agent_loop.py
agent_loop_path = None
for fp in nodes:
    if "agent_loop" in fp:
        agent_loop_path = fp
        break

if agent_loop_path:
    impact = analyzer.analyze([agent_loop_path])
    assert impact.total_impact >= 0
    print(f"  [PASS] 影响分析(agent_loop): "
          f"direct={len(impact.direct_impact)}, "
          f"indirect={len(impact.indirect_impact)}, "
          f"level={impact.impact_level}")

    # 报告生成
    report = analyzer.generate_report([agent_loop_path])
    assert "影响分析" in report
    assert "风险评估" in report
    print(f"  [PASS] 影响报告: {len(report)} 字符")
else:
    print("  [SKIP] agent_loop.py not found in graph")

# 统一入口
code_analyzer = CodeAnalyzer(project_root)
built = code_analyzer.build_dependency_graph(
    [os.path.join(project_root, "core")]
)
assert len(built) > 0
print(f"  [PASS] CodeAnalyzer: {len(built)} 个节点")

if agent_loop_path:
    impact_dict = code_analyzer.analyze_impact([agent_loop_path])
    assert "changed_files" in impact_dict
    assert "impact_level" in impact_dict
    print(f"  [PASS] analyze_impact: level={impact_dict['impact_level']}")

print()
print("=" * 60)
print("模块导入测试")
print("=" * 60)

# 确保模块可以被正确导入
from core.tool_enhancer import ToolEnhancer, get_tool_enhancer
from core.session_intelligence import SessionIntelligence, get_session_intelligence
from core.code_analyzer import CodeAnalyzer, DependencyGraph, ImpactAnalyzer
print("  [PASS] 所有模块导入成功")

print()
print("ALL TESTS PASSED!")
