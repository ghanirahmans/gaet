#!/usr/bin/env python3
"""
gaet — Database Backup & Sync CLI (Cross-Platform)
===================================================
Backup PostgreSQL lokal ke cloud (Supabase, Neon, RDS, VPS).

Usage:
  gaet init              Setup wizard
  gaet push              Local → cloud
  gaet fetch             Cloud → local
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
DEF_LOCAL_USER = "hindsight"
DEF_LOCAL_DB = "hindsight"
DEF_LOCAL_PASS = "hindsight"
DEF_RETENTION_DAYS = 7
DEF_AUTO_INTERVAL = 6
DEF_DASHBOARD_PORT = 9191
DEF_DASHBOARD_HOST = "0.0.0.0"
DEF_REMOTE_SSLMODE = "require"
DEF_SERVICE_PREFIX = "gaet"

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

def echo(msg: str = "") -> None:
    """Print with our formatting conventions."""
    print(msg)


def box_title(title: str) -> None:
    """Draw a boxed title."""
    width = 56
    pad = max(0, (width - len(title) - 2) // 2)
    rpad = width - len(title) - 2 - pad
    echo()
    echo(f"  {C}╭{NC}─{D}────────────────────────────────────────────────────{NC}─{C}╮{NC}")
    echo(f"  {C}│{NC}  {' ' * pad}{B}{title}{NC}{' ' * rpad}  {C}│{NC}")
    echo(f"  {C}╰{NC}─{D}────────────────────────────────────────────────────{NC}─{C}╯{NC}")
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
            parts.append(f"{D}─{NC}" + "─" * w + f"{D}─{NC}")
            if i < ncols - 1:
                parts.append(f"{D}{junction}{NC}")
            else:
                parts.append(f"{D}{right}{NC}")
        return "  " + "".join(parts)

    top = sep_row("╭", "┬", "╮", "┬")
    mid_sep = sep_row("├", "┼", "┤", "┼")
    bot = sep_row("╰", "┴", "╯", "┴")

    echo(top)
    # Header
    hdr = f"  {D}│{NC}"
    for i, h in enumerate(h_list):
        pad = widths[i] - len(h)
        hdr += f" {B}{h}{NC}{' ' * (pad + 1)}{D}│{NC}"
    echo(hdr)
    echo(mid_sep)

    for vals in data:
        row = f"  {D}│{NC}"
        for i, v in enumerate(vals):
            pad = widths[i] - len(v)
            row += f" {v}{' ' * (pad + 1)}{D}│{NC}"
        echo(row)

    echo(bot)


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
    h = get_env_str(env, "GAET_LOCAL_DB_HOST", DEF_LOCAL_HOST)
    p = get_env_str(env, "GAET_LOCAL_DB_PORT", DEF_LOCAL_PORT)
    u = get_env_str(env, "GAET_LOCAL_DB_USER", DEF_LOCAL_USER)
    n = get_env_str(env, "GAET_LOCAL_DB_NAME", DEF_LOCAL_DB)
    w = get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS)
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


# ═══════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

def cmd_init(args: argparse.Namespace) -> None:
    """Setup wizard interaktif."""
    env = load_env()
    box_title(f"{NAME} init")

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
        echo(f"  {D}Default: hindsight@127.0.0.1:5432/hindsight{NC}")
        h = get_env_str(env, "GAET_LOCAL_DB_HOST", DEF_LOCAL_HOST)
        p = get_env_str(env, "GAET_LOCAL_DB_PORT", DEF_LOCAL_PORT)
        u = get_env_str(env, "GAET_LOCAL_DB_USER", DEF_LOCAL_USER)
        n = get_env_str(env, "GAET_LOCAL_DB_NAME", DEF_LOCAL_DB)
        w = get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS)

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

        env_content = textwrap.dedent(f"""\
        # ══════════════════════════════════════════════════════════════
        # gaet — Konfigurasi
        # ══════════════════════════════════════════════════════════════
        # Dibuat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        # ══════════════════════════════════════════════════════════════

        # Database Lokal
        GAET_LOCAL_DB_HOST={h}
        GAET_LOCAL_DB_PORT={p}
        GAET_LOCAL_DB_USER={u}
        GAET_LOCAL_DB_NAME={n}
        GAET_LOCAL_DB_PASS={w}

        # Remote Database (Cloud)
        GAET_REMOTE_URL={remote_url}

        # Backup
        GAET_RETENTION_DAYS={ret}
        """)

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
    h = get_env_str(env, "GAET_LOCAL_DB_HOST", DEF_LOCAL_HOST)
    p = get_env_str(env, "GAET_LOCAL_DB_PORT", DEF_LOCAL_PORT)
    u = get_env_str(env, "GAET_LOCAL_DB_USER", DEF_LOCAL_USER)
    n = get_env_str(env, "GAET_LOCAL_DB_NAME", DEF_LOCAL_DB)
    w = get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS)

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
    h = get_env_str(env, "GAET_LOCAL_DB_HOST", DEF_LOCAL_HOST)
    p = get_env_str(env, "GAET_LOCAL_DB_PORT", DEF_LOCAL_PORT)
    u = get_env_str(env, "GAET_LOCAL_DB_USER", DEF_LOCAL_USER)
    n = get_env_str(env, "GAET_LOCAL_DB_NAME", DEF_LOCAL_DB)
    w = get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS)

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

    # Local DB
    box_section("Database Lokal")
    if psql:
        out, _, rc = run_cmd(
            [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
             "SELECT count(*) || ' memories' FROM memory_units;"],
            env={"PGPASSWORD": w},
            timeout=10,
        )
        if rc == 0 and out:
            echo(f"    {G}{ICON_OK}{NC}  {out}")
            size_out, _, _ = run_cmd(
                [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1) || ' MB';"],
                env={"PGPASSWORD": w},
                timeout=5,
            )
            status_arrow(f"Size: {size_out}")
        else:
            echo(f"    {Y}tidak tersedia{NC}")
    else:
        echo(f"    {Y}tidak tersedia{NC}")

    # Cloud
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)
    if parsed:
        echo()
        box_section("Cloud Database")
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        out, _, rc = run_cmd(
            [psql, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc",
             "SELECT count(*) || ' memories' FROM memory_units;"],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=10,
        )
        if rc == 0 and out:
            echo(f"  {G}{ICON_OK}{NC}  {out}")
        else:
            echo(f"  {Y}tidak terjangkau{NC}")

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
    h = get_env_str(env, "GAET_LOCAL_DB_HOST", DEF_LOCAL_HOST)
    p = get_env_str(env, "GAET_LOCAL_DB_PORT", DEF_LOCAL_PORT)
    u = get_env_str(env, "GAET_LOCAL_DB_USER", DEF_LOCAL_USER)
    n = get_env_str(env, "GAET_LOCAL_DB_NAME", DEF_LOCAL_DB)
    w = get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS)

    tables_def = [
        "memory_units", "banks", "chunks", "entities", "documents",
        "async_operations", "audit_log", "file_storage", "memory_links"
    ]

    local_counts: Dict[str, int] = {}
    remote_counts: Dict[str, int] = {}
    error = None

    # Check local
    if psql:
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

    memories = local_counts.get("memory_units", 0)

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
        "memories": memories,
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

        echo()
        echo(f"  {G}{ICON_OK}{NC}  {B}Push selesai!{NC}")
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

    h = get_env_str(env, "GAET_LOCAL_DB_HOST", DEF_LOCAL_HOST)
    p = get_env_str(env, "GAET_LOCAL_DB_PORT", DEF_LOCAL_PORT)
    u = get_env_str(env, "GAET_LOCAL_DB_USER", DEF_LOCAL_USER)
    n = get_env_str(env, "GAET_LOCAL_DB_NAME", DEF_LOCAL_DB)
    w = get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS)
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
    """Hentikan auto-backup."""
    env = load_env()
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)

    status_info("Menghentikan auto-backup...")
    scheduler_disable(prefix)
    status_ok("Auto-backup dihentikan")


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

    port = get_env_str(env, "GAET_DASHBOARD_PORT", str(DEF_DASHBOARD_PORT))
    host = get_env_str(env, "GAET_DASHBOARD_HOST", DEF_DASHBOARD_HOST)

    box_title(f"{NAME} serve")

    # Build jika belum
    dist_dir = dashboard_dir / ".next"
    if not dist_dir.is_dir():
        echo(f"  {C}📦{NC}  {B}Membangun dashboard...{NC}")
        if not (dashboard_dir / "node_modules").is_dir():
            run_cmd(["npm", "install", "--silent"], timeout=120, cwd=str(dashboard_dir))
        out, err, rc = run_cmd(["npm", "run", "build"], timeout=120, cwd=str(dashboard_dir))
        if rc == 0:
            echo(f"    {G}{ICON_OK}{NC}  Build selesai!")
        else:
            die(f"Build dashboard gagal. Coba manual: cd {dashboard_dir} && npm install && npm run build")

    if IS_LINUX:
        # systemd service (same as original)
        prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
        service_file = HOME / ".config" / "systemd" / "user" / f"{prefix}-dashboard.service"
        (HOME / ".config" / "systemd" / "user").mkdir(parents=True, exist_ok=True)

        node_path = shutil.which("node") or "node"
        service_file.write_text(textwrap.dedent(f"""\
        [Unit]
        Description={NAME} Dashboard (Next.js)
        After=network.target

        [Service]
        Type=simple
        Environment=PORT={port}
        Environment=HOST={host}
        ExecStart={node_path} {dashboard_dir / 'node_modules' / '.bin' / 'next'} start {dashboard_dir} --port {port}
        Restart=on-failure
        RestartSec=3
        WorkingDirectory={dashboard_dir}

        [Install]
        WantedBy=default.target
        """))

        # Enable linger
        run_cmd(["loginctl", "enable-linger"], timeout=5)

        run_cmd(["systemctl", "--user", "daemon-reload"], timeout=10)
        run_cmd(
            ["systemctl", "--user", "enable", "--now", f"{prefix}-dashboard.service"],
            timeout=10,
        )

        echo()
        out, _, rc = run_cmd(
            ["systemctl", "--user", "is-active", f"{prefix}-dashboard.service"],
            timeout=5,
        )
        if rc == 0 and out.strip() == "active":
            echo(f"  {G}{ICON_OK}{NC}  {B}Dashboard aktif!{NC}")
            echo(f"  {D}{ICON_ARROW}{NC}  http://localhost:{port}")
        else:
            status_fail("Gagal memulai dashboard")
    else:
        # macOS / Windows: run Next.js directly
        node_path = shutil.which("node") or "node"
        echo(f"  {C}🚀{NC}  {B}Menjalankan dashboard...{NC}")
        echo(f"  {D}{ICON_ARROW}{NC}  http://localhost:{port}")
        echo(f"  {D}{ICON_ARROW}{NC}  Tekan Ctrl+C untuk berhenti{NC}")
        echo()

        try:
            subprocess.run(
                [node_path, str(dashboard_dir / "node_modules" / ".bin" / "next"), "start",
                 str(dashboard_dir), "--port", str(port)],
                env={**os.environ, "PORT": port, "HOST": host},
                cwd=str(dashboard_dir),
            )
        except KeyboardInterrupt:
            echo()
            status_info("Dashboard dihentikan")


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
              stop              Hentikan auto-backup
              serve             Jalankan dashboard web
        """),
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"{NAME} v{VERSION}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Perintah")

    # init
    subparsers.add_parser("init", help="Setup wizard interaktif")

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
    subparsers.add_parser("stop", help="Hentikan auto-backup")

    # log
    log_parser = subparsers.add_parser("log", help="Lihat log backup")
    log_parser.add_argument("lines", nargs="?", type=int, default=30, help="Jumlah baris (default 30)")

    # serve
    subparsers.add_parser("serve", help="Jalankan dashboard web")

    args = parser.parse_args()

    # Default command: status
    if args.command is None:
        args.command = "status"

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
