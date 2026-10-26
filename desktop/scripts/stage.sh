#!/usr/bin/env bash
# ============================================================
# AuraCode desktop - stage resources (bash port of stage.ps1)
#
# Copies portable Python + curated engine source into
# desktop/resources/, consumed by electron-builder extraResources.
# Git-Bash friendly (no powershell dependency).
#
# Usage (from desktop/):
#   bash scripts/stage.sh
# ============================================================
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP="$(dirname "$SCRIPT_DIR")"
REPO="$(dirname "$DESKTOP")"
RES="$DESKTOP/resources"

# 0. clean stale output
rm -rf "$RES"
mkdir -p "$RES"

# 1. portable Python
PY_SRC="${PYTHON_SRC:-$USERPROFILE/.workbuddy/binaries/python/versions/3.13.12}"
if [ ! -f "$PY_SRC/python.exe" ]; then
  echo "ERROR: portable python not found: $PY_SRC/python.exe" >&2
  echo "       set PYTHON_SRC to a dir containing python.exe" >&2
  exit 1
fi
echo "==> copying portable python: $PY_SRC -> $RES/python"
cp -r "$PY_SRC" "$RES/python"
find "$RES/python" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
find "$RES/python" -type f -name '*.pyc' -delete 2>/dev/null

# 2. engine source (curated, same list as stage.ps1)
echo "==> copying engine source: $REPO -> $RES/engine"
mkdir -p "$RES/engine"
for f in cli.py config.yaml config.example.yaml requirements.txt LICENSE README.md; do
  [ -f "$REPO/$f" ] && cp "$REPO/$f" "$RES/engine/"
done
for d in bridge core skills tools mcp hooks plugins permissions services commands config; do
  [ -d "$REPO/$d" ] && cp -r "$REPO/$d" "$RES/engine/"
done
find "$RES/engine" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
find "$RES/engine" -type f -name '*.pyc' -delete 2>/dev/null

# 3. size report
du -sm "$RES/python" "$RES/engine" 2>/dev/null
echo "done. next: electron-vite build && electron-builder --win nsis"
