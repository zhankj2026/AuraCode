#!/usr/bin/env bash
# ============================================================
# AuraCode desktop - stage resources (bash port of stage.ps1)
# SECURITY-HARDENED version: compiles engine to .pyc bytecode
# and removes plaintext .py sources from the staged copy.
#
# What it does:
#   1. copy portable Python -> resources/python
#   2. copy curated engine source -> resources/engine
#   3. compileall -b engine (pyc next to py, source-keeping mode)
#   4. DELETE every .py except cli.py (entry shell spawned by
#      desktop main process via `python cli.py --bridge`)
#   5. optional: pip install engine deps into staged python
#      (skipped silently when offline; deps then expected in
#      the source python already)
#
# Why cli.py stays: Electron spawns it by filename. It contains
# no business logic beyond arg parsing + dispatch, acceptable.
#
# Reversing difficulty: Python 3.13 bytecode has NO mature
# decompiler today (uncompyle6 stops at 3.8; pycdc quality on
# 3.13 is poor). Sources are effectively protected.
#
# Usage (from desktop/):
#   bash scripts/stage.sh
# Env:
#   PYTHON_SRC   - portable python source dir
#   SKIP_COMPILE=1 - keep .py sources (debug only)
#   PIP_MIRROR   - defaults to tsinghua
# ============================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP="$(dirname "$SCRIPT_DIR")"
REPO="$(dirname "$DESKTOP")"
RES="$DESKTOP/resources"

PY_SRC="${PYTHON_SRC:-$USERPROFILE/.workbuddy/binaries/python/versions/3.13.12}"

# 0. clean stale output
rm -rf "$RES"
mkdir -p "$RES"

# 1. portable Python
if [ ! -f "$PY_SRC/python.exe" ]; then
  echo "ERROR: portable python not found: $PY_SRC/python.exe" >&2
  echo "       set PYTHON_SRC to a dir containing python.exe" >&2
  exit 1
fi
echo "==> copying portable python: $PY_SRC -> $RES/python"
# tar is used instead of cp/robocopy: the managed-python root holds a
# self-referential symlink `3.13.12` -> the install dir itself. `cp -rL`
# dereferences it (infinite python/3.13.12/3.13.12/...); robocopy's /flags
# get mangled to paths by MSYS in Git Bash. tar --exclude drops the symlink;
# -h derefs any other symlinks to real files (portable, no dangling links).
mkdir -p "$RES/python"
tar -C "$PY_SRC" -cf - --exclude='3.13.12' -h . 2>/dev/null | tar -C "$RES/python" -xf - 2>/dev/null
if [ ! -f "$RES/python/python.exe" ]; then
  echo "ERROR: staged python.exe missing after copy" >&2
  echo "       (source junction failed to dereference? check $PY_SRC)" >&2
  exit 1
fi
find "$RES/python" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
find "$RES/python" -type f -name '*.pyc' -delete 2>/dev/null

# 2. engine source (curated, same list as stage.ps1)
echo "==> copying engine source: $REPO -> $RES/engine"
mkdir -p "$RES/engine"
for f in cli.py config.yaml config.example.yaml requirements.txt LICENSE README.md; do
  [ -f "$REPO/$f" ] && cp "$REPO/$f" "$RES/engine/"
done
for d in bridge core skills tools mcp hooks plugins permissions services commands config; do
  [ -d "$REPO/$d" ] && cp -rL "$REPO/$d" "$RES/engine/"
done
find "$RES/engine" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
find "$RES/engine" -type f -name '*.pyc' -delete 2>/dev/null

# 3. config sanitization: NEVER ship real api_key in installer.
#    python-based (CRLF-safe, idempotent); fails the build if a
#    real key would remain. Users configure their own key on
#    first run (config UI / OPENAI_API_KEY env).
#    Falls back to any available system python if the staged one
#    is unusable (sanitizer is stdlib-only, interpreter-agnostic).
SANI_PY="$RES/python/python.exe"
if [ ! -f "$SANI_PY" ]; then
  SANI_PY="$(command -v python || command -v python3 || true)"
  if [ -z "$SANI_PY" ]; then
    echo "ERROR: no python available for config sanitization" >&2
    exit 1
  fi
  echo "    (staged python unavailable, falling back to system python)"
fi
if [ -f "$RES/engine/config.yaml" ]; then
  echo "==> sanitizing config.yaml (stripping api_key)"
  if ! "$SANI_PY" "$SCRIPT_DIR/sanitize_config.py" "$RES/engine/config.yaml"; then
    echo ""
    echo "ERROR: config.yaml api_key sanitization failed" >&2
    exit 1
  fi
fi

# 4. compile engine to bytecode + strip sources
PY_EXE="$RES/python/python.exe"
if [ ! -f "$PY_EXE" ]; then
  echo "ERROR: staged python.exe missing - cannot compile. Aborting." >&2
  exit 1
fi
if [ "${SKIP_COMPILE:-0}" = "1" ]; then
  echo "==> SKIP_COMPILE=1: keeping .py sources (DEBUG ONLY, do not ship)"
else
  echo "==> compiling engine sources to bytecode (.pyc)"
  (cd "$RES/engine" && "$PY_EXE" -m compileall -q -b . )
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "ERROR: compileall failed (rc=$rc), aborting to keep build safe" >&2
    exit 1
  fi
  echo "==> removing plaintext .py sources (cli.py kept as spawn entry)"
  find "$RES/engine" -name '*.py' ! -name 'cli.py' -delete
  # drop legacy __pycache__ dirs if any (we use -b legacy layout)
  find "$RES/engine" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
fi

# 5. optional dep install into staged python (network required)
PIP_MIRROR="${PIP_MIRROR:-https://pypi.tuna.tsinghua.edu.cn/simple}"
if [ "${SKIP_PIP:-0}" != "1" ]; then
  echo "==> installing engine deps into staged python (best-effort)"
  (cd "$RES/python" && NO_PROXY='*' no_proxy='*' ./python.exe -m pip install \
     --no-input -i "$PIP_MIRROR" -q \
     openai pyyaml fastapi uvicorn pydantic httpx websockets aiohttp pywin32 \
     2>&1 | grep -v '^$' | head -5)
  # verify
  if NO_PROXY='*' "$PY_EXE" -c "import openai, yaml, fastapi, uvicorn, pydantic, httpx, websockets, aiohttp" 2>/dev/null; then
    echo "    deps OK"
  else
    echo "    WARN: deps missing in staged python (offline?)."
    echo "    Engine will fail at runtime unless source python already has them."
  fi
fi

# 6. size report + security audit
echo "==> security audit:"
echo "    .py remaining : $(find "$RES/engine" -name '*.py' | wc -l) (expect 1: cli.py)"
echo "    .pyc count    : $(find "$RES/engine" -name '*.pyc' | wc -l)"
if [ -f "$RES/engine/config.yaml" ]; then
  KEY_STATE=$(cd "$RES/engine" && "$PY_EXE" -c "import re; s=open('config.yaml','rb').read().decode('utf-8'); m=re.search(r'(?m)^\s*api_key:[ \t]*([^\r\n]*)', s); print('SANITIZED' if (m is None or m.group(1).strip() in ('','\x22\x22',\"''\")) else 'LEAKED')")
  if [[ "$KEY_STATE" == "SANITIZED" ]]; then
    echo "    config api_key: SANITIZED"
  else
    echo "    config api_key: LEAKED !!! DO NOT SHIP" >&2
  fi
fi
du -sm "$RES/python" "$RES/engine" 2>/dev/null
echo "done. next: electron-vite build && electron-builder --win nsis"
