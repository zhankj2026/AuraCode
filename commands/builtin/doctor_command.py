"""
Doctor 命令 - 环境诊断与健康检查

功能:
- 检查 Python 版本和平台信息
- 检查关键依赖是否已安装 (openai, yaml, etc.)
- 检查 LLM API 连通性
- 检查配置文件有效性
- 检查 Git 环境
- 检查 auracode 模块加载状态

用法:
  /doctor        运行完整诊断
"""

import sys
import os
import platform
from commands.registry import register_command


def _check(label: str, ok: bool, detail: str = "") -> str:
    """生成单条检查结果"""
    icon = "✅" if ok else "❌"
    suffix = f"  ({detail})" if detail else ""
    return f"  {icon} {label}{suffix}"


def doctor_handler(args: list, loop=None) -> str:
    """doctor 命令处理函数"""
    lines = []
    lines.append("🩺 auracode 环境诊断")
    lines.append("=" * 60)
    passed = 0
    total = 0
    warnings = []

    # ── 1. Python 环境 ──
    lines.append("\n🐍 Python 环境:")
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    total += 1
    ok = sys.version_info >= (3, 8)
    if ok:
        passed += 1
    else:
        warnings.append("Python 版本低于 3.8，部分功能可能不兼容")
    lines.append(_check("Python 版本", ok, f"{py_version} ({platform.system()} {platform.release()})"))

    total += 1
    encoding_ok = sys.getdefaultencoding() == "utf-8"
    if encoding_ok:
        passed += 1
    lines.append(_check("默认编码", encoding_ok, sys.getdefaultencoding()))

    # ── 2. 关键依赖 ──
    lines.append("\n📦 关键依赖:")
    dependencies = [
        ("openai", "LLM API 客户端"),
        ("yaml", "配置文件解析"),
        ("json", "JSON 处理"),
        ("threading", "线程支持"),
        ("asyncio", "异步支持"),
    ]
    for mod_name, desc in dependencies:
        total += 1
        try:
            __import__(mod_name)
            passed += 1
            ver = ""
            try:
                m = __import__(mod_name)
                ver = getattr(m, "__version__", "")
            except Exception:
                pass
            lines.append(_check(mod_name, True, ver or "已安装"))
        except ImportError as e:
            warnings.append(f"依赖 {mod_name} 缺失: {desc}")
            lines.append(_check(mod_name, False, str(e)))

    # ── 3. LLM API 连通性 ──
    lines.append("\n🌐 LLM API 连通性:")
    if loop is not None:
        total += 1
        try:
            client = getattr(loop, 'client', None)
            if client:
                # 尝试简单 API 调用验证
                model = getattr(loop, 'model', 'unknown')
                lines.append(_check("LLM 客户端", True, f"已初始化 (model={model})"))
                passed += 1

                # 测试连通性（轻量请求）
                total += 1
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=1,
                        temperature=0,
                    )
                    lines.append(_check("API 连通", True, f"响应正常"))
                    passed += 1
                except Exception as e:
                    err_msg = str(e)[:80]
                    warnings.append(f"API 连通性测试失败: {err_msg}")
                    lines.append(_check("API 连通", False, err_msg))
            else:
                warnings.append("LLM 客户端未初始化")
                lines.append(_check("LLM 客户端", False, "未初始化"))
        except Exception as e:
            warnings.append(f"LLM 检查异常: {e}")
            lines.append(_check("LLM 检查", False, str(e)[:80]))
    else:
        total += 1
        lines.append(_check("AgentLoop", False, "未初始化"))
        warnings.append("AgentLoop 未初始化")

    # ── 4. 配置文件 ──
    lines.append("\n📋 配置文件:")
    config_files = [
        ("config.yaml", "主配置"),
        ("requirements.txt", "依赖清单"),
    ]
    auracode_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for fname, desc in config_files:
        total += 1
        fpath = os.path.join(auracode_dir, fname)
        exists = os.path.isfile(fpath)
        if exists:
            passed += 1
        else:
            warnings.append(f"配置文件缺失: {fname}")
        lines.append(_check(f"{fname} ({desc})", exists))

    # ── 5. Git 环境 ──
    lines.append("\n🔧 Git 环境:")
    total += 1
    try:
        import subprocess
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True, timeout=5
        )
        git_ok = result.returncode == 0
        git_ver = result.stdout.strip() if git_ok else "未安装"
        if git_ok:
            passed += 1
        lines.append(_check("Git", git_ok, git_ver))
    except Exception as e:
        warnings.append(f"Git 不可用: {e}")
        lines.append(_check("Git", False, str(e)[:60]))

    # ── 6. auracode 模块 ──
    lines.append("\n📐 auracode 模块:")
    modules = [
        ("core.agent_loop", "核心循环"),
        ("core.session_state", "会话状态"),
        ("core.memory", "记忆系统"),
        ("tools.registry", "工具注册表"),
        ("commands.registry", "命令注册表"),
        ("hooks.manager", "Hook 管理器"),
        ("permissions.manager", "权限管理器"),
        ("skills.loader", "技能加载器"),
        ("plugins.loader", "插件加载器"),
    ]
    for mod, desc in modules:
        total += 1
        try:
            __import__(mod)
            passed += 1
            lines.append(_check(f"{mod} ({desc})", True))
        except ImportError:
            warnings.append(f"模块加载失败: {mod}")
            lines.append(_check(f"{mod} ({desc})", False))

    # ── 7. 工具 & 命令统计 ──
    lines.append("\n📊 系统统计:")
    try:
        from tools.registry import TOOL_REGISTRY
        tool_count = len(TOOL_REGISTRY)
        lines.append(f"  🔧 已注册工具: {tool_count}")
    except Exception:
        lines.append(f"  🔧 工具注册表: 无法读取")

    try:
        from commands.registry import COMMAND_REGISTRY
        cmd_count = len(COMMAND_REGISTRY)
        lines.append(f"  📝 已注册命令: {cmd_count}")
    except Exception:
        lines.append(f"  📝 命令注册表: 无法读取")

    try:
        from hooks.manager import HOOK_EVENTS
        lines.append(f"  🪝 Hook 事件: {len(HOOK_EVENTS)} 种")
    except Exception:
        lines.append(f"  🪝 Hook 系统: 无法读取")

    # ── 汇总 ──
    lines.append(f"\n{'=' * 60}")
    pct = (passed / total * 100) if total > 0 else 0
    icon = "🟢" if pct == 100 else ("🟡" if pct >= 80 else "🔴")
    lines.append(f"{icon} 诊断结果: {passed}/{total} 项通过 ({pct:.0f}%)")

    if warnings:
        lines.append(f"\n⚠️  发现 {len(warnings)} 个问题:")
        for w in warnings:
            lines.append(f"  • {w}")
    else:
        lines.append("  ✅ 所有检查项均通过！")

    lines.append("=" * 60)
    return "\n".join(lines)


register_command("doctor", {
    "description": "环境诊断与健康检查 - Python/依赖/API/配置/Git/模块",
    "handler": doctor_handler,
    "category": "system",
    "args_help": ""
})
