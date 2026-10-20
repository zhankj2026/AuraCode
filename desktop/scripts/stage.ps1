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

# 0. Clean stale output (idempotent)
if (Test-Path $resDir) {
  Write-Host '==> cleaning old resources/ ...' -ForegroundColor Yellow
  Remove-Item $resDir -Recurse -Force
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
robocopy $pySrc $pyDst /E /NFL /NDL /NJH /NJS /NC /NS /XD __pycache__ /XF *.pyc | Out-Null
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
Get-ChildItem $engDst -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
Get-ChildItem $engDst -Recurse -File -Filter *.pyc | Remove-Item -Force

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
Write-Host ''
Write-Host 'done. Run: npm run package' -ForegroundColor Green
