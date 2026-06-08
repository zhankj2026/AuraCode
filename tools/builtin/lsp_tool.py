"""
LSP 工具 - Language Server Protocol 代码智能

参考 Claude Code LSPTool 设计，通过 LSP 协议与语言服务器交互：
- goToDefinition: 跳转定义
- findReferences: 查找引用
- hover: 悬停信息（类型、文档）
- documentSymbol: 文件符号列表
- workspaceSymbol: 工作区符号搜索
- goToImplementation: 跳转实现

支持的语言服务器（自动检测）：
- Python: pylsp (python-lsp-server) 或 pyright-langserver
- TypeScript/JavaScript: typescript-language-server
- 通用: 任意支持 stdio 的 LSP 服务器
"""

import os
import json
import subprocess
import threading
import logging
import time
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, quote
from pathlib import Path

from tools.registry import register_tool

logger = logging.getLogger(__name__)

# ── LSP 服务器管理 ────────────────────────────────────────────────────────────────

_LSP_SERVERS: Dict[str, Dict] = {}  # lang -> {process, root, initialized}
_LSP_LOCK = threading.Lock()
_LSP_REQUEST_ID = 0
_LSP_ID_LOCK = threading.Lock()


def _next_id() -> int:
    global _LSP_REQUEST_ID
    with _LSP_ID_LOCK:
        _LSP_REQUEST_ID += 1
        return _LSP_REQUEST_ID


def _path_to_uri(path: str) -> str:
    """将文件路径转换为 LSP file:// URI"""
    abs_path = os.path.abspath(path)
    # Windows 路径处理
    if os.name == 'nt':
        abs_path = abs_path.replace('\\', '/')
        if not abs_path.startswith('/'):
            abs_path = '/' + abs_path
    return f"file://{abs_path}"


def _uri_to_path(uri: str) -> str:
    """将 LSP URI 转换回文件路径"""
    if uri.startswith("file://"):
        path = uri[7:]
        if os.name == 'nt' and path.startswith('/'):
            path = path[1:]
        return path.replace('/', os.sep)
    return uri


# ── LSP 服务器配置 ────────────────────────────────────────────────────────────────

LSP_SERVER_CONFIGS = {
    "python": [
        {"command": ["pylsp"], "name": "pylsp"},
        {"command": ["pyright-langserver", "--stdio"], "name": "pyright"},
    ],
    "typescript": [
        {"command": ["typescript-language-server", "--stdio"], "name": "typescript-language-server"},
    ],
    "javascript": [
        {"command": ["typescript-language-server", "--stdio"], "name": "typescript-language-server"},
    ],
}


def _detect_language(file_path: str) -> str:
    """根据文件扩展名检测语言"""
    ext = os.path.splitext(file_path)[1].lower()
    lang_map = {
        '.py': 'python',
        '.pyi': 'python',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.mjs': 'javascript',
        '.cjs': 'javascript',
    }
    return lang_map.get(ext, '')


def _get_or_start_server(language: str, workspace_root: str) -> Optional[Dict]:
    """获取或启动对应语言的 LSP 服务器"""
    with _LSP_LOCK:
        if language in _LSP_SERVERS:
            server = _LSP_SERVERS[language]
            if server.get("process") and server["process"].poll() is None:
                return server
            # 进程已死，清理
            del _LSP_SERVERS[language]

    configs = LSP_SERVER_CONFIGS.get(language, [])
    for config in configs:
        try:
            proc = subprocess.Popen(
                config["command"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            server_info = {
                "process": proc,
                "name": config["name"],
                "root": workspace_root,
                "initialized": False,
                "language": language,
            }

            # 发送 initialize 请求
            init_params = {
                "processId": os.getpid(),
                "rootUri": _path_to_uri(workspace_root),
                "capabilities": {
                    "textDocument": {
                        "hover": {"contentFormat": ["plaintext"]},
                        "definition": {},
                        "references": {},
                        "documentSymbol": {},
                    },
                    "workspace": {
                        "symbol": {},
                    }
                }
            }

            init_result = _send_request(server_info, "initialize", init_params)
            if init_result is not None:
                # 发送 initialized 通知
                _send_notification(server_info, "initialized", {})
                server_info["initialized"] = True

                with _LSP_LOCK:
                    _LSP_SERVERS[language] = server_info

                logger.info(f"LSP 服务器启动: {config['name']} for {language}")
                return server_info

        except FileNotFoundError:
            logger.debug(f"LSP 服务器未找到: {config['command'][0]}")
            continue
        except Exception as e:
            logger.warning(f"LSP 服务器启动失败 ({config['name']}): {e}")
            continue

    return None


# ── LSP 通信 ──────────────────────────────────────────────────────────────────────

def _send_lsp_message(server: Dict, msg: Dict):
    """发送 LSP JSON-RPC 消息"""
    proc = server.get("process")
    if not proc or proc.poll() is not None:
        return

    body = json.dumps(msg)
    header = f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n"
    try:
        proc.stdin.write(header + body)
        proc.stdin.flush()
    except (OSError, BrokenPipeError) as e:
        logger.warning(f"LSP 写入失败: {e}")


def _read_lsp_message(server: Dict, timeout: float = 10.0) -> Optional[Dict]:
    """读取 LSP JSON-RPC 响应"""
    proc = server.get("process")
    if not proc or proc.poll() is not None:
        return None

    try:
        import select
        # 等待 stdout 有数据
        start = time.time()
        while time.time() - start < timeout:
            # 尝试读取 Content-Length 头
            line = ""
            try:
                proc.stdout.flush()
                line = proc.stdout.readline()
            except Exception:
                time.sleep(0.1)
                continue

            if not line:
                time.sleep(0.1)
                continue

            if line.strip() == "":
                continue

            if line.startswith("Content-Length:"):
                length = int(line.split(":")[1].strip())
                # 读取空行
                proc.stdout.readline()
                # 读取 body
                body = proc.stdout.read(length)
                return json.loads(body)

        return None

    except Exception as e:
        logger.warning(f"LSP 读取失败: {e}")
        return None


def _send_request(server: Dict, method: str, params: Dict, timeout: float = 10.0) -> Any:
    """发送 LSP 请求并等待响应"""
    req_id = _next_id()
    msg = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
    }
    _send_lsp_message(server, msg)

    # 读取响应（忽略通知）
    start = time.time()
    while time.time() - start < timeout:
        resp = _read_lsp_message(server, timeout=max(0.1, timeout - (time.time() - start)))
        if resp is None:
            break
        if resp.get("id") == req_id:
            if "error" in resp:
                err = resp["error"]
                logger.warning(f"LSP 错误: {err}")
                return None
            return resp.get("result")
        # 通知消息，继续读

    return None


def _send_notification(server: Dict, method: str, params: Dict):
    """发送 LSP 通知（无 id，无响应）"""
    msg = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
    }
    _send_lsp_message(server, msg)


def _open_document(server: Dict, file_path: str):
    """通知 LSP 服务器打开文档"""
    abs_path = os.path.abspath(file_path)
    uri = _path_to_uri(abs_path)
    try:
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        content = ""

    _send_notification(server, "textDocument/didOpen", {
        "textDocument": {
            "uri": uri,
            "languageId": server.get("language", "python"),
            "version": 1,
            "text": content,
        }
    })
    time.sleep(0.5)  # 等待服务器解析


# ── 格式化工具 ──────────────────────────────────────────────────────────────────────

def _format_location(loc: Dict) -> str:
    """格式化 LSP Location 为可读字符串"""
    uri = loc.get("uri", "")
    path = _uri_to_path(uri)
    range_info = loc.get("range", {})
    start = range_info.get("start", {})
    line = start.get("line", 0) + 1  # LSP 0-based → 1-based
    char = start.get("character", 0) + 1
    return f"{path}:{line}:{char}"


def _format_symbol(sym: Dict) -> str:
    """格式化 LSP Symbol"""
    name = sym.get("name", "")
    kind = sym.get("kind", 0)
    kind_names = {
        1: "File", 2: "Module", 3: "Namespace", 4: "Package",
        5: "Class", 6: "Method", 7: "Property", 8: "Field",
        9: "Constructor", 10: "Enum", 11: "Interface", 12: "Function",
        13: "Variable", 14: "Constant", 15: "String", 16: "Number",
        17: "Boolean", 18: "Array", 19: "Object", 20: "Key",
        21: "Null", 22: "EnumMember", 23: "Struct", 24: "Event",
        25: "Operator", 26: "TypeParameter",
    }
    kind_str = kind_names.get(kind, f"Kind({kind})")
    loc = sym.get("location", {})
    loc_str = _format_location(loc) if loc else ""
    return f"  [{kind_str}] {name}  {loc_str}"


# ── 主处理函数 ──────────────────────────────────────────────────────────────────

def lsp_handler(
    operation: str,
    file_path: str = "",
    line: int = 1,
    character: int = 1,
    query: str = "",
    workspace_root: str = ".",
) -> str:
    """
    通过 LSP 协议与语言服务器交互，获取代码智能功能。

    支持操作：
    - goToDefinition: 跳转到符号定义
    - findReferences: 查找符号的所有引用
    - hover: 获取悬停信息（类型、文档）
    - documentSymbol: 列出文件中的所有符号
    - workspaceSymbol: 在工作区搜索符号
    - goToImplementation: 跳转到接口/抽象方法的实现

    Args:
        operation: 操作类型
        file_path: 目标文件路径（workspaceSymbol 可选）
        line: 行号（1-based，如编辑器显示）
        character: 列号（1-based）
        query: 搜索关键词（仅 workspaceSymbol 使用）
        workspace_root: 工作区根目录

    Returns:
        操作结果
    """
    if not operation:
        return "错误: operation 不能为空"

    # 检测语言
    language = _detect_language(file_path) if file_path else "python"
    if not language:
        return f"错误: 无法识别文件 '{file_path}' 的语言类型"

    # 获取或启动 LSP 服务器
    server = _get_or_start_server(language, os.path.abspath(workspace_root))
    if not server:
        return (
            f"错误: 无法启动 {language} 的 LSP 服务器。\n"
            f"请安装对应的语言服务器:\n"
            f"  Python: pip install python-lsp-server\n"
            f"  TypeScript: npm install -g typescript-language-server\n"
            f"  或使用 pyright: pip install pyright"
        )

    abs_path = os.path.abspath(file_path) if file_path else ""
    uri = _path_to_uri(abs_path) if abs_path else ""
    # LSP 使用 0-based 行列
    lsp_line = max(0, line - 1)
    lsp_char = max(0, character - 1)

    try:
        if operation == "goToDefinition":
            _open_document(server, abs_path)
            result = _send_request(server, "textDocument/definition", {
                "textDocument": {"uri": uri},
                "position": {"line": lsp_line, "character": lsp_char},
            })
            if not result:
                return f"未找到定义: {file_path}:{line}:{character}"
            if isinstance(result, list):
                locations = [_format_location(loc) for loc in result]
                return f"定义位置:\n" + "\n".join(locations)
            return f"定义位置: {_format_location(result)}"

        elif operation == "findReferences":
            _open_document(server, abs_path)
            result = _send_request(server, "textDocument/references", {
                "textDocument": {"uri": uri},
                "position": {"line": lsp_line, "character": lsp_char},
                "context": {"includeDeclaration": True},
            })
            if not result:
                return f"未找到引用: {file_path}:{line}:{character}"
            locations = [_format_location(loc) for loc in result]
            return f"找到 {len(locations)} 个引用:\n" + "\n".join(locations)

        elif operation == "hover":
            _open_document(server, abs_path)
            result = _send_request(server, "textDocument/hover", {
                "textDocument": {"uri": uri},
                "position": {"line": lsp_line, "character": lsp_char},
            })
            if not result:
                return f"无悬停信息: {file_path}:{line}:{character}"
            contents = result.get("contents", "")
            if isinstance(contents, dict):
                return contents.get("value", str(contents))
            return str(contents)

        elif operation == "documentSymbol":
            _open_document(server, abs_path)
            result = _send_request(server, "textDocument/documentSymbol", {
                "textDocument": {"uri": uri},
            })
            if not result:
                return f"未找到符号: {file_path}"
            lines = [f"文件符号 ({len(result)} 个):"]
            for sym in result:
                lines.append(_format_symbol(sym))
            return "\n".join(lines)

        elif operation == "workspaceSymbol":
            if not query:
                return "错误: workspaceSymbol 需要提供 query 参数"
            result = _send_request(server, "workspace/symbol", {
                "query": query,
            })
            if not result:
                return f"未找到匹配 '{query}' 的符号"
            lines = [f"工作区符号搜索 '{query}' ({len(result)} 个):"]
            for sym in result[:50]:
                lines.append(_format_symbol(sym))
            if len(result) > 50:
                lines.append(f"... (还有 {len(result) - 50} 个)")
            return "\n".join(lines)

        elif operation == "goToImplementation":
            _open_document(server, abs_path)
            result = _send_request(server, "textDocument/implementation", {
                "textDocument": {"uri": uri},
                "position": {"line": lsp_line, "character": lsp_char},
            })
            if not result:
                return f"未找到实现: {file_path}:{line}:{character}"
            if isinstance(result, list):
                locations = [_format_location(loc) for loc in result]
                return f"实现位置:\n" + "\n".join(locations)
            return f"实现位置: {_format_location(result)}"

        else:
            return (
                f"错误: 未知操作 '{operation}'\n"
                f"支持的操作: goToDefinition, findReferences, hover, "
                f"documentSymbol, workspaceSymbol, goToImplementation"
            )

    except Exception as e:
        logger.error(f"LSP 操作失败: {e}", exc_info=True)
        return f"LSP 错误: {str(e)}"


register_tool("lsp", {
    "description": (
        "通过 Language Server Protocol (LSP) 与语言服务器交互，获取代码智能功能。\n"
        "支持操作:\n"
        "- goToDefinition: 跳转到符号定义\n"
        "- findReferences: 查找所有引用\n"
        "- hover: 获取类型/文档信息\n"
        "- documentSymbol: 列出文件所有符号（函数、类等）\n"
        "- workspaceSymbol: 在工作区搜索符号\n"
        "- goToImplementation: 跳转到接口/抽象方法实现\n"
        "支持语言: Python（pylsp/pyright）、TypeScript/JavaScript。\n"
        "需要先安装对应的 LSP 服务器。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "goToDefinition", "findReferences", "hover",
                    "documentSymbol", "workspaceSymbol", "goToImplementation"
                ],
                "description": "操作类型"
            },
            "file_path": {
                "type": "string",
                "description": "目标文件路径（workspaceSymbol 可省略）"
            },
            "line": {
                "type": "integer",
                "description": "行号（1-based，如编辑器显示）",
                "default": 1
            },
            "character": {
                "type": "integer",
                "description": "列号（1-based）",
                "default": 1
            },
            "query": {
                "type": "string",
                "description": "搜索关键词（仅 workspaceSymbol 使用）",
                "default": ""
            },
            "workspace_root": {
                "type": "string",
                "description": "工作区根目录",
                "default": "."
            }
        },
        "required": ["operation"]
    },
    "handler": lsp_handler,
    "permission_level": "read"
})
