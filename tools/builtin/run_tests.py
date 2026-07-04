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
run_tests 工具 - 运行测试套件

基于 code.md Phase 3 实现
参考: 第 5.2 节
"""

import os
import re
import subprocess
from tools.registry import register_tool


def _detect_test_framework(project_root: str = '.') -> str:
    """
    自动检测测试框架
    
    Args:
        project_root: 项目根目录
    
    Returns:
        框架名称: pytest/jest/unittest/unknown
    """
    # 检查 pytest
    if os.path.exists(os.path.join(project_root, 'pytest.ini')):
        return 'pytest'
    
    if os.path.exists(os.path.join(project_root, 'pyproject.toml')):
        with open(os.path.join(project_root, 'pyproject.toml'), 'r', encoding='utf-8') as f:
            content = f.read()
            if '[tool.pytest' in content:
                return 'pytest'
    
    # 检查 jest
    if os.path.exists(os.path.join(project_root, 'jest.config.js')):
        return 'jest'
    
    if os.path.exists(os.path.join(project_root, 'jest.config.ts')):
        return 'jest'
    
    if os.path.exists(os.path.join(project_root, 'package.json')):
        with open(os.path.join(project_root, 'package.json'), 'r', encoding='utf-8') as f:
            content = f.read()
            if '"jest"' in content or '@jest/' in content:
                return 'jest'
    
    # 检查 tests 目录结构
    tests_dir = os.path.join(project_root, 'tests')
    if os.path.exists(tests_dir):
        # 如果有 test_*.py 或 *_test.py 文件,使用 pytest
        for root, dirs, files in os.walk(tests_dir):
            for file in files:
                if file.startswith('test_') or file.endswith('_test.py'):
                    return 'pytest'
    
    # 默认尝试 pytest
    return 'pytest'


def _parse_test_output(output: str, framework: str) -> dict:
    """
    解析测试输出,提取统计信息
    
    Args:
        output: 测试输出文本
        framework: 测试框架名称
    
    Returns:
        统计信息字典
    """
    stats = {
        'passed': 0,
        'failed': 0,
        'skipped': 0,
        'errors': 0,
        'total': 0,
    }
    
    if framework == 'pytest':
        # pytest 输出示例: "10 passed, 2 failed, 1 skipped in 1.23s"
        passed_match = re.search(r'(\d+) passed', output)
        failed_match = re.search(r'(\d+) failed', output)
        skipped_match = re.search(r'(\d+) skipped', output)
        error_match = re.search(r'(\d+) error', output)
        
        if passed_match:
            stats['passed'] = int(passed_match.group(1))
        if failed_match:
            stats['failed'] = int(failed_match.group(1))
        if skipped_match:
            stats['skipped'] = int(skipped_match.group(1))
        if error_match:
            stats['errors'] = int(error_match.group(1))
        
        stats['total'] = stats['passed'] + stats['failed'] + stats['skipped']
    
    elif framework == 'jest':
        # jest 输出示例: "Tests:       10 passed, 12 total"
        passed_match = re.search(r'(\d+) passed', output)
        total_match = re.search(r'(\d+) total', output)
        failed_match = re.search(r'(\d+) failed', output)
        
        if passed_match:
            stats['passed'] = int(passed_match.group(1))
        if total_match:
            stats['total'] = int(total_match.group(1))
        if failed_match:
            stats['failed'] = int(failed_match.group(1))
        
        stats['skipped'] = stats['total'] - stats['passed'] - stats['failed']
    
    elif framework == 'unittest':
        # unittest 输出示例: "Ran 10 tests in 1.234s"
        total_match = re.search(r'Ran (\d+) tests', output)
        failed_match = re.search(r'failures=(\d+)', output)
        error_match = re.search(r'errors=(\d+)', output)
        
        if total_match:
            stats['total'] = int(total_match.group(1))
        if failed_match:
            stats['failed'] = int(failed_match.group(1))
        if error_match:
            stats['errors'] = int(error_match.group(1))
        
        stats['passed'] = stats['total'] - stats['failed'] - stats['errors']
    
    return stats


def run_tests_handler(
    test_path: str = None,
    framework: str = None,
    failed_only: bool = False,
    verbose: bool = False
) -> str:
    """
    运行测试套件
    
    Args:
        test_path: 测试文件或目录路径,默认自动检测
        framework: 测试框架(pytest/jest/unittest),默认自动检测
        failed_only: 只运行上次失败的测试
        verbose: 是否输出详细日志
    
    Returns:
        测试结果和统计信息
    """
    try:
        # 自动检测框架
        if not framework:
            framework = _detect_test_framework()
        
        # 构建命令
        if framework == 'pytest':
            cmd = ['pytest']
            
            if test_path:
                cmd.append(test_path)
            else:
                cmd.append('.')
            
            if failed_only:
                cmd.append('--last-failed')
            
            if verbose:
                cmd.append('-v')
            else:
                cmd.append('--tb=short')
        
        elif framework == 'jest':
            cmd = ['npx', 'jest']
            
            if test_path:
                cmd.append(test_path)
            
            if failed_only:
                cmd.append('--onlyFailures')
            
            if verbose:
                cmd.append('--verbose')
            else:
                cmd.append('--silent')
        
        elif framework == 'unittest':
            cmd = ['python', '-m', 'unittest', 'discover']
            
            if test_path:
                if os.path.isfile(test_path):
                    # 单个文件
                    cmd = ['python', '-m', 'unittest', test_path]
                else:
                    cmd = ['python', '-m', 'unittest', 'discover', '-s', test_path]
            
            if verbose:
                cmd.append('-v')
        
        else:
            return f"❌ 不支持的测试框架: {framework}\n\n支持的框架: pytest, jest, unittest"
        
        # 执行测试
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=os.getcwd()
        )
        
        output = result.stdout or result.stderr
        
        # 解析统计
        stats = _parse_test_output(output, framework)
        
        # 格式化输出
        lines = []
        lines.append(f"测试框架: {framework}")
        lines.append(f"测试路径: {test_path or '.'}")
        lines.append("")
        
        # 统计信息
        lines.append("测试结果:")
        if stats['total'] > 0:
            lines.append(f"  ✅ 通过: {stats['passed']}")
            if stats['failed'] > 0:
                lines.append(f"  ❌ 失败: {stats['failed']}")
            if stats['skipped'] > 0:
                lines.append(f"  ⏭️  跳过: {stats['skipped']}")
            if stats['errors'] > 0:
                lines.append(f"  💥 错误: {stats['errors']}")
            lines.append(f"  📊 总计: {stats['total']}")
        else:
            lines.append("  未找到测试用例")
        
        lines.append("")
        
        # 详细输出
        if output:
            # 限制输出长度
            test_output = output.strip()
            if len(test_output) > 3000:
                test_output = test_output[:3000]
                test_output += "\n\n... (输出过长,已截断)"
            
            lines.append("详细输出:")
            lines.append(test_output)
        
        result_text = "\n".join(lines)
        
        # 返回状态
        if result.returncode == 0:
            return f"✅ 所有测试通过\n\n{result_text}"
        else:
            return f"❌ 测试失败\n\n{result_text}"
    
    except subprocess.TimeoutExpired:
        return f"❌ 测试执行超时(120秒)\n\n框架: {framework or 'auto'}\n路径: {test_path or '.'}"
    
    except FileNotFoundError as e:
        tool_name = framework or 'pytest'
        return f"❌ 未找到测试工具: {tool_name}\n\n请先安装:\n- pytest: pip install pytest\n- jest: npm install -g jest"
    
    except Exception as e:
        return f"❌ 测试执行失败\n\n错误: {str(e)}"


# 注册工具
register_tool("run_tests", {
    "description": "运行测试套件(pytest/jest/unittest),支持失败重跑",
    "parameters": {
        "type": "object",
        "properties": {
            "test_path": {
                "type": "string",
                "description": "测试文件或目录路径"
            },
            "framework": {
                "type": "string",
                "description": "测试框架(pytest/jest/unittest),默认自动检测",
                "enum": ["pytest", "jest", "unittest"]
            },
            "failed_only": {
                "type": "boolean",
                "description": "只运行上次失败的测试",
                "default": False
            },
            "verbose": {
                "type": "boolean",
                "description": "是否输出详细日志",
                "default": False
            }
        },
        "required": []
    },
    "handler": run_tests_handler,
    "permission_level": "execute"
})
