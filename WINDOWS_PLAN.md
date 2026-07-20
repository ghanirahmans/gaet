# Plan: gaet for Windows

## Masalah

`gaet` saat ini bash script (`#!/bin/bash`). Di Windows:
- Bash gak ada secara native
- `systemd` gak ada (Task Scheduler sebagai ganti)
- Path berbeda (`C:\Users\...` vs `/home/...`)
- pg0 (Hindsight) gak available
- ANSI terminal support terbatas di CMD lama

## Opsi Pendekatan

### A. Python rewrite (⭐ RECOMMENDED)
Tulis ulang `gaet` jadi Python CLI. Semua logic bash → Python.

| Pro | Kontra |
|-----|--------|
| Satu kode untuk Linux + Windows + macOS | Butuh ngoding ulang |
| `status.py` udah ada, tinggal expand | |
| Bisa pake `rich` — TUI lebih cantik dari bash | |
| `pip install gaet` distribusi mudah | |
| PyInstaller → `.exe` tanpa Python | |

### B. PowerShell
Tulis ulang jadi PowerShell script (`.ps1`).

| Pro | Kontra |
|-----|--------|
| Native Windows | PS Core di Linux beda behavior |
| Bisa pake Task Scheduler API | Syntax berat, gak seasik Python |
| | Pengguna Linux harus install PowerShell |

### C. Git Bash + Wrapper
Bundling bash script dengan Git for Windows + handle path.

| Pro | Kontra |
|-----|--------|
| Reuse bash yang udah jadi | Dependency berat (Git for Windows) |
| | systemd gak bisa |
| | User harus install PostgreSQL manual |

## Recommended: Python Rewrite

### Arsitektur

```
gaet/                  → Python package
├── __init__.py
├── __main__.py        → python -m gaet
├── cli.py             → CLI entry (argparse + rich)
├── config.py          → Load .env, detect tools
├── backup.py          → push, fetch, cron logic
├── db.py              → pg_dump, pg_restore wrapper
├── status.py          → Status module (udah ada, tinggal adapt)
├── system.py          → Systemd (Linux) / Task Scheduler (Windows)
├── ui.py              → Rich console output (tables, boxes)
└── server.py          → Dashboard API server (udah ada, adapt)

setup.py               → pip installable
gaet.exe               → PyInstaller build
```

### File-by-file plan

1. **`cli.py`** — Argparse CLI, `gaet push`, `gaet status`, dll. Ganti `bash case` jadi Python argparse.
2. **`ui.py`** — `rich` library: `Console`, `Table`, `Panel`, `Box`. Output cantik lintas platform.
3. **`config.py`** — Baca `~/.gaet/.env`. Auto-detect `pg_dump`/`psql` di PATH + `Program Files`.
4. **`db.py`** — Wrapper `subprocess.run` untuk pg_dump/pg_restore. Handle timeout, retry, integritas.
5. **`backup.py`** — Logic push/fetch/cron. Concurrency lock via tempfile.
6. **`system.py`** — Abstraksi service:
   - Linux: systemd user service (udah ada)
   - Windows: Task Scheduler via `schtasks.exe` + `powershell`
7. **`server.py`** — Adaptasi server.py yang udah ada. Panggil Python gaet, bukan bash.
8. **`__main__.py`** — `python -m gaet`

### Windows-specific challenges

| Challenge | Solution |
|-----------|----------|
| PostgreSQL path | Cek `%PROGRAMFILES%\PostgreSQL\*\bin\pg_dump.exe`, `%PATH%`, `pg_config` |
| systemd → Task Scheduler | `schtasks /create /tn "gaet-backup" /tr "gaet push" /mo 6 /sc hourly` |
| Lock mechanism | `tempfile.mkdtemp()` (cross-platform) |
| Path config | `%APPDATA%\gaet\.env` instead of `~/.gaet/.env` |
| ANSI in CMD | Rich library handle fallback otomatis |
| Daemon/service | `pywin32` atau NSSM untuk dashboard |
| Lingger (reboot) | Task Scheduler "Run whether user logged on or not" |

### Distribusi

```bash
# 1. PyPI
pip install gaet

# 2. Standalone .exe (no Python needed)
# PyInstaller bundling
gaet.exe push

# 3. Atau tetap bash untuk Linux (backward compat)
# ./gaet push   (bash version)
# gaet push     (Python version)
```

### Timeline Estimate

| Phase | Tasks | Estimate |
|-------|-------|----------|
| 1 | `cli.py` + `config.py` + argparse | 1 session |
| 2 | `db.py` + `backup.py` (push/fetch) | 1 session |
| 3 | `ui.py` — rich tables, boxes | 1 session |
| 4 | `system.py` — systemd + Task Scheduler | 1 session |
| 5 | Windows testing + path handling | 1 session |
| 6 | PyInstaller + distribusi | 1 session |

### Migration Path

```
Phase 1: Python CLI + Linux (bash tetap jalan)
Phase 2: Windows support (python gaet)
Phase 3: Deprecate bash (optional, semua pake Python)
```

### Risiko

- **`rich` library** — dependency tambahan. Tapi bisa fallback ke print biasa.
- **pg_dump Windows version** — EDB punya installer, path beda-beda.
- **Task Scheduler via schtasks** — butuh admin? Cek dulu.
- **Performance** — Python startup ~100ms vs bash ~10ms. Gak signifikan buat CLI backup.
