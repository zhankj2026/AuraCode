"""
NotebookEdit 工具 - Jupyter Notebook 编辑

参考 NotebookEditTool 设计，支持对 .ipynb 文件进行
单元格级别的编辑、插入、删除操作，无需整体重写整个 notebook。
"""

import json
import os
from typing import Optional, List, Dict, Any
from tools.registry import register_tool


def _load_notebook(path: str) -> Dict[str, Any]:
    """加载 notebook 文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_notebook(path: str, nb: Dict[str, Any]):
    """保存 notebook 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)


def _cell_summary(cell: Dict, idx: int) -> str:
    """单元格摘要"""
    cell_type = cell.get("cell_type", "?")
    source = "".join(cell.get("source", []))
    preview = source[:80].replace("\n", " ")
    if len(source) > 80:
        preview += "..."
    return f"[{idx}] {cell_type}: {preview}"


def notebook_edit_handler(
    file_path: str = "",
    action: str = "list",
    cell_index: int = -1,
    cell_type: str = "code",
    content: str = "",
    insert_after: int = -1,
) -> str:
    """
    编辑 Jupyter Notebook

    Args:
        file_path: .ipynb 文件路径
        action: 操作 (list/read/edit/insert/delete/clear_output)
        cell_index: 单元格索引（0-based，用于 read/edit/delete）
        cell_type: 单元格类型 (code/markdown/raw，用于 insert)
        content: 新内容（用于 edit/insert）
        insert_after: 在此单元格之后插入（-1 表示末尾，用于 insert）
    """
    if not file_path:
        return "错误: 需要提供 file_path 参数"

    if not os.path.exists(file_path):
        return f"文件不存在: {file_path}"

    if not file_path.endswith(".ipynb"):
        return f"不是 Notebook 文件: {file_path}"

    try:
        nb = _load_notebook(file_path)
    except (json.JSONDecodeError, IOError) as e:
        return f"加载 Notebook 失败: {e}"

    cells = nb.get("cells", [])

    if action == "list":
        if not cells:
            return f"Notebook 为空: {file_path}"
        output = f"Notebook: {file_path} ({len(cells)} 个单元格)\n\n"
        for i, cell in enumerate(cells):
            output += _cell_summary(cell, i) + "\n"
        return output

    if action == "read":
        if cell_index < 0 or cell_index >= len(cells):
            return f"无效的单元格索引: {cell_index}（共 {len(cells)} 个）"
        cell = cells[cell_index]
        source = "".join(cell.get("source", []))
        cell_type = cell.get("cell_type", "?")
        output = f"单元格 [{cell_index}] ({cell_type}):\n"
        output += "─" * 40 + "\n"
        output += source
        # 如果有输出
        outputs = cell.get("outputs", [])
        if outputs:
            output += "\n" + "─" * 40 + "\n"
            output += f"输出 ({len(outputs)} 个):\n"
            for out in outputs[:3]:  # 最多显示 3 个输出
                if "text" in out:
                    text = "".join(out["text"])[:500]
                    output += f"  {text}\n"
                elif "data" in out and "text/plain" in out["data"]:
                    text = "".join(out["data"]["text/plain"])[:500]
                    output += f"  {text}\n"
        return output

    if action == "edit":
        if cell_index < 0 or cell_index >= len(cells):
            return f"无效的单元格索引: {cell_index}（共 {len(cells)} 个）"
        if not content:
            return "错误: edit 操作需要提供 content 参数"
        # 按行分割，每行以 \n 结尾（notebook 格式）
        lines = content.split("\n")
        source_lines = [line + "\n" for line in lines[:-1]]
        if lines[-1]:  # 最后一行不加 \n
            source_lines.append(lines[-1])
        cells[cell_index]["source"] = source_lines
        # 清除该单元格的输出
        cells[cell_index]["outputs"] = []
        _save_notebook(file_path, nb)
        return f"已编辑单元格 [{cell_index}] ({cells[cell_index].get('cell_type', '?')})"

    if action == "insert":
        if not content:
            return "错误: insert 操作需要提供 content 参数"
        lines = content.split("\n")
        source_lines = [line + "\n" for line in lines[:-1]]
        if lines[-1]:
            source_lines.append(lines[-1])

        new_cell = {
            "cell_type": cell_type,
            "source": source_lines,
            "metadata": {},
        }
        if cell_type == "code":
            new_cell["outputs"] = []
            new_cell["execution_count"] = None

        # 插入位置
        if insert_after < 0 or insert_after >= len(cells):
            cells.append(new_cell)
            idx = len(cells) - 1
        else:
            idx = insert_after + 1
            cells.insert(idx, new_cell)

        _save_notebook(file_path, nb)
        return f"已插入 {cell_type} 单元格在位置 [{idx}]"

    if action == "delete":
        if cell_index < 0 or cell_index >= len(cells):
            return f"无效的单元格索引: {cell_index}（共 {len(cells)} 个）"
        removed = cells.pop(cell_index)
        _save_notebook(file_path, nb)
        summary = _cell_summary(removed, cell_index)
        return f"已删除单元格: {summary}"

    if action == "clear_output":
        if cell_index >= 0:
            # 清除指定单元格输出
            if cell_index < len(cells):
                cells[cell_index]["outputs"] = []
                cells[cell_index]["execution_count"] = None
                _save_notebook(file_path, nb)
                return f"已清除单元格 [{cell_index}] 的输出"
            return f"无效的单元格索引: {cell_index}"
        # 清除所有输出
        cleared = 0
        for cell in cells:
            if cell.get("cell_type") == "code":
                if cell.get("outputs"):
                    cell["outputs"] = []
                    cell["execution_count"] = None
                    cleared += 1
        _save_notebook(file_path, nb)
        return f"已清除 {cleared} 个代码单元格的输出"

    return f"未知操作: {action}（支持 list/read/edit/insert/delete/clear_output）"


register_tool("notebook_edit", {
    "description": (
        "Edit Jupyter Notebook (.ipynb) files. "
        "Supports list/read/edit/insert/delete/clear_output operations. "
        "Cell indices start from 0."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": ".ipynb file path",
            },
            "action": {
                "type": "string",
                "description": "Operation: list/read/edit/insert/delete/clear_output",
                "default": "list",
                "enum": ["list", "read", "edit", "insert", "delete", "clear_output"],
            },
            "cell_index": {
                "type": "integer",
                "description": "Cell index (0-based)",
                "default": -1,
            },
            "cell_type": {
                "type": "string",
                "description": "Cell type: code/markdown/raw (for insert)",
                "default": "code",
                "enum": ["code", "markdown", "raw"],
            },
            "content": {
                "type": "string",
                "description": "New content (for edit/insert)",
                "default": "",
            },
            "insert_after": {
                "type": "integer",
                "description": "Insert after this cell (-1 for end)",
                "default": -1,
            },
        },
        "required": ["file_path", "action"],
    },
    "handler": notebook_edit_handler,
    "permission_level": "write",
})
