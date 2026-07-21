<p align="center">
  <img src="https://raw.githubusercontent.com/ghanirahmans/gaet/master/dashboard/public/gaet-logo.png" alt="gaet logo" width="120">
</p>

<h1 align="center">gaet</h1>

<p align="center">
  <strong>Your PostgreSQL. Backed up. Synced. Safe.</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#commands">Commands</a> •
  <a href="#dashboard-web">Dashboard</a> •
  <a href="#configuration">Config</a> •
  <a href="#security">Security</a> •
  <a href="#changelog">Changelog</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT">
  <img src="https://img.shields.io/badge/python-3.8+-green" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey" alt="Linux | macOS | Windows">
  <img src="https://img.shields.io/badge/deps-0%20pip%20packages-blueviolet" alt="Zero pip dependencies">
</p>

---

**gaet** is a zero-config CLI tool that backs up your local PostgreSQL database to any cloud PostgreSQL. Supabase, Neon, AWS RDS, or your own VPS. No YAML. No complex setup. Just one command and you're protected.

```bash
# Install (one-liner)
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash

# Configure & backup
gaet init
gaet push

# Monitor
gaet status
gaet serve
```

---

## Why gaet?

> "I lost 3 months of data because I forgot to set up backups."
> — Every developer, at least once.

**gaet exists so this never happens to you.**

| Problem | gaet Solution |
|---------|---------------|
| "I keep forgetting to backup" | Auto-backup every N hours via OS scheduler |
| "My backup script broke silently" | Integrity checks (`pg_restore --list`) before every upload |
| "I don't know if my data is synced" | Real-time dashboard with per-table status |
| "Setup takes too long" | One command. That's it. |
| "I need this for production" | Concurrency locks, timeouts, retention policies |

---

## Features

### Core
| Feature | What it does | Why it matters |
|---------|--------------|----------------|
| 🔒 **Concurrency lock** | Prevents overlapping backups | Your data stays consistent |
| ⏱️ **120s timeout** | Cloud connections never hang | No frozen terminals |
| ✅ **Integrity check** | Validates dump (`pg_restore --list`) | No corrupt backups |
| 📦 **Compressed dumps** | Custom format, compression level 9 | ~70% smaller files |
| 🧹 **Auto-retention** | Old backups auto-deleted | No disk space waste |
| 🔄 **Auto-backup** | Periodic via OS scheduler | Set it and forget it |
| 🔌 **Multi-cloud** | Supabase, Neon, RDS, VPS | Works with your stack |
| 📋 **Table auto-discovery** | Detects all public tables | No manual configuration needed |
| 📊 **Sync visualization** | Per-table status with progress | Know exactly what's synced |
| 🖥️ **Web dashboard** | Real-time status, one-click actions | See everything at a glance |
| 🌓 **Dark/Light mode** | Dashboard supports both themes | Comfortable for everyone |
| 🧪 **Dry-run mode** | Simulate without executing | Test before you commit |

### Security
| Feature | What it does |
|---------|--------------|
| 🔐 **Password encryption** | Passwords stored separately from URLs, never in logs |
| 🛡️ **PGPASSFILE** | Uses temp files instead of env vars to avoid `/proc` leaks |
| 🧹 **Credential cleanup** | Temp password files auto-deleted after use |
| 🚫 **No shell injection** | All commands use `execFileSync` with argument arrays |
| 👮 **CORS validation** | Dashboard API validates Origin headers |
| 🔒 **.env permissions** | Config file created with `0o600` (owner read/write only) |

### Platform Support
| Platform | CLI | Auto-backup | Dashboard Service |
|----------|-----|-------------|-------------------|
| 🐧 **Linux** | ✅ Full | systemd user timer | systemd user service |
| 🍎 **macOS** | ✅ Full | launchd timer | launchd agent |
| 🪟 **Windows** | ✅ Full | Task Scheduler | Background PID |

**gaet is pure Python.** Zero pip dependencies. Only requires PostgreSQL tools.

---

## Quick Start

### 1. Install

**Linux/macOS:**
```bash
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.ps1 | iex
```

**Or from source:**
```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
python gaet.py --help
```

### 2. Configure

```bash
# Run the interactive wizard
gaet init

# For Hindsight AI database
gaet init hindsight
```

The wizard will:
- Auto-detect your local PostgreSQL instance
- Test the connection immediately
- Guide you through cloud database setup
- Save config to `~/.gaet/.env` with secure permissions

### 3. First Backup

```bash
gaet check        # Verify connections
gaet push         # Backup local → cloud
gaet status       # Check sync status
gaet serve        # Open dashboard at http://localhost:9191
```

---

## Commands

### Configuration
| Command | Description |
|---------|-------------|
| `gaet init` | Interactive setup wizard |
| `gaet init hindsight` | Setup with Hindsight AI preset |
| `gaet init hindsight hermes` | Setup with Hermes Agent (Nous Research) preset |
| `gaet check` | Validate config & connections |
| `gaet status` | Show sync status with colored table |
| `gaet status --json` | Status as JSON for scripting/API |

### Backup & Restore
| Command | Description |
|---------|-------------|
| `gaet push` | Backup local → cloud |
| `gaet push --dry-run` | Simulate push without executing |
| `gaet fetch` | Restore cloud → local (overwrites local DB) |
| `gaet fetch --dry-run` | Simulate fetch without executing |
| `gaet push --auto[=N]` | Enable auto-backup every N hours (default: 6, max: 24) |
| `gaet stop` | Stop auto-backup & dashboard |

### Monitoring
| Command | Description |
|---------|-------------|
| `gaet log [N]` | View last N lines of backup log (default: 30) |
| `gaet log --filter KEYWORD` | Filter log by keyword (case-insensitive) |
| `gaet log --since YYYY-MM-DD` | Filter log since a date |
| `gaet serve` | Start web dashboard (background service) |

### Maintenance
| Command | Description |
|---------|-------------|
| `gaet update` | Update to latest version from GitHub |
| `gaet update --force` | Force update (skip local changes check) |
| `gaet update --skip-build` | Update without rebuilding dashboard |
| `gaet uninstall` | Remove gaet CLI (keeps config & backups) |
| `gaet uninstall --purge` | Remove everything including config & backups |
| `gaet --version` | Show version |
| `gaet --help` | Show this help |

---

## How Push Works

```
┌─────────────┐    pg_dump     ┌──────────────┐    pg_restore    ┌──────────────┐
│  Local DB   │ ──────────────→│  .dump file   │ ──────────────→ │  Cloud DB    │
│  (source)   │  (compressed)  │  (temp file)  │  (auto-create)  │  (target)    │
└─────────────┘                └──────────────┘                 └──────────────┘
```

1. **Dump**: `pg_dump` with custom format + max compression
2. **Integrity**: `pg_restore --list` validates the dump file
3. **Restore**: `pg_restore --clean --if-exists --no-owner --no-acl` to cloud
4. **Retention**: Auto-deletes backups older than `GAET_RETENTION_DAYS` (default 7)

**Auto-backup (cron) path** also runs the same integrity check before restoring.

---

## How Fetch Works

1. **Cloud dump**: Downloads compressed dump from cloud
2. **Warning**: Confirms before overwriting local database
3. **Connection kill**: Terminates active connections to local DB
4. **Restore**: `pg_restore --clean --if-exists` to local database
5. **Cleanup**: Temp file deleted after completion

---

## Dry-Run Mode

Test before you execute — no locks acquired, no data touched:

```bash
gaet push --dry-run
# 📦  Simulasi push local → cloud
# Local:  postgres@127.0.0.1:5432/mydb
# Cloud:  user@host:5432/clouddb
# Tables: 12 ditemukan
# Retensi: 7 hari
# Dry-run: Tidak ada perubahan yang dilakukan.

gaet fetch --dry-run
# ☁️   Simulasi fetch cloud → local
# Cloud:  user@host:5432/clouddb
# Local:  postgres@127.0.0.1:5432/mydb
# Aksi:   Dump cloud → restore ke local (overwrite)
# Dry-run: Tidak ada perubahan yang dilakukan.
```

---

## Presets

gaet works with **any PostgreSQL database**. For popular databases, presets auto-configure everything:

| Preset | Description | Usage |
|--------|-------------|-------|
| `hindsight` | Hindsight AI memory database | `gaet init hindsight` |
| `hindsight-hermes` | Hermes Agent (Nous Research) memory database | `gaet init hindsight hermes` |

```bash
# Generic (any database)
gaet init

# With preset
gaet init hindsight

# Hermes Agent preset
gaet init hindsight hermes
```

---

## Auto-Backup

```bash
# Enable auto-backup (default: every 6 hours)
gaet push --auto

# Every 3 hours
gaet push --auto=3

# Stop
gaet stop
gaet stop --scheduler    # Only stop scheduler
gaet stop --dashboard    # Only stop dashboard
```

### Platform details
| Platform | Check Status | Logs |
|----------|--------------|------|
| 🐧 Linux | `systemctl --user list-timers \| grep gaet` | `journalctl --user -u gaet-backup.service` |
| 🍎 macOS | `launchctl list \| grep gaet-backup` | `~/.gaet/backups/cron.log` |
| 🪟 Windows | `schtasks /Query /TN "gaet-backup"` | `%USERPROFILE%\.gaet\backups\cron.log` |

---

## Dashboard Web

Next.js 15 dashboard with Tailwind CSS v4. Runs as a background service.

```bash
# Start
gaet serve

# Open in browser
http://localhost:9191
```

### Dashboard Features
- **Auto-refresh**: Recursive `setTimeout` polling (no race conditions)
- **Stat cards**: Tables count, sync status, backup count, auto-backup status
- **Per-table view**: Local vs Cloud row counts with sync badges
- **One-click actions**: Push, Fetch, Stop/Enable Auto-Backup with loading indicators
- **Error boundaries**: Graceful error handling for all API routes
- **Light/Dark mode**: Persisted in localStorage

### Dashboard API Routes
| Route | Method | Description |
|-------|--------|-------------|
| `/api/status` | GET | Sync status from `gaet status --json` |
| `/api/push` | POST | Execute `gaet push` |
| `/api/push?auto=N` | POST | Enable auto-backup with interval N |
| `/api/fetch` | POST | Execute `gaet fetch` |
| `/api/stop` | POST | Execute `gaet stop` |

All routes use `execFileSync` (no shell injection), validate CORS origins, and include error handling.

---

## Configuration

All config in `~/.gaet/.env`:

### Local Database
| Variable | Default | Description |
|----------|---------|-------------|
| `GAET_LOCAL_URL` | `postgresql://postgres@127.0.0.1:5432/postgres` | Local DB URL (without password) |
| `GAET_LOCAL_DB_PASS` | — | Local DB password (stored separately, never in URL) |

> **Security**: Passwords are never stored in the URL. `GAET_LOCAL_DB_PASS` is stored as a separate variable to avoid plain-text passwords in connection strings. Existing URL-based passwords still work for backward compatibility.

### Cloud Database
| Variable | Default | Description |
|----------|---------|-------------|
| `GAET_REMOTE_URL` | — | PostgreSQL URL for cloud **(REQUIRED)** |
| `GAET_REMOTE_SSLMODE` | `require` | SSL mode for cloud connection |

### Backup
| Variable | Default | Description |
|----------|---------|-------------|
| `GAET_TABLES` | auto-discover | Comma-separated table list override |
| `GAET_RETENTION_DAYS` | `7` | Days to keep old backup files |
| `GAET_AUTO_INTERVAL` | `6` | Auto-backup interval in hours |

### Dashboard
| Variable | Default | Description |
|----------|---------|-------------|
| `GAET_DASHBOARD_PORT` | `9191` | Dashboard web port |
| `GAET_DASHBOARD_HOST` | `0.0.0.0` | Dashboard bind address |

### PostgreSQL Tools
| Variable | Default | Description |
|----------|---------|-------------|
| `GAET_PG_DUMP` | auto-detect | Path to `pg_dump` |
| `GAET_PG_RESTORE` | auto-detect | Path to `pg_restore` |
| `GAET_PSQL` | auto-detect | Path to `psql` |

### Service & Paths
| Variable | Default | Description |
|----------|---------|-------------|
| `GAET_SERVICE_PREFIX` | `gaet` | Prefix for systemd/launchd/schtasks names |
| `GAET_PROJECT_DIR` | — | Override project root path |
| `GAET_PATH` | — | Dashboard API: path to gaet binary |

---

## Security

### Password Handling
- Passwords are stored in `GAET_LOCAL_DB_PASS`, **not** in the connection URL
- Passwords are **never logged** to any file (log, cron, or dashboard)
- Connection URLs in display output are masked (`postgresql://user:****@host:5432/db`)
- Uses `PGPASSFILE` temp files instead of `PGPASSWORD` env var to avoid `/proc` leaks
- Temp password files are **automatically deleted** after each command

### API Security
- All dashboard API routes use `execFileSync` with argument arrays — **no shell injection**
- CORS origin validation on every request
- Environment variable `DASHBOARD_ORIGIN` for custom allowed origins

### File Permissions
- `~/.gaet/.env` created with `0o600` (owner read/write only)
- `PGPASSFILE` temp files created with `0o600`

### Update Security
- `gaet update` downloads from GitHub raw URLs with individual file validation
- For git users: integrity checked via git hashes

### Configuration File
```env
# Example minimal secure config
GAET_LOCAL_URL=postgresql://postgres@127.0.0.1:5432/mydb
GAET_LOCAL_DB_PASS=your_password_here
GAET_REMOTE_URL=postgresql://user:pass@host:5432/clouddb
```

> **Note**: The remote URL still contains a password because cloud providers (Supabase, Neon) generate connection strings in this format. For maximum security, use environment variable injection instead of `.env` for `GAET_REMOTE_URL`.

---

## Project Structure

```
gaet/
├── gaet.py                  # Main CLI (Python, ~2500 lines)
├── install.sh               # Linux/macOS installer
├── install.ps1              # Windows installer (PowerShell)
├── install.py               # Python installer wrapper
├── .env.example             # Config template
├── README.md                # This file
├── CHANGELOG.md             # Version history
├── SECURITY.md              # Security policy
│
├── dashboard/               # Next.js 15 app
│   ├── app/
│   │   ├── page.tsx         # Dashboard main page (378 lines)
│   │   ├── globals.css      # Full design system (dark/light)
│   │   ├── layout.tsx       # Root layout & fonts
│   │   ├── error.tsx        # Error boundary component
│   │   └── api/
│   │       ├── status/      # GET /api/status
│   │       ├── push/        # POST /api/push
│   │       ├── fetch/       # POST /api/fetch
│   │       ├── stop/        # POST /api/stop
│   │       └── utils.ts     # Shared gaet binary finder
│   ├── public/              # Static assets (logo)
│   ├── package.json
│   └── next.config.ts
│
├── scripts/                 # Python support modules
│   ├── __init__.py
│   ├── status.py            # Status module (379 lines)
│   ├── scheduler.py         # Cross-platform scheduler (441 lines)
│   ├── service_manager.py   # Dashboard service (454 lines)
│   └── installer.py         # Universal installer (707 lines)
│
└── tests/
    └── test_gaet.py         # Unit tests (17 tests)
```

---

## Development

```bash
# Run from source
python gaet.py --help

# Run tests
python -m unittest tests.test_gaet -v

# Build dashboard
cd dashboard
npm install
npm run build

# Run dashboard foreground (debug)
python gaet.py serve
```

### Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Zero pip dependencies** | Guarantees portability; stdlib only |
| **Directory-based lock** | Atomic `mkdir` — works on all filesystems |
| **PGPASSFILE over PGPASSWORD** | Avoids `/proc` credential leak on Linux |
| **execFileSync over execSync** | Prevents shell injection in dashboard API |
| **Recursive setTimeout** | Prevents race conditions in status polling |
| **Separate password var** | Keeps plain-text passwords out of connection URLs |

---

## Requirements

| Dependency | Required? | Notes |
|------------|-----------|-------|
| **Python 3.8+** | ✅ Required | The CLI itself |
| **PostgreSQL tools** | ✅ Required | `pg_dump`, `pg_restore`, `psql` |
| **Node.js 18+** | ⚠️ Dashboard only | For the web dashboard |
| **Cloud PostgreSQL** | ✅ Required | Your backup target |

---

## Troubleshooting

### `gaet check` fails
```bash
which pg_dump pg_restore psql    # Verify tools
cat ~/.gaet/.env                 # Check config
gaet check                       # Detailed diagnostics
```

### Dashboard won't open
```bash
gaet stop --dashboard && gaet serve   # Restart
journalctl --user -u gaet-dashboard   # Check logs (Linux)
lsof -i :9191                         # Verify port
```

### Auto-backup not running
```bash
systemctl --user list-timers | grep gaet    # Check timer (Linux)
launchctl list | grep gaet                  # Check launchd (macOS)
gaet stop --scheduler && gaet push --auto   # Restart
```

### `gaet update` won't work
```bash
# For git-clone users
gaet update --force

# For curl-install users
gaet update    # Downloads from GitHub automatically
```

---

## FAQ

**Q: Does gaet support databases other than PostgreSQL?**
A: Not yet. gaet is designed specifically for the PostgreSQL ecosystem.

**Q: Can I backup to S3/GCS directly?**
A: No. gaet backs up to PostgreSQL cloud (Supabase, Neon, RDS). For object storage, consider other tools.

**Q: How long are backups kept?**
A: Default 7 days. Configure with `GAET_RETENTION_DAYS`.

**Q: Is it safe?**
A: Yes. gaet stores passwords outside connection URLs, uses `PGPASSFILE` to avoid `/proc` leaks, and never logs credentials. See [Security](#security) section.

**Q: Can I use it in CI/CD?**
A: Yes. `gaet status --json` outputs JSON for scripting. Use `gaet push --dry-run` to validate in CI.

**Q: What if `gaet fetch` fails halfway?**
A: Local DB may be in an inconsistent state. Re-run `gaet fetch` to retry. The cloud backup is never modified during a fetch.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Links

- **GitHub**: [github.com/ghanirahmans/gaet](https://github.com/ghanirahmans/gaet)
- **Issues**: [github.com/ghanirahmans/gaet/issues](https://github.com/ghanirahmans/gaet/issues)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
- **Security**: [SECURITY.md](SECURITY.md)

---

*gaet v1.0.0. Designed to be a safety net for your database.*
