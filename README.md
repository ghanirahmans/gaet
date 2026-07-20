# gaet — Database Backup & Sync

**gaet** is a cross-platform CLI tool to back up local PostgreSQL databases to cloud PostgreSQL (Supabase, Neon, RDS, or any VPS). Comes with a beautiful Next.js dashboard and supports auto-backup via your OS's native scheduler.

```bash
gaet check        # Verify all connections
gaet push         # Backup local → cloud
gaet status       # Sync status at a glance
gaet serve        # Dashboard web (port 9191)
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔒 **Concurrency lock** | Prevents overlapping backups |
| ⏱️ **120s timeout** | Cloud connections never hang forever |
| ✅ **Integrity check** | Dump verified before sending to cloud |
| 📦 **Compressed dumps** | Custom format, compression level 9 |
| 🧹 **Auto-retention** | Old backups auto-deleted (default 7 days) |
| 🔄 **Auto-backup** | Periodic backup via systemd / launchd / Task Scheduler |
| 🚀 **Web dashboard** | Next.js 15 — real-time status, one-click push/fetch |
| 🔌 **Multi-cloud** | Supabase, Neon, RDS, or your own PostgreSQL VPS |

---

## 🖥️ Platform Support

| Platform | Status | Backup Scheduler | Dashboard Service |
|----------|--------|-----------------|-------------------|
| 🐧 **Linux** | ✅ Full | systemd (--user) timer | systemd (--user) service |
| 🍎 **macOS** | ✅ Full | launchd timer | launchd agent |
| 🪟 **Windows** | ✅ Full | Task Scheduler (schtasks) | Background PID process |

All platforms are fully supported. **gaet is pure Python** — zero external Python dependencies (stdlib only).

---

## 📋 Requirements

| Dependency | Required? | Notes |
|-----------|-----------|-------|
| **Python 3.8+** | ✅ Required | The CLI itself |
| **PostgreSQL tools** (`pg_dump`, `pg_restore`, `psql`) | ✅ Required | For backup/restore operations |
| **Node.js 18+** | ⚠️ Dashboard only | For the web dashboard |
| **Cloud PostgreSQL** | ✅ Required | Your backup target (Supabase, Neon, RDS, etc.) |

---

## 🚀 Quick Start

### 1. Install

```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
python install.py          # Interactive installer (recommended)
```

Or with auto-pilot mode:

```bash
python install.py --yes    # Auto-detect OS, check deps, setup everything
```

### 2. Configure

Run the built-in setup wizard:

```bash
python gaet.py init
```

Or edit `~/.gaet/.env` manually:

```env
# Target cloud database
GAET_REMOTE_URL=postgresql://user:password@host:5432/db

# Local database (default: hindsight@127.0.0.1:5432/hindsight)
GAET_LOCAL_DB_HOST=127.0.0.1
GAET_LOCAL_DB_PORT=5432
GAET_LOCAL_DB_NAME=hindsight
GAET_LOCAL_USER=hindsight

# Retention
GAET_RETENTION_DAYS=7
```

See `.env.example` for all options.

### 3. Run your first backup

```bash
python gaet.py check        # Verify all connections
python gaet.py push         # Backup local → cloud
python gaet.py status       # See sync status
python gaet.py serve        # Open dashboard at http://localhost:9191
```

---

## 📖 Commands

| Command | Description |
|---------|-------------|
| `gaet init` | Interactive setup wizard |
| `gaet push` | Backup local database → cloud |
| `gaet fetch` | Restore cloud database → local |
| `gaet status` | Show sync status (tables, rows) |
| `gaet status --json` | Status as JSON (for scripting) |
| `gaet check` | Validate config & all connections |
| `gaet log [N]` | View last N lines of backup log |
| `gaet push --auto[=N]` | Enable auto-backup every N hours (default 6) |
| `gaet stop` | Stop auto-backup & dashboard service |
| `gaet serve` | Start web dashboard (background) |
| `gaet install` | Universal installer (same as `install.py`) |
| `gaet --version` | Show version |

---

## 🗓️ Auto-Backup

Enable periodic backups with your OS native scheduler:

```bash
# Every 6 hours (default)
python gaet.py push --auto

# Every 3 hours
python gaet.py push --auto=3
```

To stop auto-backup:

```bash
python gaet.py stop
```

**How it works per platform:**

| Platform | Tool | Check status | Remove |
|----------|------|-------------|--------|
| 🐧 Linux | `systemctl --user list-timers` | `systemctl --user disable gaet-backup.timer` |
| 🍎 macOS | `launchctl list \| grep gaet` | `launchctl unload ~/Library/LaunchAgents/com.gaet.backup.plist` |
| 🪟 Windows | `schtasks /Query /TN "gaet-backup"` | `schtasks /Delete /TN "gaet-backup" /F` |

---

## 🖥️ Dashboard Web

The dashboard is a production Next.js 15 app with Tailwind CSS v4. It runs in the background and auto-refreshes every 8 seconds.

```bash
# Start dashboard (background)
python gaet.py serve

# Open in browser
open http://localhost:9191      # macOS
xdg-open http://localhost:9191  # Linux
start http://localhost:9191     # Windows
```

### Dashboard Features

- Real-time sync status (auto-refresh every 8 seconds)
- Per-table sync status (9 tracked tables)
- One-click push / fetch buttons
- Auto-backup indicator with countdown
- Dark theme UI
- API endpoints: `/api/status`, `/api/push`, `/api/fetch`, `/api/stop`

### Manage Dashboard Service

```bash
# Linux (systemd)
systemctl --user status gaet-dashboard.service
journalctl --user -u gaet-dashboard.service -f
systemctl --user restart gaet-dashboard.service

# macOS (launchd)
launchctl list | grep gaet-dashboard
tail -f ~/.gaet/backups/dashboard.log
launchctl stop com.gaet.dashboard

# Windows (PID file)
# Status: python gaet.py status --json | find "running"
# Log:    type %USERPROFILE%\.gaet\backups\dashboard.log
# Stop:   python gaet.py stop (also stops auto-backup)
```

---

## 📁 Project Structure

```
gaet/
├── gaet.py                 # Main CLI (Python, ~1500 lines)
├── install.py              # Python installer entry point
├── .env.example            # Config template with docs
├── README.md               # This file
├── dashboard/              # Next.js 15 app
│   ├── app/
│   │   ├── page.tsx        # Dashboard main page
│   │   ├── globals.css     # Dark theme
│   │   └── api/            # 4 API routes
│   ├── package.json
│   └── next.config.ts
└── scripts/
    ├── __init__.py
    ├── scheduler.py        # Platform scheduler abstraction
    ├── status.py           # Cross-platform status checks
    ├── service_manager.py  # Dashboard service manager
    └── installer.py        # Universal installer module
```

---

## ⚙️ Configuration

All config lives in `~/.gaet/.env`. Here are all available variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GAET_REMOTE_URL` | — | PostgreSQL connection string for cloud target |
| `GAET_LOCAL_DB_HOST` | `127.0.0.1` | Local database host |
| `GAET_LOCAL_DB_PORT` | `5432` | Local database port |
| `GAET_LOCAL_DB_NAME` | `hindsight` | Local database name |
| `GAET_LOCAL_USER` | `hindsight` | Local database user |
| `GAET_LOCAL_PASSWORD` | — | Local database password |
| `GAET_RETENTION_DAYS` | `7` | Days to keep local backup files |
| `GAET_DASHBOARD_PORT` | `9191` | Dashboard web server port |
| `GAET_DASHBOARD_HOST` | `0.0.0.0` | Dashboard bind address |
| `GAET_BACKUP_INTERVAL` | `6` | Auto-backup interval in hours |
| `GAET_SERVICE_PREFIX` | `gaet` | Prefix for systemd/launchd/schtasks names |
| `GAET_PROJECT_DIR` | — | Override project root (for dashboard discovery) |

---

## 🔧 Development

```bash
# Run from source
python gaet.py --help

# Test with no PostgreSQL (status only)
python gaet.py status --json

# Run dashboard in foreground (for debugging)
python -c "from scripts.service_manager import service_start; service_start(foreground=True)"
```

### Testing Across Platforms

- **Windows**: Tested on Windows 10 with Git Bash — Task Scheduler, PID-based service
- **Linux**: systemd --user for scheduler + service
- **macOS**: launchd for scheduler + service (code ready, not yet live-tested)

---

## 📦 Dependencies (Zero Python External Deps)

gaet uses **only Python standard library** — no `pip install` needed. The only external tools are:

- `pg_dump`, `pg_restore`, `psql` — from PostgreSQL
- `node`, `npm` — for the dashboard
- Platform-native: `systemctl`, `launchctl`, `schtasks` — auto-detected

---

## 🔗 Links

- **GitHub**: [github.com/ghanirahmans/gaet](https://github.com/ghanirahmans/gaet)
- **Issues**: [github.com/ghanirahmans/gaet/issues](https://github.com/ghanirahmans/gaet/issues)

---

*gaet v1.0.0 — Built with ❤️ for self-hosters and PostgreSQL lovers.*
