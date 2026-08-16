# gaet(1) — PostgreSQL Backup & Sync CLI

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![Platform: Linux | macOS | Windows](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20Windows-supported-brightgreen.svg)]()
[![v3.0.1](https://img.shields.io/badge/v3.0.1-blue?label=release)](CHANGELOG.md)

> **gaet** is a zero-dependency, Git-styled PostgreSQL backup & synchronization CLI tool. It provides seamless snapshot management, local-to-cloud push/fetch operations, structured status badges, and automated retention policies.

---

## 📖 Table of Contents

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
`gaet` — Zero-dependency PostgreSQL database backup, synchronization, and snapshot management CLI.

**SYNOPSIS**  
```bash
gaet [<global-options>] <command> [<args>]
```

**GLOBAL OPTIONS**  
- `-q, --quiet` : Suppress non-essential informational headers and output formatting.
- `--plain`     : Output plain, unformatted TSV output (pipe-safe for `grep`, `awk`, `sed`).
- `--json`      : Return structured JSON objects for programmatic consumption.
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

1. **Zero External Dependencies**: Implemented strictly using the Python Standard Library (`subprocess`, `urllib`, `argparse`, `pathlib`, `json`). Requires no `pip` packages.
2. **Passwordless Security Model**: PostgreSQL operations (`psql`, `pg_dump`, `pg_restore`) enforce the `-w` (`--no-password`) flag alongside atomic, temporary `PGPASSFILE` instances (`0600` permission level). Plaintext passwords are never passed as command-line flags or logged to history.
3. **Atomic State & Environment Updates**: Configuration key updates via `gaet set` utilize atomic line-by-line single-pass updates to `~/.gaet/.env` to prevent config corruption.
4. **Concurrency Safety**: Non-blocking file locks (`~/.gaet/gaet.lock`) prevent overlapping execution during automated scheduled backups or simultaneous manual invocations.
5. **Git Workspace Integration**: Running `gaet init` initializes a version-controlled workspace in `~/.gaet` (with strict `.gitignore` rules shielding secrets, lock files, and dump payloads).

---

## Quick Start

Get up and running in under 2 minutes:

```bash
# 1. Install gaet CLI
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash

# 2. Run interactive setup wizard
gaet init

# 3. Create your first cloud backup
gaet push

# 4. Verify table sync status
gaet status
```

---

## Installation

### Method 1: Automated Script (Recommended)

**Linux / macOS:**
```bash
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.ps1 | iex
```

### Method 2: System Package / Source Installation

```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
pip install -e .
```

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
- **`gaet uninstall [--purge]`**  
  Safely removes binary symlinks and background tasks. Use `--purge` to delete `~/.gaet` data.

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

### 5. Services & Monitoring

- **`gaet serve [--port PORT] [--host HOST]`**  
  Launches the lightweight zero-dependency web monitoring dashboard at `http://127.0.0.1:9191`.
- **`gaet stop`**  
  Stops active web dashboard servers and background cron/systemd automated backup tasks.

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

For error codes, exit values, and common solutions, consult [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## See Also

- [COMMAND_SCOPES.md](COMMAND_SCOPES.md) — Technical scope boundaries and invariants.
- [QUICKSTART.md](QUICKSTART.md) — 5-minute walkthrough guide.
- [ARCHITECTURE.md](ARCHITECTURE.md) — Internal system design and module specs.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Diagnostic guides and error code index.
- Manual Page: `man gaet` (or `man ./gaet.1`).
