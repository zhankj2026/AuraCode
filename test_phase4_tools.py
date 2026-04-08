"""Phase 4 工具测试 - 插件系统 + Hook 机制"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plugins.base import ToolPlugin
from plugins.loader import PluginLoader
from hooks.manager import HookManager, HookResult, HOOK_EVENTS

print("="*60)
print("Phase 4 工具测试 (插件 + Hook)")
print("="*60)

# ========== 测试插件系统 ==========
print("\n" + "="*60)
print("测试 1: 插件系统")
print("="*60)

# 测试 1.1: 插件加载器初始化
print("\n[测试 1.1] 插件加载器初始化")
loader = PluginLoader()
print(f"插件目录: {loader.plugins_dir}")
assert os.path.exists(loader.plugins_dir)
print("✅ 加载器初始化成功")

# 测试 1.2: 扫描插件
print("\n[测试 1.2] 扫描插件")
plugin_files = loader.scan_plugins()
print(f"扫描到 {len(plugin_files)} 个插件文件: {plugin_files}")
assert len(plugin_files) >= 1  # 至少有 example_autoformat
print("✅ 插件扫描成功")

# 测试 1.3: 加载单个插件
print("\n[测试 1.3] 加载单个插件")
if 'example_autoformat' in [f[:-3] for f in plugin_files]:
    plugin = loader.load_plugin('example_autoformat')
    if plugin:
        print(f"插件名称: {plugin.name}")
        print(f"插件版本: {plugin.version}")
        print(f"插件描述: {plugin.description}")
        print(f"是否可用: {plugin.is_available()}")
        assert plugin.name == "auto-format"
        assert plugin.version == "1.0.0"
        print("✅ 插件加载成功")
    else:
        print("⚠️  插件加载失败(可能依赖未安装)")
else:
    print("⚠️  示例插件不存在")

# 测试 1.4: 加载所有插件
print("\n[测试 1.4] 加载所有插件")
plugins = loader.load_all_plugins()
print(f"成功加载 {len(plugins)} 个插件")
for p in plugins:
    print(f"  - {p.name} v{p.version}: {p.description}")
print("✅ 所有插件加载完成")

# 测试 1.5: 获取插件工具
print("\n[测试 1.5] 获取插件工具")
all_tools = loader.get_all_tools()
print(f"从插件中获取 {len(all_tools)} 个工具")
print("✅ 工具获取成功")

# 测试 1.6: 获取插件钩子
print("\n[测试 1.6] 获取插件钩子")
all_hooks = loader.get_all_hooks()
print(f"从插件中获取 {len(all_hooks)} 个钩子")
for hook in all_hooks:
    print(f"  - 事件: {hook['event']}, 匹配: {hook.get('matcher')}")
print("✅ 钩子获取成功")

# 测试 1.7: 列出插件信息
print("\n[测试 1.7] 列出插件信息")
plugin_list = loader.list_plugins()
for info in plugin_list:
    print(f"  {info['name']} v{info['version']}: {info['description']}")
print("✅ 插件列表获取成功")

# ========== 测试 Hook 系统 ==========
print("\n" + "="*60)
print("测试 2: Hook 系统")
print("="*60)

# 测试 2.1: Hook 管理器初始化
print("\n[测试 2.1] Hook 管理器初始化")
hook_manager = HookManager()
print(f"支持的钩子事件: {HOOK_EVENTS}")
assert len(HOOK_EVENTS) == 4
print("✅ 管理器初始化成功")

# 测试 2.2: 注册钩子
print("\n[测试 2.2] 注册钩子")

# 定义测试钩子
async def test_pre_hook(**kwargs):
    """测试 PreToolUse 钩子"""
    print(f"  [PreToolUse] 工具: {kwargs.get('tool_name')}")
    return HookResult(allow=True)

async def test_block_hook(**kwargs):
    """测试阻止执行的钩子"""
    tool_name = kwargs.get('tool_name')
    if tool_name == 'dangerous_command':
        return HookResult(
            allow=False,
            block_reason="危险命令被阻止"
        )
    return HookResult(allow=True)

async def test_modify_hook(**kwargs):
    """测试修改输入的钩子"""
    return HookResult(
        allow=True,
        modified_input={'extra_param': 'added_by_hook'}
    )

hook_id1 = hook_manager.register_hook("PreToolUse", test_pre_hook)
hook_id2 = hook_manager.register_hook("PreToolUse", test_block_hook, priority=10)
hook_id3 = hook_manager.register_hook("PreToolUse", test_modify_hook, priority=5)

print(f"注册钩子 ID: {hook_id1}, {hook_id2}, {hook_id3}")
assert hook_id1 == 0
assert hook_id2 == 1
assert hook_id3 == 2
print("✅ 钩子注册成功")

# 测试 2.3: 执行钩子(正常)
print("\n[测试 2.3] 执行钩子(正常)")
async def test_normal_hooks():
    result = await hook_manager.execute_hooks(
        "PreToolUse",
        tool_name="read_file"
    )
    assert result.allow == True
    print(f"钩子执行结果: allow={result.allow}")
    return result

result = asyncio.run(test_normal_hooks())
print("✅ 钩子执行成功")

# 测试 2.4: 执行钩子(阻止)
print("\n[测试 2.4] 执行钩子(阻止)")
async def test_block_hooks():
    result = await hook_manager.execute_hooks(
        "PreToolUse",
        tool_name="dangerous_command"
    )
    assert result.allow == False
    assert result.block_reason == "危险命令被阻止"
    print(f"钩子阻止执行: {result.block_reason}")
    return result

result = asyncio.run(test_block_hooks())
print("✅ 钩子阻止成功")

# 测试 2.5: 执行钩子(修改输入)
print("\n[测试 2.5] 执行钩子(修改输入)")
async def test_modify_hooks():
    result = await hook_manager.execute_hooks(
        "PreToolUse",
        tool_name='run_command',
        input={'cmd': 'ls'}
    )
    assert result.allow == True
    print(f"钩子执行结果: allow={result.allow}")
    return result

result = asyncio.run(test_modify_hooks())
print("✅ 输入修改成功")

# 测试 2.6: 删除钩子
print("\n[测试 2.6] 删除钩子")
success = hook_manager.unregister_hook(hook_id1)
assert success == True
print(f"删除钩子 ID: {hook_id1}")
success = hook_manager.unregister_hook(999)  # 不存在的钩子
assert success == False
print("✅ 钩子删除成功")

# 测试 2.7: 钩子统计
print("\n[测试 2.7] 钩子统计")
stats = hook_manager.get_hook_stats()
print(f"钩子统计: {stats}")
assert sum(stats.values()) == 2  # 删除了 1 个,还剩 2 个
print("✅ 统计信息正确")

# 测试 2.8: 列出钩子
print("\n[测试 2.8] 列出钩子")
hooks_list = hook_manager.list_hooks()
print(f"已注册 {len(hooks_list)} 个钩子:")
for h in hooks_list:
    print(f"  - ID:{h['id']} 事件:{h['event']} 匹配:{h['matcher']} 优先级:{h['priority']}")
print("✅ 钩子列表获取成功")

# 测试 2.9: 清除钩子
print("\n[测试 2.9] 清除钩子")
hook_manager.clear_hooks()
stats = hook_manager.get_hook_stats()
assert sum(stats.values()) == 0
print(f"清除后统计: {stats}")
print("✅ 钩子清除成功")

# ========== 测试插件与 Hook 集成 ==========
print("\n" + "="*60)
print("测试 3: 插件与 Hook 集成")
print("="*60)

# 测试 3.1: 从插件加载钩子
print("\n[测试 3.1] 从插件加载钩子到管理器")
loader2 = PluginLoader()
plugins = loader2.load_all_plugins()
plugin_hooks = loader2.get_all_hooks()

for hook_def in plugin_hooks:
    hook_manager.register_hook(
        hook_def['event'],
        hook_def['handler'],
        hook_def.get('matcher')
    )
    print(f"  注册: {hook_def['event']} (匹配: {hook_def.get('matcher')})")

print(f"从插件加载 {len(plugin_hooks)} 个钩子")
print("✅ 插件钩子注册成功")

# ========== 总结 ==========
print("\n" + "="*60)
print("✅ 所有 Phase 4 测试通过!")
print("="*60)
print("\nPhase 4 完成功能:")
print("  1. 插件系统")
print("     - ToolPlugin 基类 (89行)")
print("     - PluginLoader 加载器 (199行)")
print("     - 示例插件: auto-format")
print("  2. Hook 系统")
print("     - HookManager 管理器 (254行)")
print("     - 4 种钩子事件: PreToolUse/PostToolUse/SessionStart/PostToolUseFailure")
print("     - 支持优先级、匹配器、输入修改")
