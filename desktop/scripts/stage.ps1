# ============================================================
# Stage built-in resources for Windows production packaging:
#   portable Python + AuraCode engine source.
# Produces desktop/resources/python and desktop/resources/engine,
# consumed by electron-builder extraResources into <install>/resources.
#
# Python source: env PYTHON_SRC (default managed Python 3.13.12,
#   already has fastapi/uvicorn/etc). Copied as portable python.
# Engine source: repo root (parent of desktop). Only files needed to
#   run `cli.py --bridge` are copied (node_modules/.workbuddy/large
#   demo dirs/__pycache__ are excluded).
# best-effort: pip install -r requirements.txt into the copy.
# This script does NOT modify any source; it only writes under
# desktop/resources.
# ============================================================

$ErrorActionPreference = 'Continue'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$desktop   = Split-Path -Parent $scriptDir
$repo      = Split-Path -Parent $desktop
$resDir    = Join-Path $desktop 'resources'

# 0. Clean stale output (idempotent).
# Use robocopy /MIR to an empty temp dir for deletion: plain Remove-Item
# -Recurse fails once a prior broken run leaves path-too-long nesting
# (e.g. python/3.13.12/3.13.12/...). /MIR can delete arbitrarily deep trees.
if (Test-Path $resDir) {
  Write-Host '==> cleaning old resources/ ...' -ForegroundColor Yellow
  $emptyTmp = Join-Path $env:TEMP ('ac_stage_clean_' + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $emptyTmp | Out-Null
  robocopy $emptyTmp $resDir /MIR /R:0 /W:0 /NFL /NDL /NJH | Out-Null
  Remove-Item $emptyTmp -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item $resDir -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $resDir | Out-Null

# 1. Portable Python
$pySrc = if ($env:PYTHON_SRC) { $env:PYTHON_SRC } else { "$env:USERPROFILE\.workbuddy\binaries\python\versions\3.13.12" }
$pyDst = Join-Path $resDir 'python'
if (-not (Test-Path (Join-Path $pySrc 'python.exe'))) {
  Write-Error "portable Python not found: $pySrc\python.exe`nSet `$env:PYTHON_SRC to a dir containing python.exe."
  exit 1
}
Write-Host "==> copying portable Python: $pySrc -> $pyDst" -ForegroundColor Cyan
# IMPORTANT: the managed-python root contains a self-referential symlink
# `3.13.12` that points back to the install dir itself. Copying it (or
# dereferencing it) creates python/3.13.12/3.13.12/... recursion that
# exceeds MAX_PATH. Exclude it by name (/XD) and skip junctions (/XJ).
robocopy $pySrc $pyDst /E /NFL /NDL /NJH /NJS /NC /NS /XJ /XD __pycache__ 3.13.12 /XF *.pyc | Out-Null
$pyExe = Join-Path $pyDst 'python.exe'
if (-not (Test-Path $pyExe)) { Write-Error 'python.exe copy failed'; exit 1 }

# 2. Engine source (curated)
$engDst = Join-Path $resDir 'engine'
New-Item -ItemType Directory -Path $engDst | Out-Null
$files = @('cli.py', 'config.yaml', 'config.example.yaml', 'requirements.txt', 'LICENSE', 'README.md')
$dirs  = @('bridge', 'core', 'skills', 'tools', 'mcp', 'hooks', 'plugins', 'permissions', 'services', 'commands', 'config')
Write-Host "==> copying engine source: $repo -> $engDst" -ForegroundColor Cyan
foreach ($f in $files) {
  $src = Join-Path $repo $f
  if (Test-Path $src) { Copy-Item $src $engDst -Force }
}
foreach ($d in $dirs) {
  $src = Join-Path $repo $d
  $dst = Join-Path $engDst $d
  if (Test-Path $src) { robocopy $src $dst /E /NFL /NDL /NJH /NJS /NC /NS /XD __pycache__ /XF *.pyc | Out-Null }
}
$p = Get-ChildItem $engDst -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue
if ($p) { Microsoft.PowerShell.Management\Remove-Item -LiteralPath $p.FullName -Recurse -Force }
$q = Get-ChildItem $engDst -Recurse -File -Filter *.pyc -ErrorAction SilentlyContinue
if ($q) { Microsoft.PowerShell.Management\Remove-Item -LiteralPath $q.FullName -Force }

# 2b. Sanitize config: NEVER ship a real api_key in the installer.
#     sanitize_config.py is stdlib-only; uses the staged python. Fails the
#     build if a non-empty api_key would remain.
$cfgPath = Join-Path $engDst 'config.yaml'
if (Test-Path $cfgPath) {
  $saniPy = Join-Path $scriptDir 'sanitize_config.py'
  Write-Host '==> sanitizing config.yaml (stripping api_key)' -ForegroundColor Cyan
  & $pyExe $saniPy $cfgPath
  if ($LASTEXITCODE -ne 0) {
    Write-Error 'ERROR: config.yaml api_key sanitization failed'
    exit 1
  }
}

# 2c. Compile engine to bytecode, then strip plaintext .py sources.
#     Python 3.13 bytecode has no mature decompiler (uncompyle6 stops at 3.8,
#     pycdc quality on 3.13 is poor), so this materially raises leak cost.
#     cli.py is the Electron spawn entry and is kept as plaintext shell.
$skipCompile = if ($env:SKIP_COMPILE) { $env:SKIP_COMPILE -eq '1' } else { $false }
if ($skipCompile) {
  Write-Host '==> SKIP_COMPILE=1: keeping .py sources (DEBUG ONLY, do not ship)' -ForegroundColor Yellow
} else {
  Write-Host '==> compiling engine sources to bytecode (.pyc)' -ForegroundColor Cyan
  & $pyExe -m compileall -q -b $engDst
  if ($LASTEXITCODE -ne 0) {
    Write-Error 'compileall failed; aborting to keep build safe'
    exit 1
  }
  Write-Host '==> removing plaintext .py sources (cli.py kept as spawn entry)' -ForegroundColor Cyan
                      $pyFiles = Get-ChildItem $engDst -Recurse -File -Filter *.py -ErrorAction SilentlyContinue |
                        Where-Object { $_.Name -ne 'cli.py' }
                      if ($pyFiles) { Microsoft.PowerShell.Management\Remove-Item -LiteralPath $pyFiles.FullName -Force }
                      $p2 = Get-ChildItem $engDst -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue
                      if ($p2) { Microsoft.PowerShell.Management\Remove-Item -LiteralPath $p2.FullName -Recurse -Force }
}

# 3. best-effort dependency install
Write-Host '==> checking deps (best-effort; skips if offline)...' -ForegroundColor Cyan
$req = Join-Path $repo 'requirements.txt'
try {
  & $pyExe -m pip install --no-input -r $req 2>&1 | ForEach-Object { Write-Host "   pip: $_" }
} catch {
  Write-Warning "pip install failed (likely offline); using deps already in source Python. Error: $_"
}
$deps = @('fastapi', 'uvicorn', 'pydantic', 'yaml', 'httpx', 'websockets', 'aiohttp', 'openai')
$bad = @()
foreach ($m in $deps) {
  & $pyExe -c "import $m" 2>$null
  if ($LASTEXITCODE -ne 0) { $bad += $m }
}
if ($bad.Count -eq 0) {
  Write-Host '   dep check passed: fastapi/uvicorn/pydantic/... ok' -ForegroundColor Green
} else {
  Write-Warning "missing deps: $($bad -join ', ')"
}

# 4. Size report
function SizeMB($p) {
  $bytes = (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
  return '{0:N1} MB' -f ($bytes / 1MB)
}
Write-Host ''
Write-Host '==> artifact sizes:' -ForegroundColor Green
Write-Host "    resources/python : $(SizeMB $pyDst)"
Write-Host "    resources/engine : $(SizeMB $engDst)"
Write-Host "    total            : $(SizeMB $resDir)"

# 5. Security audit
$pyCount  = (Get-ChildItem $engDst -Recurse -File -Filter *.py).Count
$pycCount = (Get-ChildItem $engDst -Recurse -File -Filter *.pyc).Count
Write-Host ''
Write-Host '==> security audit:' -ForegroundColor Green
Write-Host "    engine .py  : $pyCount (expect 1: cli.py)"
Write-Host "    engine .pyc : $pycCount"
if ($pyCount -ne 1) {
  Write-Warning "engine has $pyCount .py files (expected 1 = cli.py). Do NOT ship plaintext sources."
}
if ($skipCompile) {
  Write-Warning 'SKIP_COMPILE was set - plaintext .py sources present. DEBUG ONLY.'
}
Write-Host ''
Write-Host 'done. Run: npm run package' -ForegroundColor Green
