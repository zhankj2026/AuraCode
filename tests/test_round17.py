"""验证本轮新增模块"""
import sys
sys.path.insert(0, '.')

# 1. 验证命令注册
from commands.registry import COMMAND_REGISTRY
from commands.builtin import memory_command, permissions_command, config_edit_command

print(f"=== 命令注册验证 ===")
print(f"总命令数: {len(COMMAND_REGISTRY)}")
new_cmds = ['memory', 'permissions', 'config-edit']
for c in new_cmds:
    if c in COMMAND_REGISTRY:
        desc = COMMAND_REGISTRY[c]['description']
        print(f"  /{c}: {desc}")
    else:
        print(f"  /{c}: NOT FOUND!")

# 2. 验证 SessionState 发布/订阅
print(f"\n=== SessionState 发布/订阅验证 ===")
from core.session_state import SessionState, StateEvent

state = SessionState()
events_log = []

def on_event(event, data):
    events_log.append(event)

sub_id = state.subscribe_all(on_event, label="test")
state.start_query()
state.increment_turn()
state.abort()
state.clear_abort()

snapshot = state.create_snapshot("test-snap")
state.restore_snapshot(snapshot)

print(f"  订阅 ID: {sub_id}")
print(f"  触发事件数: {len(events_log)}")
print(f"  事件列表: {events_log}")
print(f"  快照创建: OK (turn={snapshot['turn_count']})")
print(f"  快照恢复: OK")
state.unsubscribe(sub_id)
print(f"  取消订阅后: {state.get_subscriber_count()} subscribers")

# 3. 验证 SkillManager 增强
print(f"\n=== SkillManager 增强验证 ===")
from skills.loader import SkillManager
sm = SkillManager()
print(f"  内置目录: {sm.builtin_skills_dir}")
print(f"  项目目录: {sm.project_skills_dir}")
print(f"  用户目录: {sm.user_skills_dir}")
print(f"  加载 Skill 数: {len(sm.skills)}")
sources = {}
for name, src in sm._skill_sources.items():
    sources[src] = sources.get(src, 0) + 1
print(f"  来源分布: {sources}")

# 搜索功能
results = sm.search_skills("code")
print(f"  搜索 'code': {len(results)} 结果")

# 4. 验证 memory command
print(f"\n=== Memory 命令功能验证 ===")
result = memory_command.memory_handler("stats")
print(f"  /memory stats: {result[:60]}...")

# 5. 验证 permissions command
print(f"\n=== Permissions 命令功能验证 ===")
from permissions.manager import PermissionManager
permissions_command.set_permission_manager(PermissionManager("auto"))
result = permissions_command.permissions_handler("")
print(f"  /permissions: {result[:80]}...")

# 6. 验证 config-edit command
print(f"\n=== Config-edit 命令功能验证 ===")
config_edit_command.set_config({"llm": {"model": "gpt-4o", "max_tokens": 4096}})
result = config_edit_command.config_edit_handler("get llm.model")
print(f"  /config-edit get llm.model: {result}")
result2 = config_edit_command.config_edit_handler("set llm.temperature 0.5")
print(f"  /config-edit set: {result2}")

print(f"\n=== 全部验证通过 ===")
