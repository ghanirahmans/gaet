<p align="center">
  <img src="https://raw.githubusercontent.com/ghanirahmans/gaet/master/dashboard/public/gaet-logo.png" alt="gaet logo" width="120">
</p>

<h1 align="center">gaet</h1>

<p align="center">
  <strong>PostgreSQL Backup & Sync for Developers</strong>
</p>

<p align="center">
  <a href="#why-gaet">Why gaet?</a> •
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#commands">Commands</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#security">Security</a> •
  <a href="#faq">FAQ</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT">
  <img src="https://img.shields.io/badge/python-3.8+-green" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/platform-linux%20only-orange" alt="Linux (primary)">
  <img src="https://img.shields.io/badge/macOS%20%7C%20Windows-in%20development-lightgrey" alt="macOS | Windows in development">
  <img src="https://img.shields.io/badge/version-2.0.0LTS-blue" alt="v2.0.0 LTS">
</p>

---

## TL;DR

**gaet** backs up your PostgreSQL database to any cloud PostgreSQL. One command, no YAML, no config files.

```bash
# Install
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash

# Configure (interactive wizard)
gaet init

# Backup
gaet push

# Check status
gaet status
```

---

## Why gaet?

**gaet** is a PostgreSQL backup tool that syncs your local database to a cloud PostgreSQL instance (Supabase, Neon, RDS, or any VPS). It's designed for developers who want a simple, scriptable backup solution without running their own infrastructure.

### What it does

- `gaet push` — dump local DB → restore to cloud
- `gaet fetch` — dump cloud DB → restore to local
- `gaet status` — show per-table sync state
- `gaet diff` — compare local vs cloud tables
- `gaet doctor` — comprehensive health check
- `gaet serve` — web dashboard for monitoring
- `gaet push --auto` — schedule periodic backups via OS scheduler

### How it works

gaet runs `pg_dump` locally, checks the dump with `pg_restore --list`, then restores it to the remote database. File-based locks prevent overlapping runs. Old backups are cleaned up after `GAET_RETENTION_DAYS`.

### What it doesn't do

- gaet does not manage your database (no schema migrations, no user management)
- gaet does not stream replication (it's a point-in-time backup tool)
- gaet does not support cross-platform fully yet (Linux is the reference implementation)

---

## Features

### Core

| Feature | What it does |
|---------|-------------|
| Concurrency lock | Prevents overlapping backup jobs |
| 120s timeout | Cloud connections don't hang indefinitely |
| Integrity check | `pg_restore --list` validates every dump before upload |
| Compression | `pg_dump --compress=9` — typical 70-90% size reduction |
| Auto-retention | Backups older than `GAET_RETENTION_DAYS` are deleted |
| Auto-backup | Runs via systemd, launchd, or Task Scheduler |
| Multi-cloud | Supabase, Neon, AWS RDS, Azure, or any PostgreSQL URL |
| Table discovery | Auto-detects all public tables from `information_schema` |
| Web dashboard | Per-table sync status, backup history, push/fetch buttons |
| Dry-run | `gaet push --dry-run` simulates without touching data |

### Security

| Feature | Detail |
|---------|--------|
| Password handling | Stored in `.env`, masked in logs, never in command-line args |
| `.env` permissions | Created with `0o600` (owner read/write only) |
| No shell injection | All subprocess calls use argument arrays |
| CORS | Dashboard API validates `Origin` headers |

### Platform

| Platform | CLI | Auto-Backup | Dashboard |
|----------|-----|-------------|-----------|
| Linux | ✅ | systemd timer | systemd service |
| macOS | 🚧 | launchd (experimental) | launchd (experimental) |
| Windows | 🚧 | Task Scheduler (experimental) | Background service (experimental) |

> Cross-platform is still in development. gaet is built and tested primarily on Linux.

**Dependencies:** Only PostgreSQL client tools (`pg_dump`, `pg_restore`, `psql`). No pip packages.

---

## What's New in 2.0.0 LTS

This is a **Long-Term Support (LTS)** release for Linux. Supported until at least 2027.

### New Commands

| Command | Description |
|---------|-------------|
| `gaet doctor` | Comprehensive health check (config, tools, DB, backups, scheduler) |
| `gaet diff` | Compare local vs cloud tables side-by-side |
| `gaet export` | Print config as shell `export` statements |
| `gaet completion` | Generate shell completions (bash/zsh/fish) |
| `gaet help <cmd>` | Git-style command help |

### New Flags

| Flag | Works on | Description |
|------|----------|-------------|
| `--json` | check, push, fetch, status, doctor, diff, help | Machine-readable JSON output |
| `--plain` | all commands | Pipe-safe TSV output (no box-drawing) |
| `--quiet` | all commands | Suppress non-essential output |
| `--follow` / `-F` | log | Real-time log tailing (tail -f style) |
| `--notify` | push | Webhook URL to notify after push completes |
| `--tables` | push | Override table list for selective backup |
| `--watch` | status | Auto-refresh status every 2 seconds |

### Other Changes

- Semantic exit codes (80-89) for CI/CD scripting
- `NO_COLOR` / `CLICOLOR_FORCE` env var support
- Unix socket auto-detection in `gaet init`
- Config priority: individual vars (`GAET_LOCAL_DB_*`) override `GAET_LOCAL_URL`
- `gaet set KEY=` (empty value) deletes the key
- Typo suggestions ("Did you mean: gaet push?")
- Man page (`gaet.1`)
- Mermaid pipeline diagrams in README

See [CHANGELOG.md](CHANGELOG.md) for the full list.

---

## Quick Start

### 1. Install

**Linux/macOS:**
```bash
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
```

**Windows (PowerShell):** ⚠️ Experimental — cross-platform support is still in development. Prefer Linux for production use.
```powershell
irm https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.ps1 | iex
```

**From source:**
```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
pip install -e .
python gaet.py --help
```

### 2. Configure

```bash
gaet init
```

The interactive wizard will:
- Auto-detect your local PostgreSQL instance (including Unix sockets)
- Test the connection
- Guide you through cloud database setup (Supabase, Neon, RDS, etc.)
- Save config to `~/.gaet/.env` with restricted permissions

### 3. First backup

```bash
# Verify configuration
gaet check

# Dry-run (simulate without executing)
gaet push --dry-run

# Backup local → cloud
gaet push

# Check sync status
gaet status

# Open dashboard at http://localhost:9191
gaet serve
```

---

## Commands Reference

### Configuration

```bash
gaet init                        # Interactive setup wizard
gaet init hindsight              # Preset for Hindsight AI database
gaet init hindsight hermes       # Preset for Hermes Agent (Nous Research)
gaet check                       # Validate all connections
gaet check --json                # Machine-readable health check (CI)
gaet status                      # Show sync status with colored table
gaet status --json               # Status as JSON (for scripting/APIs)
gaet doctor                      # Comprehensive health check
gaet doctor --json               # Doctor results as JSON
gaet get [VARIABLE]              # Get environment variable(s)
gaet set KEY=VALUE [KEY2=VALUE2] # Set environment variables
gaet set KEY=                    # Delete a variable (empty value)
gaet export                      # Print config as shell export statements
```

### Backup & Restore

```bash
gaet push                        # Backup local PostgreSQL → cloud
gaet push --dry-run              # Simulate without executing
gaet push --auto=6               # Enable auto-backup every 6 hours (default)
gaet push --auto=24              # Or every 24 hours (max)
gaet push --tables=users,posts   # Backup specific tables only
gaet push --notify=https://...   # Webhook notification after push

gaet fetch                       # Restore cloud PostgreSQL → local (overwrites!)
gaet fetch --dry-run             # Simulate fetch without overwriting
gaet stop                        # Stop auto-backup & dashboard
```

### Diff & Compare

```bash
gaet diff                        # Compare local vs cloud tables
gaet diff --json                 # Diff as JSON
```

### Monitoring

```bash
gaet log                         # View last 30 lines of backup log
gaet log 100                     # View last 100 lines
gaet log --follow                # Real-time log tailing (Ctrl+C to stop)
gaet log --filter ERROR          # Show only ERROR lines (case-insensitive)
gaet log --since 2024-01-15      # Show logs since a date
gaet log --filter CRON           # Show only auto-backup entries

gaet serve                       # Start web dashboard (http://localhost:9191)
gaet serve --port 8080           # Custom port
gaet serve --no-browser          # Don't auto-open browser
gaet status --watch              # Auto-refresh status every 2 seconds
```

### Shell Completions

```bash
gaet completion                  # Auto-detect shell and show install instructions
gaet completion --shell bash     # Print bash completions
gaet completion --shell zsh      # Print zsh completions
gaet completion --shell fish     # Print fish completions
```

### Maintenance

```bash
gaet update                      # Update to latest version from GitHub
gaet update --force              # Force update (skip local changes check)
gaet update --skip-build         # Update CLI only (skip dashboard rebuild)

gaet uninstall                   # Remove gaet (keeps config & backups)
gaet uninstall --purge           # Complete removal (deletes everything)

gaet help <command>              # Git-style help for a command
gaet help --json                 # Machine-readable command schema

gaet --version                   # Show version
gaet --help                      # Show full help
```

---

## How It Works

### Push pipeline

```mermaid
flowchart LR
    A[Local DB] --> B[pg_dump]
    B -->|compress=9| C[Integrity Check]
    C -->|pg_restore --list| D{Valid?}
    D -->|yes| E[pg_restore]
    D -->|no| F[Abort]
    E -->|clean mode| G[Cloud DB]
    E --> H[Release lock]
    H --> I[Delete old backups]

    style A fill:#4CAF50,color:#fff
    style G fill:#2196F3,color:#fff
    style F fill:#f44336,color:#fff
```

**Steps:**

1. Acquire file lock (prevents overlapping backups)
2. `pg_dump --format=custom --compress=9` to temp file
3. `pg_restore --list` on dump file (validates integrity)
4. Restore to cloud with `pg_restore --clean --if-exists --no-owner --no-acl`
5. Delete temp file, update log, release lock
6. Delete backups older than `GAET_RETENTION_DAYS`

### Benchmarks

Measured on PostgreSQL 18, Linux (i5-12450H, NVMe). Raw data in [`benchmarks/`](benchmarks/).

| Database | Size | pg_dump | pg_restore | Total |
|----------|------|---------|------------|-------|
| Simple (2 tables, 110k rows) | 126 MB | 0.46s | 0.50s | 0.96s |
| Complex (7 tables, 750k rows) | 404 MB | 2.51s | 5.69s | 8.20s |
| Ultra-complex (19 objects, 1M+ rows) | 343 MB | 3.68s | 6.61s | 10.29s |

### Fetch pipeline

```mermaid
flowchart RL
    A[Cloud DB] --> B[pg_dump]
    B --> C[Verify]
    C --> D[Kill Active Connections]
    D --> E[pg_restore]
    E -->|overwrite| F[Local DB]

    style A fill:#2196F3,color:#fff
    style F fill:#4CAF50,color:#fff
    style D fill:#FF9800,color:#fff
```

**Note:** Fetch overwrites your local database. Use `--dry-run` first.

### Auto-backup

```mermaid
flowchart TD
    A[OS Scheduler] -->|every N hours| B[gaet push --auto]
    B --> C{Lock held?}
    C -->|yes| D[Skip — backup in progress]
    C -->|no| E[Run push]
    E --> F[Log to cron.log]
    E --> G[Apply retention]
```

```bash
gaet log --filter CRON      # Show only cron entries
gaet log | tail -20         # Show latest backups
```

---

## Configuration

Config is stored in `~/.gaet/.env` (permissions `0o600`).

### Variables

```bash
# Local PostgreSQL
GAET_LOCAL_DB_HOST=localhost
GAET_LOCAL_DB_PORT=5432
GAET_LOCAL_DB_NAME=mydb
GAET_LOCAL_DB_USER=postgres
GAET_LOCAL_DB_PASS=secret

# Cloud PostgreSQL (connection URL)
GAET_REMOTE_URL=postgresql://user:***@host:5432/dbname

# Backup retention (days)
GAET_RETENTION_DAYS=7

# Cloud connection security
GAET_REMOTE_SSLMODE=require

# Dashboard
GAET_DASHBOARD_PORT=9191
GAET_DASHBOARD_HOST=127.0.0.1
```

### Get/set variables

```bash
gaet get                           # View all config
gaet get GAET_LOCAL_DB             # View specific variable
gaet set GAET_LOCAL_DB=newdb       # Set a variable
gaet set KEY=                      # Delete a variable (empty value)
gaet set K1=v1 K2=v2              # Set multiple variables
gaet export                        # Print as shell export statements
```

---

## Dry-Run Mode

Test before you backup or restore. Dry-run shows what would happen without touching data.

```bash
gaet push --dry-run               # Test backup
gaet fetch --dry-run              # Test restore
```

---

## Dashboard Web UI

```bash
gaet serve                        # Starts at http://localhost:9191
gaet serve --port 8080            # Custom port
gaet serve --no-browser           # Don't auto-open browser
```

### Features

- Sync status matrix (per-table)
- Backup history
- Push/Fetch buttons
- Configuration view
- Dark/light mode (follows system preference)
- Responsive (works on mobile)

### API routes

```bash
curl http://localhost:9191/api/status       # Get status
curl http://localhost:9191/api/sync         # Get sync details
curl http://localhost:9191/api/history      # Get backup history
curl -X POST http://localhost:9191/api/push  # Trigger backup
curl -X POST http://localhost:9191/api/fetch # Trigger restore
```

---

## Architecture

### Why no dependencies?

gaet is a single Python file with no pip packages. The only requirements are PostgreSQL client tools (`pg_dump`, `pg_restore`, `psql`).

Rationale: fewer dependencies = fewer things to update, fewer supply-chain risks, easier to audit.

### Why custom format + compression?

PostgreSQL dump formats: plain SQL, custom, directory, tar. gaet uses custom (`--format=custom --compress=9`) because:

- `pg_restore --list` can validate without restoring (integrity check)
- Built-in compression (no gzip dependency)
- Can restore individual tables if needed

### Why file locks?

gaet uses file-based locks (`~/.gaet/backups/.gaet.lock`) instead of database locks because:

- No schema changes required (no lock tables, no advisory locks)
- Works with any PostgreSQL setup (local, cloud, managed)
- Easy to debug (`ls ~/.gaet/backups/*.lock`)
- Stale locks auto-detected via PID check

### Why 120s timeout?

Each `pg_dump` and `pg_restore` call has a 120-second timeout. This prevents hanging on slow cloud connections. For very large databases, increase the timeout or run during maintenance windows.

Cloud connections can be slow. 120 seconds is the sweet spot:

- **Large Dumps** - Time to transfer 10GB+ to cloud
- **Slow Networks** - VPN, Tor, satellite internet
- **Not Too Long** - Prevents zombie processes
- **Per-Operation** - Each step (dump, restore) gets its own timer

---

## Security

### Password handling

Passwords are stored in `~/.gaet/.env` (permissions `0o600`). They are masked in `gaet get` output and never appear in command-line arguments (which would be visible in `ps` / `/proc`).

```bash
gaet get                           # Shows GAET_LOCAL_DB_PASS = ***
gaet get GAET_LOCAL_DB_PASS        # Shows "not found" (masked)
```

gaet does not:
- Log passwords or connection strings
- Pass credentials via command-line arguments
- Store credentials in shell history
- Use unencrypted connections (defaults to `sslmode=require`)

---

## Project Structure

```
gaet/
├── gaet.py                    # CLI (~3800 lines)
├── dashboard/                 # Next.js web UI
│   ├── app/                   # App Router
│   ├── public/                # Static assets
│   └── package.json
├── completions/               # Shell completions
│   ├── gaet.bash
│   ├── gaet.zsh
│   └── gaet.fish
├── scripts/
│   ├── installer.py           # Cross-platform installer
│   └── scheduler.py           # systemd/launchd/Task Scheduler
├── tests/
│   └── test_gaet.py           # unittest
├── benchmarks/                # Benchmark datasets + methodology
├── gaet.1                     # Man page
├── README.md
├── CHANGELOG.md
└── install.sh / install.ps1
```

---

## Presets

gaet has built-in presets for popular platforms:

| Preset | Command |
|--------|---------|
| Hindsight | `gaet init hindsight` |
| Hermes Agent | `gaet init hindsight hermes` |
| Custom | `gaet init` |

Presets pre-fill `GAET_TABLES` and default user/db names. You still need to set the cloud URL.

---

## Troubleshooting

### `gaet check` fails

```bash
# Is PostgreSQL running?
pg_lsclusters                        # Linux
brew services list | grep postgres   # macOS

# Wrong port?
gaet set GAET_LOCAL_PORT=5433

# Wrong credentials?
gaet set GAET_LOCAL_USER=postgres

# Reconfigure
gaet init
```

### Dashboard won't start

```bash
gaet serve --port 8080               # Different port
gaet stop && gaet serve              # Restart
gaet log | grep -i error             # Check logs
```

### Auto-backup not running

```bash
systemctl --user list-timers         # Linux
launchctl list | grep gaet           # macOS
Get-ScheduledTask -TaskName *gaet*   # Windows
gaet log --filter CRON               # View cron logs
```

### `gaet update` won't work

```bash
gaet update --force                  # Overwrite local changes
# OR
git stash && gaet update && git stash pop
```

---

## FAQ

**Q: Is gaet production-ready?**
A: gaet is used in production environments. It has auto-backup, retention policies, integrity checks, and logging. It handles databases up to several GB. For very large databases (10GB+), test with your specific workload.

**Q: Can I backup multiple databases?**
A: One local → one cloud per installation. Run separate instances for multiple databases.

**Q: How often should I backup?**
A: Default is 6 hours. For critical data, every 1-2 hours. For development, daily.

**Q: Will a large backup timeout?**
A: Each `pg_dump`/`pg_restore` has a 120s timeout. For 10GB+ databases, increase the timeout or run during maintenance windows.

**Q: Can I restore without overwriting?**
A: `gaet fetch` overwrites the local database. Use `--dry-run` first to preview, or restore to a separate test database.

**Q: What if my cloud database goes down?**
A: Local backups are in `~/.gaet/backups/`. Create a new cloud database and restore the latest backup.

**Q: How do I know if backups are working?**
A: `gaet status` shows sync state, `gaet log` shows backup events, `gaet serve` shows a timeline, `gaet doctor` checks everything.

**Q: Can I schedule backups differently on weekends?**
A: Modify the systemd timer / launchd plist / Task Scheduler directly.

**Q: Is my password safe?**
A: Passwords are in `~/.gaet/.env` with `0o600` permissions. They are not logged or passed via command line.

**Q: Does gaet work with Heroku Postgres?**
A: Yes. Use the Heroku connection string as `GAET_REMOTE_URL`.

**Q: Can I sync databases between servers?**
A: Yes. Set one as local, another as cloud. Works in both directions.

---

## Development

```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
python -m unittest discover -s tests    # Run tests
python gaet.py --help                    # CLI
cd dashboard && npm run dev             # Dashboard dev mode
```

### Design principles

1. **No dependencies** — single Python file, only PostgreSQL client tools
2. **Fail loudly** — abort on error rather than silently corrupt
3. **Log everything** — timestamps on all operations
4. **Test the pipeline** — backup/restore are the critical paths

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your branch
5. Open a Pull Request

Include tests for new features or bug fixes.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Support & Links

- 🐛 [Report Issues](https://github.com/ghanirahmans/gaet/issues) — bugs, crashes, unexpected behavior
- 💡 [Feature Requests](https://github.com/ghanirahmans/gaet/issues) — same tracker, label as enhancement
- 📦 [Source & Releases](https://github.com/ghanirahmans/gaet) — code, changelog, tags
- 📖 [Benchmarks](benchmarks/) — reproducible datasets & methodology

> Questions? Open a [GitHub Issue](https://github.com/ghanirahmans/gaet/issues) — gaet is maintained by a single developer, so issues are the fastest way to get help.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release notes and version history.
