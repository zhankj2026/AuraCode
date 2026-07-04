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
History command - session history management.
View, search, export current or historical session records.
"""
import os
import json
import time
from datetime import datetime
from commands.registry import register_command

_SESSION_HISTORY = []


def record_session(session_id, messages, summary=""):
    _SESSION_HISTORY.append({
        "session_id": session_id[:12],
        "messages": list(messages),
        "created_at": time.time(),
        "summary": summary,
    })


def history_handler(args, loop=None):
    action = args[0] if args else "show"
    if action == "show":
        return _show_history(loop)
    elif action == "search":
        kw = " ".join(args[1:]) if len(args) > 1 else ""
        return _search_history(kw, loop)
    elif action == "export":
        return _export_history(loop)
    elif action == "list":
        return _list_sessions()
    elif action == "stats":
        return _session_stats(loop)
    else:
        return "Usage: /history [show|search|export|list|stats]"


def _show_history(loop):
    if not loop:
        return "Error: AgentLoop not initialized"
    msgs = loop.state.messages
    lines = ["=" * 60, f"Session history ({len(msgs)} messages)", "=" * 60]
    icons = {"system": "S", "user": "U", "assistant": "A", "tool": "T"}
    for i, msg in enumerate(msgs):
        role = msg.get("role", "?")
        content = msg.get("content", "")
        tc = msg.get("tool_calls", [])
        icon = icons.get(role, "?")
        preview = content[:120].replace("\n", " ") if content else ""
        if len(content) > 120:
            preview += "..."
        tc_info = ""
        if tc:
            names = [t.get("function", {}).get("name", "?") for t in tc]
            tc_info = f" [tools: {', '.join(names)}]"
        lines.append(f"  {i:>3} [{icon}]{tc_info}")
        if preview:
            lines.append(f"       {preview}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _search_history(keyword, loop):
    if not keyword:
        return "Usage: /history search <keyword>"
    sources = []
    if loop:
        sources.append(("current", loop.state.messages))
    for sess in _SESSION_HISTORY:
        sources.append((f"sess:{sess['session_id']}", sess["messages"]))
    matches = []
    kw = keyword.lower()
    for src, msgs in sources:
        for i, msg in enumerate(msgs):
            if kw in msg.get("content", "").lower():
                matches.append({"src": src, "idx": i, "role": msg.get("role", "?"),
                                "snippet": msg.get("content", "")[:200]})
    if not matches:
        return f"No matches for '{keyword}'"
    lines = [f"Found {len(matches)} matches for '{keyword}'", ""]
    for m in matches[:20]:
        lines.append(f"  [{m['src']}] #{m['idx']} ({m['role']})")
        lines.append(f"    {m['snippet'][:150]}")
        lines.append("")
    return "\n".join(lines)


def _export_history(loop):
    if not loop:
        return "Error: AgentLoop not initialized"
    data = {
        "exported_at": datetime.now().isoformat(),
        "message_count": len(loop.state.messages),
        "token_usage": {"total": loop.state.usage.total_tokens},
        "cost_usd": loop.state.total_cost_usd,
        "messages": loop.state.messages,
    }
    export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "exports")
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fp = os.path.join(export_dir, f"session_{ts}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return f"Exported to {fp}\nMessages: {len(loop.state.messages)}\nTokens: {loop.state.usage.total_tokens}"


def _list_sessions():
    if not _SESSION_HISTORY:
        return "No historical sessions"
    lines = [f"Historical sessions ({len(_SESSION_HISTORY)})", ""]
    for i, s in enumerate(_SESSION_HISTORY[-20:]):
        ts = datetime.fromtimestamp(s["created_at"]).strftime("%Y-%m-%d %H:%M")
        lines.append(f"  {i+1}. [{s['session_id']}] {ts} ({len(s['messages'])} msgs)")
    return "\n".join(lines)


def _session_stats(loop):
    if not loop:
        return "Error: AgentLoop not initialized"
    msgs = loop.state.messages
    by_role = {}
    total_chars = 0
    tc_count = 0
    for msg in msgs:
        r = msg.get("role", "?")
        by_role[r] = by_role.get(r, 0) + 1
        total_chars += len(msg.get("content", ""))
        tc_count += len(msg.get("tool_calls", []))
    lines = ["=" * 40, "Session Stats", "=" * 40]
    lines.append(f"Messages: {len(msgs)}")
    for r, c in sorted(by_role.items()):
        lines.append(f"  {r}: {c}")
    lines.append(f"Tool calls: {tc_count}")
    lines.append(f"Total chars: {total_chars:,}")
    lines.append(f"Tokens: {loop.state.usage.total_tokens:,}")
    lines.append(f"Cost: ${loop.state.total_cost_usd:.4f}")
    lines.append(f"Turns: {loop.state.turn_count}")
    lines.append("=" * 40)
    return "\n".join(lines)


register_command("history", {
    "description": "Session history management (view/search/export/stats)",
    "handler": history_handler,
    "category": "system",
    "args_help": "[show|search <kw>|export|list|stats]",
})
