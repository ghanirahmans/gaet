# ============================================================================
# gaet — Windows PowerShell installer
# Usage: irm https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.ps1 | iex
# ============================================================================
param()

$ErrorActionPreference = "Stop"

$GAET_DIR = "$env:USERPROFILE\.local\bin"
$GAET_CONFIG = "$env:USERPROFILE\.gaet"
$GAET_APP_DIR = if ($env:LOCALAPPDATA) { "$env:LOCALAPPDATA\gaet" } else { "$env:USERPROFILE\AppData\Local\gaet" }

# Clean up legacy un-isolated folders if present
Remove-Item -Recurse -Force "$GAET_DIR\gaet_pkg" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$GAET_DIR\scripts" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$GAET_DIR\dashboard" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$GAET_DIR\completions" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$GAET_CONFIG\app" -ErrorAction SilentlyContinue

# Use TLS 1.2 for GitHub
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$GAET_BRANCH = if ($env:GAET_BRANCH) { $env:GAET_BRANCH } else { "lts/v1.0" }

# Resolve commit SHA dynamically to bypass GitHub raw CDN 5-minute cache
try {
    $commitResp = Invoke-RestMethod -Uri "https://api.github.com/repos/ghanirahmans/gaet/commits/$GAET_BRANCH" -UseBasicParsing -ErrorAction SilentlyContinue
    $commitSha = $commitResp.sha
} catch {
    $commitSha = $GAET_BRANCH
}
if (-not $commitSha) { $commitSha = $GAET_BRANCH }
$GITHUB_RAW = "https://raw.githubusercontent.com/ghanirahmans/gaet/$commitSha"

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
New-Item -ItemType Directory -Force -Path $GAET_APP_DIR | Out-Null
New-Item -ItemType Directory -Force -Path "$GAET_APP_DIR\scripts" | Out-Null
New-Item -ItemType Directory -Force -Path "$GAET_APP_DIR\src\gaet" | Out-Null
New-Item -ItemType Directory -Force -Path "$GAET_APP_DIR\completions" | Out-Null
New-Item -ItemType Directory -Force -Path "$GAET_APP_DIR\dashboard\static" | Out-Null
New-Item -ItemType Directory -Force -Path "$GAET_APP_DIR\dashboard\public" | Out-Null

# ── 4. Download gaet app bundle ───────────────────────────────────────────
Write-Host "  Downloading gaet.py... " -NoNewline
try {
    Invoke-WebRequest -Uri "$GITHUB_RAW/gaet.py" -OutFile "$GAET_APP_DIR\gaet.py" -UseBasicParsing
    Write-Host " OK" -ForegroundColor Green
} catch {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "  ✗ Download failed. Check your internet connection."
    Write-Host ""
    Read-Host "Press Enter to exit"
    return
}

# ── 4b. Download gaet_pkg ───────────────────────────────────────────────
$pkgDir = "$GAET_APP_DIR\src\gaet"
$pkgFiles = @(
    "__init__.py", "__main__.py", "registry.py", "cli.py", "core.py",
    "detect.py", "init.py", "config.py", "status.py", "backup.py",
    "scheduler.py", "log.py", "serve.py", "export.py", "update.py",
    "remote.py", "snapshots.py"
)
foreach ($f in $pkgFiles) {
    try {
        Invoke-WebRequest -Uri "$GITHUB_RAW/src/gaet/$f" -OutFile "$pkgDir\$f" -UseBasicParsing
    } catch {
        Write-Host "  ⚠  Failed to download src/gaet/$f" -ForegroundColor Yellow
    }
}

# ── 5. Download scripts ───────────────────────────────────────────────────
$scripts = @("status.py", "scheduler.py", "service_manager.py", "installer.py", "__init__.py")
foreach ($f in $scripts) {
    try {
        Invoke-WebRequest -Uri "$GITHUB_RAW/scripts/$f" -OutFile "$GAET_APP_DIR\scripts\$f" -UseBasicParsing
    } catch {
        Write-Host "  ⚠  Failed to download scripts/$f" -ForegroundColor Yellow
    }
}

# ── 5a. Download completions ──────────────────────────────────────────────
$compDir = "$GAET_APP_DIR\completions"
$compFiles = @("gaet.bash", "gaet.zsh", "gaet.fish", "gaet.ps1")
foreach ($f in $compFiles) {
    try {
        Invoke-WebRequest -Uri "$GITHUB_RAW/completions/$f" -OutFile "$compDir\$f" -UseBasicParsing
    } catch {
        Write-Host "  ⚠  Failed to download completions/$f" -ForegroundColor Yellow
    }
}

# ── 5b. Download dashboard ────────────────────────────────────────────────
$dashboardDir = "$GAET_APP_DIR\dashboard"
$dashboardFiles = @("server.py", "static/index.html", "public/gaet-logo.png")
foreach ($f in $dashboardFiles) {
    try {
        Invoke-WebRequest -Uri "$GITHUB_RAW/dashboard/$f" -OutFile "$dashboardDir\$f" -UseBasicParsing
    } catch {
        Write-Host "  ⚠  Failed to download dashboard/$f" -ForegroundColor Yellow
    }
}
Write-Host "  App bundle downloaded ($GAET_APP_DIR)" -ForegroundColor Green

# ── 6. Create gaet.cmd wrapper ────────────────────────────────────────────
$wrapperContent = @"
@echo off
python "$GAET_APP_DIR\gaet.py" %*
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
