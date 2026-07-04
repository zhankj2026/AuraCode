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
Code Validator - 代码验证器

自动验证代码修改的正确性，包括：
- 语法检查
- 类型检查（可选）
- 运行测试
- Lint 检查
"""

import os
import re
import subprocess
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_check(self, name: str, passed: bool, message: str = "", details: str = ""):
        """添加一个检查项"""
        self.checks.append({
            "name": name,
            "passed": passed,
            "message": message,
            "details": details
        })
        if not passed:
            self.errors.append(f"{name}: {message}")
    
    def add_warning(self, warning: str):
        """添加警告"""
        self.warnings.append(warning)
    
    def summary(self) -> str:
        """生成验证摘要"""
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        status = "✅ 通过" if self.passed else "❌ 失败"
        
        lines = [f"验证结果: {status} ({passed}/{total})"]
        
        for check in self.checks:
            icon = "✅" if check["passed"] else "❌"
            lines.append(f"  {icon} {check['name']}: {check['message']}")
        
        if self.warnings:
            lines.append(f"⚠️ {len(self.warnings)} 个警告")
        
        return "\n".join(lines)


class CodeValidator:
    """代码验证器"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self._detected_tools: Optional[Dict[str, str]] = None
    
    def detect_tools(self) -> Dict[str, str]:
        """检测项目中可用的验证工具"""
        if self._detected_tools is not None:
            return self._detected_tools
        
        tools = {}
        
        # Python 工具检测
        python_files = list(self.project_root.glob("**/*.py"))
        if python_files:
            # pytest
            if self._command_exists("pytest"):
                tools["pytest"] = "pytest"
            elif self._command_exists("python") and self._pip_has_package("pytest"):
                tools["pytest"] = "python -m pytest"
            
            # mypy
            if self._command_exists("mypy"):
                tools["mypy"] = "mypy"
            
            # ruff
            if self._command_exists("ruff"):
                tools["ruff"] = "ruff"
            elif self._file_exists("pyproject.toml") and self._toml_has_tool("ruff"):
                tools["ruff"] = "ruff"
            
            # flake8
            if self._command_exists("flake8"):
                tools["flake8"] = "flake8"
            
            # pylint
            if self._command_exists("pylint"):
                tools["pylint"] = "pylint"
        
        # JavaScript/TypeScript 工具检测
        js_files = list(self.project_root.glob("**/*.{js,ts,tsx,jsx}"))
        if js_files:
            # eslint
            if self._file_exists("node_modules/.bin/eslint") or self._command_exists("eslint"):
                tools["eslint"] = "eslint"
            
            # tsc (TypeScript)
            ts_files = list(self.project_root.glob("**/*.{ts,tsx}"))
            if ts_files and (self._file_exists("tsconfig.json") or self._command_exists("tsc")):
                tools["tsc"] = "tsc"
            
            # jest
            if self._file_exists("node_modules/.bin/jest") or self._command_exists("jest"):
                tools["jest"] = "jest"
        
        # 通用工具
        if self._command_exists("git"):
            tools["git"] = "git"
        
        self._detected_tools = tools
        logger.info(f"Detected validation tools: {list(tools.keys())}")
        return tools
    
    def validate(self, file_paths: Optional[List[str]] = None, run_tests: bool = True) -> ValidationResult:
        """
        执行完整验证
        
        Args:
            file_paths: 指定要验证的文件路径，None 表示全部
            run_tests: 是否运行测试
        
        Returns:
            ValidationResult
        """
        result = ValidationResult(passed=True)
        tools = self.detect_tools()
        
        # 1. 语法检查
        self._check_syntax(result, file_paths, tools)
        
        # 2. 类型检查（如果有工具）
        if "mypy" in tools or "tsc" in tools:
            self._check_types(result, file_paths, tools)
        
        # 3. Lint 检查
        self._check_lint(result, file_paths, tools)
        
        # 4. 运行测试
        if run_tests:
            self._run_tests(result, tools)
        
        # 判断总体结果
        result.passed = len(result.errors) == 0
        
        return result
    
    def _check_syntax(self, result: ValidationResult, file_paths: Optional[List[str]], tools: Dict):
        """语法检查"""
        if not file_paths:
            # 检查所有 Python 文件的语法
            py_files = list(self.project_root.glob("**/*.py"))
            py_files = [f for f in py_files if not self._is_ignored(f)]
            
            errors = []
            for f in py_files[:20]:  # 限制数量避免超时
                try:
                    compile(f.read_text(encoding='utf-8'), str(f), 'exec')
                except SyntaxError as e:
                    errors.append(f"{f.name}: {e}")
            
            if errors:
                result.add_check("Python 语法", False, f"{len(errors)} 个语法错误", "\n".join(errors[:5]))
            else:
                result.add_check("Python 语法", True, f"检查 {len(py_files)} 个文件")
    
    def _check_types(self, result: ValidationResult, file_paths: Optional[List[str]], tools: Dict):
        """类型检查"""
        if "mypy" in tools:
            cmd = tools["mypy"]
            if file_paths:
                cmd += " " + " ".join(file_paths)
            
            success, output = self._run_command(cmd)
            result.add_check(
                "类型检查 (mypy)",
                success,
                "通过" if success else "有类型错误",
                output[:500] if not success else ""
            )
        
        if "tsc" in tools:
            cmd = tools["tsc"] + " --noEmit"
            success, output = self._run_command(cmd)
            result.add_check(
                "类型检查 (tsc)",
                success,
                "通过" if success else "有类型错误",
                output[:500] if not success else ""
            )
    
    def _check_lint(self, result: ValidationResult, file_paths: Optional[List[str]], tools: Dict):
        """Lint 检查"""
        lint_tools = ["ruff", "flake8", "pylint", "eslint"]
        
        for tool in lint_tools:
            if tool in tools:
                cmd = tools[tool]
                if file_paths:
                    cmd += " " + " ".join(file_paths)
                else:
                    # 默认检查 src 或当前目录
                    if self._file_exists("src"):
                        cmd += " src/"
                
                success, output = self._run_command(cmd, timeout=30)
                
                # 有些工具返回非零但有输出也算通过（如警告）
                has_errors = not success and "error" in output.lower()
                
                result.add_check(
                    f"Lint ({tool})",
                    not has_errors,
                    "通过" if not has_errors else "有问题",
                    output[:300] if has_errors else ""
                )
                break  # 只用一个 lint 工具
    
    def _run_tests(self, result: ValidationResult, tools: Dict):
        """运行测试"""
        test_tools = ["pytest", "jest"]
        
        for tool in test_tools:
            if tool in tools:
                cmd = tools[tool]
                if tool == "pytest":
                    cmd += " -v --tb=short -x"  # 快速失败
                elif tool == "jest":
                    cmd += " --passWithNoTests"
                
                success, output = self._run_command(cmd, timeout=120)
                
                # 解析测试结果
                test_count = self._parse_test_count(output)
                
                result.add_check(
                    f"测试 ({tool})",
                    success,
                    f"{test_count}" if test_count else ("通过" if success else "失败"),
                    output[:500] if not success else ""
                )
                break
    
    def _command_exists(self, cmd: str) -> bool:
        """检查命令是否存在"""
        try:
            subprocess.run(
                ["which", cmd] if os.name != "nt" else ["where", cmd],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _pip_has_package(self, package: str) -> bool:
        """检查 pip 是否安装了包"""
        try:
            result = subprocess.run(
                ["pip", "show", package],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        return (self.project_root / path).exists()
    
    def _toml_has_tool(self, tool: str) -> bool:
        """检查 pyproject.toml 是否配置了工具"""
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding='utf-8')
            return f"[tool.{tool}]" in content
        return False
    
    def _is_ignored(self, path: Path) -> bool:
        """检查是否应该忽略该文件"""
        ignore_patterns = [
            "node_modules", ".git", "__pycache__", ".venv", "venv",
            "dist", "build", ".mypy_cache", ".pytest_cache"
        ]
        path_str = str(path)
        return any(p in path_str for p in ignore_patterns)
    
    def _run_command(self, cmd: str, timeout: int = 60) -> Tuple[bool, str]:
        """运行命令并返回结果"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"命令超时 ({timeout}s)"
        except Exception as e:
            return False, str(e)
    
    def _parse_test_count(self, output: str) -> str:
        """解析测试数量"""
        # pytest 格式: "5 passed, 2 failed"
        match = re.search(r"(\d+)\s+passed", output)
        if match:
            passed = match.group(1)
            failed_match = re.search(r"(\d+)\s+failed", output)
            failed = failed_match.group(1) if failed_match else "0"
            return f"{passed} 通过, {failed} 失败"
        
        # jest 格式: "Tests: 5 passed, 2 total"
        match = re.search(r"Tests:\s*(\d+)\s+passed", output)
        if match:
            return f"{match.group(1)} 通过"
        
        return ""


# 全局验证器实例
_validator: Optional[CodeValidator] = None


def get_validator(project_root: str = ".") -> CodeValidator:
    """获取全局验证器实例"""
    global _validator
    if _validator is None:
        _validator = CodeValidator(project_root)
    return _validator


def validate_code(file_paths: Optional[List[str]] = None, run_tests: bool = True) -> ValidationResult:
    """便捷函数：验证代码"""
    return get_validator().validate(file_paths, run_tests)
