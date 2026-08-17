# ============================================================================
# gaet v1.1.0 LTS — PowerShell One-liner Installer (Windows)
# Usage: irm https://raw.githubusercontent.com/ghanirahmans/gaet/main/install.ps1 | iex
# ============================================================================
$ErrorActionPreference = "Stop"

$GaetBinDir = Join-Path $env:USERPROFILE ".local\bin"
$GaetConfig = Join-Path $env:USERPROFILE ".gaet"
$BinaryPath = Join-Path $GaetBinDir "gaet.exe"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  gaet v1.1.0 LTS - Database Backup & Cloud Sync CLI  " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Create directories
New-Item -ItemType Directory -Force -Path $GaetBinDir | Out-Null
New-Item -ItemType Directory -Force -Path $GaetConfig | Out-Null

# Clean legacy python app share
$LegacyAppDir = Join-Path $env:LOCALAPPDATA "gaet"
if (Test-Path $LegacyAppDir) {
    Remove-Item -Recurse -Force $LegacyAppDir -ErrorAction SilentlyContinue
}

# Install Go binary
if (Test-Path "go.mod") {
    Write-Host "  [INFO]  Building gaet.exe from local source..." -ForegroundColor Yellow
    go build -ldflags="-s -w" -o $BinaryPath ./cmd/gaet
    Write-Host "  [ OK ]  Built binary -> $BinaryPath" -ForegroundColor Green
} else {
    Write-Host "  [INFO]  Downloading latest gaet.exe release..." -ForegroundColor Yellow
    $DownloadUrl = "https://github.com/ghanirahmans/gaet/releases/latest/download/gaet-windows-amd64.exe"
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $BinaryPath
    Write-Host "  [ OK ]  Downloaded binary -> $BinaryPath" -ForegroundColor Green
}

# Create default .env if missing
$EnvFile = Join-Path $GaetConfig ".env"
if (-not (Test-Path $EnvFile)) {
    $DefaultConfig = @"
# gaet configuration
GAET_LOCAL_URL=postgresql://postgres@127.0.0.1:5432/postgres
GAET_REMOTE_URL=
GAET_RETENTION_DAYS=7
"@
    Set-Content -Path $EnvFile -Value $DefaultConfig
    Write-Host "  [ OK ]  Config created -> $EnvFile" -ForegroundColor Green
}

# Ensure PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$GaetBinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$GaetBinDir", "User")
    Write-Host "  [ OK ]  Added $GaetBinDir to User PATH" -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "     Installation complete!                           " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Run 'gaet init' to configure database connections."
Write-Host ""
