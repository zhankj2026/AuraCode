"""
AskUserQuestion 工具 - 向用户提出多项选择题

参考 AskUserQuestionTool 设计：
- LLM 主动向用户提问（收集偏好/澄清需求/获取决策）
- 支持单选和多选模式
- 用户可选择预设选项或输入自定义文本
- 支持 CLI 模式和 Bridge 远程模式（回调机制）
"""

import sys
import threading
import logging
from typing import List, Dict, Any, Optional, Callable

from tools.registry import register_tool

logger = logging.getLogger(__name__)

# ── 全局回调（Bridge 模式使用） ────────────────────────────────────────────────────

_ask_user_callback: Optional[Callable] = None
_callback_lock = threading.Lock()


def set_ask_user_callback(callback: Callable):
    """
    注册全局用户询问回调（Bridge 远程模式使用）。

    回调函数签名: callback(question: str, options: list, multi_select: bool) -> str
    返回值: 用户选择的选项标签或自定义文本
    """
    global _ask_user_callback
    with _callback_lock:
        _ask_user_callback = callback


def clear_ask_user_callback():
    global _ask_user_callback
    with _callback_lock:
        _ask_user_callback = None


def _get_ask_user_callback() -> Optional[Callable]:
    with _callback_lock:
        return _ask_user_callback


# ── CLI 模式实现 ──────────────────────────────────────────────────────────────────

def _ask_user_cli(
    question: str,
    options: List[Dict[str, str]],
    multi_select: bool = False,
) -> str:
    """
    CLI 模式：通过 stdin 询问用户。
    阻塞等待用户输入。
    """
    print(f"\n{'─' * 60}")
    print(f"❓ {question}")
    print(f"{'─' * 60}")

    mode_hint = "（可多选，用逗号分隔序号）" if multi_select else "（单选）"
    print(f"  {mode_hint}\n")

    for i, opt in enumerate(options, 1):
        label = opt.get("label", f"选项{i}")
        desc = opt.get("description", "")
        print(f"  [{i}] {label}")
        if desc:
            print(f"      {desc}")

    print(f"\n  [0] 其他（输入自定义文本）")

    try:
        while True:
            prompt_text = "\n请选择" + ("（多个用逗号分隔）" if multi_select else "") + ": "
            try:
                user_input = input(prompt_text).strip()
            except EOFError:
                return "(用户未响应)"

            if not user_input:
                print("  请输入选项序号")
                continue

            if user_input == "0":
                try:
                    custom = input("请输入自定义内容: ").strip()
                except EOFError:
                    custom = ""
                return custom or "(用户取消)"

            # 解析输入
            if multi_select:
                parts = [p.strip() for p in user_input.split(",")]
                selections = []
                valid = True
                for part in parts:
                    try:
                        idx = int(part) - 1
                        if 0 <= idx < len(options):
                            selections.append(options[idx].get("label", ""))
                        else:
                            print(f"  序号 {part} 超出范围")
                            valid = False
                            break
                    except ValueError:
                        print(f"  '{part}' 不是有效序号")
                        valid = False
                        break
                if valid and selections:
                    return ", ".join(selections)
                continue
            else:
                try:
                    idx = int(user_input) - 1
                    if 0 <= idx < len(options):
                        return options[idx].get("label", "")
                    else:
                        print(f"  序号超出范围（1-{len(options)}）")
                except ValueError:
                    print("  请输入数字序号")

    except Exception as e:
        return f"(交互错误: {e})"


# ── 主处理函数 ──────────────────────────────────────────────────────────────────

def ask_user_handler(
    question: str,
    options: List[Dict[str, str]],
    multi_select: bool = False,
) -> str:
    """
    向用户提出多项选择题。

    LLM 使用此工具在以下场景：
    1. 收集用户偏好或需求
    2. 澄清模糊指令
    3. 在工作过程中获取决策
    4. 向用户提供方向选择

    Args:
        question: 问题文本（清晰、具体、以问号结尾）
        options: 选项列表，每项含:
            - label: 选项显示标签（简短，1-5 词）
            - description: 选项说明（可选）
        multi_select: 是否允许多选（默认 false）

    Returns:
        用户选择的选项标签（或自定义文本）
    """
    if not question:
        return "错误: question 不能为空"

    if not options:
        return "错误: options 不能为空，至少提供 2 个选项"

    if len(options) < 2:
        return "错误: options 至少需要 2 个选项"

    # 验证选项格式
    for i, opt in enumerate(options):
        if not isinstance(opt, dict):
            return f"错误: options[{i}] 必须是字典"
        if not opt.get("label"):
            return f"错误: options[{i}].label 不能为空"

    # 优先使用回调（Bridge 模式）
    callback = _get_ask_user_callback()
    if callback is not None:
        try:
            result = callback(question, options, multi_select)
            return f"用户选择: {result}"
        except Exception as e:
            logger.warning(f"Bridge 回调失败，降级到 CLI: {e}")

    # CLI 模式
    user_response = _ask_user_cli(question, options, multi_select)
    return f"用户选择: {user_response}"


register_tool("ask_user", {
    "description": (
        "Ask the user a multiple-choice question to gather information.\n"
        "Use for:\n"
        "1. Collecting user preferences or requirements\n"
        "2. Clarifying ambiguous instructions\n"
        "3. Getting implementation decisions during work\n"
        "4. Offering directional choices to the user\n"
        "Users can always select 'Other' for custom input.\n"
        "Put recommended option first with '(Recommended)' suffix in the label."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Clear, specific question (end with '?')"
            },
            "options": {
                "type": "array",
                "description": "Option list (2-4 options)",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "Option label (concise, 1-5 words)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Option explanation (optional)"
                        }
                    },
                    "required": ["label"]
                },
                "minItems": 2,
                "maxItems": 4
            },
            "multi_select": {
                "type": "boolean",
                "description": "Allow multiple selections (default: false)",
                "default": False
            }
        },
        "required": ["question", "options"]
    },
    "handler": ask_user_handler,
    "permission_level": "read"
})
