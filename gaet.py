#!/usr/bin/env python3
"""
gaet — Database Backup & Sync CLI (Cross-Platform)
===================================================
Backup PostgreSQL lokal ke cloud (Supabase, Neon, RDS, VPS).

Usage:
  gaet init              Setup wizard
  gaet push              Local → cloud
  gaet push --dry-run    Simulasi push
  gaet fetch             Cloud → local
  gaet fetch --dry-run   Simulasi fetch
  gaet update            Update ke versi terbaru
  gaet --version         Show version
  gaet status            Tampilkan status
  gaet status --json     Status dalam JSON
  gaet check             Validasi konfigurasi
  gaet log               View backup log
  gaet log --filter      Filter log berdasarkan keyword
  gaet push --auto[=N]   Aktifkan auto-backup tiap N jam (default 6)
  gaet stop              Stop auto-backup
  gaet serve             Start web dashboard
  gaet --version         Show version
  gaet --help            Show help
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Version ──────────────────────────────────────────────────────────────
VERSION = "2.0.0"
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
    "hindsight-hermes": {
        "local_user": "hindsight",
        "local_db": "hindsight",
        "local_pass": "hindsight",
        "tables": "memory_units,banks,chunks,entities,documents,memory_links,unit_entities,entity_cooccurrences,observation_history,mental_models,mental_model_history,directives,async_operations,webhooks,file_storage,audit_log,llm_requests,graph_maintenance_queue",
        "description": "Hindsight memory database for Hermes Agent (Nous Research)",
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
    Password is optional. Returns dict or None.
    """
    if not url:
        return None
    m = re.match(
        r"postgres(?:ql)?://([^:]+)(?::([^@]*))?@([^:]+):(\d+)/([^?\s]+)",
        url,
    )
    if not m:
        return None
    return {
        "user": m.group(1),
        "pass": m.group(2) or "",
        "host": m.group(3),
        "port": m.group(4),
        "db": m.group(5),
    }


def mask_url_password(url: str) -> str:
    """Mask password in a PostgreSQL URL for safe display."""
    return re.sub(r"(postgres(?:ql)?://[^:]+):([^@]+)@", r"\1:****@", url)


def get_local_db(env: Dict[str, str]) -> Tuple[str, str, str, str, str]:
    """Parse GAET_LOCAL_URL or individual vars. Returns (host, port, user, db, passwd)."""
    url = get_env_str(env, "GAET_LOCAL_URL")
    if url:
        p = parse_remote_url(url)
        if p:
            passwd = p["pass"] or get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS)
            return p["host"], p["port"], p["user"], p["db"], passwd
    # Fallback: individual vars (backward compat)
    return (
        get_env_str(env, "GAET_LOCAL_DB_HOST", DEF_LOCAL_HOST),
        get_env_str(env, "GAET_LOCAL_DB_PORT", DEF_LOCAL_PORT),
        get_env_str(env, "GAET_LOCAL_DB_USER", DEF_LOCAL_USER),
        get_env_str(env, "GAET_LOCAL_DB_NAME", DEF_LOCAL_DB),
        get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS),
    )


def detect_local_pg(psql_path: str) -> List[Dict[str, str]]:
    """
    Auto-detect running PostgreSQL instances on this machine.
    Returns list of dicts with keys: host, port, user, databases.
    """
    results: List[Dict[str, str]] = []
    if not psql_path:
        return results

    # Common ports to scan
    ports_to_try = ["5432", "5433", "5434", "5435", "5436"]
    users_to_try = ["postgres", "root"]

    for port in ports_to_try:
        for user in users_to_try:
            # Try connecting with no password (common for local dev)
            out, _, rc = run_cmd(
                [psql_path, "-h", "127.0.0.1", "-p", port, "-U", user,
                 "-d", "postgres", "-tAc",
                 "SELECT current_database();"],
                env={"PGPASSWORD": ""},
                timeout=3,
            )
            if rc == 0 and out.strip():
                db = out.strip()
                # List all databases on this server
                dbs_out, _, _ = run_cmd(
                    [psql_path, "-h", "127.0.0.1", "-p", port, "-U", user,
                     "-d", "postgres", "-tAc",
                     "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"],
                    env={"PGPASSWORD": ""},
                    timeout=3,
                )
                databases = [d.strip() for d in dbs_out.strip().split("\n") if d.strip()] if dbs_out.strip() else [db]
                results.append({
                    "host": "127.0.0.1",
                    "port": port,
                    "user": user,
                    "databases": ", ".join(databases),
                    "default_db": db,
                })
                break  # Found this port, no need to try other users

    return results


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
    # Remove ANSI codes for visible length calculation
    clean_title = re.sub(r'\033\[[0-9;]*m', '', title)
    
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
            clean = re.sub(r'\033\[[0-9;]*m', '', v)
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
            clean = re.sub(r'\033\[[0-9;]*m', '', v)
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
    status_arrow(f"Local: {local_count} rows")
    status_arrow(f"Cloud: {remote_count} rows")


def print_push_summary(backup_file: str, size_mb: float, tables_synced: int) -> None:
    """Print summary after successful push."""
    echo()
    box_section("Push Selesai")
    status_ok(f"Backups stored: {backup_file} ({size_mb:.1f} MB)")
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


def pg_env(user: str, passwd: str, ssl_mode: Optional[str] = None) -> Dict[str, str]:
    """Create env dict using PGPASSFILE instead of PGPASSWORD (avoids /proc leak).
    Caller must call cleanup_pg_env(env) after use to delete the temp file."""
    env: Dict[str, str] = {}
    if not passwd:
        return env
    pgpass_content = f"*:*:*:{user}:{passwd}\n"
    try:
        fd, pgpass_path = tempfile.mkstemp(prefix=".pgpass_", suffix=".tmp")
        with os.fdopen(fd, 'w') as f:
            f.write(pgpass_content)
        os.chmod(pgpass_path, 0o600)
        env["PGPASSFILE"] = pgpass_path
    except OSError:
        env["PGPASSWORD"] = passwd
    if ssl_mode:
        env["PGSSLMODE"] = ssl_mode
    return env


def cleanup_pg_env(env: Dict[str, str]) -> None:
    """Delete the PGPASSFILE temp file if one was created."""
    pgpass = env.get("PGPASSFILE")
    if pgpass:
        try:
            os.unlink(pgpass)
        except OSError:
            pass


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

    env_dict = pg_env(u, w)
    out, _, rc = run_cmd(
        [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
        env=env_dict,
        timeout=5,
    )
    cleanup_pg_env(env_dict)
    if rc != 0 or out.strip() != "1":
        die(
            f"Cannot connect to local database ({h}:{p}/{n})\n"
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
        if IS_LINUX:
            user_systemd = HOME / ".config" / "systemd" / "user"
            user_systemd.mkdir(parents=True, exist_ok=True)
            svc = user_systemd / f"{prefix}-backup.service"
            svc.write_text(
                f"[Unit]\nDescription={NAME} backup\nAfter=network.target\n\n"
                f"[Service]\nType=oneshot\nExecStart=\"{cli_path}\" push --cron\n"
            )
            tim = user_systemd / f"{prefix}-backup.timer"
            tim.write_text(
                f"[Unit]\nDescription={NAME} periodic backup (every {interval}h)\n\n"
                f"[Timer]\nOnCalendar=*-*-* 00/{interval}:00:00\nPersistent=true\n\n"
                f"[Install]\nWantedBy=timers.target\n"
            )
            run_cmd(["systemctl", "--user", "daemon-reload"], timeout=10)
            _, _, rc = run_cmd(
                ["systemctl", "--user", "enable", "--now", f"{prefix}-backup.timer"],
                timeout=10,
            )
            return rc == 0
        elif IS_MACOS:
            from xml.sax.saxutils import escape as xml_escape
            plist = HOME / "Library" / "LaunchAgents" / f"{prefix}-backup.plist"
            plist.parent.mkdir(parents=True, exist_ok=True)
            plist.write_text(
                f'<?xml version="1.0"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                f'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0">'
                f"<dict><key>Label</key><string>{xml_escape(f'{prefix}-backup')}</string>"
                f"<key>ProgramArguments</key><array><string>{xml_escape(cli_path)}</string>"
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
    from scripts import service_manager as _svc_mod
    _svc_available = True
except ImportError:
    _svc_available = False


def _svc_start(dashboard_dir=None, port=9191, host="0.0.0.0", foreground=False):
    if _svc_available:
        return _svc_mod.service_start(dashboard_dir, port, host, foreground)
    print("  ⚠  service_manager module tidak tersedia. Jalankan dari folder proyek.")
    return False, "module not found"


def _svc_stop():
    if _svc_available:
        return _svc_mod.service_stop()
    return True, "module not loaded"


def _svc_is_running():
    if _svc_available:
        return _svc_mod.service_is_running()
    return False


def _svc_status():
    if _svc_available:
        return _svc_mod.service_status()
    return {"running": False, "platform": "unknown", "pid": None}


# ═══════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

def cmd_init(args: argparse.Namespace) -> None:
    """Interactive setup wizard."""
    env = load_env()
    box_title(f"{NAME} init")

    # Resolve preset
    preset_name = getattr(args, "preset_flag", None)
    if not preset_name:
        preset_raw = getattr(args, "preset", None)
        preset_name = "-".join(preset_raw) if preset_raw else None
    preset: Optional[Dict[str, str]] = None
    if preset_name:
        preset = PRESETS.get(preset_name.lower())
        if not preset:
            die(f"Preset '{preset_name}' not found. Available: {', '.join(PRESETS.keys())}")
        echo(f"  {C}📋{NC}  Preset: {preset.get('description', preset_name)}")

    # PG Tools
    box_section("PostgreSQL Tools")
    tools = find_pg_tools(env)
    for name in ("pg_dump", "pg_restore", "psql"):
        path = tools.get(name, "")
        if path:
            status_ok(f"{name:12} {D}\"{path}\"{NC}")
        else:
            status_fail(f"{name:12} not found")

    GAET_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Backup existing config before re-init
    if ENV_FILE.is_file():
        backup_path = GAET_DIR / f".env.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copy2(str(ENV_FILE), str(backup_path))
            status_info(f"Old config backed up to: {backup_path}")
        except OSError:
            pass

    if not ENV_FILE.is_file():
        echo()
        box_section("Local Database")

        # Auto-detect running PostgreSQL
        detected = []
        psql = tools.get("psql", "")
        if psql:
            status_info("Auto-detecting local PostgreSQL...")
            detected = detect_local_pg(psql)

        h, p, u, n, w = "", "", "", "", ""

        if preset:
            # Preset mode: show preset info, then select instance or use default
            u = preset.get("local_user", "postgres")
            n = preset.get("local_db", "postgres")
            w = preset.get("local_pass", "")
            echo(f"  {D}Preset '{preset_name}': user={u}, db={n}{NC}")
            echo()

            if detected:
                # Offer to select from detected instances when using preset
                for i, inst in enumerate(detected):
                    echo(f"  {C}{i + 1}{NC}  {inst['user']}@{inst['host']}:{inst['port']}")
                    echo(f"      {D}Databases: {inst['databases']}{NC}")
                echo(f"  {C}0{NC}  Use default (127.0.0.1:5432)")
                echo()

                choice = input(f"  Select instance [{len(detected)}]: ").strip() or str(len(detected))
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(detected):
                        inst = detected[idx]
                        h = inst["host"]
                        p = inst["port"]
                        echo(f"  {D}→ {u}@{h}:{p}/{n}{NC}")
                    elif choice == "0":
                        # Use default
                        h = "127.0.0.1"
                        p = "5432"
                        echo(f"  {D}→ {u}@{h}:{p}/{n}{NC}")
                    else:
                        raise ValueError()
                except (ValueError, IndexError):
                    h = "127.0.0.1"
                    p = "5432"
                    echo(f"  {D}→ {u}@{h}:{p}/{n}{NC}")
            else:
                # No detection — use default silently for preset
                h = "127.0.0.1"
                p = "5432"
                echo(f"  {D}→ {u}@{h}:{p}/{n} (default){NC}")

        elif detected:
            # Auto-detected instances (non-preset mode)
            echo()
            for i, inst in enumerate(detected):
                echo(f"  {C}{i + 1}{NC}  {inst['user']}@{inst['host']}:{inst['port']}")
                echo(f"      {D}Databases: {inst['databases']}{NC}")
            echo(f"  {C}0{NC}  Enter connection URL manually / Manual input")
            echo()

            choice = input(f"  Select [1]: ").strip() or "1"
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(detected):
                    inst = detected[idx]
                    h = inst["host"]
                    p = inst["port"]
                    u = inst["user"]
                    n = inst["default_db"]
                    w = ""
                    echo(f"  {D}→ {u}@{h}:{p}/{n}{NC}")
                else:
                    # Manual mode
                    h, p, u, n, w = _manual_db_input()
            except (ValueError, IndexError):
                h, p, u, n, w = _manual_db_input()
        else:
            # No detection — offer URL or manual
            echo(f"  {D}No PostgreSQL detected.{NC}")
            echo()
            echo(f"  {C}1{NC}  Paste connection URL")
            echo(f"  {C}2{NC}  Manual input")
            echo()

            choice = input(f"  Select [1]: ").strip() or "1"
            if choice == "1":
                h, p, u, n, w = _url_input()
            else:
                h, p, u, n, w = _manual_db_input()

        # Test connection immediately
        echo()
        if psql and h:
            echo(f"  {C}💾{NC}  Testing connection {u}@{h}:{p}/{n}... ", end="")
            out, _, rc = run_cmd(
                [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
                env={"PGPASSWORD": w},
                timeout=5,
            )
            if rc == 0 and out.strip() == "1":
                echo(f"{G}OK{NC}")
            else:
                echo(f"{Y}WARN{NC} — connection failed, but config is still saved")
                echo(f"  {D}Make sure PostgreSQL is running and password is correct{NC}")

        echo()
        box_section("Cloud / Remote Database (optional)")
        echo(f"  {D}Enter the target PostgreSQL connection string.{NC}")
        echo(f"  {D}Can be from Supabase, Neon, RDS, or your own VPS.{NC}")
        echo(f"  {D}Press Enter to skip.{NC}")
        remote_url = input("  GAET_REMOTE_URL: ").strip()

        echo()
        box_section("Backup")
        ret_inp = input(f"  Retention (days) [{DEF_RETENTION_DAYS}]: ").strip()
        ret = ret_inp or str(DEF_RETENTION_DAYS)

        # Tables line for preset (ACTIVE, not commented)
        tables_line = ""
        if preset and "tables" in preset:
            tables_line = f"GAET_TABLES={preset['tables']}"

        # Build local URL without password in the URL string
        if w:
            local_url = f"postgresql://{u}@{h}:{p}/{n}"
            pass_line = f"GAET_LOCAL_DB_PASS={w}"
        else:
            local_url = f"postgresql://{u}@{h}:{p}/{n}"
            pass_line = "# GAET_LOCAL_DB_PASS="

        env_content = textwrap.dedent(f"""\
        # ══════════════════════════════════════════════════════════════
        # gaet — Konfigurasi
        # ══════════════════════════════════════════════════════════════
        # Dibuat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        # ══════════════════════════════════════════════════════════════

        # Local Database
        GAET_LOCAL_URL={local_url}
        {pass_line}

        # Remote Database (Cloud)
        GAET_REMOTE_URL={remote_url}

        # Backup
        GAET_RETENTION_DAYS={ret}
        {tables_line}""")

        fd = os.open(str(ENV_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(env_content)
        echo()
        status_ok(f"Config saved to {ENV_FILE}")
    else:
        status_info(f"Config already exists: {ENV_FILE}")

    echo()
    box_section("Summary")
    env = load_env()  # reload
    tools = find_pg_tools(env)
    _print_summary(env, tools)


def _url_input() -> Tuple[str, str, str, str, str]:
    """Input via connection URL. Returns (host, port, user, db, passwd)."""
    echo(f"  {D}Format: postgresql://user:password@host:5432/dbname{NC}")
    url = input("  URL: ").strip()
    if url:
        parsed = parse_remote_url(url)
        if parsed:
            return parsed["host"], parsed["port"], parsed["user"], parsed["db"], parsed["pass"]
        else:
            echo(f"  {Y}URL tidak valid, fallback ke input manual{NC}")
    return _manual_db_input()


def _manual_db_input() -> Tuple[str, str, str, str, str]:
    """Manual field-by-field input with smart defaults."""
    h = input(f"  Host [127.0.0.1]: ").strip() or "127.0.0.1"
    p = input(f"  Port [5432]: ").strip() or "5432"
    u = input(f"  User [postgres]: ").strip() or "postgres"
    n = input(f"  Database [postgres]: ").strip() or "postgres"
    w = getpass.getpass(f"  Password []: ").strip()
    return h, p, u, n, w


def _print_summary(env: Dict[str, str], tools: Dict[str, str]) -> None:
    """Print config summary after init."""
    h, p, u, n, w = get_local_db(env)
    psql = tools.get("psql", "")

    # Local DB status
    echo(f"  {C}💾{NC}  Local:  {u}@{h}:{p}/{n}", end="")
    if psql:
        out, _, rc = run_cmd(
            [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
            env={"PGPASSWORD": w}, timeout=5,
        )
        if rc == 0 and out.strip() == "1":
            echo(f"  {G}connected{NC}")
        else:
            echo(f"  {Y}not connected yet{NC}")
    else:
        echo()

    # Remote status — mask password in display
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or ""
    if remote_url:
        display_url = mask_url_password(remote_url)
        echo(f"  {C}☁️{NC}   Remote: {display_url[:60]}{'...' if len(display_url) > 60 else ''}")
    else:
        echo(f"  {C}☁️{NC}   Remote: {Y}not configured{NC} (set GAET_REMOTE_URL later)")

    echo()
    echo(f"  {D}Config:{NC}  {ENV_FILE}")
    echo(f"  {D}Edit:{NC}    gaet init  (re-run to change)")
    echo(f"  {D}Check:{NC}   gaet check")
    echo(f"  {D}Push:{NC}    gaet push")
    echo()


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

    echo(f"  {C}💾{NC}  Local database ({h}:{p}/{n})... ", end="")
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
        status_arrow(f"Backups stored: {count}")
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
        status_arrow("Enable with: gaet push --auto")

    echo()
    if all_ok:
        echo(f"  {G}{ICON_OK}{NC}  {B}All checks passed!{NC}")
    else:
        echo(f"  {Y}{ICON_WARN}{NC}  {B}Some checks failed — fix before backup.{NC}")
    return all_ok


def cmd_check(args: argparse.Namespace) -> None:
    """Validate config & connections."""
    box_title(f"{NAME} check")
    env = load_env()
    tools = find_pg_tools(env)
    cmd_check_inner(env, tools)


def cmd_status(args: argparse.Namespace) -> None:
    """Show sync status."""
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
            status_ok(f"Last backup: {mtime} {D}({size_mb:.1f} MB){NC}")
        else:
            status_warn("Belum pernah backup")
    except OSError:
        status_warn("Belum pernah backup")

    try:
        count = len(list(BACKUP_DIR.glob("*.dump")))
    except OSError:
        count = 0
    status_arrow(f"Total backups: {count}")

    echo()

    # Get table list for detailed status
    tables_def = get_tables(env, tools)

    # Local DB - get row counts
    box_section("Local Database")
    local_rows = 0
    if psql:
        out, _, rc = run_cmd(
            [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
             "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"],
            env={"PGPASSWORD": w}, timeout=10,
        )
        if rc == 0 and out:
            try:
                local_rows = int(out.strip())
            except ValueError:
                pass
            echo(f"    {G}{ICON_OK}{NC}  {local_rows} tables")
            size_out, _, _ = run_cmd(
                [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1) || ' MB';"],
                env={"PGPASSWORD": w}, timeout=5,
            )
            status_arrow(f"Size: {size_out}")
        else:
            echo(f"    {Y}tidak tersedia{NC}")
    else:
        echo(f"    {Y}tidak tersedia{NC}")

    # Cloud
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)
    remote_rows = 0
    if parsed:
        echo()
        box_section("Cloud Database")
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        out, _, rc = run_cmd(
            [psql, "-w", "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc",
             "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl}, timeout=10,
        )
        if rc == 0 and out:
            try:
                remote_rows = int(out.strip())
            except ValueError:
                pass
            echo(f"  {G}{ICON_OK}{NC}  {remote_rows} tables")
            size_out, _, _ = run_cmd(
                [psql, "-w", "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"], "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1) || ' MB';"],
                env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl}, timeout=10,
            )
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
                    [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", union],
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
                        [psql, "-w", "-h", parsed["host"], "-p", parsed["port"],
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
                status_warn(f"Gagal query tabel: {e}")

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
        status_ok(f"Auto-backup active")
    else:
        status_warn("Auto-backup inactive")


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
                error = f"Local DB unreachable ({h}:{p}/{n})"
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
    dry_run = getattr(args, "dry_run", False)

    if dry_run:
        env = load_env()
        tools = find_pg_tools(env)
        h, p, u, n, w = get_local_db(env)
        remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
        parsed = parse_remote_url(remote_url)
        tables = get_tables(env, tools)
        box_title("gaet push --dry-run")
        
        box_section("Simulation Details")
        status_arrow(f"Source:  {u}@{h}:{p}/{n}")
        if parsed:
            status_arrow(f"Target:  {parsed['user']}@{parsed['host']}:{parsed['port']}/{parsed['db']}")
        else:
            status_warn("Target: Cloud not configured")
        status_arrow(f"Tables:  {len(tables)} tables")
        status_arrow(f"Backup:  ~/.gaet/backups/gaet_*.dump")
        retention = get_env_int(env, "GAET_RETENTION_DAYS", DEF_RETENTION_DAYS)
        status_arrow(f"Retention: {retention} days")
        
        echo()
        status_info("Dry-run mode: No changes will be made")
        echo()
        status_info("To proceed: gaet push")
        echo()
        return

    acquire_lock()
    try:
        env = load_env()
        tools = find_pg_tools(env)
        check_tools(env)

        h, p, u, n, w = check_local_db(env)
        remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
        parsed = parse_remote_url(remote_url)
        if not parsed:
            die(
                "GAET_REMOTE_URL belum dikonfigurasi.\n"
                f"  Jalankan: {C}gaet init{NC} lalu set remote URL\n"
                f"  Atau edit langsung: {D}{ENV_FILE}{NC}"
            )

        log("🚀 Push: local → cloud")
        box_title("gaet push")
        pg_dump = tools["pg_dump"]
        pg_restore = tools["pg_restore"]

        # Step 1: Local dump
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        echo(f"  {C}📦{NC}  {B}Dumping local database...{NC}")
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
            Path(backup_file).unlink(missing_ok=True)
            die("Dump gagal")

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
    dry_run = getattr(args, "dry_run", False)

    if dry_run:
        env = load_env()
        tools = find_pg_tools(env)
        h, p, u, n, w = get_local_db(env)
        remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
        parsed = parse_remote_url(remote_url)
        box_title("gaet fetch --dry-run")
        echo(f"  {C}☁️{NC}   {B}Simulasi fetch cloud → local{NC}")
        echo()
        cloud_info = f"Cloud:  {parsed['user']}@{parsed['host']}:{parsed['port']}/{parsed['db']}" if parsed else "Cloud: not configured"
        status_arrow(cloud_info)
        status_arrow(f"Local:  {u}@{h}:{p}/{n}")
        status_arrow(f"Aksi:   Dump cloud → restore ke local (overwrite)")
        echo()
        status_info("Dry-run: Tidak ada perubahan yang dilakukan.")
        return

    acquire_lock()
    try:
        env = load_env()
        check_tools(env)
        h, p, u, n, w = check_local_db(env)
        remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
        parsed = parse_remote_url(remote_url)
        if not parsed:
            die(
                "GAET_REMOTE_URL belum dikonfigurasi.\n"
                f"  Jalankan: {C}gaet init{NC} lalu set remote URL\n"
                f"  Atau edit langsung: {D}{ENV_FILE}{NC}"
            )

        tools = find_pg_tools(env)
        psql = tools["psql"]
        pg_dump = tools["pg_dump"]
        pg_restore = tools["pg_restore"]

        log("⬇️ Fetch: cloud → local")
        box_title("gaet fetch")

        # Confirmation before overwriting local DB
        echo(f"  {Y}⚠  PERINGATAN: Operasi ini akan OVERWRITE database lokal!{NC}")
        echo(f"  {D}Database: {u}@{h}:{p}/{n}{NC}")
        echo(f"  {D}Cloud:    {parsed['user']}@{parsed['host']}:{parsed['port']}/{parsed['db']}{NC}")
        echo()
        confirm = input(f"  Ketik 'yes' untuk melanjutkan: ").strip().lower()
        if confirm != "yes":
            echo(f"  {G}Dibatalkan.{NC}")
            return

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
            Path(fetch_file).unlink(missing_ok=True)
            die("Dump cloud gagal")

        # Step 2: Restore to local
        echo(f"  {C}💾{NC}  {B}Restoring to local database...{NC}")
        # Terminate connections first
        status_warn("Menutup koneksi aktif ke database lokal...")
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
            echo(f"    {G}{ICON_OK}{NC}  Local restore complete!")
        else:
            echo(f"    {Y}{ICON_WARN}{NC}  Restore selesai (dengan peringatan)")

        Path(fetch_file).unlink(missing_ok=True)
        echo()
        
        box_section("Summary")
        status_ok("Fetch complete - local database updated")
        status_arrow(f"Source: {parsed['user']}@{parsed['host']}:{parsed['port']}/{parsed['db']}")
        status_arrow(f"Target: {u}@{h}:{p}/{n}")
        
        echo()
        status_info("Next: gaet push  (to sync changes back to cloud)")
        echo()
        
        log("⬇️ Fetch complete")
    finally:
        release_lock()


def cmd_push_cron(env: Dict[str, str]) -> None:
    """Cron job execution - no terminal output (logs to file only).
    
    Called by scheduler with --cron flag. Output goes to ~/.gaet/backups/cron.log
    Check log with: gaet log | grep CRON
    """
    tools = find_pg_tools(env)
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)
    if not parsed:
        cronlog("❌ GAET_REMOTE_URL tidak dikonfigurasi")
        sys.exit(1)
    assert parsed is not None

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
        # Integrity check
        _, _, rc_check = run_cmd(
            [pg_restore, "--list", cron_file],
            timeout=30,
        )
        if rc_check != 0:
            Path(cron_file).unlink(missing_ok=True)
            cronlog("❌ [cron] Dump korup — backup dibatalkan")
            return

        out2, err2, rc2 = run_cmd(
            [pg_restore, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"],
             "--clean", "--if-exists", "--no-owner", "--no-acl", cron_file],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=120,
        )
        if rc2 == 0:
            size_mb = Path(cron_file).stat().st_size / (1024 * 1024)
            cronlog(f"✅ [cron] Backup success ({size_mb:.1f} MB)")
        else:
            cronlog("⚠️ [cron] Restore bermasalah")
    else:
        cronlog("❌ [cron] Local dump failed!")

    Path(cron_file).unlink(missing_ok=True)


def cmd_auto_on(args: argparse.Namespace) -> None:
    """Enable auto-backup."""
    env = load_env()
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
    interval = args.auto if args.auto is not None else get_env_int(env, "GAET_AUTO_INTERVAL", DEF_AUTO_INTERVAL)

    # Validate interval
    if interval is None or interval <= 0:
        die("Interval must be a positive number (hours).\n"
            f"  Example: {C}gaet push --auto=4{NC}  (auto-backup every 4 hours)")
    if interval > 24:
        die("Maximum interval is 24 hours.\n"
            f"  Example: {C}gaet push --auto=12{NC}  (auto-backup every 12 hours)")

    box_title("Auto-backup")
    status_info(f"Enabling auto-backup every {interval} hours (scheduler: {get_scheduler_name()})")

    # Determine cli_path for the scheduler to call
    cli_path = str(Path(sys.argv[0]).resolve())

    if scheduler_enable(prefix, interval, cli_path):
        status_ok(f"Auto-backup enabled every {interval} hours!")
        status_arrow(f"Interval: {interval} hours")
        status_arrow(f"Scheduler: {get_scheduler_name()}")
        echo()
    else:
        status_fail("Failed to enable auto-backup")
        status_warn("On this system, enable auto-backup manually.")
        echo()


def cmd_stop_auto(args: argparse.Namespace) -> None:
    """Stop auto-backup &/or dashboard."""
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
            status_warn("Dashboard tidak aktif")
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
    """View backup log."""
    lines = args.lines or 30
    filter_str = getattr(args, "filter", None) or ""
    since_str = getattr(args, "since", None) or ""
    if not LOG_FILE.is_file():
        echo(f"  {Y}Belum ada log. Jalankan 'gaet push' dulu.{NC}")
        return

    with open(str(LOG_FILE), "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()

    # Apply filters
    filtered = all_lines
    if filter_str:
        filtered = [l for l in filtered if filter_str.lower() in l.lower()]
    if since_str:
        filtered = [l for l in filtered if l.startswith(f"[{since_str}") or since_str in l]

    total = len(all_lines)
    total_filtered = len(filtered)
    start = max(0, total_filtered - lines)

    box_title(f"{NAME} log")
    echo(f"  {D}{total} total lines", end="")
    if filter_str or since_str:
        echo(f" ({total_filtered} filtered)", end="")
    echo(f" (showing {min(lines, total_filtered)}){NC}")
    echo()
    for line in filtered[start:]:
        echo(f"  {D}│{NC} {line.rstrip()}")


def cmd_get(args: argparse.Namespace) -> None:
    """Get environment variables from .env file.
    
    Usage:
      gaet get                 Show all variables
      gaet get KEY             Show specific key
      gaet get KEY1 KEY2 ...   Show multiple keys
    """
    env = load_env()
    
    if not env:
        status_warn("No .env file found or file is empty")
        return
    
    box_title(f"{NAME} get")
    
    # Determine which keys to show
    if hasattr(args, 'keys') and args.keys:
        keys_to_show = args.keys
    else:
        keys_to_show = sorted(env.keys())
    
    # Display variables
    found_count = 0
    not_found = []
    
    for key in keys_to_show:
        if key in env:
            value = env[key]
            # Mask sensitive values in display
            display_value = value
            if key.lower().endswith("password") or key.lower().endswith("url") or key == "GAET_REMOTE_URL":
                if len(value) > 20:
                    display_value = value[:10] + "***" + value[-5:]
                else:
                    display_value = "***"
            status_ok(f"{C}{key}{NC}  =  {display_value}")
            found_count += 1
        else:
            not_found.append(key)
    
    # Report not found keys
    if not_found:
        for key in not_found:
            status_warn(f"{key} not found")
    
    echo()
    if hasattr(args, 'keys') and args.keys:
        # User requested specific keys
        if found_count > 0:
            status_info(f"Showing {found_count} of {len(keys_to_show)} requested variables")
    else:
        # Show all
        status_info(f"Total {found_count} variables configured")
    echo()


def cmd_set(args: argparse.Namespace) -> None:
    """Set environment variables in .env file.
    
    Usage:
      gaet set KEY=value
      gaet set KEY1=value1 KEY2=value2
      gaet set GAET_REMOTE_URL=postgres://...
    """
    if not args.variables:
        die("Usage: gaet set KEY=value [KEY2=value2] ...")
    
    # Ensure .env directory exists
    GAET_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing env
    env = load_env()
    
    # Parse and update variables
    updates = {}
    for var in args.variables:
        if "=" not in var:
            die(f"Invalid format: {var}. Use KEY=value")
        key, value = var.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            die("Key cannot be empty")
        updates[key] = value
        env[key] = value
    
    # Save back to .env file
    lines = []
    existing_keys = set()
    
    # First pass: update existing lines
    if ENV_FILE.is_file():
        with open(str(ENV_FILE), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                original_line = line.rstrip("\n")
                # Check if this line contains a key we're updating
                m = re.match(r"^(?:export\s+)?([^=]+)=", original_line)
                if m:
                    key = m.group(1).strip()
                    existing_keys.add(key)
                    if key in updates:
                        lines.append(f"export {key}={updates[key]}\n")
                    else:
                        lines.append(original_line + "\n")
                else:
                    # Keep comments and empty lines
                    lines.append(original_line + "\n")
    
    # Second pass: add new keys
    for key, value in updates.items():
        if key not in existing_keys:
            lines.append(f"export {key}={value}\n")
    
    # Write back
    with open(str(ENV_FILE), "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    # Display result
    box_title(f"{NAME} set")
    for key, value in updates.items():
        # Mask sensitive values in display
        display_value = value
        if key.lower().endswith("password") or key.lower().endswith("url") or key == "GAET_REMOTE_URL":
            if len(value) > 20:
                display_value = value[:10] + "***" + value[-5:]
            else:
                display_value = "***"
        status_ok(f"{C}{key}{NC}  =  {display_value}")
    echo()
    status_info(f"Config saved: {ENV_FILE}")
    echo()


def cmd_install(args: argparse.Namespace) -> None:
    """Setup/install dependencies & config."""
    try:
        from scripts.installer import run as installer_run
    except ImportError:
        box_title(f"{NAME} install")
        status_fail("installer module not found")
        status_warn("Run from project root: pip install -e .")
        echo()
        sys.exit(1)

    box_title(f"{NAME} install")
    status_info("Starting installation process...")
    echo()
    
    rc = installer_run(
        yes=args.yes,
        skip_deps=getattr(args, "skip_deps", False),
        skip_build=getattr(args, "skip_build", False),
        skip_config=getattr(args, "skip_config", False),
        skip_service=getattr(args, "skip_service", False),
        interval=getattr(args, "interval", 0),
    )
    
    echo()
    if rc == 0:
        status_ok("Installation complete")
    else:
        status_fail(f"Installation failed (exit code: {rc})")
    echo()
    
    sys.exit(rc)


def cmd_uninstall(args: argparse.Namespace) -> None:
    """Uninstall gaet. Safe mode keeps config, purge removes everything."""
    purge = getattr(args, "purge", False)
    mode = "purge" if purge else "safe"
    
    box_title(f"{NAME} uninstall ({mode})")
    
    if purge:
        echo(f"  {Y}⚠  PURGE MODE: Akan menghapus gaet DAN semua config/backup{NC}")
        echo("")
        confirm = input(f"  Ketik 'yes' untuk konfirmasi: ").strip().lower()
        if confirm != "yes":
            echo(f"  {G}Dibatalkan.{NC}")
            return
    
    # ── 1. Stop services ──────────────────────────────────────────────
    echo(f"  {C}▸{NC} Menghentikan service...")
    
    # Stop scheduler
    try:
        if scheduler_is_active(DEF_SERVICE_PREFIX):
            scheduler_disable(DEF_SERVICE_PREFIX)
            echo(f"    {G}✓{NC} Scheduler dihentikan")
        else:
            echo(f"    {D}  Scheduler tidak aktif{NC}")
    except Exception as e:
        echo(f"    {Y}⚠  Scheduler error: {e}{NC}")
    
    # Stop dashboard
    try:
        if _svc_is_running():
            ok, msg = _svc_stop()
            if ok:
                echo(f"    {G}✓{NC} Dashboard dihentikan")
            else:
                echo(f"    {Y}⚠  Dashboard gagal dihentikan: {msg}{NC}")
        else:
            echo(f"    {D}  Dashboard tidak aktif{NC}")
    except Exception as e:
        echo(f"    {Y}⚠  Dashboard error: {e}{NC}")
    
    # ── 2. Disable services ──────────────────────────────────────────
    echo(f"  {C}▸{NC} Menonaktifkan service...")
    
    if IS_LINUX:
        # Disable systemd services
        try:
            prefix = DEF_SERVICE_PREFIX
            timer = f"{prefix}-backup.timer"
            svc = f"{prefix}-backup.service"
            
            run_cmd(["systemctl", "--user", "disable", "--now", timer], timeout=10)
            echo(f"    {G}✓{NC} Timer dinonaktifkan: {timer}")
            
            run_cmd(["systemctl", "--user", "disable", "--now", svc], timeout=10)
            echo(f"    {G}✓{NC} Service dinonaktifkan: {svc}")
        except Exception as e:
            echo(f"    {Y}⚠  Disable error: {e}{NC}")
    
    elif IS_MACOS:
        # Unload launchd plists
        try:
            plist_dir = Path.home() / "Library" / "LaunchAgents"
            for pattern in ["com.gaet.dashboard.plist", f"{DEF_SERVICE_PREFIX}-backup.plist"]:
                plist_path = plist_dir / pattern
                if plist_path.exists():
                    run_cmd(["launchctl", "unload", str(plist_path)], timeout=10)
                    plist_path.unlink()
                    echo(f"    {G}✓{NC} Unloaded: {pattern}")
        except Exception as e:
            echo(f"    {Y}⚠  Unload error: {e}{NC}")
    
    elif IS_WINDOWS:
        # Remove Task Scheduler tasks
        try:
            _, _, rc = run_cmd(["schtasks", "/Query", "/TN", f"{DEF_SERVICE_PREFIX}-backup"], timeout=10)
            if rc == 0:
                run_cmd(["schtasks", "/Delete", "/TN", f"{DEF_SERVICE_PREFIX}-backup", "/F"], timeout=10)
                echo(f"    {G}✓{NC} Task Scheduler dihapus")
        except Exception as e:
            echo(f"    {Y}⚠  Task removal error: {e}{NC}")
    
    # ── 3. Remove CLI and scripts ────────────────────────────────────
    echo(f"  {C}▸{NC} Menghapus gaet CLI...")
    
    bin_dir = Path.home() / ".local" / "bin"
    
    # Remove gaet CLI
    gaet_bin = bin_dir / "gaet"
    if gaet_bin.exists():
        gaet_bin.unlink()
        echo(f"    {G}✓{NC} Dihapus: {gaet_bin}")
    
    # Remove scripts directory
    scripts_dir = bin_dir / "scripts"
    if scripts_dir.exists():
        shutil.rmtree(scripts_dir)
        echo(f"    {G}✓{NC} Dihapus: {scripts_dir}")
    
    # ── 4. Purge mode: remove service files + config ────────────────
    if purge:
        echo(f"  {C}▸{NC} Menghapus service files...")
        
        prefix = DEF_SERVICE_PREFIX
        if IS_LINUX:
            # Remove systemd unit files
            systemd_dir = HOME / ".config" / "systemd" / "user"
            for pattern in [f"{prefix}-dashboard.service", f"{prefix}-backup.service",
                          f"{prefix}-backup.timer", "gaet-dashboard.service"]:
                unit_path = systemd_dir / pattern
                if unit_path.exists():
                    unit_path.unlink()
                    echo(f"    {G}✓{NC} Dihapus: {unit_path}")
            
            # Reload systemd daemon
            try:
                run_cmd(["systemctl", "--user", "daemon-reload"], timeout=10)
                echo(f"    {G}✓{NC} Systemd daemon reloaded")
            except Exception:
                pass
        
        elif IS_MACOS:
            # Plists already removed in step 2 (unload + unlink)
            echo(f"    {D}  Plist sudah dihapus{NC}")
        
        elif IS_WINDOWS:
            # Tasks already removed in step 2
            echo(f"    {D}  Task sudah dihapus{NC}")
        
        echo(f"  {C}▸{NC} Menghapus config dan data...")
        
        config_dir = GAET_DIR
        if config_dir.exists():
            shutil.rmtree(config_dir)
            echo(f"    {G}✓{NC} Dihapus: {config_dir}")
        else:
            echo(f"    {D}  Config directory tidak ditemukan{NC}")
    
    # ── 5. Summary ───────────────────────────────────────────────────
    echo("")
    echo(f"  {G}✓ Uninstall selesai ({mode} mode){NC}")
    echo("")
    
    if purge:
        echo(f"  Semua sudah dihapus.")
    else:
        echo(f"  Config disimpan di: {GAET_DIR}/")
        echo(f"  Untuk hapus config juga, jalankan: gaet uninstall --purge")
    
    echo(f"  Untuk reinstall: curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash")
    echo("")


GITHUB_API = "https://api.github.com/repos/ghanirahmans/gaet/contents"


def _gh_download(url: str, timeout: int = 15) -> bytes:
    """Download file from GitHub API, decoding base64 content."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    if isinstance(data, dict) and "content" in data:
        return base64.b64decode(data["content"])
    raise RuntimeError(f"GitHub API: {data.get('message', 'unknown error')}")


def _update_download(install_dir: Path, skip_build: bool = False) -> None:
    """Update gaet by downloading files from GitHub (for curl-install users)."""

    status_info("Downloading latest gaet from GitHub...")

    files = [
        ("gaet.py", "gaet"),
    ]
    script_files = ["__init__.py", "status.py", "scheduler.py", "service_manager.py", "installer.py"]

    for src, dst in files:
        url = f"{GITHUB_API}/{src}?ref=master"
        try:
            data = _gh_download(url)
            dest_path = install_dir / dst
            dest_path.write_bytes(data)
            dest_path.chmod(0o755)
            status_ok(f"{dst} → {dest_path}")
        except Exception as e:
            die(f"Failed to download {src}: {e}")

    # Download scripts
    scripts_dst = install_dir / "scripts"
    scripts_dst.mkdir(parents=True, exist_ok=True)
    for sf in script_files:
        url = f"{GITHUB_API}/scripts/{sf}?ref=master"
        try:
            data = _gh_download(url)
            (scripts_dst / sf).write_bytes(data)
            status_ok(f"scripts/{sf} → {scripts_dst}/")
        except Exception as e:
            status_warn(f"Failed to download scripts/{sf}: {e}")

    # Download and build dashboard
    if not skip_build:
        try:
            dashboard_dst = install_dir / "dashboard"
            dash_files = ["package.json", "next.config.ts", "tsconfig.json", "postcss.config.js",
                          "app/layout.tsx", "app/page.tsx", "app/globals.css",
                          "app/api/status/route.ts", "app/api/push/route.ts",
                          "app/api/fetch/route.ts", "app/api/stop/route.ts"]

            for df in dash_files:
                url = f"{GITHUB_API}/dashboard/{df}?ref=master"
                try:
                    data = _gh_download(url)
                    df_path = dashboard_dst / df
                    df_path.parent.mkdir(parents=True, exist_ok=True)
                    df_path.write_bytes(data)
                except Exception:
                    pass  # some files may not exist

            node = shutil.which("node")
            npm = shutil.which("npm")
            if node and npm and dashboard_dst.is_dir() and (dashboard_dst / "package.json").is_file():
                status_info("Building dashboard...")
                run_cmd([npm, "install"], cwd=str(dashboard_dst), timeout=120)
                run_cmd([npm, "run", "build"], cwd=str(dashboard_dst), timeout=120)
                status_ok("Dashboard built")
        except Exception as e:
            status_warn(f"Dashboard update skipped: {e}")

    echo()
    status_ok("Update complete!")


def cmd_update(args: argparse.Namespace) -> None:
    """Update gaet to latest version from GitHub."""
    box_title(f"{NAME} update")

    install_dir = Path.home() / ".local" / "bin"
    
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
        # No git repo found — use download fallback for curl-install users
        status_info("Mode: curl-install (download from GitHub)")
        _update_download(install_dir, skip_build=args.skip_build)
        return
    
    echo(f"  {C}📁{NC}  Project: {D}{project_dir}{NC}")
    
    # Check if git is available
    git = shutil.which("git") or ""
    if not git:
        die("git not found. Please install git first.")
    
    # Check if there are local changes
    out, _, rc = run_cmd([git, "-C", str(project_dir), "status", "--porcelain"], timeout=10)
    if out.strip():
        status_warn("Local changes detected in project")
        if not args.force:
            status_info("Commit changes first or use --force")
            echo(f"    {D}git -C {project_dir} stash{NC}")
            echo(f"    {D}gaet update --force{NC}")
            return
    
    # Fetch and pull
    echo()
    box_section("Fetching update")
    
    status_info("Fetching from remote...")
    out, err, rc = run_cmd([git, "-C", str(project_dir), "fetch", "origin"], timeout=30)
    if rc != 0:
        die(f"Fetch failed: {err}")
    status_ok("Fetch complete")
    
    # Check current vs remote
    out_local, _, _ = run_cmd([git, "-C", str(project_dir), "rev-parse", "HEAD"], timeout=5)
    out_remote, _, _ = run_cmd([git, "-C", str(project_dir), "rev-parse", "origin/master"], timeout=5)
    
    is_up_to_date = out_local.strip() == out_remote.strip()
    
    if not is_up_to_date:
        # Show what will be updated
        out_log, _, _ = run_cmd([git, "-C", str(project_dir), "log", "--oneline", f"{out_local.strip()}..{out_remote.strip()}"], timeout=10)
        if out_log.strip():
            echo()
            box_section("New commits")
            for line in out_log.strip().split("\n")[:5]:
                status_arrow(line)
        
        # Pull
        echo()
        box_section("Pulling update")
        out, err, rc = run_cmd([git, "-C", str(project_dir), "pull", "origin", "master"], timeout=30)
        if rc != 0:
            die(f"Pull failed: {err}")
        status_ok("Pull complete")
    else:
        status_ok("Already up to date!")
    
    # Always copy to install location (even if already up to date)
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
                        status_warn(f"Restart failed: {msg}")
            except Exception:
                pass
        else:
            status_warn("Node.js/npm not found — skipping dashboard build")
    
    # Show version
    echo()
    box_section("Version")
    try:
        r = run_cmd([sys.executable, str(dst), "--version"], timeout=5)
        if r[2] == 0 and r[0].strip():  # rc == 0 and stdout
            status_ok(f"Version: {r[0].strip()}")
        else:
            status_ok("Update complete - version check skipped")
    except Exception as e:
        status_warn(f"Version check failed: {e}")
        status_ok("Update complete")
    
    echo()
    status_ok("Update complete!")


def cmd_serve(args: argparse.Namespace) -> None:
    """Start web dashboard."""
    env = load_env()

    # Cari dashboard directory
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "dashboard",
        script_dir.parent / "dashboard",
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
        die("Dashboard tidak ditemukan")

    # Check if dashboard is built
    if not (dashboard_dir / ".next").is_dir():
        status_info("Dashboard belum di-build. Building...")
        node = shutil.which("node")
        npm = shutil.which("npm")
        if node and npm:
            run_cmd([npm, "install"], cwd=str(dashboard_dir), timeout=120)
            run_cmd([npm, "run", "build"], cwd=str(dashboard_dir), timeout=120)
            status_ok("Dashboard built")
        else:
            die("Node.js/npm tidak ditemukan. Install Node.js terlebih dahulu.")

    # Stop existing service first
    if _svc_is_running():
        status_info("Menghentikan service lama...")
        _svc_stop()
        time.sleep(1)

    # Start dashboard
    ok, msg = _svc_start(dashboard_dir=dashboard_dir, port=port, host=host, foreground=False)

    if ok:
        echo(f"\n  {G}{ICON_OK}{NC}  {B}Dashboard is running!{NC}")
        echo(f"  {D}{ICON_ARROW}{NC}  http://localhost:{port}")
        # Auto-open browser
        import webbrowser
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass
    else:
        status_fail(f"Dashboard failed: {msg}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """CLI entry point. Routes commands to their handlers."""
    parser = argparse.ArgumentParser(
        prog=NAME,
        description=f"{NAME} — Database Backup & Sync CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Commands:
              init              Setup wizard (config + test)
              get               Get environment variables
              set               Set environment variables
              push              Backup local → cloud
              push --dry-run    Simulate push without execution
              fetch             Restore cloud → local
              fetch --dry-run   Simulate fetch without execution
              status            Show sync status
              status --json     Output status as JSON
              check             Validate config & connections
              log               View backup log
              log --filter      Filter log by keyword
              push --auto[=N]   Enable auto-backup every N hours
              stop              Stop auto-backup & dashboard
              serve             Start web dashboard (background)
              install           Setup/install dependencies & config
        """),
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"{NAME} v{VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init
    init_parser = subparsers.add_parser("init", help="Interactive setup wizard")
    init_parser.add_argument(
        "preset", nargs="*", default=None,
        help="Preset database (contoh: hindsight, hindsight hermes)",
    )
    init_parser.add_argument(
        "--preset", dest="preset_flag", default=None,
        help="Preset database (contoh: --preset hindsight)",
    )

    # check
    subparsers.add_parser("check", help="Validate config & connections")

    # status
    status_parser = subparsers.add_parser("status", help="Show sync status")
    status_parser.add_argument("--json", action="store_true", help="Output JSON")

    # push
    push_parser = subparsers.add_parser("push", help="Backup local → cloud")
    push_parser.add_argument(
        "--auto", nargs="?", const=0, type=int,
        help="Aktifkan auto-backup (opsional: interval jam, default 6)",
    )
    push_parser.add_argument("--cron", action="store_true", help="Jalankan dari scheduler (internal)")
    push_parser.add_argument("--dry-run", action="store_true", help="Simulasi tanpa mengeksekusi")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Restore cloud → local")
    fetch_parser.add_argument("--dry-run", action="store_true", help="Simulasi tanpa mengeksekusi")

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop auto-backup &/or dashboard")
    stop_parser.add_argument("--scheduler", action="store_true", help="Stop auto-backup saja")
    stop_parser.add_argument("--dashboard", action="store_true", help="Hentikan dashboard saja")

    # log
    log_parser = subparsers.add_parser("log", help="View backup log")
    log_parser.add_argument("lines", nargs="?", type=int, default=30, help="Jumlah baris (default 30)")
    log_parser.add_argument("--filter", "-f", type=str, default="", help="Filter log berdasarkan keyword")
    log_parser.add_argument("--since", "-s", type=str, default="", help="Filter sejak tanggal (YYYY-MM-DD)")

    # serve
    subparsers.add_parser("serve", help="Start web dashboard")

    # get
    get_parser = subparsers.add_parser("get", help="Get environment variables")
    get_parser.add_argument(
        "keys", nargs="*", default=[],
        help="Keys to retrieve (if empty, shows all)"
    )

    # set
    set_parser = subparsers.add_parser("set", help="Set environment variables")
    set_parser.add_argument(
        "variables", nargs="+",
        help="Variables to set (format: KEY=value)"
    )

    # install
    install_parser = subparsers.add_parser("install", help="Setup/install dependencies & config")
    install_parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve")
    install_parser.add_argument("--skip-deps", action="store_true", help="Skip cek dependencies")
    install_parser.add_argument("--skip-build", action="store_true", help="Skip build dashboard")
    install_parser.add_argument("--skip-config", action="store_true", help="Skip config wizard")
    install_parser.add_argument("--skip-service", action="store_true", help="Skip setup service")
    install_parser.add_argument("--interval", type=int, default=0, help="Interval auto-backup (jam)")

    # update
    update_parser = subparsers.add_parser("update", help="Update to latest version")
    update_parser.add_argument("--force", action="store_true", help="Force update (skip local changes check)")
    update_parser.add_argument("--skip-build", action="store_true", help="Skip build dashboard")

    # uninstall
    uninstall_parser = subparsers.add_parser("uninstall", help="Remove gaet from system")
    uninstall_parser.add_argument("--purge", action="store_true", help="Remove everything including config and backups")

    args = parser.parse_args()

    # Default command: status
    if args.command is None:
        if not ENV_FILE.is_file():
            # No config yet — show friendly intro instead of failing
            box_title(f"{NAME}")
            echo(f"  {Y}Belum dikonfigurasi.{NC}")
            echo()
            echo(f"  Mulai dengan:")
            echo(f"    {C}gaet init{NC}          Setup wizard")
            echo()
            echo(f"  Atau paste URL langsung:")
            echo(f"    {C}gaet init{NC}          lalu pilih 'Paste connection URL'")
            echo()
            sys.exit(0)
        args.command = "status"

    # Set defaults for attributes that may not exist on main parser
    if not hasattr(args, "json"):
        args.json = False
    if not hasattr(args, "cron"):
        args.cron = False
    if not hasattr(args, "auto"):
        args.auto = None
    if not hasattr(args, "dry_run"):
        args.dry_run = False

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
        "get": lambda: cmd_get(args),
        "set": lambda: cmd_set(args),
        "install": lambda: cmd_install(args),
        "update": lambda: cmd_update(args),
        "uninstall": lambda: cmd_uninstall(args),
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
        status_info("Cancelled by user")
        sys.exit(0)
