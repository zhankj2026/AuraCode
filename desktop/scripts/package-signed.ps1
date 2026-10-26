# ============================================================
# AuraCode desktop - signed packaging script (PowerShell)
#
# Purpose: npm run package + Authenticode signing in one step.
# Cert and password are read from local files only, never
# hardcoded, never on the command line:
#   - D:\certs\auracode-selfsign.pfx     cert (CSC_LINK)
#   - D:\certs\sign-password.txt         key password (CSC_KEY_PASSWORD)
#
# If either file is missing, falls back to unsigned build
# (identical to plain `npm run package`).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/package-signed.ps1
#
# NOTE: keep this file ASCII-only. PowerShell 5.1 reads BOM-less
# UTF-8 scripts as ANSI/GBK and Chinese comments break parsing.
# ============================================================

$ErrorActionPreference = 'Continue'

# CN mirrors (first run downloads Electron dist / NSIS / sign tools)
$env:ELECTRON_MIRROR = 'https://npmmirror.com/mirrors/electron/'
$env:npm_config_electron_builder_binaries_mirror = 'https://npmmirror.com/mirrors/electron-builder-binaries/'

$pfxPath = 'D:\certs\auracode-selfsign.pfx'
$pwdFile = 'D:\certs\sign-password.txt'

if ((Test-Path $pfxPath) -and (Test-Path $pwdFile)) {
  $env:CSC_LINK = $pfxPath
  $env:CSC_KEY_PASSWORD = (Get-Content $pwdFile -Raw).Trim()
  Write-Host "==> signing ENABLED with $pfxPath" -ForegroundColor Cyan
} else {
  Write-Host '==> cert or password file missing, building UNSIGNED' -ForegroundColor Yellow
  Write-Host "    expected: $pfxPath and $pwdFile" -ForegroundColor DarkGray
}

# Run from desktop/ (this script lives in desktop/scripts/)
Set-Location (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) '..')

Write-Host '==> npm run package ...' -ForegroundColor Cyan
npm run package
exit $LASTEXITCODE
