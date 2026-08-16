# gaet — PostgreSQL Backup & Sync CLI

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![Platform: Linux | macOS | Windows](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20Windows-supported-brightgreen.svg)]()
[![v3.0.0](https://img.shields.io/badge/v3.0.0-blue?label=release)](CHANGELOG.md)

Backup PostgreSQL to any cloud instance. Zero external dependencies. Cross-platform support.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Commands Reference](#commands-reference)
- [Architecture](#architecture)
- [Security](#security)
- [Troubleshooting](TROUBLESHOOTING.md)
- [FAQ](#faq)
- [See Also](#see-also)

---

## Quick Start

```bash
# Install (Linux/macOS)
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash

# Or Windows (PowerShell)
irm https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.ps1 | iex

# Initialize (interactive wizard)
gaet init

# First backup
gaet push

# Check status
gaet status
```

For a detailed walkthrough, see [QUICKSTART.md](QUICKSTART.md).

---

## Installation

### Requirements

- Python 3.8+
- PostgreSQL client tools (`pg_dump`, `pg_restore`, `psql`)
- No pip packages required (zero dependencies)

### Install via script (recommended)

```bash
# Linux/macOS
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash

# Windows (PowerShell as Administrator)
irm https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.ps1 | iex
```

### Install from source

```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
pip install -e .
python gaet.py --help
```

### Verify installation

```bash
gaet --version
# Output: gaet v3.0.0

gaet doctor
# Comprehensive health check
```

---

## Usage

### Basic Workflow

```bash
# 1. Configure
gaet init

# 2. Verify connections
gaet check

# 3. Test before running
gaet push --dry-run

# 4. Run backup
gaet push

# 5. Monitor sync status
gaet status
```

### Configuration

Config is stored in `~/.gaet/.env` (permissions `0600`).

```bash
# View config
gaet get

# Set variables
gaet set GAET_REMOTE_URL=postgresql://user:pass@host:5432/db

# Delete variable
gaet set KEY=

# Export as shell commands
gaet export
```

### Machine-Readable Output

```bash
# JSON output for scripting
gaet status --json | jq '.tables[] | select(.ok == false)'

# Plain TSV for grep/awk
gaet status --plain | grep -v "✓"

# Quiet mode for scripts
gaet push -q
```

### Web Dashboard

```bash
# Start dashboard (http://localhost:9191)
gaet serve

# Custom port
gaet serve --port 8080

# Stop dashboard
gaet stop
```

---

## Commands Reference

### Health & Status

| Command | Description |
|---------|-------------|
| `gaet check` | Validate config and connections |
| `gaet status` | Show sync status per table |
| `gaet doctor` | Comprehensive health check |
| `gaet diff` | Compare local vs cloud row counts |

### Backup & Restore

| Command | Description |
|---------|-------------|
| `gaet push` | Backup local → cloud |
| `gaet push --dry-run` | Simulate without executing |
| `gaet push --auto=6` | Enable auto-backup every 6 hours |
| `gaet fetch` | Restore cloud → local (overwrites!) |
| `gaet fetch --dry-run` | Simulate restore |
| `gaet stop` | Stop auto-backup and dashboard |

### Monitoring

| Command | Description |
|---------|-------------|
| `gaet log` | View last 30 backup log lines |
| `gaet log 100` | View last 100 lines |
| `gaet log --follow` | Real-time tailing |
| `gaet log --filter ERROR` | Filter by keyword |
| `gaet log --filter CRON` | Show cron/auto-backup entries |
| `gaet serve` | Start web dashboard |

### Configuration

| Command | Description |
|---------|-------------|
| `gaet init` | Interactive setup wizard |
| `gaet init hindsight` | Preset for Hindsight database |
| `gaet init hindsight hermes` | Preset for Hermes Agent |
| `gaet get` | View all config variables |
| `gaet get KEY` | View specific variable |
| `gaet set KEY=value` | Set variable |
| `gaet set KEY=` | Delete variable |
| `gaet export` | Print config as shell exports |

### Maintenance

| Command | Description |
|---------|-------------|
| `gaet install` | Setup/install dependencies |
| `gaet update` | Update to latest version |
| `gaet uninstall` | Remove gaet (keeps data) |
| `gaet uninstall --purge` | Complete removal |

### Help

| Command | Description |
|---------|-------------|
| `gaet --help` | Show full help |
| `gaet help <cmd>` | Show help for command |
| `gaet help --json` | Machine-readable schema |
| `gaet completion` | Generate shell completions |
| `gaet --version` | Show version |

### Flags (work on all commands)

| Flag | Description |
|------|-------------|
| `-q, --quiet` | Suppress non-essential output |
| `--plain` | Pipe-safe TSV output (no box-drawing) |
| `--json` | JSON output (where supported) |
| `--dry-run` | Simulate without executing |

---

## Architecture

### How It Works

```mermaid
flowchart LR
    A[Local DB] --> B[pg_dump --compress=9]
    B --> C[Integrity Check\npg_restore --list]
    C -->|Valid| D[pg_restore to Cloud]
    C -->|Invalid| E[Abort]
    D --> F[Cloud DB]
    
    style A fill:#4CAF50,color:#fff
    style F fill:#2196F3,color:#fff
    style E fill:#f44336,color:#fff
```

**Steps:**
1. Acquire file lock (prevents overlapping runs)
2. `pg_dump --format=custom --compress=9` to temp file
3. `pg_restore --list` validates dump integrity
4. Restore to cloud with `pg_restore --clean --if-exists`
5. Delete temp file, release lock, update log
6. Apply retention policy (delete old backups)

### File Structure

```
gaet/
├── gaet.py                    # CLI (~4200 lines, pure stdlib)
├── dashboard/
│   ├── server.py              # Python HTTP server (no Node.js needed)
│   └── static/index.html      # Web UI
├── scripts/
│   ├── installer.py           # Cross-platform installer
│   ├── service_manager.py     # systemd/launchd/Task Scheduler
│   └── scheduler.py           # Auto-backup scheduling
├── completions/
│   ├── gaet.bash              # Bash completions
│   ├── gaet.zsh               # Zsh completions
│   ├── gaet.fish              # Fish completions
│   └── gaet.ps1               # PowerShell completions
├── tests/
│   └── test_gaet.py           # 17 unit tests
├── benchmarks/                # Benchmark datasets
├── gaet.1                     # Man page
├── README.md
├── CHANGELOG.md
├── QUICKSTART.md
├── TROUBLESHOOTING.md
├── SECURITY.md
├── install.sh                 # Linux/macOS installer
└── install.ps1                # Windows installer
```

### Benchmarks

Measured on PostgreSQL 18, Linux (i5-12450H, NVMe, 8GB RAM).

| Database | Size | pg_dump | pg_restore | gaet push | gaet fetch |
|----------|------|---------|------------|-----------|------------|
| Simple (2 tables, 110k rows) | 126 MB | 0.46s | 0.50s | ~1s | ~1s |
| Complex (7 tables, 750k rows) | 404 MB | 2.51s | 5.69s | ~8s | ~7s |
| Production-like (38 tables, 10.7M rows) | 1944 MB | 50.09s | 58.24s | 91.06s | 80.49s |

Compression: 1944 MB → **359.6 MB** (82% reduction)

For large databases (>1GB), increase timeout:
```bash
gaet set GAET_PG_TIMEOUT=600
```

---

## Security

See [SECURITY.md](SECURITY.md) for detailed security information.

### Key Points

- Passwords stored in `~/.gaet/.env` with `0600` permissions
- Credentials never logged or passed via command-line arguments
- SQL injection protected via parameterized queries and input validation
- No external network dependencies (only connects to your PostgreSQL instances)

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GAET_LOCAL_DB_HOST` | `localhost` | Local PostgreSQL host |
| `GAET_LOCAL_DB_PORT` | `5432` | Local PostgreSQL port |
| `GAET_LOCAL_DB_NAME` | `postgres` | Local database name |
| `GAET_LOCAL_DB_USER` | `postgres` | Local database user |
| `GAET_LOCAL_DB_PASS` | — | Local database password |
| `GAET_REMOTE_URL` | — | Cloud PostgreSQL connection URL |
| `GAET_RETENTION_DAYS` | `7` | Days to keep backups |
| `GAET_PG_TIMEOUT` | `120` | Seconds per pg_dump/pg_restore operation |
| `GAET_REMOTE_SSLMODE` | `prefer` | SSL mode for cloud connections |
| `GAET_DASHBOARD_PORT` | `9191` | Dashboard listening port |
| `GAET_DASHBOARD_HOST` | `127.0.0.1` | Dashboard binding address |

### Config Priority

Individual variables (`GAET_LOCAL_DB_*`) override `GAET_LOCAL_URL`:
```bash
gaet set GAET_LOCAL_DB_HOST=localhost
gaet set GAET_LOCAL_DB_PORT=5432
gaet set GAET_LOCAL_DB_NAME=mydb
# These take precedence over GAET_LOCAL_URL
```

---

## FAQ

### What's the difference between `push` and `fetch`?

- `gaet push` — Dumps local database and restores to cloud (backup)
- `gaet fetch` — Dumps cloud database and restores to local (restore/overwrite)

### Is my data encrypted in transit?

By default, `GAET_REMOTE_SSLMODE=prefer` tries SSL first, falls back to plain if server doesn't support it. For strict encryption, set `GAET_REMOTE_SSLMODE=require`.

### Can I backup specific tables only?

Yes:
```bash
gaet push --tables=users,posts,orders
```

### How do I schedule automatic backups?

```bash
gaet push --auto        # Every 6 hours (default)
gaet push --auto=24     # Every 24 hours
```

This creates a systemd timer (Linux), launchd job (macOS), or Task Scheduler task (Windows).

### Where are backups stored?

`~/.gaet/backups/gaet_YYYYMMDD_HHmmss.dump`

Older backups are automatically deleted after `GAET_RETENTION_DAYS`.

### How do I restore from a specific backup?

Use `gaet fetch` — it restores from the latest backup. To restore an older backup, copy it to the backups directory and run fetch.

### Can I use gaet with Supabase/Neon/RDS?

Yes! Any PostgreSQL instance works. Set `GAET_REMOTE_URL` to your connection string:
```bash
gaet set GAET_REMOTE_URL=postgresql://user:pass@host.supabase.co:5432/dbname
```

---

## See Also

- [QUICKSTART.md](QUICKSTART.md) — 5-minute getting started guide
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common errors and fixes
- [SECURITY.md](SECURITY.md) — Security policy and considerations
- [CHANGELOG.md](CHANGELOG.md) — Version history
- [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute
- [benchmarks/README.md](benchmarks/README.md) — Detailed benchmark methodology
- [gaet.1](gaet.1) — Manual page (`man gaet.1`)

---

## Links

- **Repository:** https://github.com/ghanirahmans/gaet
- **Issues:** https://github.com/ghanirahmans/gaet/issues
- **License:** MIT
