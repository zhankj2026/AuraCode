"""
Worktree Tool — Git Worktree 隔离工作区管理

创建/退出/管理 Git Worktree，支持并行开发。
参考 EnterWorktreeTool / ExitWorktreeTool。

功能:
  - 创建隔离的 git worktree 工作区
  - 自动创建分支并切换工作目录
  - 退出时保留或删除 worktree
  - 会话绑定: 跟踪当前 worktree 状态
"""
import os
import re
import shutil
import string
import random
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Dict

from tools.registry import register_tool


# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class WorktreeSession:
    """当前 worktree 会话状态"""
    original_cwd: str
    worktree_path: str
    worktree_branch: Optional[str] = None
    worktree_name: str = ""
    original_head: str = ""
    created_at: float = 0.0


@dataclass
class WorktreeInfo:
    """worktree 信息"""
    path: str
    branch: str
    head: str
    bare: bool = False
    prunable: bool = False


# ── 全局会话状态 ──────────────────────────────────────────

_current_session: Optional[WorktreeSession] = None
_lock = threading.Lock()


def get_current_worktree_session() -> Optional[WorktreeSession]:
    return _current_session


# ── Git 工具函数 ──────────────────────────────────────────

def _run_git(*args, cwd: str = None, check: bool = True) -> subprocess.CompletedProcess:
    """执行 git 命令"""
    cmd = ["git"] + list(args)
    return subprocess.run(
        cmd, capture_output=True, text=True,
        cwd=cwd or os.getcwd(), timeout=30,
        check=check,
    )


def _find_git_root(path: str = None) -> Optional[str]:
    """查找 git 仓库根目录"""
    try:
        result = _run_git("rev-parse", "--show-toplevel", cwd=path, check=False)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_head_commit(cwd: str = None) -> str:
    """获取当前 HEAD commit"""
    try:
        result = _run_git("rev-parse", "HEAD", cwd=cwd, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _validate_worktree_name(name: str) -> bool:
    """验证 worktree 名称格式"""
    pattern = r'^[a-zA-Z0-9._-]+$'
    return bool(re.match(pattern, name)) and len(name) <= 64


def _generate_random_name() -> str:
    """生成随机 worktree 名称"""
    chars = string.ascii_lowercase + string.digits
    return "wt-" + "".join(random.choices(chars, k=8))


def _get_worktree_dir(git_root: str) -> str:
    """获取 worktree 存储目录"""
    wt_dir = os.path.join(git_root, ".auracode", "worktrees")
    os.makedirs(wt_dir, exist_ok=True)
    return wt_dir


# ── 核心功能 ──────────────────────────────────────────────

class WorktreeManager:
    """Git Worktree 管理器"""

    def __init__(self):
        self._lock = threading.Lock()

    def list_worktrees(self, git_root: str = None) -> List[WorktreeInfo]:
        """列出所有 worktree"""
        root = git_root or _find_git_root()
        if not root:
            return []

        result = _run_git("worktree", "list", "--porcelain", cwd=root, check=False)
        if result.returncode != 0:
            return []

        worktrees = []
        current = {}

        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    worktrees.append(WorktreeInfo(**current))
                current = {"path": line[9:], "branch": "", "head": "", "bare": False, "prunable": False}
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line == "bare":
                current["bare"] = True
            elif line == "prunable":
                current["prunable"] = True

        if current:
            worktrees.append(WorktreeInfo(**current))

        return worktrees

    def create_worktree(self, name: str = None, base_branch: str = None,
                        git_root: str = None) -> WorktreeSession:
        """
        创建新的 git worktree。

        Args:
            name: worktree 名称（自动生成随机名如果为空）
            base_branch: 基于哪个分支创建（默认 HEAD）
            git_root: git 仓库根目录

        Returns:
            WorktreeSession

        Raises:
            ValueError: 已在 worktree 中或名称无效
            RuntimeError: git 操作失败
        """
        global _current_session

        with self._lock:
            if _current_session is not None:
                raise ValueError("已在 worktree 会话中，请先退出当前 worktree")

            root = git_root or _find_git_root()
            if not root:
                raise RuntimeError("当前目录不在 git 仓库中")

            # 生成名称
            wt_name = name or _generate_random_name()
            if not _validate_worktree_name(wt_name):
                raise ValueError(f"无效的 worktree 名称: {wt_name} (仅允许字母/数字/./_-/，最长64)")

            # worktree 路径
            wt_base = _get_worktree_dir(root)
            wt_path = os.path.join(wt_base, wt_name)

            if os.path.exists(wt_path):
                raise ValueError(f"Worktree 路径已存在: {wt_path}")

            # 分支名
            branch_name = f"worktree/{wt_name}"

            # 记录当前 HEAD
            original_head = _get_head_commit(root)
            original_cwd = os.getcwd()

            # 基础分支
            base = base_branch or "HEAD"

            # 创建 worktree
            result = _run_git(
                "worktree", "add", "-b", branch_name, wt_path, base,
                cwd=root, check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"git worktree add 失败: {result.stderr.strip()}")

            # 创建会话
            import time
            session = WorktreeSession(
                original_cwd=original_cwd,
                worktree_path=wt_path,
                worktree_branch=branch_name,
                worktree_name=wt_name,
                original_head=original_head,
                created_at=time.time(),
            )
            _current_session = session

            return session

    def exit_worktree(self, action: str = "keep",
                      discard_changes: bool = False) -> Dict:
        """
        退出当前 worktree 会话。

        Args:
            action: "keep" 保留 worktree, "remove" 删除
            discard_changes: 删除时是否丢弃未提交变更

        Returns:
            操作结果字典
        """
        global _current_session

        with self._lock:
            if _current_session is None:
                raise ValueError("当前不在 worktree 会话中")

            session = _current_session
            wt_path = session.worktree_path
            original_cwd = session.original_cwd

            # 统计变更
            changed_files, commits = self._count_changes(wt_path, session.original_head)

            if action == "remove":
                if (changed_files > 0 or commits > 0) and not discard_changes:
                    parts = []
                    if changed_files > 0:
                        parts.append(f"{changed_files} 个未提交文件")
                    if commits > 0:
                        parts.append(f"{commits} 个未合并提交")
                    raise ValueError(
                        f"Worktree 有 {' 和 '.join(parts)}。"
                        f"请设置 discard_changes=True 确认删除，或使用 action='keep' 保留。"
                    )

                # 先切回原目录
                try:
                    os.chdir(original_cwd)
                except Exception:
                    pass

                # 删除 worktree
                root = _find_git_root(original_cwd)
                if root:
                    _run_git("worktree", "remove", "--force", wt_path, cwd=root, check=False)

                # 删除分支
                if session.worktree_branch:
                    _run_git("branch", "-D", session.worktree_branch,
                             cwd=root, check=False)

                result_msg = f"已退出并删除 worktree: {wt_path}"
                if changed_files > 0:
                    result_msg += f" (丢弃了 {changed_files} 个文件)"
                if commits > 0:
                    result_msg += f" (丢弃了 {commits} 个提交)"

            else:
                # keep
                try:
                    os.chdir(original_cwd)
                except Exception:
                    pass
                result_msg = f"已退出 worktree，工作保留在: {wt_path}"
                if session.worktree_branch:
                    result_msg += f" (分支: {session.worktree_branch})"

            _current_session = None

            return {
                "action": action,
                "original_cwd": original_cwd,
                "worktree_path": wt_path,
                "worktree_branch": session.worktree_branch,
                "changed_files": changed_files,
                "commits": commits,
                "message": result_msg,
            }

    def get_status(self) -> Dict:
        """获取当前 worktree 状态"""
        session = _current_session
        if session is None:
            return {"in_worktree": False, "message": "当前不在 worktree 中"}

        changed_files, commits = self._count_changes(
            session.worktree_path, session.original_head
        )
        return {
            "in_worktree": True,
            "worktree_name": session.worktree_name,
            "worktree_path": session.worktree_path,
            "worktree_branch": session.worktree_branch,
            "original_cwd": session.original_cwd,
            "changed_files": changed_files,
            "commits": commits,
        }

    def _count_changes(self, wt_path: str, original_head: str):
        """统计 worktree 中的变更"""
        changed_files = 0
        commits = 0

        # 未提交文件
        result = _run_git("status", "--porcelain", cwd=wt_path, check=False)
        if result.returncode == 0:
            changed_files = len([l for l in result.stdout.splitlines() if l.strip()])

        # 未合并提交
        if original_head:
            result = _run_git(
                "rev-list", "--count", f"{original_head}..HEAD",
                cwd=wt_path, check=False,
            )
            if result.returncode == 0:
                try:
                    commits = int(result.stdout.strip())
                except ValueError:
                    commits = 0

        return changed_files, commits


# ── /worktree 命令 ──────────────────────────────────────

def worktree_handler(args: list, loop=None) -> str:
    """
    管理 Git Worktree 隔离工作区。

    用法:
        /worktree create [name]  — 创建新 worktree
        /worktree exit [keep|remove] — 退出当前 worktree
        /worktree list           — 列出所有 worktree
        /worktree status         — 查看当前状态
    """
    from commands.registry import register_command as _  # 确保已注册

    manager = get_worktree_manager()

    if not args:
        args = ["status"]

    action = args[0]

    if action == "create":
        name = args[1] if len(args) > 1 else None
        try:
            session = manager.create_worktree(name=name)
            return (
                f"✅ 已创建 worktree: {session.worktree_name}\n"
                f"   路径: {session.worktree_path}\n"
                f"   分支: {session.worktree_branch}\n"
                f"   原目录: {session.original_cwd}\n"
                f"\n💡 使用 /worktree exit 退出 worktree"
            )
        except (ValueError, RuntimeError) as e:
            return f"❌ 创建失败: {e}"

    elif action == "exit":
        keep_or_remove = args[1] if len(args) > 1 else "keep"
        discard = keep_or_remove == "remove"
        try:
            result = manager.exit_worktree(
                action=keep_or_remove,
                discard_changes=discard,
            )
            return f"✅ {result['message']}"
        except ValueError as e:
            return f"❌ {e}"

    elif action == "list":
        worktrees = manager.list_worktrees()
        if not worktrees:
            return "📭 没有找到任何 worktree。"

        lines = [f"🌳 Worktree 列表 ({len(worktrees)}):\n"]
        for wt in worktrees:
            branch = wt.branch.replace("refs/heads/", "") if wt.branch else "(detached)"
            marker = " ← 当前" if _current_session and wt.path == _current_session.worktree_path else ""
            lines.append(f"  📁 {wt.path}")
            lines.append(f"     分支: {branch}  HEAD: {wt.head[:8]}{marker}")
        return "\n".join(lines)

    elif action == "status":
        status = manager.get_status()
        if not status["in_worktree"]:
            return "📍 当前不在 worktree 中。使用 /worktree create 创建。"
        return (
            f"📍 当前 Worktree 状态:\n"
            f"   名称: {status['worktree_name']}\n"
            f"   路径: {status['worktree_path']}\n"
            f"   分支: {status['worktree_branch']}\n"
            f"   原目录: {status['original_cwd']}\n"
            f"   未提交文件: {status['changed_files']}\n"
            f"   未合并提交: {status['commits']}"
        )

    else:
        return "用法: /worktree [create|exit|list|status] [参数...]"


# ── 工具注册 ──────────────────────────────────────────────

def enter_worktree(name: str = None, base_branch: str = None) -> Dict:
    """工具函数: 创建并进入 worktree"""
    manager = get_worktree_manager()
    session = manager.create_worktree(name=name, base_branch=base_branch)
    try:
        os.chdir(session.worktree_path)
    except Exception:
        pass
    return {
        "worktree_path": session.worktree_path,
        "worktree_branch": session.worktree_branch,
        "message": f"Created worktree at {session.worktree_path} on branch {session.worktree_branch}. "
                   f"Session is now working in the worktree. Use exit_worktree to leave.",
    }


def exit_worktree(action: str = "keep", discard_changes: bool = False) -> Dict:
    """工具函数: 退出当前 worktree"""
    manager = get_worktree_manager()
    return manager.exit_worktree(action=action, discard_changes=discard_changes)


# 注册工具
register_tool("enter_worktree", {
    "description": "Create an isolated git worktree and switch into it for parallel development",
    "handler": enter_worktree,
    "parameters": {
        "name": {"type": "string", "description": "Worktree name (auto-generated if empty)"},
        "base_branch": {"type": "string", "description": "Base branch (default: HEAD)"},
    },
    "category": "git",
    "permission_level": "write",
})

register_tool("exit_worktree", {
    "description": "Exit current worktree session, optionally removing the worktree",
    "handler": exit_worktree,
    "parameters": {
        "action": {"type": "string", "enum": ["keep", "remove"], "description": "Keep or remove the worktree"},
        "discard_changes": {"type": "boolean", "description": "Force discard uncommitted changes when removing"},
    },
    "category": "git",
    "permission_level": "write",
})

# 注册命令
try:
    from commands.registry import register_command
    register_command("worktree", {
        "description": "Git Worktree 管理 — 创建/退出隔离工作区",
        "handler": worktree_handler,
        "category": "git",
        "args_help": "[create|exit|list|status] [参数...]",
    })
except Exception:
    pass


# ── 全局单例 ──────────────────────────────────────────────

_worktree_manager: Optional[WorktreeManager] = None


def get_worktree_manager() -> WorktreeManager:
    global _worktree_manager
    if _worktree_manager is None:
        _worktree_manager = WorktreeManager()
    return _worktree_manager
