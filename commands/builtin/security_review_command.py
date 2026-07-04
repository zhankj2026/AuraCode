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
Security Review 命令 — 安全漏洞扫描

对当前分支的 Git 变更进行安全专项审查，
覆盖 16 类安全漏洞（注入/认证/密码学/XSS/数据泄露等），
使用模式匹配 + 严重性分级 + 误报过滤，生成结构化报告。
"""
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from commands.registry import register_command


# ── 安全发现数据类 ──────────────────────────────────────────

@dataclass
class SecurityFinding:
    """单个安全发现"""
    file: str
    line: int
    severity: str        # HIGH / MEDIUM / LOW
    category: str        # sql_injection / xss / command_injection 等
    message: str
    code_snippet: str
    confidence: float    # 0.0 ~ 1.0
    recommendation: str = ""

    def to_markdown(self, index: int) -> str:
        """转为 Markdown 格式"""
        return (
            f"### Vuln {index}: {self.category}: `{self.file}:{self.line}`\n\n"
            f"- **Severity**: {self.severity}\n"
            f"- **Confidence**: {self.confidence:.1f}\n"
            f"- **Description**: {self.message}\n"
            f"- **Code**: `{self.code_snippet[:120]}`\n"
            f"- **Recommendation**: {self.recommendation}\n"
        )


# ── 16 类安全检查规则 ──────────────────────────────────────

@dataclass
class SecurityRule:
    """安全检查规则"""
    rule_id: str
    category: str
    severity: str
    confidence: float
    pattern: str           # 正则表达式
    message: str
    recommendation: str
    exclude_patterns: List[str] = field(default_factory=list)


# 16 类安全检查规则库
SECURITY_RULES: List[SecurityRule] = [
    # 1. SQL 注入
    SecurityRule(
        rule_id="SQL001",
        category="sql_injection",
        severity="HIGH",
        confidence=0.9,
        pattern=r'(?:execute|cursor\.execute|raw\(|query)\s*\(\s*["\'].*?%s|'
                r'(?:execute|cursor\.execute)\s*\(\s*f["\']|'
                r'(?:execute|cursor\.execute)\s*\(.*?\+\s*\w+|'
                r'\.raw\s*\(.*?\+',
        message="SQL 查询使用字符串拼接/格式化，存在 SQL 注入风险",
        recommendation="使用参数化查询（%s 占位符或 ORM 查询构建器）",
        exclude_patterns=[r'#.*execute', r'test_.*\.py', r'_test\.py'],
    ),

    # 2. 命令注入
    SecurityRule(
        rule_id="CMD001",
        category="command_injection",
        severity="HIGH",
        confidence=0.85,
        pattern=r'(?:os\.system|os\.popen|subprocess\.call|subprocess\.Popen)\s*\(.*?\+|'
                r'(?:os\.system|os\.popen)\s*\(\s*f["\']|'
                r'subprocess\.\w+\s*\(\s*["\'].*?\.format\(|'
                r'subprocess\.\w+\s*\(\s*f["\']|'
                r'shell\s*=\s*True',
        message="系统命令使用字符串拼接/shell=True，存在命令注入风险",
        recommendation="使用 subprocess 列表参数形式，避免 shell=True",
        exclude_patterns=[r'shell\s*=\s*False', r'#.*subprocess'],
    ),

    # 3. 路径遍历
    SecurityRule(
        rule_id="PATH001",
        category="path_traversal",
        severity="HIGH",
        confidence=0.85,
        pattern=r'(?:open|os\.path\.join)\s*\(.*?(?:request|params|args|query|input|user)',
        message="文件操作使用用户输入路径，存在路径遍历风险",
        recommendation="验证和规范化路径，使用 os.path.realpath() 检查是否在允许目录内",
        exclude_patterns=[r'os\.path\.realpath', r'sanitize', r'validate'],
    ),

    # 4. XSS 跨站脚本
    SecurityRule(
        rule_id="XSS001",
        category="xss",
        severity="HIGH",
        confidence=0.85,
        pattern=r'(?:render_template_string|Markup\s*\(|mark_safe|dangerouslySetInnerHTML|'
                r'innerHTML\s*=|\.html\s*\(|SafeString|safe_substitute)',
        message="模板渲染或 DOM 操作可能存在 XSS 漏洞",
        recommendation="使用自动转义模板引擎，避免直接插入用户输入到 HTML",
        exclude_patterns=[r'escape', r'sanitize', r'bleach'],
    ),

    # 5. 硬编码密钥/密码
    SecurityRule(
        rule_id="SECRET001",
        category="hardcoded_secrets",
        severity="HIGH",
        confidence=0.9,
        pattern=r'(?:password|passwd|secret|api_key|apikey|token|private_key|'
                r'aws_secret|access_key)\s*=\s*["\'][^"\']{4,}["\']',
        message="硬编码密钥/密码/Token 被提交到代码中",
        recommendation="使用环境变量或密钥管理服务（如 AWS Secrets Manager, Vault）",
        exclude_patterns=[r'os\.environ', r'getenv', r'config\.', r'\.env',
                          r'#.*password', r'example', r'placeholder', r'fake',
                          r'test_.*\.py', r'fixture'],
    ),

    # 6. 不安全的反序列化
    SecurityRule(
        rule_id="DESER001",
        category="insecure_deserialization",
        severity="HIGH",
        confidence=0.9,
        pattern=r'(?:pickle\.loads?\s*\(|yaml\.load\s*\((?!.*Loader)|'
                r'marshal\.loads?\s*\(|shelve\.open)',
        message="不安全的反序列化操作，可能导致远程代码执行",
        recommendation="使用 json 替代 pickle；yaml.load() 必须指定 Loader=yaml.SafeLoader",
        exclude_patterns=[r'SafeLoader', r'safe_load', r'json\.loads'],
    ),

    # 7. eval/exec 动态代码执行
    SecurityRule(
        rule_id="EVAL001",
        category="code_execution",
        severity="HIGH",
        confidence=0.85,
        pattern=r'(?:\beval\s*\(|\bexec\s*\(|compile\s*\()',
        message="使用 eval/exec/compile 动态执行代码，存在代码注入风险",
        recommendation="避免使用 eval/exec，改用安全的解析器或白名单方法",
        exclude_patterns=[r'#.*eval', r'test_.*\.py', r'ast\.literal_eval'],
    ),

    # 8. 认证绕过
    SecurityRule(
        rule_id="AUTH001",
        category="authentication_bypass",
        severity="HIGH",
        confidence=0.8,
        pattern=r'(?:verify\s*=\s*False|check_hostname\s*=\s*False|'
                r'CERT_NONE|skip_auth|no_auth|allow_anonymous|'
                r'disable_auth|auth_required\s*=\s*False)',
        message="禁用了安全验证机制（SSL验证/认证/证书检查）",
        recommendation="保持安全验证启用，仅在测试环境中通过配置禁用",
        exclude_patterns=[r'if\s+TESTING', r'if\s+DEBUG', r'#.*test'],
    ),

    # 9. JWT 漏洞
    SecurityRule(
        rule_id="JWT001",
        category="jwt_vulnerability",
        severity="HIGH",
        confidence=0.85,
        pattern=r'(?:algorithms\s*=\s*\[["\']none["\']|'
                r'jwt\.decode\s*\([^)]*algorithms\s*=\s*\[|'
                r'verify\s*=\s*False.*jwt|'
                r'HMAC.*secret.*=.*["\']\w{1,10}["\'])',
        message="JWT 实现存在安全缺陷（none 算法/禁用验证/弱密钥）",
        recommendation="使用 RS256/ES256 算法，密钥长度至少 256 位，始终验证签名和过期时间",
    ),

    # 10. 弱密码算法
    SecurityRule(
        rule_id="CRYPTO001",
        category="weak_cryptography",
        severity="MEDIUM",
        confidence=0.85,
        pattern=r'(?:MD5|SHA1|DES|RC4|md5\(|sha1\(|'
                r'hashlib\.md5|hashlib\.sha1|'
                r'random\.random|random\.randint|random\.choice)',
        message="使用弱密码算法（MD5/SHA1/DES）或不安全的随机数生成器",
        recommendation="使用 SHA-256 或更强的哈希算法；使用 secrets 模块生成安全随机数",
        exclude_patterns=[r'sha256', r'sha512', r'bcrypt', r'argon2',
                          r'#.*md5', r'hashlib\.sha256'],
    ),

    # 11. XXE 注入
    SecurityRule(
        rule_id="XXE001",
        category="xxe_injection",
        severity="HIGH",
        confidence=0.85,
        pattern=r'(?:etree\.parse\s*\(|etree\.fromstring\s*\(|'
                r'xml\.dom\.minidom\.parse|minidom\.parseString|'
                r'etree\.XMLParser\s*\(\s*\))',
        message="XML 解析未禁用外部实体，存在 XXE 注入风险",
        recommendation="使用 defusedxml 库或显式禁用 DTD/外部实体加载",
        exclude_patterns=[r'defusedxml', r'no_network', r'resolve_entities.*False'],
    ),

    # 12. SSRF 服务端请求伪造
    SecurityRule(
        rule_id="SSRF001",
        category="ssrf",
        severity="MEDIUM",
        confidence=0.8,
        pattern=r'(?:requests\.(?:get|post|put|delete|head|patch)\s*\(\s*(?:request|params|args|user|input)|'
                r'urllib\.request\.urlopen\s*\(\s*(?:request|params|args|user|input)|'
                r'httpx\.(?:get|post)\s*\(\s*(?:request|params|args|user|input))',
        message="HTTP 请求 URL 来自用户输入，存在 SSRF 风险",
        recommendation="验证 URL 白名单（协议/域名/IP），阻止内网地址（127.0.0.1, 10.x, 192.168.x）",
        exclude_patterns=[r'validate_url', r'allowed_domains', r'url_whitelist'],
    ),

    # 13. 敏感数据日志
    SecurityRule(
        rule_id="LOG001",
        category="data_exposure",
        severity="MEDIUM",
        confidence=0.8,
        pattern=r'(?:log(?:ger)?\.\w+\s*\(.*?(?:password|secret|token|credit_card|'
                r'ssn|social_security|private_key|api_key)|'
                r'print\s*\(.*?(?:password|secret|token|api_key))',
        message="日志/打印输出可能包含敏感数据（密码/Token/密钥）",
        recommendation="脱敏后再记录日志，使用结构化日志并过滤敏感字段",
        exclude_patterns=[r'#.*log', r'test_.*\.py', r'redact', r'mask'],
    ),

    # 14. CORS 配置不当
    SecurityRule(
        rule_id="CORS001",
        category="cors_misconfiguration",
        severity="MEDIUM",
        confidence=0.85,
        pattern=r'(?:Access-Control-Allow-Origin.*\*|'
                r'CORSMiddleware.*allow_origins\s*=\s*\["\*"\]|'
                r'allow_credentials\s*=\s*True.*allow_origins\s*=\s*\["\*"\]|'
                r'CORS_ORIGIN_ALLOW_ALL\s*=\s*True)',
        message="CORS 配置过于宽松（允许所有来源 + 凭证）",
        recommendation="限制 allow_origins 为具体域名列表，避免通配符 + credentials 组合",
    ),

    # 15. 不安全的临时文件
    SecurityRule(
        rule_id="TMP001",
        category="insecure_tempfile",
        severity="LOW",
        confidence=0.8,
        pattern=r'(?:tempfile\.mktemp\s*\(|'
                r'open\s*\(\s*["\']\/tmp\/|'
                r'NamedTemporaryFile\s*\(\s*delete\s*=\s*False)',
        message="使用不安全的临时文件操作（可预测路径/未自动删除）",
        recommendation="使用 tempfile.mkstemp() 或 tempfile.TemporaryFile()，确保自动清理",
    ),

    # 16. 正则拒绝服务 (ReDoS)
    SecurityRule(
        rule_id="REDOS001",
        category="regex_dos",
        severity="LOW",
        confidence=0.75,
        pattern=r're\.compile\s*\(\s*["\'].*?\(.*?\+.*?\)*|'
                r're\.(?:match|search|findall)\s*\(\s*["\'].*?\(.*?\+.*?\)*',
        message="正则表达式包含嵌套量词，可能导致 ReDoS 拒绝服务",
        recommendation="使用 re2 或检查正则复杂度，避免嵌套量词 (a+)+",
    ),
]


# ── 误报排除 ──────────────────────────────────────────────

# 硬排除规则：匹配这些模式的发现直接丢弃
HARD_EXCLUSIONS = [
    r'test_.*\.py$',          # 测试文件
    r'_test\.py$',
    r'\.test\.(?:js|ts)$',
    r'spec\.(?:js|ts)$',
    r'__tests__/',
    r'\.md$',                  # 文档文件
    r'\.rst$',
    r'\.txt$',
    r'conftest\.py$',
    r'fixture',
    r'mock',
    r'factory',
]


def _is_excluded_file(filepath: str) -> bool:
    """检查文件是否在排除列表中"""
    for pattern in HARD_EXCLUSIONS:
        if re.search(pattern, filepath, re.IGNORECASE):
            return True
    return False


def _should_exclude_finding(finding: SecurityFinding, rule: SecurityRule) -> bool:
    """检查单个发现是否应被排除（误报过滤）"""
    # 规则级别的排除
    for pattern in rule.exclude_patterns:
        if re.search(pattern, finding.code_snippet, re.IGNORECASE):
            return True
    # 文件级别排除
    if _is_excluded_file(finding.file):
        return True
    return False


# ── 核心扫描引擎 ──────────────────────────────────────────

class SecurityScanner:
    """安全漏洞扫描器"""

    def __init__(self, rules: List[SecurityRule] = None,
                 min_confidence: float = 0.7,
                 min_severity: str = "LOW"):
        self.rules = rules or SECURITY_RULES
        self.min_confidence = min_confidence
        self.severity_levels = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        self.min_severity_val = self.severity_levels.get(min_severity, 1)

    def scan_diff(self, diff: str) -> List[SecurityFinding]:
        """扫描 diff 输出，返回安全发现列表"""
        findings = []
        current_file = ""
        line_number = 0

        for raw_line in diff.splitlines():
            # 追踪当前文件
            if raw_line.startswith("diff --git"):
                parts = raw_line.split(" b/")
                if len(parts) > 1:
                    current_file = parts[-1]
                continue

            # 追踪行号
            if raw_line.startswith("@@"):
                match = re.search(r'\+(\d+)', raw_line)
                if match:
                    line_number = int(match.group(1))
                continue

            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                content = raw_line[1:]

                # 对每条规则检查
                for rule in self.rules:
                    if rule.confidence < self.min_confidence:
                        continue
                    sev_val = self.severity_levels.get(rule.severity, 0)
                    if sev_val < self.min_severity_val:
                        continue

                    if re.search(rule.pattern, content, re.IGNORECASE):
                        finding = SecurityFinding(
                            file=current_file,
                            line=line_number,
                            severity=rule.severity,
                            category=rule.category,
                            message=rule.message,
                            code_snippet=content.strip(),
                            confidence=rule.confidence,
                            recommendation=rule.recommendation,
                        )
                        # 误报过滤
                        if not _should_exclude_finding(finding, rule):
                            findings.append(finding)

            if not raw_line.startswith("---"):
                line_number += 1

        return findings

    def scan_file_content(self, filepath: str, content: str) -> List[SecurityFinding]:
        """扫描单个文件内容"""
        findings = []
        if _is_excluded_file(filepath):
            return findings

        for line_num, line in enumerate(content.splitlines(), 1):
            for rule in self.rules:
                if rule.confidence < self.min_confidence:
                    continue
                if re.search(rule.pattern, line, re.IGNORECASE):
                    finding = SecurityFinding(
                        file=filepath,
                        line=line_num,
                        severity=rule.severity,
                        category=rule.category,
                        message=rule.message,
                        code_snippet=line.strip(),
                        confidence=rule.confidence,
                        recommendation=rule.recommendation,
                    )
                    if not _should_exclude_finding(finding, rule):
                        findings.append(finding)
        return findings


# ── Git 工具函数 ──────────────────────────────────────────

def _run_git(*args) -> str:
    """执行 git 命令"""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout
    except Exception as e:
        return f"(git error: {e})"


def _get_branch_diff(base: str = None) -> str:
    """获取分支差异"""
    if base:
        return _run_git("diff", f"{base}...")
    # 尝试 origin/HEAD, origin/main, origin/master
    for remote_base in ["origin/HEAD", "origin/main", "origin/master"]:
        diff = _run_git("diff", f"{remote_base}...")
        if diff.strip() and "error" not in diff.lower():
            return diff
    # fallback: 未提交变更
    return _run_git("diff") + "\n" + _run_git("diff", "--cached")


def _get_changed_files(diff: str) -> List[str]:
    """从 diff 提取变更文件列表"""
    files = []
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            if len(parts) > 1:
                files.append(parts[-1])
    return files


def _get_diff_stats(diff: str) -> Dict[str, int]:
    """统计 diff 信息"""
    files, additions, deletions = 0, 0, 0
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            files += 1
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return {"files": files, "additions": additions, "deletions": deletions}


# ── 报告生成 ──────────────────────────────────────────────

def generate_security_report(findings: List[SecurityFinding],
                             stats: Dict[str, int],
                             changed_files: List[str]) -> str:
    """生成安全审查 Markdown 报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("🔒 安全审查报告")
    lines.append("=" * 60)

    # 统计摘要
    high = sum(1 for f in findings if f.severity == "HIGH")
    medium = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")

    lines.append(f"\n📊 变更范围: {stats['files']} 文件, "
                 f"+{stats['additions']}/-{stats['deletions']}")
    lines.append(f"🔍 发现: {len(findings)} 个问题")
    lines.append(f"   🔴 HIGH: {high}  🟡 MEDIUM: {medium}  🔵 LOW: {low}")

    # 按类别统计
    categories = {}
    for f in findings:
        categories[f.category] = categories.get(f.category, 0) + 1
    if categories:
        lines.append(f"\n📋 类别分布:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            lines.append(f"   - {cat}: {count}")

    lines.append("")

    # 详细发现（按严重性排序）
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sorted_findings = sorted(findings, key=lambda f: (severity_order.get(f.severity, 9), -f.confidence))

    if not sorted_findings:
        lines.append("✅ 未发现安全漏洞！代码变更看起来是安全的。")
    else:
        for i, finding in enumerate(sorted_findings, 1):
            lines.append(finding.to_markdown(i))

    # 变更文件列表
    if changed_files:
        lines.append(f"\n📁 变更文件 ({len(changed_files)}):")
        for f in changed_files[:30]:
            lines.append(f"   - {f}")
        if len(changed_files) > 30:
            lines.append(f"   ... 及 {len(changed_files) - 30} 个更多文件")

    return "\n".join(lines)


# ── 命令处理函数 ──────────────────────────────────────────

def security_review_handler(args: list, loop=None) -> str:
    """
    安全审查当前分支的代码变更。

    用法:
        /security-review              — 审查分支所有变更
        /security-review --staged     — 仅审查暂存变更
        /security-review --high       — 仅显示 HIGH 严重性
        /security-review --base <ref> — 对比指定基准分支
        /security-review <file>       — 扫描指定文件
    """
    # 解析参数
    staged_only = "--staged" in args
    high_only = "--high" in args
    base_ref = None
    target_file = None

    for i, a in enumerate(args):
        if a == "--base" and i + 1 < len(args):
            base_ref = args[i + 1]
        elif not a.startswith("-"):
            target_file = a

    min_severity = "HIGH" if high_only else "LOW"

    # 创建扫描器
    scanner = SecurityScanner(min_confidence=0.75, min_severity=min_severity)

    # 获取变更并扫描
    if target_file:
        if not os.path.exists(target_file):
            return f"错误: 文件不存在: {target_file}"
        try:
            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            findings = scanner.scan_file_content(target_file, content)
            stats = {"files": 1, "additions": content.count("\n"), "deletions": 0}
            changed_files = [target_file]
        except Exception as e:
            return f"错误: 无法读取文件: {e}"
    elif staged_only:
        diff = _run_git("diff", "--cached")
        findings = scanner.scan_diff(diff)
        stats = _get_diff_stats(diff)
        changed_files = _get_changed_files(diff)
    else:
        diff = _get_branch_diff(base_ref)
        if not diff.strip() or "error" in diff.lower():
            # fallback to uncommitted changes
            diff = _run_git("diff") + "\n" + _run_git("diff", "--cached")
        findings = scanner.scan_diff(diff)
        stats = _get_diff_stats(diff)
        changed_files = _get_changed_files(diff)

    # 生成报告
    report = generate_security_report(findings, stats, changed_files)
    return report


# ── 注册命令 ──────────────────────────────────────────────

register_command("security-review", {
    "description": "安全漏洞扫描 — 审查分支变更中的安全问题(16类漏洞检测)",
    "handler": security_review_handler,
    "category": "analysis",
    "args_help": "[--staged] [--high] [--base <ref>] [file]  安全审查代码变更",
})
