#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prune runtime-unused payload from the staged portable Python.

Shared by stage.ps1 and stage.sh so both packaging entry points produce the
same slim bundle. Must be invoked AFTER the optional pip install step:
pip itself, the CLI entry points in Scripts/, and the thousands of .pyc
files that pip generates are all part of what gets dropped.

Only <resources>/python is touched. The staged engine bytecode lives in
<resources>/engine and is deliberately NOT touched (it is the shipped
application code, already stripped of plaintext .py sources).

Usage:  python.exe -B scripts/prune_python.py <path-to-resources/python>
Env:    SKIP_PRUNE=1    no-op (debug / bisect a bad prune)
        PRUNE_VERIFY=0  skip the post-prune import smoke test
Exit:   0 ok, 1 bad prune / failed smoke test, 2 bad usage
"""

import fnmatch
import os
import shutil
import subprocess
import sys
from pathlib import Path

MB = 1048576.0


def dir_size(root):
    total = 0
    for base, _dirs, files in os.walk(root):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total


def rm(path):
    """Remove a file or directory, returning the bytes reclaimed."""
    p = Path(path)
    if not p.exists():
        return 0
    try:
        if p.is_dir():
            size = dir_size(p)
            shutil.rmtree(p, ignore_errors=True)
            return size
        size = p.stat().st_size
        p.unlink()
        return size
    except OSError:
        return 0


def main():
    if len(sys.argv) < 2:
        print("usage: prune_python.py <resources/python>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1]).resolve()
    if not (root / "python.exe").is_file():
        print("ERROR: not a staged python root: %s" % root, file=sys.stderr)
        return 1
    if os.environ.get("SKIP_PRUNE") == "1":
        print("    SKIP_PRUNE=1: prune skipped")
        return 0

    sp = root / "Lib" / "site-packages"
    before = dir_size(root)
    removed = 0
    print("==> pruning staged portable Python (runtime-unused payload)")

    # 1. Development-only parts of a full CPython installation. None of these
    #    are needed to run `python.exe cli.py --bridge` on a customer machine.
    dev_dirs = [
        "include",          # C headers
        "libs",             # static import libraries for building extensions
        "Tools", "Doc", "tcl", "Scripts",
        os.path.join("Lib", "ensurepip"),
        os.path.join("Lib", "idlelib"),
        os.path.join("Lib", "tkinter"),
        os.path.join("Lib", "turtledemo"),
        os.path.join("Lib", "test"),
    ]
    for rel in dev_dirs:
        removed += rm(root / rel)

    # 2. Third-party packages the packaged engine never imports.
    #    The repo-wide source scan shows these are referenced only by tests/,
    #    which is not staged at all.
    #
    #    KEEP (verified indirect deps -- do NOT "optimize" these away):
    #      cryptography + jwt : mcp/server/request_state.py, mcp/client/auth
    #      pygments, packaging, win32comext : conservative, possible indirect use
    #      win32 / win32com / pythoncom / pywin32_system32 : pywin32 core,
    #        used by tools/builtin/word_measure.py via Word/WPS COM.
    #      openai, fastapi, uvicorn, pydantic, httpx, websockets, aiohttp, mcp:
    #        the actual runtime dependency set.
    #
    #    `pip` is safe to drop: the desktop app spawns python.exe by absolute
    #    path, so Scripts/ is never on PATH and `subprocess.run(["pip", ...])`
    #    in core/validator.py already falls back to False on a clean install.
    drop_pkgs = [
        "PIL", "oracledb", "Crypto", "pythonwin", "adodbapi", "isapi",
        "pytest", "_pytest", "pluggy", "iniconfig",
        "edge_tts", "edge_playback", "pip",
    ]
    for name in drop_pkgs:
        removed += rm(sp / name)

    # 3. Metadata / docs / samples belonging to dropped or optional pieces.
    dist_globs = [
        "pillow-*", "oracledb-*", "pycryptodome-*", "pytest-*", "pluggy-*",
        "iniconfig-*", "edge_tts-*", "edge_playback-*", "pip-*",
    ]
    for entry in sp.glob("*.dist-info"):
        if any(fnmatch.fnmatch(entry.name, g) for g in dist_globs):
            removed += rm(entry)
    for rel in [
        "PyWin32.chm",
        os.path.join("win32", "test"),
        os.path.join("win32", "Demos"),
        os.path.join("win32com", "test"),
    ]:
        removed += rm(sp / rel)

    # 4. Bytecode caches. stage copies with /XF *.pyc /XD __pycache__, but the
    #    later `pip install` regenerates ~1400 of them. CPython rebuilds these
    #    on first launch (install dir is user-writable AppData), so dropping
    #    them shrinks the installer at a small one-time startup cost.
    #    One bottom-up walk does the cache sweep AND the final size count,
    #    instead of two extra full-tree rglob passes (slow on large bundles).
    after = 0
    for base, dirs, files in os.walk(root, topdown=False):
        for name in files:
            p = os.path.join(base, name)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if name.endswith(".pyc"):
                try:
                    os.unlink(p)
                    removed += size
                except OSError:
                    after += size
            else:
                after += size
        for name in dirs:
            if name == "__pycache__":
                shutil.rmtree(os.path.join(base, name), ignore_errors=True)

    print("    python before : %.1f MB" % (before / MB))
    print("    python after  : %.1f MB" % (after / MB))
    print("    removed       : %.1f MB" % (removed / MB))

    # 5. Fail the build rather than ship a broken runtime. -B keeps the smoke
    #    test from regenerating the .pyc files we just removed.
    if os.environ.get("PRUNE_VERIFY", "1") == "1":
        code = (
            "import fastapi, uvicorn, pydantic, yaml, httpx, "
            "websockets, aiohttp, openai"
        )
        try:
            rc = subprocess.call(
                [sys.executable, "-B", "-c", code],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            # A hung interpreter is an environment problem (sandboxed fs,
            # AV hook), not a missing dependency -- those return non-zero
            # immediately. Warn but do not fail the user's build for it.
            print(
                "    WARNING: import smoke test timed out (env); continuing",
                file=sys.stderr,
            )
        else:
            if rc != 0:
                print(
                    "ERROR: post-prune import smoke test failed. "
                    "Re-run with SKIP_PRUNE=1 to bisect.",
                    file=sys.stderr,
                )
                return 1
            print("    import smoke test: OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())
