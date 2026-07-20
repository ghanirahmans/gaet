#!/usr/bin/env python3
"""
gaet — Database Backup & Sync CLI (Cross-Platform)
===================================================
Backup PostgreSQL lokal ke cloud (Supabase, Neon, RDS, VPS).

Usage:
  gaet init              Setup wizard
  gaet push              Local → cloud
  gaet fetch             Cloud → local
  gaet update            Update ke versi terbaru
  gaet --version         Tampilkan versi
  gaet status            Tampilkan status
  gaet status --json     Status dalam JSON
  gaet check             Validasi konfigurasi
  gaet log               Lihat log backup
  gaet push --auto[=N]   Aktifkan auto-backup tiap N jam (default 6)
  gaet stop              Hentikan auto-backup
  gaet serve             Jalankan dashboard web
  gaet --version         Tampilkan versi
  gaet --help            Tampilkan bantuan
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Version ──────────────────────────────────────────────────────────────
VERSION = "1.0.0"
NAME = "gaet"

# ─── OS Detection ─────────────────────────────────────────────────────────
SYSTEM = sys.platform
IS_LINUX = SYSTEM.startswith("linux")
IS_MACOS = SYSTEM == "darwin"
IS_WINDOWS = SYSTEM == "win32" or SYSTEM.startswith("msys") or SYSTEM.startswith("cygwin")

# ─── Paths ────────────────────────────────────────────────────────────────
HOME = Path.home()
GAET_DIR = HOME / ".gaet"
BACKUP_DIR = GAET_DIR / "backups"
LOG_FILE = BACKUP_DIR / "gaet.log"
CRON_LOG = BACKUP_DIR / "cron.log"
LOCK_PATH = BACKUP_DIR / ".gaet.lock"
ENV_FILE = GAET_DIR / ".env"

# ─── Defaults ─────────────────────────────────────────────────────────────
DEF_LOCAL_HOST = "127.0.0.1"
DEF_LOCAL_PORT = "5432"
DEF_LOCAL_USER = "postgres"
DEF_LOCAL_DB = "postgres"
DEF_LOCAL_PASS = ""
DEF_RETENTION_DAYS = 7
DEF_AUTO_INTERVAL = 6
DEF_DASHBOARD_PORT = 9191
DEF_DASHBOARD_HOST = "0.0.0.0"
DEF_REMOTE_SSLMODE = "require"
DEF_SERVICE_PREFIX = "gaet"

# ─── Presets ──────────────────────────────────────────────────────────────
# Predefined configs for popular databases
PRESETS: Dict[str, Dict[str, str]] = {
    "hindsight": {
        "local_user": "hindsight",
        "local_db": "hindsight",
        "local_pass": "hindsight",
        "tables": "memory_units,banks,chunks,entities,documents,async_operations,audit_log,file_storage,memory_links",
        "description": "Hindsight AI memory database",
    },
}

# ─── ANSI Colors ──────────────────────────────────────────────────────────
if sys.stdout.isatty():
    R = "\033[0;31m"
    G = "\033[0;32m"
    Y = "\033[1;33m"
    C = "\033[0;36m"
    B = "\033[1m"
    D = "\033[2m"
    W = "\033[1;37m"
    NC = "\033[0m"
    ICON_OK = "✓"
    ICON_FAIL = "✗"
    ICON_WARN = "⚠"
    ICON_INFO = "ℹ"
    ICON_ARROW = "→"
    ICON_STAR = "✦"
else:
    R = G = Y = C = B = D = W = NC = ""
    ICON_OK = "OK"
    ICON_FAIL = "FAIL"
    ICON_WARN = "WARN"
    ICON_INFO = "i"
    ICON_ARROW = ">"
    ICON_STAR = "*"


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def die(msg: str, code: int = 1) -> None:
    """Print error and exit."""
    print(f"  {R}{ICON_FAIL}{NC}  {msg}", file=sys.stderr)
    sys.exit(code)


# ─── Logging ──────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    """Write to log file and print."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(LOG_FILE), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def cronlog(msg: str) -> None:
    """Write to cron log file only."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(CRON_LOG), "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ─── Lock ─────────────────────────────────────────────────────────────────

def acquire_lock() -> None:
    """Acquire exclusive lock via directory creation (atomic cross-platform)."""
    try:
        LOCK_PATH.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        die(f"gaet sedang berjalan (lock: {LOCK_PATH})")


def release_lock() -> None:
    """Release lock."""
    try:
        LOCK_PATH.rmdir()
    except (OSError, FileNotFoundError):
        pass


# ─── Config Loading ───────────────────────────────────────────────────────

def load_env() -> Dict[str, str]:
    """Parse ~/.gaet/.env, return dict. Supports 'export KEY=val' and bare 'KEY=val'."""
    env: Dict[str, str] = {}
    if not ENV_FILE.is_file():
        return env
    with open(str(ENV_FILE), "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # export KEY="val" # comment
            m = re.match(r"^export\s+([^=]+)=\"?([^#]*?)\"?\s*(?:#.*)?$", line)
            if m:
                env[m.group(1).strip()] = m.group(2).strip().strip('"').strip("'")
                continue
            m = re.match(r"^([^=]+)=(.*)$", line)
            if m:
                env[m.group(1).strip()] = m.group(2).strip().strip('"').strip("'")
    return env


def get_env_str(env: Dict[str, str], key: str, default: str = "") -> str:
    """Get string value from env dict, respecting OS environment override."""
    # OS environment (e.g., export before running gaet) takes priority
    os_val = os.environ.get(key)
    if os_val is not None:
        return os_val
    return env.get(key, default)


def get_env_int(env: Dict[str, str], key: str, default: int) -> int:
    """Get int value from env."""
    val = get_env_str(env, key)
    if val:
        try:
            return int(val)
        except ValueError:
            return default
    return default


def parse_remote_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parse postgresql://user:pass@host:port/db.
    Returns dict or None.
    """
    if not url:
        return None
    m = re.match(
        r"postgres(?:ql)?://([^:]+):([^@]+)@([^:]+):(\d+)/([^?\s]+)",
        url,
    )
    if not m:
        return None
    return {
        "user": m.group(1),
        "pass": m.group(2),
        "host": m.group(3),
        "port": m.group(4),
        "db": m.group(5),
    }


def get_local_db(env: Dict[str, str]) -> Tuple[str, str, str, str, str]:
    """Parse GAET_LOCAL_URL or individual vars. Returns (host, port, user, db, passwd)."""
    url = get_env_str(env, "GAET_LOCAL_URL")
    if url:
        p = parse_remote_url(url)
        if p:
            return p["host"], p["port"], p["user"], p["db"], p["pass"]
        # Try with default password if URL doesn't have one
        return p["host"], p["port"], p["user"], p["db"], ""
    # Fallback: individual vars (backward compat)
    return (
        get_env_str(env, "GAET_LOCAL_DB_HOST", DEF_LOCAL_HOST),
        get_env_str(env, "GAET_LOCAL_DB_PORT", DEF_LOCAL_PORT),
        get_env_str(env, "GAET_LOCAL_DB_USER", DEF_LOCAL_USER),
        get_env_str(env, "GAET_LOCAL_DB_NAME", DEF_LOCAL_DB),
        get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS),
    )


# ─── Table Discovery ─────────────────────────────────────────────────────

def discover_tables(psql: str, h: str, p: str, u: str, n: str, w: str) -> List[str]:
    """Auto-discover tables from information_schema.tables (public schema)."""
    query = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    out, _, rc = run_cmd(
        [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", query],
        env={"PGPASSWORD": w},
        timeout=10,
    )
    if rc == 0 and out.strip():
        return [t.strip() for t in out.strip().split("\n") if t.strip()]
    return []


def get_tables(env: Dict[str, str], tools: Dict[str, str]) -> List[str]:
    """Get table list: config override > auto-discover > empty."""
    # 1. Check GAET_TABLES config
    tables_str = get_env_str(env, "GAET_TABLES")
    if tables_str:
        return [t.strip() for t in tables_str.split(",") if t.strip()]

    # 2. Auto-discover from local DB
    h, p, u, n, w = get_local_db(env)
    psql = tools.get("psql", "")
    if psql:
        tables = discover_tables(psql, h, p, u, n, w)
        if tables:
            return tables

    return []


# ─── PG Tools Discovery ──────────────────────────────────────────────────

def find_pg_tools(env: Dict[str, str]) -> Dict[str, str]:
    """
    Cari pg_dump, pg_restore, psql.
    Priority: env var > pg0 > PATH > common Windows paths.
    """
    pg_dump = get_env_str(env, "GAET_PG_DUMP") or ""
    pg_restore = get_env_str(env, "GAET_PG_RESTORE") or ""
    psql = get_env_str(env, "GAET_PSQL") or ""

    # Check if already found
    if pg_dump and pg_restore and psql:
        return {"pg_dump": pg_dump, "pg_restore": pg_restore, "psql": psql}

    try:
        # pg0 discovery (Linux/macOS — pg0 from hindsight setup)
        pg0_base = HOME / ".pg0" / "installation"
        if pg0_base.is_dir():
            versions = sorted(
                [d.name for d in pg0_base.iterdir() if d.is_dir()],
                key=lambda s: [int(x) for x in s.split(".")],
                reverse=True,
            )
            if versions:
                pg0_bin = pg0_base / versions[0] / "bin"
                if not pg_dump and (pg0_bin / "pg_dump").is_file():
                    pg_dump = str(pg0_bin / "pg_dump")
                if not pg_restore and (pg0_bin / "pg_restore").is_file():
                    pg_restore = str(pg0_bin / "pg_restore")
                if not psql and (pg0_bin / "psql").is_file():
                    psql = str(pg0_bin / "psql")
    except (OSError, IndexError):
        pass

    # PATH lookup
    if not pg_dump:
        pg_dump = shutil.which("pg_dump") or ""
    if not pg_restore:
        pg_restore = shutil.which("pg_restore") or ""
    if not psql:
        psql = shutil.which("psql") or ""

    # Windows: common PostgreSQL install paths
    if IS_WINDOWS:
        for pg_root in [
            "C:\\Program Files\\PostgreSQL",
            "C:\\Program Files (x86)\\PostgreSQL",
        ]:
            pg_path = Path(pg_root)
            if pg_path.is_dir():
                try:
                    versions = sorted(
                        [d.name for d in pg_path.iterdir() if d.is_dir() and d.name.isdigit()],
                        key=int,
                        reverse=True,
                    )
                    if versions:
                        bin_dir = pg_path / versions[0] / "bin"
                        if not pg_dump:
                            candidate = bin_dir / "pg_dump.exe"
                            if candidate.is_file():
                                pg_dump = str(candidate)
                        if not pg_restore:
                            candidate = bin_dir / "pg_restore.exe"
                            if candidate.is_file():
                                pg_restore = str(candidate)
                        if not psql:
                            candidate = bin_dir / "psql.exe"
                            if candidate.is_file():
                                psql = str(candidate)
                except (OSError, IndexError):
                    pass

    return {"pg_dump": pg_dump, "pg_restore": pg_restore, "psql": psql}


# ─── Terminal UI ─────────────────────────────────────────────────────────

def echo(msg: str = "", end: str = "\n") -> None:
    """Print with our formatting conventions."""
    print(msg, end=end, flush=True)


def box_title(title: str) -> None:
    """Draw a boxed title with Unicode double-line box characters."""
    import re as _re
    
    # Remove ANSI codes for visible length calculation
    clean_title = _re.sub(r'\033\[[0-9;]*m', '', title)
    
    # Double-line box - professional look
    width = 50
    visible_len = len(clean_title)
    pad = max(0, (width - visible_len) // 2)
    rpad = width - visible_len - pad
    
    echo()
    echo(f"  {C}╔{'═' * (width + 2)}╗{NC}")
    echo(f"  {C}║{NC} {' ' * pad}{B}{clean_title}{NC} {' ' * rpad}{C}║{NC}")
    echo(f"  {C}╚{'═' * (width + 2)}╝{NC}")
    echo()


def box_section(title: str) -> None:
    """Section heading."""
    echo(f"  {C}─{NC} {B}{title}{NC}")


def status_ok(msg: str) -> None:
    echo(f"  {G}{ICON_OK}{NC}  {msg}")


def status_fail(msg: str) -> None:
    echo(f"  {R}{ICON_FAIL}{NC}  {msg}")


def status_warn(msg: str) -> None:
    echo(f"  {Y}{ICON_WARN}{NC}  {msg}")


def status_info(msg: str) -> None:
    echo(f"  {C}{ICON_INFO}{NC}  {msg}")


def status_arrow(msg: str) -> None:
    echo(f"  {D}{ICON_ARROW}{NC}  {msg}")


def draw_table(headers: str, rows: List[str]) -> None:
    """
    Draw a table similar to Bash version.
    headers: colon-separated header names (e.g., "Tabel:Lokal:Cloud:Status")
    rows: list of pipe-separated values (e.g., ["memory_units|150|150|✓"])
    """
    h_list = headers.split(":")
    ncols = len(h_list)
    widths = [len(h) for h in h_list]

    data: List[List[str]] = []
    for row in rows:
        vals = row.split("|")
        vals = vals + [""] * (ncols - len(vals))  # pad
        data.append(vals)
        for i, v in enumerate(vals):
            widths[i] = max(widths[i], len(v))

    # Separator
    def sep_row(left: str, mid: str, right: str, junction: str) -> str:
        parts = [f"{D}{left}{NC}"]
        for i, w in enumerate(widths):
            parts.append(f"{D}{'═' * (w + 2)}{NC}")
            if i < ncols - 1:
                parts.append(f"{D}{junction}{NC}")
            else:
                parts.append(f"{D}{right}{NC}")
        return "  " + "".join(parts)

    top = sep_row("╔", "╦", "╗", "╦")
    mid_sep = sep_row("╠", "╬", "╣", "╬")
    bot = sep_row("╚", "╩", "╝", "╩")

    echo(top)
    # Header
    hdr = f"  {D}║{NC}"
    for i, h in enumerate(h_list):
        pad = widths[i] - len(h)
        hdr += f" {B}{h}{NC}{' ' * (pad + 1)}{D}║{NC}"
    echo(hdr)
    echo(mid_sep)

    for vals in data:
        row = f"  {D}║{NC}"
        for i, v in enumerate(vals):
            pad = widths[i] - len(v)
            row += f" {v}{' ' * (pad + 1)}{D}║{NC}"
        echo(row)

    echo(bot)


def draw_colored_table(headers: str, rows: List[str], colors: Optional[List[str]] = None) -> None:
    """
    Draw a colored table with row-level coloring.
    headers: colon-separated header names
    rows: pipe-separated values
    colors: optional list of ANSI color codes per row
    """
    h_list = headers.split(":")
    ncols = len(h_list)
    widths = [len(h) for h in h_list]

    data: List[List[str]] = []
    for idx, row in enumerate(rows):
        vals = row.split("|")
        vals = vals + [""] * (ncols - len(vals))
        data.append(vals)
        for i, v in enumerate(vals):
            # Strip ANSI for width calculation
            import re as _re
            clean = _re.sub(r'\033\[[0-9;]*m', '', v)
            widths[i] = max(widths[i], len(clean))

    def sep_row(left: str, mid: str, right: str, junction: str) -> str:
        parts = [f"{D}{left}{NC}"]
        for i, w in enumerate(widths):
            parts.append(f"{D}{'═' * (w + 2)}{NC}")
            if i < ncols - 1:
                parts.append(f"{D}{junction}{NC}")
            else:
                parts.append(f"{D}{right}{NC}")
        return "  " + "".join(parts)

    top = sep_row("╔", "╦", "╗", "╦")
    mid_sep = sep_row("╠", "╬", "╣", "╬")
    bot = sep_row("╚", "╩", "╝", "╩")

    echo(top)
    # Header
    hdr = f"  {D}║{NC}"
    for i, h in enumerate(h_list):
        pad = widths[i] - len(h)
        hdr += f" {B}{h}{NC}{' ' * (pad + 1)}{D}║{NC}"
    echo(hdr)
    echo(mid_sep)

    # Data rows with optional color
    for idx, vals in enumerate(data):
        row_color = colors[idx] if colors and idx < len(colors) else ""
        row = f"  {D}║{NC}"
        for i, v in enumerate(vals):
            import re as _re
            clean = _re.sub(r'\033\[[0-9;]*m', '', v)
            pad = widths[i] - len(clean)
            row += f" {row_color}{v}{NC}{' ' * (pad + 1)}{D}║{NC}"
        echo(row)

    echo(bot)


def print_sync_summary(local_count: int, remote_count: int, synced: bool, table_count: int) -> None:
    """Print a compact sync summary after push/fetch."""
    echo()
    box_section("Ringkasan")
    if synced:
        status_ok(f"Semua {table_count} tabel sinkron ({local_count} rows)")
    else:
        status_warn(f"Tabel tidak sinkron — {table_count} tabel diperiksa")
    status_arrow(f"Lokal:  {local_count} rows")
    status_arrow(f"Cloud: {remote_count} rows")


def print_push_summary(backup_file: str, size_mb: float, tables_synced: int) -> None:
    """Print summary after successful push."""
    echo()
    box_section("Push Selesai")
    status_ok(f"Backup tersimpan: {backup_file} ({size_mb:.1f} MB)")
    status_ok(f"Tabel sinkron: {tables_synced}")
    status_arrow("Jalankan 'gaet status' untuk detail")


# ─── Subprocess helpers ──────────────────────────────────────────────────

def run_cmd(
    cmd: List[str],
    env: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    capture: bool = True,
    cwd: Optional[str] = None,
) -> Tuple[str, str, int]:
    """
    Run a command, return (stdout, stderr, returncode).
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
            cwd=cwd,
        )
        return proc.stdout.strip(), proc.stderr.strip(), proc.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", 1
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", 127
    except Exception as e:
        return "", str(e), 1


def check_tools(env: Dict[str, str]) -> None:
    """Verify all PostgreSQL tools are found."""
    tools = find_pg_tools(env)
    ok = True
    if not tools["pg_dump"]:
        status_fail("pg_dump tidak ditemukan")
        ok = False
    if not tools["pg_restore"]:
        status_fail("pg_restore tidak ditemukan")
        ok = False
    if not tools["psql"]:
        status_fail("psql tidak ditemukan")
        ok = False
    if not ok:
        die(
            "Pasang PostgreSQL tools dulu, atau set GAET_PG_DUMP dll di .env"
        )


def check_local_db(env: Dict[str, str]) -> Tuple[str, str, str, str, str]:
    """Verify local DB connection. Returns (host, port, user, db, passwd)."""
    h, p, u, n, w = get_local_db(env)
    tools = find_pg_tools(env)
    psql = tools["psql"]
    if not psql:
        die("psql tidak ditemukan")

    pg_env = {"PGPASSWORD": w}
    out, err, rc = run_cmd(
        [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
        env=pg_env,
        timeout=5,
    )
    if rc != 0 or out.strip() != "1":
        die(
            f"Gak bisa konek ke database lokal ({h}:{p}/{n})\n"
            f"  Cek konfigurasi database di {ENV_FILE}"
        )
    return h, p, u, n, w


# ═══════════════════════════════════════════════════════════════════════════
# SCHEDULER ABSTRACTION
# ═══════════════════════════════════════════════════════════════════════════
# Import from scripts.scheduler module — fallback ke inline kalo gak bisa import

try:
    from scripts.scheduler import (
        scheduler_is_active,
        scheduler_enable,
        scheduler_disable,
        get_scheduler_name,
    )
except ImportError:
    # Fallback: inline minimal implementation
    def scheduler_is_active(prefix: str) -> bool:
        """Check if auto-backup scheduler is active (fallback)."""
        if IS_LINUX:
            out, _, rc = run_cmd(
                ["systemctl", "--user", "is-active", f"{prefix}-backup.timer"],
                timeout=5,
            )
            return rc == 0 and out.strip() == "active"
        elif IS_MACOS:
            out, _, rc = run_cmd(["launchctl", "list", f"{prefix}-backup"], timeout=5)
            return rc == 0
        elif IS_WINDOWS:
            _, _, rc = run_cmd(
                ["schtasks", "/Query", "/TN", f"{prefix}-backup"], timeout=10,
            )
            return rc == 0
        return False

    def scheduler_enable(prefix: str, interval: int, cli_path: str) -> bool:
        """Enable scheduler (fallback)."""
        if IS_LINUX:
            user_systemd = HOME / ".config" / "systemd" / "user"
            user_systemd.mkdir(parents=True, exist_ok=True)
            svc = user_systemd / f"{prefix}-backup.service"
            svc.write_text(
                f"[Unit]\nDescription={NAME} backup\nAfter=network.target\n\n"
                f"[Service]\nType=oneshot\nExecStart={cli_path} push --cron\n"
            )
            tim = user_systemd / f"{prefix}-backup.timer"
            tim.write_text(
                f"[Unit]\nDescription={NAME} periodic backup (every {interval}h)\n\n"
                f"[Timer]\nOnCalendar=*-*-* 00/0{interval}:00:00\nPersistent=true\n\n"
                f"[Install]\nWantedBy=timers.target\n"
            )
            run_cmd(["systemctl", "--user", "daemon-reload"], timeout=10)
            _, _, rc = run_cmd(
                ["systemctl", "--user", "enable", "--now", f"{prefix}-backup.timer"],
                timeout=10,
            )
            return rc == 0
        elif IS_MACOS:
            plist = HOME / "Library" / "LaunchAgents" / f"{prefix}-backup.plist"
            plist.parent.mkdir(parents=True, exist_ok=True)
            plist.write_text(
                f'<?xml version="1.0"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                f'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0">'
                f"<dict><key>Label</key><string>{prefix}-backup</string>"
                f"<key>ProgramArguments</key><array><string>{cli_path}</string>"
                f"<string>push</string><string>--cron</string></array>"
                f"<key>StartInterval</key><integer>{interval * 3600}</integer>"
                f"<key>RunAtLoad</key><true/></dict></plist>"
            )
            _, _, rc = run_cmd(["launchctl", "load", str(plist)], timeout=10)
            return rc == 0
        elif IS_WINDOWS:
            python_exe = shutil.which("python") or sys.executable
            _, _, rc = run_cmd(
                ["schtasks", "/Create", "/F", "/TN", f"{prefix}-backup",
                 "/TR", f'"{python_exe}" "{cli_path}" push --cron',
                 "/SC", "HOURLY", "/MO", str(interval)], timeout=10)
            return rc == 0
        return False

    def scheduler_disable(prefix: str) -> bool:
        """Disable scheduler (fallback)."""
        if IS_LINUX:
            run_cmd(["systemctl", "--user", "disable", "--now", f"{prefix}-backup.timer"], timeout=10)
            run_cmd(["systemctl", "--user", "disable", "--now", f"{prefix}-backup.service"], timeout=10)
        elif IS_MACOS:
            plist = HOME / "Library" / "LaunchAgents" / f"{prefix}-backup.plist"
            if plist.is_file():
                run_cmd(["launchctl", "unload", str(plist)], timeout=10)
                plist.unlink(missing_ok=True)
        elif IS_WINDOWS:
            run_cmd(["schtasks", "/Delete", "/F", "/TN", f"{prefix}-backup"], timeout=10)
        return True

    def get_scheduler_name() -> str:
        if IS_LINUX:
            return "systemd (user)"
        elif IS_MACOS:
            return "launchd"
        elif IS_WINDOWS:
            return "Task Scheduler"
        return "unknown"


# Import from scripts.service_manager — dashboard service management
# ═══════════════════════════════════════════════════════════════════════════

try:
    from scripts.service_manager import (
        service_start,
        service_stop,
        service_is_running,
        service_status,
    )

    # Rename to short names for gaet.py usage
    def _svc_start(*a, **kw):
        return service_start(*a, **kw)

    def _svc_stop():
        return service_stop()

    def _svc_is_running():
        return service_is_running()

    def _svc_status():
        return service_status()

except ImportError:
    # Fallback: inline minimal (just print warning)
    def _svc_start(dashboard_dir=None, port=9191, host="0.0.0.0", foreground=False):
        print("  ⚠  service_manager module tidak tersedia. Jalankan dari folder proyek.")
        return False, "module not found"

    def _svc_stop():
        return True, "module not loaded"

    def _svc_is_running():
        return False

    def _svc_status():
        return {"running": False, "platform": "unknown", "pid": None}


# ═══════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

def cmd_init(args: argparse.Namespace) -> None:
    """Setup wizard interaktif."""
    env = load_env()
    box_title(f"{NAME} init")

    # Resolve preset
    preset_name = getattr(args, "preset_flag", None) or getattr(args, "preset", None)
    preset: Optional[Dict[str, str]] = None
    if preset_name:
        preset = PRESETS.get(preset_name.lower())
        if not preset:
            die(f"Preset '{preset_name}' tidak dikenal. Tersedia: {', '.join(PRESETS.keys())}")
        echo(f"  {C}📋{NC}  Preset: {preset.get('description', preset_name)}")

    # PG Tools
    box_section("PostgreSQL Tools")
    tools = find_pg_tools(env)
    for name in ("pg_dump", "pg_restore", "psql"):
        path = tools.get(name, "")
        if path:
            status_ok(f"{name:12} {D}\"{path}\"{NC}")
        else:
            status_fail(f"{name:12} tidak ditemukan")

    GAET_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if not ENV_FILE.is_file():
        echo()
        box_section("Konfigurasi Database Lokal")

        # Apply preset defaults if provided
        h, p, u, n, w = get_local_db(env)
        if preset:
            u = preset.get("local_user", u)
            n = preset.get("local_db", n)
            w = preset.get("local_pass", w)
            echo(f"  {D}Preset '{preset_name}': user={u}, db={n}{NC}")
        else:
            echo(f"  {D}Default: postgres@127.0.0.1:5432/postgres{NC}")

        h_inp = input(f"  Host [{h}]: ").strip()
        if h_inp: h = h_inp
        p_inp = input(f"  Port [{p}]: ").strip()
        if p_inp: p = p_inp
        u_inp = input(f"  User [{u}]: ").strip()
        if u_inp: u = u_inp
        n_inp = input(f"  Database [{n}]: ").strip()
        if n_inp: n = n_inp
        w_inp = input(f"  Password [{w}]: ").strip()
        if w_inp: w = w_inp

        echo()
        box_section("Cloud / Remote Database")
        echo(f"  {D}Masukkan connection string PostgreSQL tujuan.{NC}")
        echo(f"  {D}Bisa dari Supabase, Neon, RDS, atau VPS sendiri.{NC}")
        echo(f"  {D}Format: postgresql://user:***@host:5432/db{NC}")
        remote_url = input("  GAET_REMOTE_URL: ").strip()

        echo()
        box_section("Backup")
        ret_inp = input(f"  Retensi (hari) [{DEF_RETENTION_DAYS}]: ").strip()
        ret = ret_inp or str(DEF_RETENTION_DAYS)

        # Tables line for preset
        tables_line = ""
        if preset and "tables" in preset:
            tables_line = f"# GAET_TABLES={preset['tables']}"

        env_content = textwrap.dedent(f"""\
        # ══════════════════════════════════════════════════════════════
        # gaet — Konfigurasi
        # ══════════════════════════════════════════════════════════════
        # Dibuat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        # ══════════════════════════════════════════════════════════════

        # Database Lokal
        GAET_LOCAL_URL=postgresql://{u}:{w}@{h}:{p}/{n}

        # Remote Database (Cloud)
        GAET_REMOTE_URL={remote_url}

        # Backup
        GAET_RETENTION_DAYS={ret}
        {tables_line}""")

        ENV_FILE.write_text(env_content)
        ENV_FILE.chmod(0o600)
        echo()
        status_ok(f"Config tersimpan di {ENV_FILE}")
    else:
        status_info(f"Config sudah ada: {ENV_FILE}")

    echo()
    box_section("Pre-flight Check")
    # Continue to check
    env = load_env()  # reload
    tools = find_pg_tools(env)
    cmd_check_inner(env, tools)


def cmd_check_inner(env: Dict[str, str], tools: Dict[str, str]) -> bool:
    """Inner check — reused by init and check command."""
    all_ok = True

    # Tools
    echo(f"  {C}🔧{NC}  PostgreSQL tools... ", end="")
    if tools["pg_dump"] and tools["pg_restore"] and tools["psql"]:
        echo(f"{G}OK{NC}")
        status_arrow(f"pg_dump    {D}\"{tools['pg_dump']}\"{NC}")
        status_arrow(f"pg_restore {D}\"{tools['pg_restore']}\"{NC}")
        status_arrow(f"psql       {D}\"{tools['psql']}\"{NC}")
    else:
        echo(f"{R}FAIL{NC}")
        all_ok = False

    # Local DB
    h, p, u, n, w = get_local_db(env)

    echo(f"  {C}💾{NC}  Database lokal ({h}:{p}/{n})... ", end="")
    psql = tools["psql"]
    if psql:
        out, _, rc = run_cmd(
            [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
            env={"PGPASSWORD": w},
            timeout=5,
        )
        if rc == 0 and out.strip() == "1":
            echo(f"{G}OK{NC}")
            size_out, _, _ = run_cmd(
                [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1) || ' MB';"],
                env={"PGPASSWORD": w},
                timeout=5,
            )
            status_arrow(f"Size: {size_out}")
        else:
            echo(f"{R}FAIL{NC}")
            all_ok = False
    else:
        echo(f"{R}FAIL{NC}")
        all_ok = False

    # Remote config
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    echo(f"  {C}☁️{NC}   Cloud config... ", end="")
    parsed = parse_remote_url(remote_url)
    if parsed:
        echo(f"{G}OK{NC}")
        # Connection test
        echo(f"  {C}☁️{NC}   Koneksi cloud... ", end="")
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        out, _, rc = run_cmd(
            [psql, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc", "SELECT 1;"],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=10,
        )
        if rc == 0 and out.strip() == "1":
            echo(f"{G}OK{NC}")
            size_out, _, _ = run_cmd(
                [psql, "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"], "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1) || ' MB';"],
                env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
                timeout=10,
            )
            status_arrow(f"Size: {size_out}")
        else:
            echo(f"{R}FAIL{NC}")
            all_ok = False
    else:
        echo(f"{Y}LEWAT{NC}")
        status_arrow("Set GAET_REMOTE_URL di ~/.gaet/.env")

    # Backup dir
    echo(f"  {C}📁{NC}  Direktori backup... ", end="")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if BACKUP_DIR.is_dir():
        echo(f"{G}OK{NC} {D}{BACKUP_DIR}{NC}")
        try:
            count = len(list(BACKUP_DIR.glob("*.dump")))
        except OSError:
            count = 0
        status_arrow(f"Backup tersimpan: {count}")
    else:
        echo(f"{R}FAIL{NC}")
        all_ok = False

    # Auto-backup
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
    echo(f"  {C}⏰{NC}  Auto-backup timer... ", end="")
    if scheduler_is_active(prefix):
        echo(f"{G}AKTIF{NC}")
    else:
        echo(f"{Y}tidak aktif{NC}")
        status_arrow("Aktifkan dengan: gaet push --auto")

    echo()
    if all_ok:
        echo(f"  {G}{ICON_OK}{NC}  {B}Semua cek berhasil!{NC}")
    else:
        echo(f"  {Y}{ICON_WARN}{NC}  {B}Ada yang gagal — perbaiki dulu sebelum backup.{NC}")
    return all_ok


def cmd_check(args: argparse.Namespace) -> None:
    """Validasi konfigurasi & koneksi."""
    env = load_env()
    tools = find_pg_tools(env)
    box_title(f"{NAME} check")
    cmd_check_inner(env, tools)


def cmd_status(args: argparse.Namespace) -> None:
    """Tampilkan status sinkronisasi."""
    env = load_env()
    tools = find_pg_tools(env)
    psql = tools["psql"]

    if args.json:
        # JSON mode — use Python status module or built-in logic
        try:
            from scripts.status import get_status  # type: ignore
            data = get_status()
        except ImportError:
            # Fallback: inline minimal status
            data = get_status_inline(env, tools)
        print(json.dumps(data))
        return

    # Terminal table output
    h, p, u, n, w = get_local_db(env)

    box_title(f"{NAME} status")

    # Last backup
    try:
        backups = sorted(BACKUP_DIR.glob("gaet_*.dump"), reverse=True)
        if backups:
            latest = backups[0]
            size_mb = latest.stat().st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            status_ok(f"Backup terakhir: {mtime} {D}({size_mb:.1f} MB){NC}")
        else:
            status_warn("Belum pernah backup")
    except OSError:
        status_warn("Belum pernah backup")

    try:
        count = len(list(BACKUP_DIR.glob("*.dump")))
    except OSError:
        count = 0
    status_arrow(f"Total backup: {count}")

    echo()

    # Get table list for detailed status
    tables_def = get_tables(env, tools)

    # Local DB - get row counts
    box_section("Database Lokal")
    local_rows = 0
    local_size = "?"
    if psql:
        out, _, rc = run_cmd(
            [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
             "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"],
            env={"PGPASSWORD": w},
            timeout=10,
        )
        if rc == 0 and out:
            try:
                local_rows = int(out.strip())
            except ValueError:
                pass
            echo(f"    {G}{ICON_OK}{NC}  {local_rows} tables")
            size_out, _, _ = run_cmd(
                [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1) || ' MB';"],
                env={"PGPASSWORD": w},
                timeout=5,
            )
            local_size = size_out
            status_arrow(f"Size: {size_out}")
        else:
            echo(f"    {Y}tidak tersedia{NC}")
    else:
        echo(f"    {Y}tidak tersedia{NC}")

    # Cloud
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)
    remote_rows = 0
    remote_size = "?"
    ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
    if parsed:
        echo()
        box_section("Cloud Database")
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        out, _, rc = run_cmd(
            [psql, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc",
             "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=10,
        )
        if rc == 0 and out:
            try:
                remote_rows = int(out.strip())
            except ValueError:
                pass
            echo(f"  {G}{ICON_OK}{NC}  {remote_rows} tables")
            size_out, _, _ = run_cmd(
                [psql, "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"], "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1) || ' MB';"],
                env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
                timeout=10,
            )
            remote_size = size_out
            status_arrow(f"Size: {size_out}")
        else:
            echo(f"  {Y}tidak terjangkau{NC}")

    # Sync status with colored table
    if tables_def and psql:
        echo()
        box_section("Sinkronisasi")

        # Get counts for each table
        rows = []
        colors = []
        synced_count = 0

        # Query all tables at once for efficiency
        if len(tables_def) > 0:
            try:
                union = " UNION ALL ".join(
                    f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}"
                    for t in tables_def
                )
                out, _, rc = run_cmd(
                    [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", union],
                    env={"PGPASSWORD": w}, timeout=30,
                )
                local_counts = {}
                if rc == 0:
                    for line in out.strip().split("\n"):
                        if "|" in line:
                            parts = line.split("|")
                            try:
                                local_counts[parts[0].strip()] = int(parts[1].strip())
                            except ValueError:
                                pass

                # Remote counts
                remote_counts = {}
                if parsed:
                    out_r, _, rc_r = run_cmd(
                        [psql, "-h", parsed["host"], "-p", parsed["port"],
                         "-U", parsed["user"], "-d", parsed["db"], "-tAc", union],
                        env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl}, timeout=30,
                    )
                    if rc_r == 0:
                        for line in out_r.strip().split("\n"):
                            if "|" in line:
                                parts = line.split("|")
                                try:
                                    remote_counts[parts[0].strip()] = int(parts[1].strip())
                                except ValueError:
                                    pass

                # Build rows
                for t in tables_def:
                    lo = local_counts.get(t, 0)
                    re = remote_counts.get(t, 0)
                    synced = lo == re
                    if synced:
                        synced_count += 1
                    status_icon = f"{G}✓{NC}" if synced else f"{R}✗{NC}"
                    rows.append(f"{t}|{lo}|{re}|{status_icon}")
                    colors.append(G if synced else R)

            except Exception as e:
                status_warn(f"Gagal query tables: {e}")

        # Show max 10 tables, with "more" indicator
        display_rows = rows[:10]
        display_colors = colors[:10]
        if len(rows) > 10:
            display_rows.append(f"... +{len(rows) - 10} lainnya|||")
            display_colors.append(D)

        draw_colored_table("Tabel:Lokal:Cloud:Status", display_rows, display_colors)

        # Sync summary
        total_tables = len(tables_def)
        sync_pct = (synced_count / total_tables * 100) if total_tables > 0 else 0
        echo()
        if sync_pct == 100:
            status_ok(f"Tersinkron: {synced_count}/{total_tables} tabel ({sync_pct:.0f}%)")
        else:
            status_warn(f"Tersinkron: {synced_count}/{total_tables} tabel ({sync_pct:.0f}%)")

    # Auto-backup
    echo()
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
    if scheduler_is_active(prefix):
        status_ok(f"Auto-backup aktif")
    else:
        status_warn("Auto-backup tidak aktif")


def get_status_inline(env: Dict[str, str], tools: Dict[str, str]) -> Dict[str, Any]:
    """
    Inline fallback for --json when scripts.status isn't importable.
    Matches the same schema as status.py's get_status().
    """
    psql = tools["psql"]
    h, p, u, n, w = get_local_db(env)

    tables_def = get_tables(env, tools)

    local_counts: Dict[str, int] = {}
    remote_counts: Dict[str, int] = {}
    error = None

    # Check local
    if psql and tables_def:
        try:
            union = " UNION ALL ".join(
                f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}"
                for t in tables_def
            )
            out, _, rc = run_cmd(
                [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", union],
                env={"PGPASSWORD": w},
                timeout=30,
            )
            if rc == 0:
                for line in out.strip().split("\n"):
                    if "|" in line:
                        parts = line.split("|")
                        try:
                            local_counts[parts[0].strip()] = int(parts[1].strip())
                        except ValueError:
                            pass
            else:
                error = f"Lokal DB tidak terjangkau ({h}:{p}/{n})"
        except Exception as e:
            error = str(e)
    else:
        error = "psql tidak ditemukan"

    # Check remote
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)
    if parsed and psql and not error:
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        union = " UNION ALL ".join(
            f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}"
            for t in tables_def
        )
        out, _, rc = run_cmd(
            [psql, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc", union],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=30,
        )
        if rc == 0:
            for line in out.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|")
                    try:
                        remote_counts[parts[0].strip()] = int(parts[1].strip())
                    except ValueError:
                        pass

    # Build table rows
    tables = []
    all_ok = True
    for t in tables_def:
        lo = local_counts.get(t, 0)
        re = remote_counts.get(t, 0)
        synced = lo == re
        tables.append({"table": t, "local": lo, "supabase": re, "ok": synced})
        if not synced:
            all_ok = False

    total_rows = sum(local_counts.values())

    # Backup info
    last_bak = None
    bak_count = 0
    try:
        files = sorted(BACKUP_DIR.glob("gaet_*.dump"), reverse=True)
        if files:
            bak_count = len(files)
            f = files[0]
            last_bak = {
                "file": f.name,
                "size": f.stat().st_size,
                "date": f.stat().st_mtime,
            }
    except OSError:
        pass

    # Scheduler status
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
    cron_active = scheduler_is_active(prefix)

    # DB sizes
    local_size = "?"
    if psql:
        out, _, _ = run_cmd(
            [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
             "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1)"],
            env={"PGPASSWORD": w}, timeout=5,
        )
        if out:
            local_size = out.strip() + " MB"

    remote_size = "?"
    if parsed and psql:
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        out, _, _ = run_cmd(
            [psql, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc",
             "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1)"],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=15,
        )
        if out:
            remote_size = out.strip() + " MB"

    result: Dict[str, Any] = {
        "total_rows": total_rows,
        "local_size": local_size,
        "remote_size": remote_size,
        "tables": tables,
        "synced": all_ok,
        "backup_count": bak_count,
        "last_backup": last_bak,
        "cron_active": cron_active,
    }
    if error:
        result["error"] = error
    return result


def cmd_push(args: argparse.Namespace) -> None:
    """Backup local → cloud."""
    acquire_lock()
    try:
        env = load_env()
        tools = find_pg_tools(env)
        check_tools(env)

        h, p, u, n, w = check_local_db(env)
        remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
        parsed = parse_remote_url(remote_url)
        if not parsed:
            die("GAET_REMOTE_URL belum diisi")

        log("🚀 Push: local → cloud")
        box_title("gaet push")
        psql = tools["psql"]
        pg_dump = tools["pg_dump"]
        pg_restore = tools["pg_restore"]

        # Step 1: Local dump
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        echo(f"  {C}📦{NC}  {B}Dumping database lokal...{NC}")
        backup_file = str(BACKUP_DIR / f"gaet_{timestamp}.dump")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        out, err, rc = run_cmd(
            [pg_dump, "-h", h, "-p", p, "-U", u, "-d", n,
             "--format=custom", "--compress=9", f"--file={backup_file}"],
            env={"PGPASSWORD": w},
            timeout=120,
        )
        if rc == 0 and Path(backup_file).is_file():
            size_mb = Path(backup_file).stat().st_size / (1024 * 1024)
            echo(f"    {G}{ICON_OK}{NC}  Dump tersimpan {D}({size_mb:.1f} MB){NC}")
            # Integrity check
            out2, err2, rc2 = run_cmd(
                [pg_restore, "--list", backup_file],
                timeout=30,
            )
            if rc2 != 0:
                Path(backup_file).unlink(missing_ok=True)
                die("Dump korup — backup dibatalkan")
        else:
            echo(f"    {R}{ICON_FAIL}{NC}  Dump gagal!")
            Path(backup_file).unlink(missing_ok=True)
            sys.exit(2)

        # Step 2: Restore to cloud with timeout
        echo(f"  {C}☁️{NC}   {B}Mensinkronkan ke cloud...{NC}")
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        out3, err3, rc3 = run_cmd(
            [pg_restore, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"],
             "--clean", "--if-exists", "--no-owner", "--no-acl",
             backup_file],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=120,
        )
        if rc3 == 0:
            echo(f"    {G}{ICON_OK}{NC}  Sinkronisasi selesai!")
        else:
            echo(f"    {Y}{ICON_WARN}{NC}  Sinkronisasi selesai (dengan peringatan)")

        # Step 3: Retention
        retention = get_env_int(env, "GAET_RETENTION_DAYS", DEF_RETENTION_DAYS)
        cutoff = time.time() - (retention * 86400)
        try:
            for f in BACKUP_DIR.glob("gaet_*.dump"):
                if f.stat().st_mtime < cutoff:
                    f.unlink()
        except OSError:
            pass

        # Summary
        size_mb = Path(backup_file).stat().st_size / (1024 * 1024) if Path(backup_file).is_file() else 0
        tables_synced = len(get_tables(env, tools)) if tools.get("psql") else 0
        print_push_summary(backup_file, size_mb, tables_synced)
        log("✅ Push complete")
    finally:
        release_lock()


def cmd_fetch(args: argparse.Namespace) -> None:
    """Restore cloud → local."""
    acquire_lock()
    try:
        env = load_env()
        check_tools(env)
        h, p, u, n, w = check_local_db(env)
        remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
        parsed = parse_remote_url(remote_url)
        if not parsed:
            die("GAET_REMOTE_URL belum diisi")

        tools = find_pg_tools(env)
        psql = tools["psql"]
        pg_dump = tools["pg_dump"]
        pg_restore = tools["pg_restore"]

        log("⬇️ Fetch: cloud → local")
        box_title("gaet fetch")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Step 1: Cloud dump
        echo(f"  {C}☁️{NC}   {B}Dumping database cloud...{NC}")
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        fetch_file = str(BACKUP_DIR / f"cloud_{timestamp}.dump")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        out, err, rc = run_cmd(
            [pg_dump, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"],
             "--format=custom", "--compress=9", f"--file={fetch_file}"],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=120,
        )
        if rc == 0 and Path(fetch_file).is_file():
            size_mb = Path(fetch_file).stat().st_size / (1024 * 1024)
            echo(f"    {G}{ICON_OK}{NC}  Dump cloud tersimpan {D}({size_mb:.1f} MB){NC}")
        else:
            echo(f"    {R}{ICON_FAIL}{NC}  Dump cloud gagal!")
            Path(fetch_file).unlink(missing_ok=True)
            sys.exit(2)

        # Step 2: Restore to local
        echo(f"  {C}💾{NC}  {B}Merestore ke database lokal...{NC}")
        # Terminate connections first
        run_cmd(
            [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
             "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
             f"WHERE datname='{n}' AND pid <> pg_backend_pid();"],
            env={"PGPASSWORD": w},
            timeout=10,
        )

        out3, err3, rc3 = run_cmd(
            [pg_restore, "-h", h, "-p", p, "-U", u, "-d", n,
             "--clean", "--if-exists", fetch_file],
            env={"PGPASSWORD": w},
            timeout=120,
        )
        if rc3 <= 1:
            echo(f"    {G}{ICON_OK}{NC}  Restore lokal selesai!")
        else:
            echo(f"    {Y}{ICON_WARN}{NC}  Restore selesai (dengan peringatan)")

        Path(fetch_file).unlink(missing_ok=True)
        echo()
        echo(f"  {G}{ICON_OK}{NC}  {B}Fetch selesai!{NC}")
        log("⬇️ Fetch complete")
    finally:
        release_lock()


def cmd_push_cron(env: Dict[str, str]) -> None:
    """Cron job execution (internal, no output to terminal)."""
    tools = find_pg_tools(env)
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)
    if not parsed:
        cronlog("❌ GAET_REMOTE_URL tidak dikonfigurasi")
        sys.exit(1)

    h, p, u, n, w = get_local_db(env)
    pg_dump = tools["pg_dump"]
    pg_restore = tools["pg_restore"]
    ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)

    cronlog("📦 [cron] Mulai auto-backup...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cron_file = str(BACKUP_DIR / f"cron_{timestamp}.dump")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    out, err, rc = run_cmd(
        [pg_dump, "-h", h, "-p", p, "-U", u, "-d", n,
         "--format=custom", "--compress=9", f"--file={cron_file}"],
        env={"PGPASSWORD": w},
        timeout=120,
    )
    if rc == 0 and Path(cron_file).is_file():
        out2, err2, rc2 = run_cmd(
            [pg_restore, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"],
             "--clean", "--if-exists", "--no-owner", "--no-acl", cron_file],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=120,
        )
        if rc2 == 0:
            size_mb = Path(cron_file).stat().st_size / (1024 * 1024)
            cronlog(f"✅ [cron] Backup sukses ({size_mb:.1f} MB)")
        else:
            cronlog("⚠️ [cron] Restore bermasalah")
    else:
        cronlog("❌ [cron] Dump lokal gagal!")

    Path(cron_file).unlink(missing_ok=True)


def cmd_auto_on(args: argparse.Namespace) -> None:
    """Aktifkan auto-backup."""
    env = load_env()
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
    interval = args.auto if args.auto else get_env_int(env, "GAET_AUTO_INTERVAL", DEF_AUTO_INTERVAL)

    if interval < 1 or interval > 23:
        die("Interval harus 1-23 jam.")

    box_title("Auto-backup")
    status_info(f"Mengaktifkan auto-backup setiap {interval} jam...")

    # Determine cli_path for the scheduler to call
    cli_path = str(Path(sys.argv[0]).resolve())

    if scheduler_enable(prefix, interval, cli_path):
        echo(f"    {G}{ICON_OK}{NC}  Auto-backup aktif!")
    else:
        status_fail("Gagal mengaktifkan auto-backup")
        echo(f"    {Y}{ICON_WARN}{NC}  Di sistem ini, aktifkan auto-backup secara manual.")


def cmd_stop_auto(args: argparse.Namespace) -> None:
    """Hentikan auto-backup dan/atau dashboard."""
    env = load_env()
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)

    if getattr(args, "dashboard", False):
        # Only stop dashboard
        status_info("Menghentikan dashboard...")
        if _svc_is_running():
            ok, msg = _svc_stop()
            if ok:
                status_ok("Dashboard dihentikan")
            else:
                status_warn(f"Gagal menghentikan dashboard: {msg}")
        else:
            status_warn("Dashboard tidak berjalan")
        return

    if getattr(args, "scheduler", False):
        # Only stop auto-backup
        status_info("Menghentikan auto-backup...")
        scheduler_disable(prefix)
        status_ok("Auto-backup dihentikan")
        return

    # Default: stop both
    status_info("Menghentikan auto-backup...")
    scheduler_disable(prefix)
    status_ok("Auto-backup dihentikan")

    if _svc_is_running():
        status_info("Menghentikan dashboard...")
        ok, msg = _svc_stop()
        if ok:
            status_ok("Dashboard dihentikan")
        else:
            status_warn(f"Gagal menghentikan dashboard: {msg}")


def cmd_log(args: argparse.Namespace) -> None:
    """Lihat log backup."""
    lines = args.lines or 30
    if not LOG_FILE.is_file():
        echo(f"  {Y}Belum ada log. Jalankan 'gaet push' dulu.{NC}")
        return

    with open(str(LOG_FILE), "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()

    total = len(all_lines)
    start = max(0, total - lines)

    box_title(f"{NAME} log")
    echo(f"  {D}{total} baris terakhir (menampilkan {lines}){NC}")
    echo()
    for line in all_lines[start:]:
        echo(f"  {D}│{NC} {line.rstrip()}")


def cmd_install(args: argparse.Namespace) -> None:
    """Jalankan installer universal."""
    try:
        from scripts.installer import run as installer_run
    except ImportError:
        print("  ⚠  Module scripts.installer tidak ditemukan.")
        print("     Jalankan dari folder root proyek gaet atau: pip install -e .")
        sys.exit(1)

    box_title(f"{NAME} install")
    rc = installer_run(
        yes=args.yes,
        skip_deps=getattr(args, "skip_deps", False),
        skip_build=getattr(args, "skip_build", False),
        skip_config=getattr(args, "skip_config", False),
        skip_service=getattr(args, "skip_service", False),
        interval=getattr(args, "interval", 0),
    )
    sys.exit(rc)


def cmd_update(args: argparse.Namespace) -> None:
    """Update gaet to latest version from GitHub."""
    box_title(f"{NAME} update")
    
    # Find project directory (where .git exists)
    script_dir = Path(sys.argv[0]).resolve().parent
    candidates = [
        script_dir.parent,  # installed from project root
        script_dir / "..",
        HOME / "Projects/gaet",
        HOME / ".local/share/gaet",
    ]
    
    project_dir = None
    for cand in candidates:
        if (cand / ".git").is_dir() and (cand / "gaet.py").is_file():
            project_dir = cand.resolve()
            break
    
    if not project_dir:
        die("Project directory tidak ditemukan. Jalankan dari folder gaet atau set GAET_PROJECT_DIR")
    
    echo(f"  {C}📁{NC}  Project: {D}{project_dir}{NC}")
    
    # Check if git is available
    git = shutil.which("git") or ""
    if not git:
        die("git tidak ditemukan. Install git dulu.")
    
    # Check if there are local changes
    out, _, rc = run_cmd([git, "-C", str(project_dir), "status", "--porcelain"], timeout=10)
    if out.strip():
        status_warn("Ada perubahan lokal di project")
        if not args.force:
            status_info("Backup perubahan dulu atau gunakan --force")
            echo(f"    {D}git -C {project_dir} stash{NC}")
            echo(f"    {D}gaet update --force{NC}")
            return
    
    # Fetch and pull
    echo()
    box_section("Fetching update")
    
    status_info("Fetching from remote...")
    out, err, rc = run_cmd([git, "-C", str(project_dir), "fetch", "origin"], timeout=30)
    if rc != 0:
        die(f"Fetch gagal: {err}")
    status_ok("Fetch selesai")
    
    # Check current vs remote
    out_local, _, _ = run_cmd([git, "-C", str(project_dir), "rev-parse", "HEAD"], timeout=5)
    out_remote, _, _ = run_cmd([git, "-C", str(project_dir), "rev-parse", "origin/master"], timeout=5)
    
    if out_local.strip() == out_remote.strip():
        status_ok("Sudah versi terbaru!")
        return
    
    # Show what will be updated
    out_log, _, _ = run_cmd([git, "-C", str(project_dir), "log", "--oneline", f"{out_local.strip()}..{out_remote.strip()}"], timeout=10)
    if out_log.strip():
        echo()
        box_section("Commits baru")
        for line in out_log.strip().split("\n")[:5]:
            status_arrow(line)
    
    # Pull
    echo()
    box_section("Pulling update")
    out, err, rc = run_cmd([git, "-C", str(project_dir), "pull", "origin", "master"], timeout=30)
    if rc != 0:
        die(f"Pull gagal: {err}")
    status_ok("Pull selesai")
    
    # Copy to install location
    echo()
    box_section("Installing")
    install_dir = Path.home() / ".local" / "bin"
    install_dir.mkdir(parents=True, exist_ok=True)
    
    src = project_dir / "gaet.py"
    dst = install_dir / "gaet"
    
    if src.is_file():
        shutil.copy2(str(src), str(dst))
        dst.chmod(0o755)
        status_ok(f"gaet → {dst}")
    
    # Copy scripts if exists
    scripts_src = project_dir / "scripts"
    if scripts_src.is_dir():
        scripts_dst = install_dir / "scripts"
        scripts_dst.mkdir(parents=True, exist_ok=True)
        for f in scripts_src.glob("*.py"):
            shutil.copy2(str(f), str(scripts_dst / f.name))
        status_ok(f"scripts → {scripts_dst}/")
    
    # Copy dashboard if exists and rebuild
    dashboard_src = project_dir / "dashboard"
    if dashboard_src.is_dir() and not args.skip_build:
        echo()
        box_section("Building dashboard")
        node = shutil.which("node")
        npm = shutil.which("npm")
        if node and npm:
            status_info("Installing dependencies...")
            run_cmd([npm, "install"], cwd=str(dashboard_src), timeout=120)
            status_info("Building...")
            run_cmd([npm, "run", "build"], cwd=str(dashboard_src), timeout=120)
            status_ok("Dashboard built")
            
            # Restart dashboard service if running
            try:
                from scripts.service_manager import service_is_running, service_start, service_stop
                if service_is_running():
                    status_info("Restarting dashboard service...")
                    service_stop()
                    time.sleep(1)
                    port = int(get_env_str(load_env(), "GAET_DASHBOARD_PORT", "9191"))
                    host = get_env_str(load_env(), "GAET_DASHBOARD_HOST", "0.0.0.0")
                    ok, msg = service_start(dashboard_dir=dashboard_src, port=port, host=host, foreground=False)
                    if ok:
                        status_ok("Dashboard service restarted")
                    else:
                        status_warn(f"Gagal restart: {msg}")
            except Exception:
                pass
        else:
            status_warn("Node.js/npm tidak ditemukan — skip dashboard build")
    
    # Show version
    echo()
    box_section("Version")
    r = run_cmd([sys.executable, str(dst), "--version"], timeout=5)
    status_ok(r[0].strip() if r[0] else "Updated")
    
    echo()
    status_ok("Update selesai!")


def cmd_serve(args: argparse.Namespace) -> None:
    """Jalankan dashboard web."""
    env = load_env()

    # Cari dashboard directory
    script_dir = Path(sys.argv[0]).resolve().parent
    candidates = [
        script_dir / "dashboard",
        script_dir.parent / "dashboard",
        HOME / "Projects/gaet/dashboard",
        GAET_DIR / "dashboard",
        HOME / ".local/share/gaet/dashboard",
    ]
    # Also check the original project location
    if "GAET_PROJECT_DIR" in os.environ:
        candidates.insert(0, Path(os.environ["GAET_PROJECT_DIR"]) / "dashboard")

    dashboard_dir = None
    for cand in candidates:
        if cand.is_dir() and (cand / "package.json").is_file():
            dashboard_dir = cand
            break

    if not dashboard_dir:
        die(
            "Dashboard tidak ditemukan. Pastikan kamu menjalankan gaet dari folder proyek.\n"
            "  Atau set GAET_PROJECT_DIR ke direktori proyek gaet."
        )

    port = int(get_env_str(env, "GAET_DASHBOARD_PORT", str(DEF_DASHBOARD_PORT)))
    host = get_env_str(env, "GAET_DASHBOARD_HOST", DEF_DASHBOARD_HOST)

    box_title(f"{NAME} serve")

    if not dashboard_dir:
        die("Dashboard directory not found")

    # Check if dashboard is built
    if not (dashboard_dir / ".next").is_dir():
        status_info("Dashboard belum dibuild. Building...")
        node = shutil.which("node")
        npm = shutil.which("npm")
        if node and npm:
            run_cmd([npm, "install"], cwd=str(dashboard_dir), timeout=120)
            run_cmd([npm, "run", "build"], cwd=str(dashboard_dir), timeout=120)
            status_ok("Dashboard built")
        else:
            die("Node.js/npm tidak ditemukan. Install dulu.")

    # Stop existing service first
    if _svc_is_running():
        status_info("Menghentikan service lama...")
        _svc_stop()
        time.sleep(1)

    # Start dashboard
    ok, msg = _svc_start(dashboard_dir=dashboard_dir, port=port, host=host, foreground=False)

    if ok:
        echo(f"\n  {G}{ICON_OK}{NC}  {B}Dashboard aktif!{NC}")
        echo(f"  {D}{ICON_ARROW}{NC}  http://localhost:{port}")
    else:
        status_fail(f"Dashboard gagal: {msg}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        prog=NAME,
        description=f"{NAME} — Database Backup & Sync CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Perintah:
              init              Setup wizard (config + test)
              push              Backup local → cloud
              fetch             Restore cloud → local
              status            Tampilkan status sinkronisasi
              status --json     Status dalam JSON
              check             Validasi konfigurasi & koneksi
              log               Lihat log backup
              push --auto[=N]   Aktifkan auto-backup tiap N jam
              stop              Hentikan auto-backup & dashboard
              serve             Jalankan dashboard web (background)
              install           Setup/install dependencies & konfigurasi
        """),
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"{NAME} v{VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Perintah")

    # init
    init_parser = subparsers.add_parser("init", help="Setup wizard interaktif")
    init_parser.add_argument(
        "preset", nargs="?", default=None,
        help="Preset database (contoh: hindsight)",
    )
    init_parser.add_argument(
        "--preset", dest="preset_flag", default=None,
        help="Preset database (contoh: --preset hindsight)",
    )

    # check
    subparsers.add_parser("check", help="Validasi konfigurasi & koneksi")

    # status
    status_parser = subparsers.add_parser("status", help="Tampilkan status sinkronisasi")
    status_parser.add_argument("--json", action="store_true", help="Output JSON")

    # push
    push_parser = subparsers.add_parser("push", help="Backup local → cloud")
    push_parser.add_argument(
        "--auto", nargs="?", const=0, type=int,
        help="Aktifkan auto-backup (opsional: interval jam, default 6)",
    )
    push_parser.add_argument("--cron", action="store_true", help="Jalankan dari scheduler (internal)")

    # fetch
    subparsers.add_parser("fetch", help="Restore cloud → local")

    # stop
    stop_parser = subparsers.add_parser("stop", help="Hentikan auto-backup dan/atau dashboard")
    stop_parser.add_argument("--scheduler", action="store_true", help="Hentikan auto-backup saja")
    stop_parser.add_argument("--dashboard", action="store_true", help="Hentikan dashboard saja")

    # log
    log_parser = subparsers.add_parser("log", help="Lihat log backup")
    log_parser.add_argument("lines", nargs="?", type=int, default=30, help="Jumlah baris (default 30)")

    # serve
    subparsers.add_parser("serve", help="Jalankan dashboard web")

    # install
    install_parser = subparsers.add_parser("install", help="Setup/install dependencies & konfigurasi")
    install_parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve")
    install_parser.add_argument("--skip-deps", action="store_true", help="Skip cek dependencies")
    install_parser.add_argument("--skip-build", action="store_true", help="Skip build dashboard")
    install_parser.add_argument("--skip-config", action="store_true", help="Skip config wizard")
    install_parser.add_argument("--skip-service", action="store_true", help="Skip setup service")
    install_parser.add_argument("--interval", type=int, default=0, help="Interval auto-backup (jam)")

    # update
    update_parser = subparsers.add_parser("update", help="Update gaet ke versi terbaru")
    update_parser.add_argument("--force", action="store_true", help="Force update (skip local changes check)")
    update_parser.add_argument("--skip-build", action="store_true", help="Skip build dashboard")

    args = parser.parse_args()

    # Default command: status
    if args.command is None:
        args.command = "status"

    # Set defaults for attributes that may not exist on main parser
    if not hasattr(args, "json"):
        args.json = False
    if not hasattr(args, "cron"):
        args.cron = False
    if not hasattr(args, "auto"):
        args.auto = None

    # ── auto mode (push --auto = enable scheduler) ──
    if args.command == "push":
        if args.cron:
            env = load_env()
            cmd_push_cron(env)
            return
        if args.auto is not None:
            # auto=N, or auto=0 (default meaning 6)
            if args.auto == 0:
                # --auto without value: use default
                pass
            cmd_auto_on(args)
            return
        cmd_push(args)
        return

    # ── Route commands ──
    command_map = {
        "init": lambda: cmd_init(args),
        "check": lambda: cmd_check(args),
        "status": lambda: cmd_status(args),
        "fetch": lambda: cmd_fetch(args),
        "stop": lambda: cmd_stop_auto(args),
        "log": lambda: cmd_log(args),
        "serve": lambda: cmd_serve(args),
        "install": lambda: cmd_install(args),
        "update": lambda: cmd_update(args),
    }

    cmd_func = command_map.get(args.command)
    if cmd_func:
        cmd_func()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        echo()
        status_info("Dibatalkan oleh user")
        sys.exit(0)
