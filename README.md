# gaet(1) — PostgreSQL Backup & Sync CLI

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Engine: Go](https://img.shields.io/badge/engine-Go%20(Recommended)-brightgreen.svg)](SUPPORT.md)
[![Alternative: Python](https://img.shields.io/badge/legacy-Python%20(Alternative)-yellow.svg)](SUPPORT.md)
[![Platform: Linux | macOS | Windows](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20Windows-supported-brightgreen.svg)]()
[![v1.1.0 LTS](https://img.shields.io/badge/v1.1.0-LTS-blue?label=release)](SUPPORT.md)

> **gaet** is a zero-dependency PostgreSQL database backup and cloud synchronization CLI.
> 
> **Architectural Editions**:
> - **Go Engine (`v1.1.0 LTS`) — Recommended**: Single portable binary for active production and ongoing feature development.
> - **Python Engine (`v1.0.0 LTS`) — Legacy Alternative**: Maintained for backwards compatibility until August 2027.

---

## Table of Contents

1. [Name & Synopsis](#name--synopsis)
2. [Description & Architecture](#description--architecture)
3. [Quick Start](#quick-start)
4. [Installation](#installation)
5. [Command Specifications](#command-specifications)
   - [Setup & Lifecycle](#1-setup--lifecycle)
   - [Data Synchronization](#2-data-synchronization)
   - [Status & Diagnostics](#3-status--diagnostics)
   - [Configuration & Remote Management](#4-configuration--remote-management)
   - [Services & Monitoring](#5-services--monitoring)
6. [Configuration Reference](#configuration-reference)
7. [Workflows & Practical Guides](#workflows--practical-guides)
8. [Security & Hardening](#security--hardening)
9. [Troubleshooting](#troubleshooting)
10. [See Also](#see-also)

---

## Name & Synopsis

**NAME**  
`gaet` - PostgreSQL backup and synchronization CLI.

**SYNOPSIS**  
```bash
gaet [<global-options>] <command> [<args>]
```

**GLOBAL OPTIONS**  
- `-q, --quiet` : Suppress non-essential output headers.
- `--plain`     : Output plain TSV lines (pipe-safe for `grep` and `awk`).
- `--json`      : Return raw JSON objects.
- `--dry-run`   : Simulate execution without writing files or mutating databases.

---

## Description & Architecture

`gaet` bridges local PostgreSQL development environments with remote cloud database providers (Supabase, Neon, AWS RDS, GCP Cloud SQL, or custom VPS instances). Designed with Git parity in mind, `gaet` treats local database dumps as versioned snapshots that can be pushed to or fetched from remote instances cleanly.

```
                  ┌──────────────────────────────────────────────┐
                  │                 gaet CLI                     │
                  └──────────────────────┬───────────────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
      ┌─────────────────────────┐                 ┌─────────────────────────┐
      │   Local DB Instance     │                 │   Cloud DB Remote       │
      │ 127.0.0.1 / Unix Socket │                 │ Supabase / Neon / VPS   │
      └────────────┬────────────┘                 └────────────▲────────────┘
                   │                                           │
                   │ pg_dump -Fc (Compress)                    │ pg_restore --clean
                   ▼                                           │
      ┌─────────────────────────┐                              │
      │  Local Backup Snapshot  ├──────────────────────────────┘
      │  ~/.gaet/backups/*.dump │
      └─────────────────────────┘
```

### Architectural Guarantees

1. **Zero External Dependencies**: Implemented strictly using the Go Standard Library (`net/http`, `os`, `syscall`, `embed`). Compiled into a fast portable single binary without external runtime dependencies.
2. **Passwordless Security Model**: PostgreSQL operations (`psql`, `pg_dump`, `pg_restore`) enforce the `-w` (`--no-password`) flag alongside atomic, temporary `PGPASSFILE` instances (`0600` permission level). Plaintext passwords are never passed as command-line flags or logged to history.
3. **Atomic State & Environment Updates**: Configuration key updates via `gaet set` utilize atomic line-by-line single-pass updates to `~/.gaet/.env` to prevent config corruption.
4. **Concurrency Safety**: Non-blocking file locks (`~/.gaet/gaet.lock`) prevent overlapping execution during automated scheduled backups or simultaneous manual invocations.
5. **Git Workspace Integration**: Running `gaet init` initializes a version-controlled workspace in `~/.gaet` (with strict `.gitignore` rules shielding secrets, lock files, and dump payloads).

---

## Quick Start

Get up and running in under 2 minutes:

```bash
# 1. Install gaet CLI (LTS Release)
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh | bash

# 2. Run interactive setup wizard
gaet init

# 3. Create your first cloud backup
gaet push

# 4. Verify table sync status
gaet status
```

---

## Installation

### Method 1: Automated Script (Recommended LTS Release)

**Linux / macOS (Bash):**
```bash
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.ps1 | iex
```

### Method 2: Build from Source / Go Toolchain

**Option A: Install via `go install`**
```bash
go install github.com/ghanirahmans/gaet/cmd/gaet@latest
```

**Option B: Clone & Build Binary**
```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
go build -ldflags="-s -w" -o ~/.local/bin/gaet ./cmd/gaet
```

### Legacy Python Edition (Maintenance Mode)

> [!WARNING]
> The Python implementation (`v1.0.0 LTS`) is in maintenance mode. Active feature development has moved exclusively to the Golang Engine (`v1.1.0 LTS+`). Security patches for the Python engine will be maintained until August 2027, but no new features will be added.
> 
> - **Legacy Python 1-Liner**: `curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.0/install.sh | bash`
> - **Legacy Python Pip**: `pip install git+https://github.com/ghanirahmans/gaet.git@lts/v1.0`
> - Refer to the [Legacy Python Guide](docs/legacy-python.md) for full instructions.

### Shell Auto-Completion Setup

Generate shell auto-completion for your active terminal environment:

```bash
# Bash
gaet completion bash > ~/.bash_completion.d/gaet
source ~/.bash_completion.d/gaet

# Zsh
gaet completion zsh > ~/.zfunc/_gaet
fpath=(~/.zfunc $fpath) && autoload -U compinit && compinit

# Fish
gaet completion fish > ~/.config/fish/completions/gaet.fish
```

---

## Command Specifications

`gaet` provides 18 structured subcommands categorized into 5 logical operation groups:

### 1. Setup & Lifecycle

- **`gaet init [preset]`**  
  Launches the interactive setup wizard. Auto-detects local PostgreSQL instances (Unix sockets & TCP 5432), tests database connectivity, prompts for optional cloud remote credentials, and configures `.env`.
  - *Presets*: `gaet init hindsight` or `gaet init hindsight hermes`.
- **`gaet install`**  
  Installs executable symlinks and system service integration.
- **`gaet update`**  
  Checks and updates the local `gaet` installation to the latest stable release.
- **`gaet uninstall [--save] [-y]`**  
  Launches interactive uninstallation wizard (`1` Clean Uninstall, `2` Safe Uninstall, `0` Cancel [default]) to safely remove CLI executable, `.env` config, and local backups.

### 2. Data Synchronization

- **`gaet push [--dry-run] [--tables=TABLES]`**  
  Creates a compressed local dump (`~/.gaet/backups/gaet_YYYYMMDD_HHmmss.dump`) using `pg_dump -Fc`, validates binary integrity via `pg_restore --list`, and restores schema/data into the target Remote Cloud DB.
- **`gaet fetch [--dry-run] [--yes]`**  
  Fetches snapshot data from Remote Cloud DB and restores it into the local database instance (**Overwrites local DB!**). Requires explicit `yes` confirmation or `--yes` flag in non-TTY environments.
- **`gaet restore [snapshot_file] [--dry-run] [--yes]`**  
  Restores the local database from a specific local snapshot `.dump` file (defaults to the latest available snapshot if unspecified).

### 3. Status & Diagnostics

- **`gaet status [--json] [--plain]`**  
  Displays visual synchronization status table, local vs cloud table row alignment, total backup directory volume, and auto-backup scheduler state.
- **`gaet check [--json]`**  
  Performs pre-flight checks verifying system binaries (`psql`, `pg_dump`, `pg_restore`), local DB authentication, and cloud connectivity.
- **`gaet diff`**  
  Displays side-by-side table row count comparison between local and cloud database instances.
- **`gaet doctor`**  
  Comprehensive diagnostic health report evaluating system environment, file permissions (`0600`), disk storage, and background services.
- **`gaet log [<lines>] [--follow] [--filter=KEYWORD]`**  
  Views structured activity log history (`~/.gaet/logs/gaet.log`).
- **`gaet snapshots [--json]`**  
  Lists all local backup `.dump` snapshots stored in `~/.gaet/backups/` along with file size, creation timestamp, and auto-retention policy details.

### 4. Configuration & Remote Management

- **`gaet get [KEY] [--list]`**  
  Retrieves configured environment variables (sensitive passwords masked). Use `--list` to view the full grouped configuration schema reference.
- **`gaet set KEY=VALUE [KEY2=VALUE2]`**  
  Atomically updates configuration variables in `~/.gaet/.env`. Provide `KEY=` with empty value to delete a setting.
- **`gaet remote [show|set-url|remove] [URL]`**  
  Git-style management of cloud database target URLs.
- **`gaet export`**  
  Outputs active `.env` configuration as shell-formatted `export GAET_...` environment variables.
- **`gaet completion [bash|zsh|fish|ps1]`**  
  Generates shell auto-completion scripts for Bash, Zsh, Fish, or PowerShell.
- **`gaet help [command]`**  
  Displays detailed CLI documentation and usage examples for a specific subcommand.

### 5. Services & Modern Web Dashboard

- **`gaet serve [--port PORT] [--host HOST] [--no-open] [--auto] [--stop]`**  
  Launches the lightweight zero-dependency web monitoring dashboard at `http://127.0.0.1:6161` (automatically opens default browser).
  - `--no-open`: Prevents automatic browser launch on startup.
  - `--auto`: Registers OS startup daemon (systemd / launchd / Task Scheduler) to auto-start the dashboard on OS boot.
  - `--stop`: Disables the OS startup daemon for the dashboard.
- **`gaet stop`**  
  Stops active background services (both automated backup scheduler and dashboard OS startup daemons).
- **`gaet uninstall [--save] [-y]`**  
  Launches an interactive uninstallation wizard (`1` Clean Uninstall, `2` Safe Uninstall, `0` Cancel [default]) to remove CLI executable, `.env` config, and local backups.

#### 🎛️ Operations Dashboard Highlights (`gaet serve`)
- **Theme Parity**: Modern glassmorphic aesthetic with seamless Dark Mode and Light Mode switching.
- **Keyboard Ergonomics**:
  - `1` – `4` or `Alt+O` / `Alt+S` / `Alt+L` / `Alt+E` : Instant tab navigation (`Overview`, `Snapshots`, `Logs`, `Settings`).
  - `Alt+K` : Global Command Palette hub.
  - `Esc` : Exit active modals or search overlays.
- **Snapshot Restore Modal**: Interactive one-click database restore confirmation (`restoreModal`) with file size validation and overwrite safety alerts.
- **Health & Storage Meter**: Real-time total snapshot volume counter (MB), table schema integrity coverage, and quick auto-backup timer toggle.

---

## Configuration Reference

Configuration settings are stored in `~/.gaet/.env` (restricted file mode `0600`).

| Group | Key Name | Type | Default | Description |
|---|---|---|---|---|
| **Local DB** | `GAET_LOCAL_URL` | URL | `(empty)` | Full local PostgreSQL connection string |
| | `GAET_LOCAL_DB_HOST` | String | `127.0.0.1` | Host address or Unix domain socket path |
| | `GAET_LOCAL_DB_PORT` | Int | `5432` | Local PostgreSQL port listener |
| | `GAET_LOCAL_DB_USER` | String | `postgres` | Database authentication username |
| | `GAET_LOCAL_DB_NAME` | String | `postgres` | Target database name |
| | `GAET_LOCAL_DB_PASS` | String | `(empty)` | Database user password |
| **Cloud Remote** | `GAET_REMOTE_URL` | URL | `(empty)` | Cloud PostgreSQL target connection URL |
| | `GAET_REMOTE_SSLMODE` | String | `require` | SSL connection requirement mode |
| **Options** | `GAET_RETENTION_DAYS` | Int | `7` | Days to keep `.dump` files before cleanup |
| | `GAET_PG_TIMEOUT` | Int | `3600` | Max timeout (seconds) for dump/restore ops |
| | `GAET_TABLES` | String | `(all)` | Comma-separated list of specific tables |

---

## Workflows & Practical Guides

### 1. Dev-to-Cloud Backup (`push`)
```bash
# Test execution safety first
gaet push --dry-run

# Run full backup & sync
gaet push
```

### 2. Cloud-to-Local Restore (`fetch`)
```bash
# Pull cloud database state to local development environment
gaet fetch --yes
```

### 3. Local Offline Snapshot Rollback (`restore`)
```bash
# List available snapshots
gaet snapshots

# Rollback local DB to specific snapshot file
gaet restore gaet_20260816_120000.dump --yes
```

### 4. Headless CI/CD Pipeline Integration
```bash
# Scripting mode with machine-readable outputs
export GAET_DIR="/tmp/ci_gaet"
gaet set GAET_LOCAL_DB_NAME="test_db" GAET_REMOTE_URL="$DATABASE_URL"
gaet check --json
gaet push -q
```

---

## Security & Hardening

1. **Strict File Permissions**: Secrets stored in `~/.gaet/.env` enforce Unix mode `0600` (`rw-------`).
2. **Password Injection Defense**: Credentials are isolated inside transient file buffers specified via `PGPASSFILE` environment bindings.
3. **Non-TTY Confirmation Requirement**: Destructive commands (`fetch`, `restore`, `uninstall`) strictly refuse execution in non-interactive terminals unless explicit flag `--yes` is supplied.

---

## Troubleshooting

Run the comprehensive health check command to diagnose issues:

```bash
gaet doctor
```

For error codes, exit values, and common solutions, consult [docs/troubleshooting.md](docs/troubleshooting.md).

---

## See Also

- [docs/roadmap.md](docs/roadmap.md) — Strategic future milestones & roadmap.
- [AGENTS.md](AGENTS.md) — Architecture guidelines and development standards.
- [docs/command_scopes.md](docs/command_scopes.md) — Technical scope boundaries and invariants.
- [docs/quickstart.md](docs/quickstart.md) — 5-minute walkthrough guide.
- [docs/architecture.md](docs/architecture.md) — Internal system design and module specs.
- [docs/troubleshooting.md](docs/troubleshooting.md) — Diagnostic guides and error code index.
- Manual Page: `man gaet` (or `man ./gaet.1`).
