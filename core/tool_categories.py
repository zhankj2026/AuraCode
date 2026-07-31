#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.tool_categories — 工具分类的单一来源

工具的「读 / 写 / 执行」分类原先散落在 6+ 处各自硬编码,且命名不一致:
    - tool_executor 写工具集用了不存在的 "edit_file" / "search_replace",
      导致 replace_in_file 漏掉自动验证(project_root 注入因 handler 不接受
      该参数,本就不应覆盖 replace_in_file)。
    - file_tracker / context_manager 各自维护 {write_file, replace_in_file}。

本模块提供权威分类,各处统一引用,消除「同名工具在不同地方写法不同」的
隐患。注意不同概念用不同集合:
    FILE_WRITE_TOOLS            修改文件的工具(→ 自动验证/历史备份/写追踪/
                                输入清理)
    PROJECT_ROOT_INJECT_TOOLS   handler 签名接受 project_root 的写入工具
                                (仅 write_file;replace_in_file 不接受)
    COMMAND_EXEC_TOOLS          shell 执行(→ 注入 working_directory + env)
    SEARCH_TOOLS                搜索(→ 注入 project_root 解析相对路径)

PARALLEL_SAFE_TOOLS(tool_dispatcher)与 MICROCOMPACT_CLEARABLE_TOOLS
(context_manager)是「可并行」「结果可丢弃」的独立语义,不在此合并。
"""

# 修改文件内容的工具
FILE_WRITE_TOOLS = frozenset({
    "write_file",
    "replace_in_file",
})

# handler 签名接受 project_root 参数的写入工具
# (write_file 需要;replace_in_file_handler 仅接受 path/old_text/new_text,
#  注入 project_root 会导致 handler(**arguments) TypeError)
PROJECT_ROOT_INJECT_TOOLS = frozenset({
    "write_file",
})

# 命令执行类工具(注入 working_directory + 会话环境脚本)
COMMAND_EXEC_TOOLS = frozenset({
    "run_command",
    "run_powershell",
})

# 搜索类工具(注入 project_root 用于解析相对路径)
SEARCH_TOOLS = frozenset({
    "glob",
    "grep",
})
