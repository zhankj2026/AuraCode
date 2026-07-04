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
会话环境脚本 (Session Environment)

参考标准~/.auracode/session-env/{sessionId}/
存储 Hook 产生的环境脚本（如 venv/conda 激活），使 shell 环境在会话内持久化。

存储结构:
~/.auracode/session-env/{session_id}/
├── setup-hook-0.sh         # Setup Hook 产生的环境脚本
├── sessionstart-hook-0.sh  # SessionStart Hook 产生
├── cwdchanged-hook-0.sh    # CwdChanged Hook 产生
└── filechanged-hook-0.sh   # FileChanged Hook 产生

作用:
- Hook 执行后输出的环境修改（export PATH=...）保存到文件
- 后续 shell 命令执行前加载这些脚本
- 确保 venv/conda 等环境在多次 shell 调用间持久
"""

import os
import re
import logging
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 路径工具 ──

def _auracode_home() -> str:
    return os.path.join(os.path.expanduser("~"), ".auracode")


def get_session_env_dir(session_id: str) -> str:
    """获取会话环境目录"""
    return os.path.join(_auracode_home(), "session-env", session_id)


def get_hook_env_path(session_id: str, hook_event: str, hook_index: int) -> str:
    """获取指定 Hook 的环境脚本路径"""
    prefix = hook_event.lower()
    return os.path.join(
        get_session_env_dir(session_id),
        f"{prefix}-hook-{hook_index}.sh",
    )


# ── Hook 事件优先级 ──

HOOK_PRIORITY = {
    "setup": 0,
    "sessionstart": 1,
    "cwdchanged": 2,
    "filechanged": 3,
}

HOOK_ENV_REGEX = re.compile(
    r"^(setup|sessionstart|cwdchanged|filechanged)-hook-(\d+)\.sh$"
)


class SessionEnv:
    """
    会话环境管理器

    用法:
        env = SessionEnv(session_id="abc123")
        env.save_hook_env("setup", 0, "export PATH=/venv/bin:$PATH")
        script = env.get_combined_script()
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._env_dir = get_session_env_dir(session_id)
        self._cache: Optional[str] = None

        os.makedirs(self._env_dir, exist_ok=True)
        logger.debug(f"SessionEnv initialized: {self._env_dir}")

    def save_hook_env(
        self,
        hook_event: str,
        hook_index: int,
        script_content: str,
    ) -> bool:
        """
        保存 Hook 产生的环境脚本

        Args:
            hook_event: Hook 事件类型 (Setup/SessionStart/CwdChanged/FileChanged)
            hook_index: Hook 在配置中的索引
            script_content: 环境脚本内容

        Returns:
            是否保存成功
        """
        path = get_hook_env_path(self.session_id, hook_event, hook_index)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(script_content)
            self._cache = None  # 清除缓存
            logger.debug(f"Hook env saved: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save hook env: {e}")
            return False

    def get_combined_script(self) -> Optional[str]:
        """
        获取所有环境脚本的合并结果（按优先级排序）。

        返回合并后的 shell 脚本，可直接 source 执行。
        """
        if self._cache is not None:
            return self._cache if self._cache else None

        scripts = []
        try:
            files = os.listdir(self._env_dir)
        except OSError:
            return None

        # 按优先级排序
        hook_files = []
        for f in files:
            match = HOOK_ENV_REGEX.match(f)
            if match:
                event_type = match.group(1)
                index = int(match.group(2))
                priority = HOOK_PRIORITY.get(event_type, 99)
                hook_files.append((priority, index, f))

        hook_files.sort(key=lambda x: (x[0], x[1]))

        for _, _, fname in hook_files:
            fpath = os.path.join(self._env_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    scripts.append(content)
            except Exception as e:
                logger.warning(f"Failed to read hook env {fname}: {e}")

        if not scripts:
            self._cache = ""
            return None

        combined = "\n".join(scripts)
        self._cache = combined
        return combined

    def clear_cwd_env_files(self) -> None:
        """清除 CwdChanged 和 FileChanged 的环境文件（目录切换时）"""
        try:
            for fname in os.listdir(self._env_dir):
                if (fname.startswith("filechanged-hook-")
                        or fname.startswith("cwdchanged-hook-")):
                    if HOOK_ENV_REGEX.match(fname):
                        fpath = os.path.join(self._env_dir, fname)
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write("")
            self._cache = None
        except Exception as e:
            logger.warning(f"Failed to clear cwd env files: {e}")

    def list_env_files(self) -> List[Dict[str, str]]:
        """列出所有环境脚本文件"""
        results = []
        try:
            for fname in sorted(os.listdir(self._env_dir)):
                fpath = os.path.join(self._env_dir, fname)
                try:
                    size = os.path.getsize(fpath)
                    results.append({
                        "name": fname,
                        "path": fpath,
                        "size": size,
                        "has_content": size > 0,
                    })
                except OSError:
                    pass
        except OSError:
            pass
        return results

    def cleanup(self) -> bool:
        """清理会话环境目录"""
        import shutil
        try:
            if os.path.exists(self._env_dir):
                shutil.rmtree(self._env_dir, ignore_errors=True)
                return True
        except Exception as e:
            logger.warning(f"SessionEnv cleanup failed: {e}")
        return False


# ── 全局单例 ──

_current_env: Optional[SessionEnv] = None


def get_session_env() -> Optional[SessionEnv]:
    """获取当前会话环境实例"""
    return _current_env


def init_session_env(session_id: str) -> SessionEnv:
    """初始化当前会话环境"""
    global _current_env
    _current_env = SessionEnv(session_id=session_id)
    return _current_env


def close_session_env():
    """关闭当前会话环境"""
    global _current_env
    _current_env = None
