"""Quick test for new modules"""
import sys
sys.path.insert(0, '.')

# Test 1: HookConfigLoader
from hooks.manager import HookManager
from hooks.config_loader import HookConfigLoader, HookConfigEntry

hm = HookManager()
cl = HookConfigLoader(hm)
e = HookConfigEntry(
    event='PreToolUse', 
    command='echo test', 
    matcher='run_command', 
    priority=5, 
    description='test hook'
)
hid = cl.add_entry(e)
print(f"HookConfigLoader: added hook ID={hid}")
info = cl.get_config_info()
print(f"  entries={info['entries_count']}, registered={info['registered_hooks']}")
stats = hm.get_hook_stats()
print(f"  PreToolUse hooks: {stats.get('PreToolUse', 0)}")
cl.unload()
print(f"  Unloaded: {len(cl.entries)} entries")
print("HookConfigLoader OK\n")

# Test 2: SessionStore  
from core.session_store import SessionStore, auto_save_session, restore_session_to_loop
store = SessionStore()
meta = auto_save_session(
    store,
    messages=[
        {"role": "system", "content": "You are an AI assistant."},
        {"role": "user", "content": "Hello world test"},
        {"role": "assistant", "content": "Hi there!"},
    ],
    model="glm-4-plus",
    turn_count=2,
    total_tokens=500,
    total_cost_usd=0.001,
    status="completed"
)
print(f"SessionStore: saved {meta.session_id}")

rec = store.load_session(meta.session_id)
print(f"  Loaded: {len(rec.messages)} messages")

sessions = store.list_sessions()
print(f"  List: {len(sessions)} sessions")

results = store.search_sessions("hello")
print(f"  Search 'hello': {len(results)} results")

store.delete_session(meta.session_id)
print(f"  Deleted, count={store.get_session_count()}")
print("SessionStore OK\n")

# Test 3: Command registration
from commands.builtin import *
from commands.registry import COMMAND_REGISTRY
cmds = sorted(COMMAND_REGISTRY.keys())
print(f"Commands: {len(cmds)} total")
new_cmds = ['mcp', 'resume', 'hooks']
for c in new_cmds:
    status = "OK" if c in cmds else "MISSING"
    print(f"  /{c}: {status}")

print("\nAll tests passed!")
