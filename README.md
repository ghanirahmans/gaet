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
  <a href="#configuration">Config</a>
</p>

---

**gaet** is a zero-config CLI tool that backs up your local PostgreSQL database to any cloud PostgreSQL. Supabase, Neon, AWS RDS, or your own VPS. No YAML. No complex setup. Just two lines of config and you're protected.

```bash
# Install
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash

# Configure (one time)
gaet init

# You're protected
gaet push        # Backup local → cloud
gaet status      # See what's synced
gaet serve       # Dashboard at localhost:9191
```

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey)

---

## Why gaet?

> "I lost 3 months of data because I forgot to set up backups."
> Every developer, at least once.

**gaet exists so this never happens to you.**

| Problem | gaet Solution |
|---------|---------------|
| "I keep forgetting to backup" | Auto-backup every N hours via OS scheduler |
| "My backup script broke silently" | Integrity checks before every upload |
| "I don't know if my data is synced" | Real-time dashboard with per-table status |
| "Setup takes too long" | Two lines of config. That's it. |
| "I need this for production" | Concurrency locks, timeouts, retention policies |

---

## Features

| Feature | What it does | Why it matters |
|---------|--------------|----------------|
| 🔒 **Concurrency lock** | Prevents overlapping backups | Your data stays consistent |
| ⏱️ **120s timeout** | Cloud connections never hang | No frozen terminals |
| ✅ **Integrity check** | Validates dump before upload | No corrupt backups |
| 📦 **Compressed dumps** | Custom format, compression 9 | 70% smaller files |
| 🧹 **Auto-retention** | Old backups auto-deleted | No disk space waste |
| 🔄 **Auto-backup** | Periodic via OS scheduler | Set it and forget it |
| 🚀 **Web dashboard** | Real-time status, one-click actions | See everything at a glance |
| 🔌 **Multi-cloud** | Supabase, Neon, RDS, VPS | Works with your stack |
| 📊 **Sync visualization** | Per-table status with progress | Know exactly what's synced |
| 🌓 **Light/Dight mode** | Dashboard supports both themes | Comfortable for everyone |

---

## Platform Support

| Platform | CLI | Auto-backup | Dashboard Service |
|----------|-----|-------------|-------------------|
| 🐧 **Linux** | ✅ Full | systemd user timer | systemd user service |
| 🍎 **macOS** | ✅ Full | launchd timer | launchd agent |
| 🪟 **Windows** | ✅ Full | Task Scheduler | Background PID |

**gaet is pure Python**. Zero pip dependencies. Only requires PostgreSQL tools.

### Quick Install

```bash
# Linux/macOS
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.ps1 | iex
```

---

## For Teams & Enterprises

gaet is built for production workloads:

- **Zero downtime backups**. Uses `pg_dump`/`pg_restore`, the same tools PostgreSQL uses internally
- **Audit trail**. Every backup is logged with timestamp, size, and status
- **No vendor lock-in**. Works with any PostgreSQL provider. Switch from Supabase to RDS? Just change one URL.
- **Self-hosted**. Your data never touches our servers. Run it on your infra.
- **MIT License**. Free for commercial use. No per-seat pricing.

```bash
# See exactly what's happening
gaet status --json | jq '.tables[] | select(.ok == false)'

# Automate in CI/CD
gaet push && echo "Backup complete" || alert-oncall
```

---

## Requirements

| Dependency | Required? | Notes |
|------------|-----------|-------|
| **Python 3.8+** | ✅ Required | The CLI itself |
| **PostgreSQL tools** | ✅ Required | `pg_dump`, `pg_restore`, `psql` |
| **Node.js 18+** | ⚠️ Dashboard only | For the web dashboard |
| **Cloud PostgreSQL** | ✅ Required | Your backup target |

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

**Or clone manually:**
```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
bash install.sh        # Linux/macOS
./install.ps1          # Windows (PowerShell)
```

### 2. Configure

```bash
# Run the wizard
gaet init

# Or edit manually
nano ~/.gaet/.env
```

**Minimal config**. Only 2 lines required:

```env
# Local database (default: hindsight@127.0.0.1:5432/hindsight)
GAET_LOCAL_URL=postgresql://user:pass@127.0.0.1:5432/db

# Cloud database (REQUIRED)
GAET_REMOTE_URL=postgresql://user:pass@host:5432/db
```

### 3. First Backup

```bash
gaet check        # Verify connections
gaet push         # Backup local → cloud
gaet status       # Check sync status
gaet serve        # Open dashboard
```

---

## Commands

| Command | Description |
|---------|-------------|
| `gaet init` | Interactive setup wizard |
| `gaet init hindsight` | Setup with Hindsight preset |
| `gaet push` | Backup local → cloud |
| `gaet fetch` | Restore cloud → local |
| `gaet status` | Sync status table |
| `gaet status --json` | Status as JSON for scripting |
| `gaet check` | Validate config & connections |
| `gaet log [N]` | View last N lines of backup log |
| `gaet push --auto[=N]` | Enable auto-backup every N hours (default 6) |
| `gaet stop` | Stop auto-backup & dashboard |
| `gaet stop --scheduler` | Stop auto-backup only |
| `gaet stop --dashboard` | Stop dashboard only |
| `gaet serve` | Start web dashboard |
| `gaet update` | Update to latest version from GitHub |
| `gaet update --force` | Force update (skip local changes) |
| `gaet uninstall` | Remove gaet (keeps config) |
| `gaet uninstall --purge` | Remove everything including config |
| `gaet --version` | Show version |
| `gaet --help` | Show help |

---

## How Push/Fetch Works

```
┌─────────────┐    pg_dump     ┌──────────────┐    pg_restore    ┌──────────────┐
│  Local DB   │ ──────────────→│  .dump file   │ ──────────────→ │  Cloud DB    │
│  (source)   │  (compressed)  │  (temp file)  │  (auto-create)  │  (target)    │
└─────────────┘                └──────────────┘                 └──────────────┘
```

**Step 1:** `pg_dump`. Extract all from local database
**Step 2:** Integrity check. Validate dump before upload
**Step 3:** `pg_restore`. Restore to cloud with cleanup flags
**Step 4:** Retention. Delete old backups (default 7 days)

**Auto-detected:**
- ✅ All tables (schema)
- ✅ All data
- ✅ Indexes & sequences
- ✅ Foreign keys & constraints
- ✅ Extensions (pgvector, etc.)

---

## Presets

gaet works with **any PostgreSQL database**. For popular databases, presets auto-configure everything:

| Preset | Description | Usage |
|--------|-------------|-------|
| `hindsight` | Hindsight AI memory database | `gaet init hindsight` |

```bash
# Generic (any database)
gaet init

# With preset
gaet init hindsight
```

**Custom presets:** Edit the `PRESETS` dict in `gaet.py`.

---

## Auto-Backup

```bash
# Enable auto-backup (default: every 6 hours)
gaet push --auto

# Every 3 hours
gaet push --auto=3

# Stop
gaet stop
```

**Platform-specific commands:**

| Platform | Check Status | Remove |
|----------|--------------|--------|
| 🐧 Linux | `systemctl --user list-timers` | `gaet stop --scheduler` |
| 🍎 macOS | `launchctl list \| grep gaet` | `gaet stop --scheduler` |
| 🪟 Windows | `schtasks /Query /TN "gaet-backup"` | `gaet stop --scheduler` |

---

## Dashboard Web

Next.js 15 dashboard with Tailwind CSS v4. Runs in background via systemd/launchd.

```bash
# Start
gaet serve

# Open in browser
http://localhost:9191
```

### Dashboard Features
- Real-time sync status (auto-refresh every 8 seconds)
- Per-table sync status
- One-click push/fetch buttons
- Auto-backup indicator
- Light/Dark mode toggle
- Responsive design (mobile-first)

### Manage Service

```bash
# Status
gaet status --json

# Log
journalctl --user -u gaet-dashboard.service -f

# Restart
gaet stop --dashboard
gaet serve
```

---

## Configuration

All config in `~/.gaet/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GAET_REMOTE_URL` | — | PostgreSQL URL for cloud (REQUIRED) |
| `GAET_LOCAL_URL` | `postgresql://postgres:@127.0.0.1:5432/postgres` | Local database |
| `GAET_TABLES` | *(auto-discover)* | Comma-separated table list |
| `GAET_RETENTION_DAYS` | `7` | Days to keep backups |
| `GAET_DASHBOARD_PORT` | `9191` | Dashboard web port |
| `GAET_DASHBOARD_HOST` | `0.0.0.0` | Dashboard bind address |
| `GAET_AUTO_INTERVAL` | `6` | Auto-backup interval (hours) |
| `GAET_SERVICE_PREFIX` | `gaet` | Service name prefix |
| `GAET_PG_DUMP` | *(auto-detect)* | Path to pg_dump |
| `GAET_PG_RESTORE` | *(auto-detect)* | Path to pg_restore |
| `GAET_PSQL` | *(auto-detect)* | Path to psql |
| `GAET_REMOTE_SSLMODE` | `require` | SSL mode for cloud |
| `GAET_PROJECT_DIR` | — | Override project root |

---

## Project Structure

```
gaet/
├── gaet.py                  # Main CLI (Python, ~2000 lines)
├── install.sh               # Universal installer
├── .env.example             # Config template
├── README.md                # This file
├── dashboard/               # Next.js 15 app
│   ├── app/
│   │   ├── page.tsx         # Dashboard main page
│   │   ├── globals.css      # Dark/Light theme
│   │   ├── layout.tsx       # Layout & fonts
│   │   └── api/             # API routes
│   ├── public/              # Static assets (logo)
│   ├── package.json
│   └── next.config.ts
└── scripts/
    ├── __init__.py
    ├── status.py            # Status module
    ├── scheduler.py         # Systemd/launchd/Task Scheduler
    ├── service_manager.py   # Dashboard service
    └── installer.py         # Universal installer
```

---

## Development

```bash
# Run from source
python gaet.py --help

# Test without PostgreSQL
python gaet.py status --json

# Build dashboard
cd dashboard
npm install
npm run build

# Run dashboard foreground (debug)
python gaet.py serve
```

### Testing

| Platform | Status |
|----------|--------|
| 🐧 Linux | ✅ systemd --user |
| 🍎 macOS | ✅ launchd (code ready) |
| 🪟 Windows | ✅ Task Scheduler + PID file |

---

## Dependencies

**Python: 0 external packages**. Stdlib only, no `pip install` needed.

**External tools:**
- `pg_dump`, `pg_restore`, `psql`. PostgreSQL (auto-detect)
- `node`, `npm`. Node.js (dashboard only)
- `systemctl` / `launchctl` / `schtasks`. Auto-detected

---

## Troubleshooting

### `gaet check` fails
- Verify PostgreSQL tools: `which pg_dump pg_restore psql`
- Check config: `cat ~/.gaet/.env`
- Test connection: `gaet check`

### Dashboard won't open
- Check service: `gaet stop --dashboard && gaet serve`
- Check logs: `journalctl --user -u gaet-dashboard.service -f`
- Verify port 9191 is free: `lsof -i :9191`

### Auto-backup not running
- Check timer: `systemctl --user list-timers | grep gaet`
- Restart: `gaet stop --scheduler && gaet push --auto`

### `gaet update` won't work
- Check local changes: `git status`
- Force update: `gaet update --force`

---

## FAQ

**Q: Does gaet support databases other than PostgreSQL?**
A: Not yet. gaet is designed specifically for the PostgreSQL ecosystem.

**Q: Can I backup to S3/GCS directly?**
A: No. gaet backs up to PostgreSQL cloud (Supabase, Neon, RDS). For object storage, consider other tools.

**Q: How long are backups kept?**
A: Default 7 days. Configure with `GAET_RETENTION_DAYS`.

**Q: Is it safe?**
A: Yes. gaet doesn't store passwords in logs. All credentials are only in `~/.gaet/.env` with 600 permissions.

---

## License

MIT License

---

## Links

- **GitHub**: [github.com/ghanirahmans/gaet](https://github.com/ghanirahmans/gaet)
- **Issues**: [github.com/ghanirahmans/gaet/issues](https://github.com/ghanirahmans/gaet/issues)

---

*gaet v1.0.0. Designed to be a safety net for your database.*
