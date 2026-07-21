# ============================================================================
# gaet — Windows PowerShell installer
# Usage: irm https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.ps1 | iex
# ============================================================================
param()

$ErrorActionPreference = "Stop"

$GAET_DIR = "$env:USERPROFILE\.local\bin"
$GAET_CONFIG = "$env:USERPROFILE\.gaet"
$GITHUB_RAW = "https://raw.githubusercontent.com/ghanirahmans/gaet/main"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  gaet — Database Backup & Sync CLI                  ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check Python ───────────────────────────────────────────────────────
Write-Host "  Checking Python... " -NoNewline
try {
    $pythonVer = python --version 2>&1 | Select-String -Pattern "Python (\d+\.\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }
    Write-Host "OK ($pythonVer)" -ForegroundColor Green
} catch {
    Write-Host "NOT FOUND" -ForegroundColor Red
    Write-Host "  ✗ Python 3.8+ is required. Install from https://python.org"
    Write-Host ""
    Read-Host "Press Enter to exit"
    return
}

# ── 2. Check PostgreSQL tools ─────────────────────────────────────────────
Write-Host "  Checking pg_dump... " -NoNewline
try {
    $pgDumpPath = (Get-Command pg_dump -ErrorAction SilentlyContinue).Source
    if (-not $pgDumpPath) {
        # Check common Windows install paths
        $pgVersions = Get-ChildItem "C:\Program Files\PostgreSQL" -Directory -ErrorAction SilentlyContinue
        foreach ($ver in $pgVersions) {
            $pgBin = Join-Path $ver.FullName "bin\pg_dump.exe"
            if (Test-Path $pgBin) {
                $pgDumpPath = $pgBin
                break
            }
        }
    }
    if ($pgDumpPath) {
        Write-Host "OK" -ForegroundColor Green
    } else {
        throw "Not found"
    }
} catch {
    Write-Host "NOT FOUND" -ForegroundColor Yellow
    Write-Host "  ⚠  PostgreSQL tools not found. Download from https://www.postgresql.org/download/windows/"
}

# ── 3. Create directories ─────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $GAET_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $GAET_CONFIG | Out-Null
New-Item -ItemType Directory -Force -Path "$GAET_DIR\scripts" | Out-Null

# ── 4. Download gaet CLI (gaet.py) ───────────────────────────────────────
Write-Host "  Downloading gaet.py... " -NoNewline
try {
    # Use TLS 1.2 for GitHub
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri "$GITHUB_RAW/gaet.py" -OutFile "$GAET_DIR\gaet.py" -UseBasicParsing
    Write-Host " OK" -ForegroundColor Green
} catch {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "  ✗ Download failed. Check your internet connection."
    Write-Host ""
    Read-Host "Press Enter to exit"
    return
}

# ── 5. Download scripts ───────────────────────────────────────────────────
$scripts = @("status.py", "scheduler.py", "service_manager.py", "installer.py", "__init__.py")
foreach ($f in $scripts) {
    try {
        Invoke-WebRequest -Uri "$GITHUB_RAW/scripts/$f" -OutFile "$GAET_DIR\scripts\$f" -UseBasicParsing
    } catch {
        Write-Host "  ⚠  Failed to download scripts/$f" -ForegroundColor Yellow
    }
}
Write-Host "  Scripts downloaded"

# ── 6. Create gaet.cmd wrapper ────────────────────────────────────────────
# This lets users run `gaet` directly from anywhere
$wrapperContent = @"
@echo off
python "%~dp0gaet.py" %*
"@
$wrapperContent | Out-File -FilePath "$GAET_DIR\gaet.cmd" -Encoding ASCII
Write-Host "  Wrapper created: $GAET_DIR\gaet.cmd"

# ── 7. Create config if not exists ────────────────────────────────────────
$envFile = "$GAET_CONFIG\.env"
if (-not (Test-Path $envFile)) {
    $configContent = @"
# gaet configuration
# Docs: https://github.com/ghanirahmans/gaet#configuration
#
# MINIMUM required: GAET_REMOTE_URL
# Everything else has sensible defaults.

# Cloud database (REQUIRED)
# GAET_REMOTE_URL=postgresql://user:***@host:5432/db

# Local database (default: postgres@127.0.0.1:5432/postgres)
# GAET_LOCAL_URL=postgresql://postgres:@127.0.0.1:5432/postgres

# Retention (days)
# GAET_RETENTION_DAYS=7

# Dashboard port
# GAET_DASHBOARD_PORT=9191
"@
    $configContent | Out-File -FilePath $envFile -Encoding UTF8
    Write-Host "  Config created: $envFile"
} else {
    Write-Host "  Config exists: $envFile"
}

# ── 8. Add to PATH if not already there ──────────────────────────────────
Write-Host ""
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -like "*$GAET_DIR*") {
    Write-Host "  ✓ $GAET_DIR is in PATH" -ForegroundColor Green
} else {
    # Add to PATH for current session
    $env:Path = "$GAET_DIR;$env:Path"

    # Add to persistent User PATH
    [Environment]::SetEnvironmentVariable("Path", "$GAET_DIR;$userPath", "User")
    Write-Host "  ✓ Added $GAET_DIR to PATH" -ForegroundColor Green
    Write-Host "    (restart your terminal to use 'gaet' from anywhere)" -ForegroundColor Yellow
}

# ── 9. Done ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✓ Installation complete!                           ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:"
Write-Host "    1. Configure:  gaet init"
Write-Host "    2. Check:      gaet check"
Write-Host "    3. Backup:     gaet push"
Write-Host "    4. Dashboard:  gaet serve"
Write-Host ""
Write-Host "  Docs: https://github.com/ghanirahmans/gaet"
Write-Host ""
