# Legacy Python Engine (`v1.0.0 LTS`) — Deprecation & Archival Guide

> [!WARNING]
> **Deprecation & Maintenance Notice**:
> The Python edition of **Gaet** (`v1.0.0 LTS`) is officially in maintenance mode. Active feature development and performance enhancements have moved exclusively to the **Golang Engine (`v1.1.0 LTS+`)**.
> 
> Critical security patches for the Python engine will be maintained until **August 2027**, but no new CLI features or subcommands will be added to the Python edition. All users are strongly encouraged to migrate to the compiled single-binary Go release.

---

## 1. Why Migrated to Go?

- **Zero Runtime Overhead**: No need for Python interpreter, `pip`, or virtual environments on target servers.
- **Single Portable Binary**: Compiled into a single executable (`gaet` / `gaet.exe`) for Linux, macOS, and Windows.
- **Fast Startup & Concurrency**: Instant CLI execution and faster PostgreSQL stream dumps.
- **OS Native Daemons**: Integrated systemd, launchd, and Windows Task Scheduler services.

---

## 2. Installing Legacy Python Edition (`v1.0.0 LTS`)

If you require the legacy Python implementation for backward compatibility or existing Python pipelines:

### Method 1: Automated 1-Liner Script (Legacy Python Branch)
```bash
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.0/install.sh | bash
```

### Method 2: Install via Pip (`lts/v1.0` Branch)
```bash
pip install git+https://github.com/ghanirahmans/gaet.git@lts/v1.0
```

### Method 3: Install from Source (Python)
```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
git checkout lts/v1.0
pip install -e .
```

---

## 3. Upgrading to the Recommended Go Engine

Upgrading from Python to the Go engine preserves your existing `~/.gaet/.env` configuration and backup snapshots (`~/.gaet/backups/`).

Run the automated one-liner installer to replace the legacy Python executable:

**Linux / macOS:**
```bash
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.ps1 | iex
```

Verify your installation:
```bash
gaet status
```
