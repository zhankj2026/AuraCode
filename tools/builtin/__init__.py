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

# Built-in tools
from . import read_file
from . import write_file
from . import run_command
from . import list_directory

# Phase 1
from . import grep
from . import find
from . import analyze_file

# Phase 2
from . import replace_in_file
from . import undo_edit

# Phase 3
from . import lint
from . import run_tests

# Phase 6
from . import subagent

# Plan Agent
from . import plan_agent

# Skill Tools
from . import skill_tools

# Memory Tools
from . import memory_tools

# ── 新增工具（按优先级）──

# 1. Glob - Glob 模式文件搜索
from . import glob_tool

# 2. WebFetch - 网页内容获取与分析
from . import web_fetch

# 3. WebSearch - 网络搜索
from . import web_search

# 4. TodoWrite - 任务进度跟踪
from . import todo_write

# 5. AskUser - 向用户提问
from . import ask_user

# 6. PowerShell - Windows PowerShell 执行
from . import run_powershell

# 7. PlanMode - 计划模式状态机
from . import plan_mode

# 8. LSP - 代码智能（Language Server Protocol）
from . import lsp_tool

# ── 高优先级工具（上下文管理增强）──

# 9. ToolSearch - 工具发现与搜索
from . import tool_search

# 10. Sleep - 等待/延迟
from . import sleep_tool

# 11. Config - 环境配置读写
from . import config_tool

# 12. NotebookEdit - Jupyter Notebook 编辑
from . import notebook_edit

# ── ContextCollapse + 工具丰富度提升 ──

# 13. REPL - 交互式 Python REPL
from . import repl_tool

# 14. TaskManager - 结构化任务管理（create/update/list）
from . import task_manager

# 15. Brief - 简洁模式切换
from . import brief_tool

# ── Phase 4: Worktree + 定时任务 ──

# 16. Worktree - Git Worktree 隔离工作区
from . import worktree_tool

# 17. Cron - 定时任务调度
from . import cron_tool

