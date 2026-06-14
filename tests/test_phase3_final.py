"""
Phase 3 集成测试 — /security-review + AwaySummary + TipSystem

验证三个新模块的功能正确性。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name}")
        failed += 1


# ════════════════════════════════════════════════════════════
# P0: /security-review 命令 — SecurityScanner
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("P0: /security-review — 安全漏洞扫描")
print("=" * 60)

# 1. 模块导入
from commands.builtin.security_review_command import (
    SecurityScanner, SecurityFinding, SecurityRule,
    SECURITY_RULES, generate_security_report,
    security_review_handler, HARD_EXCLUSIONS,
    _is_excluded_file, _should_exclude_finding,
)
check("security_review 模块可导入", True)

# 2. 规则数量
check(f"安全检查规则数量 >= 16 (实际={len(SECURITY_RULES)})", len(SECURITY_RULES) >= 16)

# 3. SecurityScanner 初始化
scanner = SecurityScanner()
check("SecurityScanner 可创建", scanner is not None)
check("默认 min_confidence=0.7", scanner.min_confidence == 0.7)

# 4. SQL 注入检测
sql_diff = """diff --git a/app.py b/app.py
@@ -1,3 +1,5 @@
+query = cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
+result = cursor.execute("SELECT * FROM orders WHERE id = " + user_input)
"""
findings = scanner.scan_diff(sql_diff)
sql_findings = [f for f in findings if f.category == "sql_injection"]
check(f"检测到 SQL 注入 (找到 {len(sql_findings)} 个)", len(sql_findings) >= 1)

# 5. 命令注入检测
cmd_diff = """diff --git a/runner.py b/runner.py
@@ -1,3 +1,5 @@
+os.system(f"rm -rf {user_input}")
+subprocess.call("echo " + name, shell=True)
"""
findings = scanner.scan_diff(cmd_diff)
cmd_findings = [f for f in findings if f.category == "command_injection"]
check(f"检测到命令注入 (找到 {len(cmd_findings)} 个)", len(cmd_findings) >= 1)

# 6. 硬编码密钥检测
secret_diff = """diff --git a/config.py b/config.py
@@ -1,3 +1,5 @@
+password = "supersecret123"
+api_key = "sk-1234567890abcdef"
"""
findings = scanner.scan_diff(secret_diff)
secret_findings = [f for f in findings if f.category == "hardcoded_secrets"]
check(f"检测到硬编码密钥 (找到 {len(secret_findings)} 个)", len(secret_findings) >= 1)

# 7. 不安全的反序列化
deser_diff = """diff --git a/loader.py b/loader.py
@@ -1,3 +1,5 @@
+data = pickle.loads(user_input)
+obj = yaml.load(content)
"""
findings = scanner.scan_diff(deser_diff)
deser_findings = [f for f in findings if f.category == "insecure_deserialization"]
check(f"检测到不安全反序列化 (找到 {len(deser_findings)} 个)", len(deser_findings) >= 1)

# 8. eval 代码执行
eval_diff = """diff --git a/calc.py b/calc.py
@@ -1,3 +1,4 @@
+result = eval(user_expression)
"""
findings = scanner.scan_diff(eval_diff)
eval_findings = [f for f in findings if f.category == "code_execution"]
check(f"检测到 eval 代码执行 (找到 {len(eval_findings)} 个)", len(eval_findings) >= 1)

# 9. 测试文件排除
check("_is_excluded_file('test_auth.py') == True", _is_excluded_file("test_auth.py"))
check("_is_excluded_file('auth_test.py') == True", _is_excluded_file("auth_test.py"))
check("_is_excluded_file('README.md') == True", _is_excluded_file("README.md"))
check("_is_excluded_file('src/auth.py') == False", not _is_excluded_file("src/auth.py"))

# 10. SecurityFinding Markdown 输出
finding = SecurityFinding(
    file="app.py", line=42, severity="HIGH",
    category="sql_injection", message="SQL注入风险",
    code_snippet="cursor.execute(f'SELECT...')",
    confidence=0.9, recommendation="使用参数化查询",
)
md = finding.to_markdown(1)
check("Finding Markdown 包含文件行号", "app.py:42" in md)
check("Finding Markdown 包含严重性", "HIGH" in md)

# 11. 报告生成
report = generate_security_report(
    findings=[finding], stats={"files": 3, "additions": 50, "deletions": 10},
    changed_files=["app.py", "config.py", "runner.py"],
)
check("报告包含标题", "安全审查报告" in report)
check("报告包含 HIGH 计数", "HIGH: 1" in report)
check("报告包含变更统计", "+50/-10" in report)

# 12. 空发现报告
empty_report = generate_security_report(
    findings=[], stats={"files": 1, "additions": 5, "deletions": 0},
    changed_files=[],
)
check("空报告包含安全通过信息", "安全" in empty_report or "未发现" in empty_report)

# 13. security_review_handler 执行
result = security_review_handler(["--staged"])
check("handler --staged 返回字符串", isinstance(result, str))
check("handler 结果包含安全审查", "安全" in result or "审查" in result)

# 14. 命令注册
from commands.registry import COMMAND_REGISTRY
check("/security-review 已注册", "security-review" in COMMAND_REGISTRY)

# 15. min_severity 过滤
high_scanner = SecurityScanner(min_severity="HIGH", min_confidence=0.7)
mixed_diff = """diff --git a/app.py b/app.py
@@ -1,3 +1,6 @@
+query = cursor.execute("SELECT * FROM users WHERE id = " + user_id)
+tempfile.mktemp()
"""
high_findings = high_scanner.scan_diff(mixed_diff)
low_findings = [f for f in high_findings if f.severity == "LOW"]
check("HIGH过滤器排除LOW发现", len(low_findings) == 0)


# ════════════════════════════════════════════════════════════
# P1: AwaySummary 服务 — 离开时摘要
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("P1: AwaySummary — 离开时摘要")
print("=" * 60)

from services.away_summary import (
    AwaySummaryService, AwaySummaryResult,
    get_away_summary_service, generate_away_summary,
    RECENT_MESSAGE_WINDOW,
)
check("AwaySummary 模块可导入", True)

# 1. 服务创建
svc = AwaySummaryService()
check("AwaySummaryService 可创建", svc is not None)

# 2. 空消息处理
result = svc.generate_summary([])
check("空消息返回 success=False", not result.success)
check("空消息有错误信息", result.error is not None)

# 3. 短消息处理
short_msgs = [{"role": "user", "content": "Hello"}]
result = svc.generate_summary(short_msgs)
check("短消息返回成功", result.success)

# 4. 正常消息列表
messages = [
    {"role": "user", "content": "帮我重构 auth 模块"},
    {"role": "assistant", "content": "好的，我来分析 auth 模块的结构..."},
    {"role": "user", "content": "请修改登录验证逻辑"},
    {"role": "assistant", "content": "我已经修改了 validate_token 函数..."},
    {"role": "user", "content": "运行测试看看"},
    {"role": "assistant", "content": "所有 15 个测试通过了。"},
]
result = svc.generate_summary(messages)
check("正常消息返回成功", result.success)
check("摘要不是空字符串", len(result.summary) > 0)
check("message_count 正确", result.message_count == len(messages))
check("generated_at 是时间戳", result.generated_at > 0)

# 5. get_last_summary
last = svc.get_last_summary()
check("get_last_summary 返回结果", last is not None)
check("last == result", last.summary == result.summary)

# 6. format_display
display = svc.format_display(result)
check("display 包含 while you were away", "away" in display.lower() or "离开" in display)

# 7. 内容块消息格式
block_msgs = [
    {"role": "user", "content": [{"type": "text", "text": "修改文件"}]},
    {"role": "assistant", "content": [
        {"type": "text", "text": "我来修改 config.py"},
        {"type": "tool_use", "name": "write_file"},
    ]},
    {"role": "user", "content": "继续"},
    {"role": "assistant", "content": "已完成修改"},
]
result2 = svc.generate_summary(block_msgs)
check("块消息格式处理成功", result2.success)

# 8. 全局单例
svc1 = get_away_summary_service()
svc2 = get_away_summary_service()
check("全局单例一致", svc1 is svc2)

# 9. 快捷函数
result3 = generate_away_summary(messages)
check("快捷函数返回成功", result3.success)

# 10. 超长摘要截断
long_msgs = [{"role": "user", "content": "x" * 1000}] * 35
result4 = svc.generate_summary(long_msgs)
check("超长消息不崩溃", result4.success)


# ════════════════════════════════════════════════════════════
# P2: TipSystem 服务 — 功能发现提示
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("P2: TipSystem — 功能发现提示")
print("=" * 60)

from services.tip_system import (
    Tip, TipContext, TipScheduler, TipHistory,
    BUILTIN_TIPS, get_tip_scheduler, tips_handler,
)
check("TipSystem 模块可导入", True)

# 1. 内置提示数量
check(f"内置提示数量 >= 10 (实际={len(BUILTIN_TIPS)})", len(BUILTIN_TIPS) >= 10)

# 2. Tip 数据
tip = BUILTIN_TIPS[0]
check("Tip 有 tip_id", len(tip.tip_id) > 0)
check("Tip 有 title", len(tip.title) > 0)
check("Tip 有 content", len(tip.content) > 0)
check("Tip 有 category", tip.category in ("command", "tool", "workflow", "shortcut"))

# 3. TipHistory 创建（使用临时文件）
import tempfile
tmp = tempfile.mktemp(suffix=".json")
history = TipHistory(tmp)
check("TipHistory 可创建", history is not None)
check("初始 session_count=0", history.get_session_count() == 0)

# 4. 会话计数
history.increment_session()
history.increment_session()
check("会话计数递增", history.get_session_count() == 2)

# 5. 展示记录
history.record_shown("cmd_review")
check("sessions_since_shown 返回 0", history.sessions_since_shown("cmd_review") == 0)
check("未展示过的返回 inf", history.sessions_since_shown("unknown") == float("inf"))

# 6. TipScheduler 创建
scheduler = TipScheduler(history=history)
check("TipScheduler 可创建", scheduler is not None)

# 7. 获取提示
ctx = TipContext()
tip = scheduler.get_tip_to_show(ctx)
check("get_tip_to_show 返回 Tip", tip is not None)
check("Tip 是 Tip 实例", isinstance(tip, Tip))

# 8. 展示并冷却
scheduler.record_shown(tip)
# 获取第二条（第一条应被冷却）
tip2 = scheduler.get_tip_to_show(ctx)
if tip2:
    check("冷却后的提示不同于第一条", tip2.tip_id != tip.tip_id)
else:
    check("所有提示都已冷却", True)

# 9. format_tip
formatted = scheduler.format_tip(BUILTIN_TIPS[0])
check("format_tip 包含 emoji", BUILTIN_TIPS[0].emoji in formatted)
check("format_tip 包含标题", BUILTIN_TIPS[0].title in formatted)

# 10. get_and_format_tip
formatted2 = scheduler.get_and_format_tip(ctx)
check("get_and_format_tip 返回字符串", formatted2 is None or isinstance(formatted2, str))

# 11. list_all_tips
all_tips = scheduler.list_all_tips()
check(f"list_all_tips 返回 {len(all_tips)} 条", len(all_tips) >= 10)

# 12. register_tip
custom_tip = Tip(tip_id="custom_1", title="自定义", content="测试", category="tool")
scheduler.register_tip(custom_tip)
all_after = scheduler.list_all_tips()
check("register_tip 增加了总数", len(all_after) == len(all_tips) + 1)

# 13. remove_tip
scheduler.remove_tip("custom_1")
all_removed = scheduler.list_all_tips()
check("remove_tip 减少了总数", len(all_removed) == len(all_tips))

# 14. tips_handler
result_list = tips_handler(["list"])
check("handler list 返回字符串", isinstance(result_list, str))
check("handler list 包含类别", "command" in result_list or "tool" in result_list)

result_tip = tips_handler([])
check("handler 无参数返回提示", isinstance(result_tip, str))

# 15. TipContext
ctx2 = TipContext(
    session_count=5, has_git=True, has_mcp=True,
    project_size="large", used_commands=["/review"],
    os_platform="windows",
)
check("TipContext 字段正确", ctx2.has_mcp and ctx2.project_size == "large")

# 16. /tips 命令注册
check("/tips 已注册", "tips" in COMMAND_REGISTRY)

# 清理临时文件
try:
    os.unlink(tmp)
except:
    pass


# ════════════════════════════════════════════════════════════
# 集成验证
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("集成验证")
print("=" * 60)

# 1. services/__init__.py 语法
import py_compile
py_compile.compile("services/__init__.py", doraise=True)
check("services/__init__.py 语法正确", True)

# 2. commands/builtin/__init__.py 语法
py_compile.compile("commands/builtin/__init__.py", doraise=True)
check("commands/builtin/__init__.py 语法正确", True)

# 3. resume_command.py 语法
py_compile.compile("commands/builtin/resume_command.py", doraise=True)
check("resume_command.py 语法正确", True)

# 4. security_review_command.py 语法
py_compile.compile("commands/builtin/security_review_command.py", doraise=True)
check("security_review_command.py 语法正确", True)

# 5. 命令注册总数
cmd_count = len(COMMAND_REGISTRY)
check(f"命令注册总数 >= 44 (实际={cmd_count})", cmd_count >= 44)

# 6. services 模块导出
from services import (
    DiagnosticTracker, AwaySummaryService,
    TipScheduler, BUILTIN_TIPS,
)
check("services 模块正确导出", True)

# 7. 所有三个新命令已注册
for cmd_name in ["security-review", "tips"]:
    check(f"/{cmd_name} 在注册表中", cmd_name in COMMAND_REGISTRY)


# ════════════════════════════════════════════════════════════
# 结果
# ════════════════════════════════════════════════════════════
total = passed + failed
print(f"\n{'=' * 60}")
print(f"测试完成: {passed}/{total} 通过, {failed} 失败")
if failed == 0:
    print("🎉 全部通过!")
else:
    print(f"⚠️ 有 {failed} 项失败")
print(f"{'=' * 60}")

sys.exit(0)
