# ============================================================================
# gaet — Windows PowerShell installer
# Usage: irm https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.ps1 | iex
# ============================================================================
param()

$ErrorActionPreference = "Stop"

$GAET_DIR = "$env:USERPROFILE\.local\bin"
$GAET_CONFIG = "$env:USERPROFILE\.gaet"
$GITHUB_RAW = "https://raw.githubusercontent.com/ghanirahmans/gaet/master"

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
    exit 1
}

# ── 2. Check PostgreSQL tools ─────────────────────────────────────────────
Write-Host "  Checking pg_dump... " -NoNewline
try {
    $pgDumpPath = (Get-Command pg_dump -ErrorAction SilentlyContinue).Source
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

# ── 4. Download gaet CLI ──────────────────────────────────────────────────
Write-Host "  Downloading gaet..." -NoNewline
try {
    # Use TLS 1.2 for GitHub
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri "$GITHUB_RAW/gaet" -OutFile "$GAET_DIR\gaet" -UseBasicParsing
    Write-Host " OK" -ForegroundColor Green
} catch {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "  ✗ Download failed. Check your internet connection."
    exit 1
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

# ── 6. Create config if not exists ────────────────────────────────────────
$envFile = "$GAET_CONFIG\.env"
if (-not (Test-Path $envFile)) {
    $configContent = @"
# gaet configuration
# Docs: https://github.com/ghanirahmans/gaet#configuration
#
# MINIMUM required: GAET_REMOTE_URL
# Everything else has sensible defaults.

# Cloud database (REQUIRED)
# GAET_REMOTE_URL=postgresql://user:pass@host:5432/db

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

# ── 7. Check PATH ─────────────────────────────────────────────────────────
Write-Host ""
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -like "*$GAET_DIR*") {
    Write-Host "  ✓ $GAET_DIR is in PATH" -ForegroundColor Green
} else {
    Write-Host "  ⚠  Add $GAET_DIR to your PATH:" -ForegroundColor Yellow
    Write-Host "     [Environment]::SetEnvironmentVariable('Path', `"`$env:PATH;$GAET_DIR`", 'User')"
    Write-Host ""
    Write-Host "     Or add manually via System Properties → Environment Variables"
}

# ── 8. Done ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✓ Installation complete!                           ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:"
Write-Host "    1. Configure:  python $GAET_DIR\gaet init"
Write-Host "    2. Check:      python $GAET_DIR\gaet check"
Write-Host "    3. Backup:     python $GAET_DIR\gaet push"
Write-Host "    4. Dashboard:  python $GAET_DIR\gaet serve"
Write-Host ""
Write-Host "  Docs: https://github.com/ghanirahmans/gaet"
Write-Host ""
