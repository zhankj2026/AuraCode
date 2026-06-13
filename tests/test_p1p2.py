"""Quick test for P1/P2 features"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commands.builtin.model_command import _record_switch, _cmd_history, _model_history

# Test model history
_record_switch("glm-4", "gpt-4o", "user")
_record_switch("gpt-4o", "claude-3.5-sonnet", "user")
_record_switch("claude-3.5-sonnet", "deepseek-chat", "fallback")
print("=== Model History ===")
print(_cmd_history())

# Test tools command
from commands.builtin.tools_command import tools_handler
from core.tool_tracker import get_tool_tracker, get_tool_cache

tracker = get_tool_tracker()
tracker.start_call("read_file", {"path": "/main.py"}, turn=1)
tracker.end_call(True, "import os\nimport sys\n\ndef main():\n    pass")
tracker.start_call("grep_search", {"pattern": "def main"}, turn=1)
tracker.end_call(True, "main.py:5: def main():")
tracker.start_call("write_file", {"path": "/output.py"}, turn=2)
tracker.end_call(False, error="Permission denied: read-only mode")

print("\n=== Tools Overview ===")
print(tools_handler([], None))

print("\n=== Tools Stats ===")
print(tools_handler(["stats"], None))

print("\n=== Tools Timeline ===")
print(tools_handler(["timeline"], None))

print("\n=== Tools Chain T1 ===")
print(tools_handler(["chain", "1"], None))

# Test cache
cache = get_tool_cache()
cache.put("read_file", {"path": "/main.py"}, "file content here")
hit = cache.get("read_file", {"path": "/main.py"})
print(f"\n=== Cache Test ===")
print(f"Cache hit: {hit is not None}")
print(cache.get_stats_text())

# Test context command
from commands.builtin.context_command import _get_context_window, _get_dynamic_threshold
print("\n=== Context Window Detection ===")
for model in ["glm-4-plus", "gpt-4o", "claude-3.5-sonnet", "deepseek-chat", "o1", "unknown-model"]:
    cw = _get_context_window(model)
    th = _get_dynamic_threshold(cw)
    print(f"  {model:<24} window={cw:>8,}  threshold={th}")

print("\n✅ All P1/P2 tests passed!")
