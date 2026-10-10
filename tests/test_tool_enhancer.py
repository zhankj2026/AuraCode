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
ToolEnhancer 测试 — read_file 豁免 / 区间采样裁剪 / 配置覆盖

背景（demo8 会话日志 llm_25911457）: 617 行中文设计文档被三层
串联裁剪（tool_executor 预截断 → Trimmer 关键行过滤 → Summarizer
文件摘要）砍到 40 行，模型被迫分 4 次分段重读同一文件。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name, cond, err=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {err}")


print("=" * 60)
print("ToolEnhancer: read_file 豁免 + 区间采样裁剪")
print("=" * 60)

# ------------------------------------------------------------
# 1. 模块可导入 + 单例
# ------------------------------------------------------------
from core.tool_enhancer import (  # noqa: E402
    ToolEnhancer, ToolOutputTrimmer, get_tool_enhancer,
)

enhancer = get_tool_enhancer()
check("get_tool_enhancer 单例", get_tool_enhancer() is enhancer)
check("默认豁免参数加载",
      enhancer.read_file_exempt_lines == 2000
      and enhancer.read_file_exempt_chars == 32768)

# ------------------------------------------------------------
# 2. read_file 豁免：617 行中文文档全文返回（demo8 场景复现）
# ------------------------------------------------------------
chinese_doc = "\n".join(f"游戏设定第{i}行：玩家操纵雷电战机。" for i in range(1, 618))
assert len(chinese_doc.splitlines()) == 617
out = enhancer.process_tool_result("read_file", chinese_doc)
check("617 行中文文档 read_file 全文返回", out == chinese_doc,
      f"{len(out)} vs {len(chinese_doc)} chars")

# 英文代码文件（500 行，豁免线内）
code_doc = "\n".join(f"def func_{i}(): return {i}" for i in range(500))
check("500 行代码文件全文返回",
      enhancer.process_tool_result("read_file", code_doc) == code_doc)

# ------------------------------------------------------------
# 3. 超限 read_file：区间采样 + 显式省略标注
# ------------------------------------------------------------
big_doc = "\n".join(f"数据行 {i}：内容" for i in range(1, 2501))
sampled = enhancer.process_tool_result("read_file", big_doc)
check("超限读取被采样", len(sampled.splitlines()) <= 520,
      f"{len(sampled.splitlines())} 行")
check("包含省略区间标注（可分段补读）", "已省略第" in sampled and "分段读取" in sampled)
check("保留首段内容", "数据行 1：" in sampled)
check("保留尾段内容", "数据行 2500：" in sampled)

# ------------------------------------------------------------
# 4. 关键行密集路径回归：代码/日志输出仍走关键行策略
# ------------------------------------------------------------
code_output = "\n".join(
    f"import mod{i}" if i % 5 == 0 else f"print({i})" for i in range(800)
)
trimmed = enhancer.process_tool_result("run_command", code_output)
check("代码类长输出仍被裁剪", len(trimmed) < len(code_output))
check("代码类输出保留关键行（import）", "import mod" in trimmed)
check("关键行策略标注", "[输出已裁剪:" in trimmed)

# ------------------------------------------------------------
# 5. 混合场景：稀疏但存在错误行 → 采样并附加关键行
# ------------------------------------------------------------
mixed = "\n".join(
    "Error: disk full on device" if i == 700 else f"普通输出 {i}"
    for i in range(1, 1201)
)
mixed_out = enhancer.process_tool_result("run_command", mixed)
check("稀疏错误行被附加保留", "Error: disk full" in mixed_out)

# ------------------------------------------------------------
# 6. 自定义参数
# ------------------------------------------------------------
custom = ToolEnhancer(read_file_exempt_lines=10, read_file_exempt_chars=100)
medium = "\n".join(f"line {i}" for i in range(600))  # > 裁剪线 500
check("自定义豁免线生效（超限被采样）",
      custom.process_tool_result("read_file", medium) != medium)

tiny = ToolOutputTrimmer(max_lines=50)
check("Trimmer max_lines 参数生效",
      len(tiny.trim("\n".join(f"x{i}" for i in range(200))).splitlines()) <= 60)

# ------------------------------------------------------------
# 7. 短结果/空结果回归
# ------------------------------------------------------------
check("短结果原样返回", enhancer.process_tool_result("run_command", "ok") == "ok")
check("空结果原样返回", enhancer.process_tool_result("read_file", "") == "")

# ------------------------------------------------------------
# 8. 集成：tool_executor 不再有硬编码预截断层（单一裁剪来源）
# ------------------------------------------------------------
import inspect  # noqa: E402
from core.loop import tool_executor  # noqa: E402

src = inspect.getsource(tool_executor)
check("tool_executor 已移除硬编码预截断层",
      "截断 {len(lines) - 500} 行" not in src)
check("tool_executor 仍走 ToolEnhancer", "process_tool_result" in src)

# ------------------------------------------------------------
# 9. 配置键（config.yaml 默认值与代码一致）
# ------------------------------------------------------------
try:
    import yaml  # noqa: E402
    with open(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "config.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    tools_cfg = cfg.get("tools", {})
    check("config.yaml tools.read_file_exempt_lines=2000",
          tools_cfg.get("read_file_exempt_lines") == 2000)
    check("config.yaml tools.output_max_lines=500",
          tools_cfg.get("output_max_lines") == 500)
except ImportError:
    print("  (跳过 config.yaml 校验: 未安装 pyyaml)")

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"测试完成: {PASS}/{total} 通过, {FAIL} 失败")
if FAIL > 0:
    print("⚠️ 有测试失败!")
    sys.exit(1)
print("🎉 全部通过!")
sys.exit(0)
