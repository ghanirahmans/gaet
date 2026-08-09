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
import threading
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
DEF_DASHBOARD_HOST = "127.0.0.1"
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
# Honor NO_COLOR (https://no-color.org) and CLICOLOR/CLICOLOR_FORCE conventions.
_FORCE_COLOR = os.environ.get("CLICOLOR_FORCE") == "1"
_NO_COLOR = os.environ.get("NO_COLOR") is not None
_USE_COLOR = (sys.stdout.isatty() or _FORCE_COLOR) and not _NO_COLOR
if _USE_COLOR:
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


# ─── Global output-mode flags (set from argparse in main) ──────────────────
# QUIET: suppress non-essential human output (scripts/CI). Errors still go stderr.
# PLAIN: drop box-drawing / color so output is safe to pipe to grep/awk/jq.
QUIET = False
PLAIN = False

# ─── Semantic exit codes (cli-output-spec: 80-89 reserved for app errors) ──
# 0  = success
# 1  = generic failure
# 2  = usage / argparse error (handled by argparse)
# 80 = configuration error (missing/invalid .env)
# 81 = local database unreachable
# 82 = cloud/remote database unreachable
# 83 = lock held (another operation in progress)
# 84 = missing PostgreSQL tools (pg_dump/psql/...)
EXIT_CONFIG = 80
EXIT_LOCAL_DOWN = 81
EXIT_CLOUD_DOWN = 82
EXIT_LOCKED = 83
EXIT_TOOLS = 84


def set_output_modes(quiet: bool, plain: bool) -> None:
    """Configure global QUIET/PLAIN from parsed args."""
    global QUIET, PLAIN
    QUIET = bool(quiet)
    PLAIN = bool(plain)


def is_plain() -> bool:
    """True when --plain is active OR stdout is not a TTY (pipe/file)."""
    return PLAIN or not sys.stdout.isatty()


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

def _lock_is_stale() -> bool:
    """Return True if the lock directory is stale (owner process is dead).

    The lock directory contains a 'pid' file. If the pid no longer exists,
    the lock is stale and can be safely removed.
    """
    pid_file = LOCK_PATH / "pid"
    if not pid_file.is_file():
        # No pid file: legacy lock. Treat as stale if older than 1 hour.
        try:
            age = time.time() - LOCK_PATH.stat().st_mtime
            return age > 3600
        except OSError:
            return False
    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return False
    if pid <= 0:
        return False
    # Check if the process is alive (signal 0). ProcessLookupError = dead.
    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True
    except PermissionError:
        return False  # exists but owned by other user → not stale
    except OSError:
        return False


def _write_lock_pid() -> None:
    """Write the current PID into the lock directory."""
    try:
        (LOCK_PATH / "pid").write_text(str(os.getpid()))
    except OSError:
        pass


def acquire_lock() -> None:
    """Acquire exclusive lock via directory creation (atomic cross-platform).

    If the lock exists but is stale (owner crashed), remove it and retry.
    """
    try:
        LOCK_PATH.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        if _lock_is_stale():
            try:
                # Remove stale lock (dir + pid file) and retry
                import shutil as _sh

                _sh.rmtree(LOCK_PATH)
            except OSError:
                pass
            try:
                LOCK_PATH.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                die(f"gaet sedang berjalan (lock: {LOCK_PATH})", EXIT_LOCKED)
        else:
            die(f"gaet sedang berjalan (lock: {LOCK_PATH})", EXIT_LOCKED)
    _write_lock_pid()
    return


def release_lock() -> None:
    """Release lock."""
    try:
        pid_file = LOCK_PATH / "pid"
        if pid_file.is_file():
            pid_file.unlink(missing_ok=True)
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
    Parse postgresql://user:pw@host:port/db.
    Password is optional and may contain '@'. Returns dict or None.
    """
    if not url:
        return None
    # Normalize scheme: accept postgres:// and postgresql://
    m = re.match(r"^postgres(?:ql)?://(.*)$", url, re.IGNORECASE)
    if not m:
        return None
    rest = m.group(1)

    # Credentials vs host: split at the LAST '@' so passwords may contain '@'
    userinfo, sep, hostpart = rest.rpartition("@")
    if not sep:
        return None  # missing '@' → invalid
    if not userinfo or not hostpart:
        return None

    # user:pass — user cannot contain ':', password may
    if ":" in userinfo:
        user, _, passwd = userinfo.partition(":")
    else:
        user, passwd = userinfo, ""

    # host:port/db — split at the LAST ':' before the first '/'
    slash_idx = hostpart.find("/")
    if slash_idx == -1:
        return None
    hostport = hostpart[:slash_idx]
    db = hostpart[slash_idx + 1:].split("?", 1)[0]  # strip query string (e.g. ?sslmode=)
    if not db:
        return None
    if ":" not in hostport:
        return None
    host, _, port = hostport.rpartition(":")
    if not host or not port.isdigit():
        return None

    return {"user": user, "pass": passwd, "host": host, "port": port, "db": db}


def mask_url_password(url: str) -> str:
    """Mask password in a PostgreSQL URL for safe display."""
    return re.sub(r"(postgres(?:ql)?://[^:]+):([^@]+)@", r"\1:****@", url)


_TABLE_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_table_name(name: str) -> bool:
    """Return True if name is a safe PostgreSQL identifier."""
    return bool(_TABLE_NAME_RE.match(name))



def get_local_db(env: Dict[str, str]) -> Tuple[str, str, str, str, str]:
    """Parse local DB connection.

    Priority: individual vars (GAET_LOCAL_DB_*) > GAET_LOCAL_URL > defaults.
    This lets users override via `gaet set GAET_LOCAL_DB_HOST=...` without
    needing to clear GAET_LOCAL_URL first.
    """
    # Check individual vars first (highest priority)
    host = get_env_str(env, "GAET_LOCAL_DB_HOST")
    port = get_env_str(env, "GAET_LOCAL_DB_PORT")
    user = get_env_str(env, "GAET_LOCAL_DB_USER")
    db = get_env_str(env, "GAET_LOCAL_DB_NAME")
    passwd = get_env_str(env, "GAET_LOCAL_DB_PASS")

    # If any individual var is set, use them (with defaults for missing)
    if any(v for v in (host, port, user, db, passwd) if v):
        return (
            host or DEF_LOCAL_HOST,
            port or DEF_LOCAL_PORT,
            user or DEF_LOCAL_USER,
            db or DEF_LOCAL_DB,
            passwd or DEF_LOCAL_PASS,
        )

    # Fallback: GAET_LOCAL_URL
    url = get_env_str(env, "GAET_LOCAL_URL")
    if url:
        p = parse_remote_url(url)
        if p:
            passwd = p["pass"] or get_env_str(env, "GAET_LOCAL_DB_PASS", DEF_LOCAL_PASS)
            return p["host"], p["port"], p["user"], p["db"], passwd

    # Defaults
    return DEF_LOCAL_HOST, DEF_LOCAL_PORT, DEF_LOCAL_USER, DEF_LOCAL_DB, DEF_LOCAL_PASS


def detect_local_pg(psql_path: str) -> List[Dict[str, str]]:
    """
    Auto-detect running PostgreSQL instances on this machine.
    Returns list of dicts with keys: host, port, user, databases.
    Detects both TCP (127.0.0.1:port) and Unix socket connections.
    """
    results: List[Dict[str, str]] = []
    if not psql_path:
        return results

    # --- 1. Try Unix socket first (common on Linux) ---
    socket_paths = [
        "/run/postgresql/.s.PGSQL.5432",
        "/var/run/postgresql/.s.PGSQL.5432",
        "/tmp/.s.PGSQL.5432",
    ]
    for sock in socket_paths:
        if os.path.exists(sock):
            # Try common users
            for user in ["postgres", "root", os.getlogin()]:
                out, _, rc = run_cmd(
                    [psql_path, "-h", os.path.dirname(sock), "-p", "5432", "-U", user,
                     "-d", "postgres", "-tAc", "SELECT current_database();"],
                    env={"PGPASSWORD": ""}, timeout=3,
                )
                if rc == 0 and out.strip():
                    db = out.strip()
                    # List all databases on this server
                    dbs_out, _, _ = run_cmd(
                        [psql_path, "-h", os.path.dirname(sock), "-p", "5432", "-U", user,
                         "-d", "postgres", "-tAc",
                         "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"],
                        env={"PGPASSWORD": ""}, timeout=3,
                    )
                    databases = [d.strip() for d in dbs_out.strip().split("\n") if d.strip()] if dbs_out.strip() else [db]
                    results.append({
                        "host": os.path.dirname(sock),  # socket directory
                        "port": "5432",
                        "user": user,
                        "databases": ", ".join(databases),
                        "default_db": db,
                    })
                    break  # Found on this socket
            if results:
                break  # Found at least one socket

    # --- 2. Try TCP ports (fallback) ---
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
                    env={"PGPASSWORD": ""}, timeout=3,
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
    """Print with our formatting conventions.

    Respects --quiet: when QUIET is set, non-essential output is suppressed
    (stdout stays silent for humans, but data/JSON should be printed directly
    with print()/json.dumps, not via echo()).
    """
    if QUIET:
        return
    print(msg, end=end, flush=True)


def safe_input(prompt: str, default: str = "") -> str:
    """input() that degrades gracefully when there is no TTY (pipes, cron, SSH).

    When stdin is not a terminal, we cannot prompt interactively. Instead of
    crashing with EOFError we print the prompt + chosen default and return it,
    so `gaet init` and friends still run in non-interactive contexts.
    """
    if not sys.stdin.isatty():
        echo(f"{prompt}{default}")
        return default
    try:
        return input(prompt)
    except EOFError:
        echo()
        return default


def safe_getpass(prompt: str) -> str:
    """getpass() that degrades to safe_input when there is no TTY."""
    if not sys.stdin.isatty():
        return safe_input(prompt).strip()
    try:
        return getpass.getpass(prompt).strip()
    except EOFError:
        return ""


# Canonical command names for typo suggestion (clig.dev §Errors: "Did you mean?")
_SUGGEST_NAMES = [
    "init", "check", "status", "push", "fetch", "stop", "log",
    "serve", "get", "set", "install", "update", "uninstall", "help",
    "completion", "doctor",
]


def suggest_command(typed: str) -> None:
    """Print a 'Did you mean X?' hint for an unknown command (Levenshtein)."""
    import difflib
    matches = difflib.get_close_matches(typed, _SUGGEST_NAMES, n=1, cutoff=0.5)
    if matches:
        echo(f"  {D}Did you mean:{NC} {C}gaet {matches[0]}{NC} ?")
    else:
        echo(f"  {D}Run 'gaet --help' to see all commands.{NC}")



class Spinner:
    """Indeterminate progress spinner for long-running operations.

    Used during pg_dump/pg_restore (which can take 10s+) so the user does not
    think the CLI has hung. Auto-disabled under --quiet, --plain, or when
    stdout is not a TTY. Stops cleanly via stop().
    """

    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, label: str = ""):
        self.label = label
        self._active = False
        self._thread = None

    def _run(self) -> None:
        i = 0
        while self._active:
            frame = self._FRAMES[i % len(self._FRAMES)]
            sys.stdout.write(f"\r  {C}{frame}{NC} {self.label} ")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

    def start(self) -> "Spinner":
        if QUIET or PLAIN or not sys.stdout.isatty():
            return self  # no-op when not interactive
        self._active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._thread is not None:
            self._active = False
            self._thread.join()
            sys.stdout.write("\r\033[K")  # clear the spinner line
            sys.stdout.flush()


def emit_help_json(topic: Optional[str]) -> None:
    """Output the CLI command schema as JSON (agent-friendly introspection).

    `gaet help --json` lists every command; `gaet help <cmd> --json` lists
    that command's flags. Mirrors the cli-output-spec `help-json` convention.
    """
    if topic and topic in subparsers.choices:
        sub = subparsers.choices[topic]
        # Resolve help text from the parent _SubParsersAction choice actions
        topic_help = ""
        for ca in subparsers._choices_actions:
            if ca.dest == topic:
                topic_help = ca.help or ""
                break
        flags = []
        for a in sub._actions:
            if not a.option_strings:
                if a.dest != "help":
                    flags.append({"name": a.dest, "positional": True,
                                  "help": a.help or ""})
                continue
            if a.dest == "help":
                continue
            flags.append({
                "names": a.option_strings,
                "help": a.help or "",
                "type": "flag" if isinstance(a, argparse._StoreTrueAction) else (a.type.__name__ if a.type else "value"),
                "default": a.default if a.default is not argparse.SUPPRESS else None,
            })
        schema = {
            "command": topic,
            "help": topic_help,
            "flags": flags,
        }
    else:
        commands = []
        for action in subparsers._choices_actions:
            name = action.dest
            if name == "help":
                continue
            commands.append({"name": name, "help": action.help or ""})
        commands.sort(key=lambda c: c["name"])
        schema = {
            "program": NAME,
            "version": VERSION,
            "commands": commands,
            "global_flags": [
                {"names": ["-q", "--quiet"], "help": "Suppress non-essential output"},
                {"names": ["--plain"], "help": "Decoration-free, pipe-safe output"},
                {"names": ["--json"], "help": "Structured JSON output (check/push/fetch/help)"},
            ],
        }
    print(json.dumps(schema, indent=2))


def box_title(title: str) -> None:
    """Draw a boxed title with Unicode double-line box characters.

    In --plain mode (or when piped), print a simple heading instead so the
    output stays grep/awk/jq-safe.
    """
    if is_plain():
        echo(f"== {title} ==")
        return
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
    if is_plain():
        echo(f"-- {title} --")
        return
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

    In --plain mode (or piped), emit TSV instead of a boxed table.
    """
    h_list = headers.split(":")
    ncols = len(h_list)

    if is_plain():
        clean_cells = lambda v: re.sub(r'\033\[[0-9;]*m', '', v)
        echo("\t".join(h_list))
        for row in rows:
            vals = row.split("|")
            vals = vals + [""] * (ncols - len(vals))
            echo("\t".join(clean_cells(v) for v in vals))
        return

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

    In --plain mode (or piped), emit TSV (tab-separated, one record per line,
    no color/box) so the output composes with grep/awk/jq.
    """
    h_list = headers.split(":")
    ncols = len(h_list)

    if is_plain():
        # Strip any embedded ANSI from cells, then emit TSV
        clean_cells = lambda v: re.sub(r'\033\[[0-9;]*m', '', v)
        echo("\t".join(h_list))
        for row in rows:
            vals = row.split("|")
            vals = vals + [""] * (ncols - len(vals))
            echo("\t".join(clean_cells(v) for v in vals))
        return

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
        die("psql tidak ditemukan", EXIT_TOOLS)

    env_dict = pg_env(u, w)
    out, _, rc = run_cmd(
        [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
        env=env_dict,
        timeout=5,
    )
    cleanup_pg_env(env_dict)
    if rc != 0 or out.strip() != "1":
        # Friendly, actionable guidance for new users
        hint = ""
        if not ENV_FILE.is_file():
            hint = (
                f"\n  {Y}Belum ada konfigurasi.{NC}\n"
                f"  Jalankan: {C}gaet init{NC}  (setup wizard — panduan langkah demi langkah)\n"
                f"  Atau set manual: {C}gaet set GAET_LOCAL_URL=postgresql://user:pw@host:5432/db{NC}"
            )
        else:
            hint = (
                f"\n  {Y}Pastikan:{NC}\n"
                f"    1. PostgreSQL berjalan di {h}:{p}\n"
                f"    2. user '{u}' & password benar\n"
                f"    3. database '{n}' ada\n"
                f"  Edit dengan: {C}gaet init{NC}  atau  {C}gaet set GAET_LOCAL_URL=...{NC}\n"
                f"  File config: {D}{ENV_FILE}{NC}"
            )
        die(
            f"Cannot connect to local database ({h}:{p}/{n})\n"
            f"  {Y}Periksa konfigurasi database.{NC}{hint}",
            EXIT_LOCAL_DOWN,
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


# ════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ════════════════════════════════════════════════════════════════════════════

def cmd_completion(args: argparse.Namespace) -> None:
    """Generate shell completions."""
    shell = args.shell
    script_dir = Path(__file__).resolve().parent / "completions"
    shell_files = {"bash": "gaet.bash", "zsh": "gaet.zsh", "fish": "gaet.fish"}

    if shell:
        if shell not in shell_files:
            die(f"Unsupported shell: {shell}. Use: {', '.join(shell_files.keys())}")
        comp_file = script_dir / shell_files[shell]
        if comp_file.is_file():
            echo(comp_file.read_text(encoding="utf-8"))
        else:
            die(f"Completion file not found: {comp_file}")
    else:
        detected_shell = os.environ.get("SHELL", "")
        if "bash" in detected_shell:
            comp_file = script_dir / shell_files["bash"]
        elif "zsh" in detected_shell:
            comp_file = script_dir / shell_files["zsh"]
        elif "fish" in detected_shell:
            comp_file = script_dir / shell_files["fish"]
        else:
            echo(f"  {Y}Cannot auto-detect shell.{NC}")
            echo(f"  Usage: gaet completion --shell bash")
            return

        if comp_file.is_file():
            shell_name = comp_file.stem.split('.')[1]
            echo(f"  {C}Shell completions for {shell_name}:{NC}")
            echo()
            echo(f"  Install with:")
            if "bash" in detected_shell:
                echo(f"    gaet completion --shell bash > ~/.bash_completion.d/gaet")
            elif "zsh" in detected_shell:
                echo(f"    gaet completion --shell zsh > ~/.zsh/completions/_gaet")
            elif "fish" in detected_shell:
                echo(f"    gaet completion --shell fish > ~/.config/fish/completions/gaet.fish")
            echo()
            echo(f"  Or source directly:")
            echo(f"    source <(gaet completion --shell {shell_name})")


def cmd_doctor(args: argparse.Namespace) -> None:
    """Check gaet health: config, DB connections, tools, recent backups."""
    box_title(f"{NAME} doctor")
    issues = 0

    # 1. Config
    box_section("Config")
    env = load_env()
    if ENV_FILE.is_file():
        status_ok(f"Config file: {ENV_FILE}")
    else:
        echo(f"    {R}{ICON_FAIL}{NC} Config file not found")
        echo(f"    {D}Run: gaet init{NC}")
        issues += 1

    # 2. PostgreSQL tools
    box_section("PostgreSQL Tools")
    tools = find_pg_tools(env)
    all_tools = True
    for name in ("pg_dump", "pg_restore", "psql"):
        if tools.get(name):
            status_ok(f"{name} found")
        else:
            echo(f"    {R}{ICON_FAIL}{NC} {name} not found")
            all_tools = False
            issues += 1
    if not all_tools:
        echo(f"    {D}Install PostgreSQL client tools: apt install postgresql-client{NC}")

    # 3. Local DB connection
    box_section("Local Database")
    h, p, u, n, w = get_local_db(env)
    psql = tools.get("psql", "")
    if psql and h:
        echo(f"    {C}Testing {u}@{h}:{p}/{n}...{NC} ", end="")
        out, _, rc = run_cmd(
            [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
            env={"PGPASSWORD": w}, timeout=5,
        )
        if rc == 0 and out.strip() == "1":
            echo(f"{G}OK{NC}")
            size_out, _, _ = run_cmd(
                [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1)||' MB';"],
                env={"PGPASSWORD": w}, timeout=5,
            )
            if size_out.strip():
                status_arrow(f"Size: {size_out.strip()}")
        else:
            echo(f"{R}FAIL{NC}")
            echo(f"    {D}Check PostgreSQL is running and credentials are correct{NC}")
            issues += 1
    else:
        echo(f"    {R}{ICON_FAIL}{NC} Cannot test (psql not found or no host)")
        issues += 1

    # 4. Cloud DB connection
    box_section("Cloud Database")
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)
    if parsed:
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        echo(f"    {C}Testing cloud connection...{NC} ", end="")
        out, _, rc = run_cmd(
            [psql, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc", "SELECT 1;"],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl}, timeout=10,
        )
        if rc == 0 and out.strip() == "1":
            echo(f"{G}OK{NC}")
            size_out, _, _ = run_cmd(
                [psql, "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"], "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1)||' MB';"],
                env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl}, timeout=10,
            )
            if size_out.strip():
                status_arrow(f"Size: {size_out.strip()}")
        else:
            echo(f"{R}FAIL{NC}")
            echo(f"    {D}Check GAET_REMOTE_URL and cloud database status{NC}")
            issues += 1
    else:
        echo(f"    {Y}Not configured{NC}")
        status_arrow("Set GAET_REMOTE_URL to enable cloud backup")

    # 5. Recent backups
    box_section("Backups")
    try:
        backups = sorted(BACKUP_DIR.glob("gaet_*.dump"), reverse=True)
        if backups:
            newest = backups[0]
            age_days = (time.time() - newest.stat().st_mtime) / 86400
            total_size = sum(f.stat().st_size for f in backups) / (1024 * 1024)
            echo(f"    {G}Found {len(backups)} backup(s){NC}")
            status_arrow(f"Newest: {newest.name} ({age_days:.0f} days ago)")
            status_arrow(f"Total: {total_size:.1f} MB")
            if age_days > 7:
                echo(f"    {Y}Newest backup is {age_days:.0f} days old — consider running 'gaet push'{NC}")
                issues += 1
        else:
            echo(f"    {Y}No backups found{NC}")
            status_arrow("Run 'gaet push' to create your first backup")
            issues += 1
    except OSError:
        echo(f"    {Y}Cannot read backup directory{NC}")
        issues += 1

    # 6. Auto-backup
    box_section("Auto-backup")
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
    if scheduler_is_active(prefix):
        status_ok("Auto-backup is active")
    else:
        echo(f"    {D}Auto-backup not active (run 'gaet push --auto' to enable){NC}")

    # Summary
    echo()
    if issues == 0:
        echo(f"  {G}{ICON_OK}{NC}  All checks passed!")
    else:
        echo(f"  {Y}{ICON_WARN}{NC}  {issues} issue(s) found")


def _local_db_menu(detected, cur_host, cur_port, cur_user, cur_db, cur_pass):
    """Interactive menu for local DB setup with full user control."""
    while True:
        echo()
        box_section("Local Database Setup")
        echo(f"  {B}Detected PostgreSQL instances:{NC}")
        
        for i, inst in enumerate(detected):
            host_display = inst['host']
            if inst['host'].startswith('/'):
                host_display = f"socket:{inst['host']}"
            echo(f"  {C}{i + 1}{NC}  {inst['user']}@{host_display}:{inst['port']}")
            echo(f"      {D}Databases: {inst['databases']}{NC}")
        
        echo()
        echo(f"  {C}A{NC}  Use detected instance (pick number)")
        echo(f"  {C}B{NC}  Manual input (full control over host/port/user/db/pass)")
        echo(f"  {C}C{NC}  Paste connection URL")
        echo(f"  {C}D{NC}  Use defaults (127.0.0.1:5432, postgres/postgres)")
        echo(f"  {C}Q{NC}  Quit init")
        echo()
        
        choice = safe_input(f"  Choose [A/B/C/D/Q]: ").strip().upper()
        
        if choice == "Q":
            echo(f"  {Y}Init dibatalkan.{NC}")
            sys.exit(0)
        
        elif choice == "A":
            # Pick detected instance
            echo()
            for i, inst in enumerate(detected):
                host_display = inst['host']
                if inst['host'].startswith('/'):
                    host_display = f"socket:{inst['host']}"
                echo(f"  {C}{i + 1}{NC}  {inst['user']}@{host_display}:{inst['port']} (DB: {inst['default_db']})")
            echo(f"  {C}0{NC}  Back to menu")
            echo()
            
            pick = safe_input(f"  Pilih instance [1-{len(detected)}]: ").strip()
            if pick == "0":
                continue
            try:
                idx = int(pick) - 1
                if 0 <= idx < len(detected):
                    inst = detected[idx]
                    h = inst["host"]
                    p = inst["port"]
                    u = inst["user"]
                    n = inst["default_db"]
                    w = ""
                    host_display = inst['host']
                    if inst['host'].startswith('/'):
                        host_display = f"socket:{inst['host']}"
                    echo(f"  {D}→ {u}@{host_display}:{p}/{n}{NC}")
                    return h, p, u, n, w
                else:
                    echo(f"  {R}Pilihan tidak valid.{NC}")
                    continue
            except (ValueError, IndexError):
                echo(f"  {R}Pilihan tidak valid.{NC}")
                continue
        
        elif choice == "B":
            # Manual input - full control
            echo()
            return _manual_db_input()
        
        elif choice == "C":
            # Connection URL
            echo()
            return _url_input()
        
        elif choice == "D":
            # Defaults
            h = "127.0.0.1"
            p = "5432"
            u = cur_user or "postgres"
            n = cur_db or "postgres"
            w = cur_pass
            echo(f"  {D}→ {u}@{h}:{p}/{n} (default){NC}")
            return h, p, u, n, w
        
        else:
            echo(f"  {R}Pilihan tidak valid. Gunakan A/B/C/D/Q.{NC}")
            continue


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

    # Always run the wizard — gaet init is re-runnable by design.
    # Existing config (if any) has been backed up above; its values are
    # used as defaults so re-init is fast, not a hard reset.
    if True:  # wizard always runs
        echo()
        box_section("Local Database")

        # Auto-detect running PostgreSQL
        detected = []
        psql = tools.get("psql", "")
        if psql:
            status_info("Auto-detecting local PostgreSQL...")
            detected = detect_local_pg(psql)

        # Preload current config as defaults (for re-init)
        cur_host, cur_port, cur_user, cur_db, cur_pass = get_local_db(env)
        old_remote = env.get("GAET_REMOTE_URL") or env.get("GAET_SUPABASE_URL") or ""

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

                choice = safe_input(f"  Select instance [{len(detected)}]: ").strip() or str(len(detected))
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
            # Auto-detected instances (non-preset mode) - FULL MENU
            h, p, u, n, w = _local_db_menu(detected, cur_host, cur_port, cur_user, cur_db, cur_pass)

        else:
            # No detection — offer URL or manual
            echo(f"  {D}No PostgreSQL detected.{NC}")
            echo()
            echo(f"  {C}1{NC}  Paste connection URL")
            echo(f"  {C}2{NC}  Manual input")
            echo()

            choice = safe_input(f"  Select [1]: ").strip() or "1"
            if choice == "1":
                h, p, u, n, w = _url_input()
            else:
                h, p, u, n, w = _manual_db_input()

        # Test connection immediately
        echo()
        conn_ok = False
        if psql and h:
            echo(f"  {C}💾{NC}  Testing connection {u}@{h}:{p}/{n}... ", end="")
            out, _, rc = run_cmd(
                [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
                env={"PGPASSWORD": w},
                timeout=5,
            )
            if rc == 0 and out.strip() == "1":
                echo(f"{G}OK{NC}")
                conn_ok = True
            else:
                echo(f"{R}GAGAL{NC}")
                echo(f"  {D}Pastikan PostgreSQL berjalan & password benar.{NC}")
                if sys.stdin.isatty():
                    retry = safe_input(f"  Ulangi input lokal? [Y/n]: ").strip().lower()
                    if retry in ("", "y", "yes"):
                        h, p, u, n, w = _manual_db_input()
                        # re-test quickly
                        echo(f"  {C}💾{NC}  Testing {u}@{h}:{p}/{n}... ", end="")
                        out2, _, rc2 = run_cmd(
                            [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
                            env={"PGPASSWORD": w}, timeout=5,
                        )
                        if rc2 == 0 and out2.strip() == "1":
                            echo(f"{G}OK{NC}")
                            conn_ok = True
                        else:
                            echo(f"{R}GAGAL{NC}")
                if not conn_ok:
                    echo(f"  {Y}Peringatan: config disimpan meski koneksi gagal — bisa di-fix via 'gaet set' atau 'gaet init'.{NC}")

        echo()
        box_section("Cloud / Remote Database (optional)")
        echo(f"  {D}Enter the target PostgreSQL connection string.{NC}")
        echo(f"  {D}Can be from Supabase, Neon, RDS, or your own VPS.{NC}")
        echo(f"  {D}Press Enter to skip.{NC}")
        remote_url = safe_input(f"  GAET_REMOTE_URL [{'set' if old_remote else 'none'}]: ").strip()
        if not remote_url:
            remote_url = old_remote  # keep existing on re-init

        echo()
        box_section("Backup")
        default_ret = env.get("GAET_RETENTION_DAYS", str(DEF_RETENTION_DAYS))
        ret_inp = safe_input(f"  Retention (days) [{default_ret}]: ").strip()
        ret = ret_inp or default_ret

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

    echo()
    box_section("Summary")
    env = load_env()  # reload
    tools = find_pg_tools(env)
    _print_summary(env, tools)


def _url_input() -> Tuple[str, str, str, str, str]:
    """Input via connection URL. Returns (host, port, user, db, passwd)."""
    echo(f"  {D}Format: postgresql://user:password@host:5432/dbname{NC}")
    url = safe_input("  URL: ").strip()
    if url:
        parsed = parse_remote_url(url)
        if parsed:
            return parsed["host"], parsed["port"], parsed["user"], parsed["db"], parsed["pass"]
        else:
            echo(f"  {Y}URL tidak valid, fallback ke input manual{NC}")
    return _manual_db_input()


def _manual_db_input() -> Tuple[str, str, str, str, str]:
    """Manual field-by-field input with smart defaults."""
    h = safe_input(f"  Host [127.0.0.1]: ").strip() or "127.0.0.1"
    p = safe_input(f"  Port [5432]: ").strip() or "5432"
    u = safe_input(f"  User [postgres]: ").strip() or "postgres"
    n = safe_input(f"  Database [postgres]: ").strip() or "postgres"
    w = safe_getpass(f"  Password []: ").strip()
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


def cmd_check_inner(env: Dict[str, str], tools: Dict[str, str]) -> Dict[str, Any]:
    """Inner check — reused by init and check command.

    Returns a structured result dict. Human rendering still goes to stdout;
    when --json is requested the caller emits this dict as JSON instead.
    """
    result: Dict[str, Any] = {"ok": True, "checks": {}}

    # Tools
    echo(f"  {C}🔧{NC}  PostgreSQL tools... ", end="")
    tools_ok = bool(tools["pg_dump"] and tools["pg_restore"] and tools["psql"])
    if tools_ok:
        echo(f"{G}OK{NC}")
        status_arrow(f"pg_dump    {D}\"{tools['pg_dump']}\"{NC}")
        status_arrow(f"pg_restore {D}\"{tools['pg_restore']}\"{NC}")
        status_arrow(f"psql       {D}\"{tools['psql']}\"{NC}")
    else:
        echo(f"{R}FAIL{NC}")
        result["ok"] = False
    result["checks"]["tools"] = {
        "ok": tools_ok,
        "pg_dump": tools.get("pg_dump") or None,
        "pg_restore": tools.get("pg_restore") or None,
        "psql": tools.get("psql") or None,
    }

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
            result["ok"] = False
    else:
        echo(f"{R}FAIL{NC}")
        result["ok"] = False

    # Remote config
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    echo(f"  {C}☁️{NC}   Cloud config... ", end="")
    parsed = parse_remote_url(remote_url)
    if parsed:
        echo(f"{G}OK{NC}")
        result["checks"]["remote_db"] = {
            "configured": True, "host": parsed["host"], "port": parsed["port"],
            "user": parsed["user"], "db": parsed["db"], "reachable": False,
        }
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
            result["ok"] = False
    else:
        echo(f"{Y}LEWAT{NC}")
        status_arrow("Set GAET_REMOTE_URL di ~/.gaet/.env")
        result["checks"]["remote_db"] = {"configured": False, "reachable": False}

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
        result["ok"] = False

    # Auto-backup
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
    echo(f"  {C}⏰{NC}  Auto-backup timer... ", end="")
    auto_active = scheduler_is_active(prefix)
    if auto_active:
        echo(f"{G}AKTIF{NC}")
    else:
        echo(f"{Y}tidak aktif{NC}")
        status_arrow("Enable with: gaet push --auto")
    result["checks"]["auto_backup"] = {"active": auto_active}

    echo()
    if result["ok"]:
        echo(f"  {G}{ICON_OK}{NC}  {B}All checks passed!{NC}")
    else:
        echo(f"  {Y}{ICON_WARN}{NC}  {B}Some checks failed — fix before backup.{NC}")
    return result


def cmd_check(args: argparse.Namespace) -> None:
    """Validate config & connections."""
    env = load_env()
    tools = find_pg_tools(env)
    if getattr(args, "json", False):
        # Machine-readable mode: suppress human rendering, emit JSON only
        set_output_modes(quiet=True, plain=True)
    result = cmd_check_inner(env, tools)
    if getattr(args, "json", False):
        # Machine-readable: emit JSON to stdout, exit non-zero if not ok
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["ok"] else 1)


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
    remote_reachable = False

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
            remote_reachable = True
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
            echo(f"  {D}Cek koneksi: gaet check{NC}")
            echo(f"  {D}Backup pertama: gaet push{NC}")

    # Sync status with colored table
    if tables_def and psql:
        echo()
        box_section("Sinkronisasi")

        # Get counts for each table
        rows = []
        colors = []
        synced_count = 0

        # Query all tables at once for efficiency
        safe_tables = [t for t in tables_def if _validate_table_name(t)]
        if len(safe_tables) > 0:
            try:
                union = " UNION ALL ".join(
                    f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}"
                    for t in safe_tables
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
                    if parsed and remote_reachable:
                        synced = lo == re
                        if synced:
                            synced_count += 1
                        status_icon = f"{G}✓{NC}" if synced else f"{R}✗{NC}"
                    else:
                        # Cloud not reachable/configured — sync state unknown
                        synced = False
                        status_icon = f"{D}?{NC}"
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
        if not parsed or not remote_reachable:
            status_warn(f"Tersinkron: ?/{total_tables} tabel — cloud tidak terjangkau")
        elif sync_pct == 100:
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
    safe_tables = [t for t in tables_def if _validate_table_name(t)]
    if psql and safe_tables:
        try:
            union = " UNION ALL ".join(
                f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}"
                for t in safe_tables
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
    remote_reachable = False
    if parsed and psql and not error and safe_tables:
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        union = " UNION ALL ".join(
            f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}"
            for t in safe_tables
        )
        out, _, rc = run_cmd(
            [psql, "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc", union],
            env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
            timeout=30,
        )
        if rc == 0:
            remote_reachable = True
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
        if parsed and remote_reachable:
            synced = lo == re
        else:
            synced = False  # unknown when cloud down
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
    want_json = getattr(args, "json", False)
    if want_json:
        set_output_modes(quiet=True, plain=True)
    result: Dict[str, Any] = {"command": "push", "ok": False}

    if dry_run:
        env = load_env()
        tools = find_pg_tools(env)
        h, p, u, n, w = get_local_db(env)
        remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
        parsed = parse_remote_url(remote_url)
        tables = get_tables(env, tools)
        if want_json:
            result.update({
                "dry_run": True,
                "source": {"host": h, "port": p, "user": u, "db": n},
                "target": ({"host": parsed["host"], "port": parsed["port"],
                             "user": parsed["user"], "db": parsed["db"]} if parsed else None),
                "tables": len(tables),
                "ok": True,
            })
            print(json.dumps(result, indent=2))
            return
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
                f"  Atau edit langsung: {D}{ENV_FILE}{NC}",
                EXIT_CONFIG,
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

        spinner = Spinner("Dumping local database").start()
        try:
            out, err, rc = run_cmd(
                [pg_dump, "-h", h, "-p", p, "-U", u, "-d", n,
                 "--format=custom", "--compress=9", f"--file={backup_file}"],
                env={"PGPASSWORD": w},
                timeout=120,
            )
        finally:
            spinner.stop()
        if rc == 0 and Path(backup_file).is_file():
            size_mb = Path(backup_file).stat().st_size / (1024 * 1024)
            echo(f"    {G}{ICON_OK}{NC}  Dump tersimpan {D}({size_mb:.1f} MB){NC}")
            result["dump"] = {"file": backup_file, "size_mb": round(size_mb, 1)}
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
        spinner = Spinner("Syncing to cloud").start()
        try:
            out3, err3, rc3 = run_cmd(
                [pg_restore, "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"],
                 "--clean", "--if-exists", "--no-owner", "--no-acl",
                 backup_file],
                env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
                timeout=120,
            )
        finally:
            spinner.stop()
        if rc3 == 0:
            echo(f"    {G}{ICON_OK}{NC}  Sinkronisasi selesai!")
            result["sync"] = {"ok": True}
        else:
            echo(f"    {Y}{ICON_WARN}{NC}  Sinkronisasi selesai (dengan peringatan)")
            result["sync"] = {"ok": True, "warning": True}

        # Step 3: Retention
        retention = get_env_int(env, "GAET_RETENTION_DAYS", DEF_RETENTION_DAYS)
        cutoff = time.time() - (retention * 86400)
        try:
            # Apply retention to ALL dump families: manual (gaet_*),
            # cron (cron_*) and fetch (cloud_*)
            for f in list(BACKUP_DIR.glob("gaet_*.dump")) + list(BACKUP_DIR.glob("cron_*.dump")) + list(BACKUP_DIR.glob("cloud_*.dump")):
                if f.stat().st_mtime < cutoff:
                    f.unlink()
        except OSError:
            pass

        # Summary
        size_mb = Path(backup_file).stat().st_size / (1024 * 1024) if Path(backup_file).is_file() else 0
        tables_synced = len(get_tables(env, tools)) if tools.get("psql") else 0
        result["ok"] = True
        result["tables_synced"] = tables_synced
        if want_json:
            print(json.dumps(result, indent=2))
            return
        print_push_summary(backup_file, size_mb, tables_synced)
        log("✅ Push complete")
    finally:
        release_lock()


def cmd_fetch(args: argparse.Namespace) -> None:
    """Restore cloud → local."""
    dry_run = getattr(args, "dry_run", False)
    want_json = getattr(args, "json", False)
    if want_json:
        set_output_modes(quiet=True, plain=True)
    result: Dict[str, Any] = {"command": "fetch", "ok": False}

    if dry_run:
        env = load_env()
        tools = find_pg_tools(env)
        h, p, u, n, w = get_local_db(env)
        remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
        parsed = parse_remote_url(remote_url)
        if want_json:
            result.update({
                "dry_run": True,
                "source": ({"host": parsed["host"], "port": parsed["port"],
                             "user": parsed["user"], "db": parsed["db"]} if parsed else None),
                "target": {"host": h, "port": p, "user": u, "db": n},
                "ok": True,
            })
            print(json.dumps(result, indent=2))
            return
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
                f"  Atau edit langsung: {D}{ENV_FILE}{NC}",
                EXIT_CONFIG,
            )

        tools = find_pg_tools(env)
        psql = tools["psql"]
        pg_dump = tools["pg_dump"]
        pg_restore = tools["pg_restore"]

        log("⬇️ Fetch: cloud → local")
        box_title("gaet fetch")

        # Confirmation before overwriting local DB
        if getattr(args, "yes", False):
            # Non-interactive mode (--yes flag)
            pass
        elif not sys.stdin.isatty():
            # Non-interactive mode (piped, dashboard, cron) — skip prompt
            echo(f"  {Y}⚠ Non-interactive mode — proceeding automatically{NC}")
        else:
            echo(f"  {Y}⚠  PERINGATAN: Operasi ini akan OVERWRITE database lokal!{NC}")
            echo(f"  {D}Database: {u}@{h}:{p}/{n}{NC}")
            echo(f"  {D}Cloud:    {parsed['user']}@{parsed['host']}:{parsed['port']}/{parsed['db']}{NC}")
            echo()
            confirm = safe_input(f"  Ketik 'yes' untuk melanjutkan: ").strip().lower()
            if confirm != "yes":
                echo(f"  {G}Dibatalkan.{NC}")
                return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Step 1: Cloud dump
        echo(f"  {C}☁️{NC}   {B}Dumping database cloud...{NC}")
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        fetch_file = str(BACKUP_DIR / f"cloud_{timestamp}.dump")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        spinner = Spinner("Dumping cloud database").start()
        try:
            out, err, rc = run_cmd(
                [pg_dump, "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"],
                 "--format=custom", "--compress=9", f"--file={fetch_file}"],
                env={"PGPASSWORD": parsed["pass"], "PGSSLMODE": ssl},
                timeout=120,
            )
        finally:
            spinner.stop()
        if rc == 0 and Path(fetch_file).is_file():
            size_mb = Path(fetch_file).stat().st_size / (1024 * 1024)
            echo(f"    {G}{ICON_OK}{NC}  Dump cloud tersimpan {D}({size_mb:.1f} MB){NC}")
            result["dump"] = {"file": fetch_file, "size_mb": round(size_mb, 1)}
        else:
            Path(fetch_file).unlink(missing_ok=True)
            die("Dump cloud gagal", EXIT_CLOUD_DOWN)

        # Step 2: Restore to local
        echo(f"  {C}💾{NC}  {B}Restoring to local database...{NC}")
        # Terminate connections first
        status_warn("Menutup koneksi aktif ke database lokal...")
        safe_db = n.replace("'", "''")
        run_cmd(
            [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
             "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
             f"WHERE datname = '{safe_db}' AND pid <> pg_backend_pid();"],
            env={"PGPASSWORD": w},
            timeout=10,
        )

        spinner = Spinner("Restoring to local database").start()
        try:
            out3, err3, rc3 = run_cmd(
                [pg_restore, "-h", h, "-p", p, "-U", u, "-d", n,
                 "--clean", "--if-exists", fetch_file],
                env={"PGPASSWORD": w},
                timeout=120,
            )
        finally:
            spinner.stop()
        if rc3 <= 1:
            echo(f"    {G}{ICON_OK}{NC}  Local restore complete!")
            result["restore"] = {"ok": True}
        else:
            echo(f"    {Y}{ICON_WARN}{NC}  Restore selesai (dengan peringatan)")
            result["restore"] = {"ok": True, "warning": True}

        Path(fetch_file).unlink(missing_ok=True)
        echo()

        result["ok"] = True
        if want_json:
            print(json.dumps(result, indent=2))
            return

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
    acquire_lock()
    try:
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
    finally:
        release_lock()


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
    """View backup log (includes cron log when filtered)."""
    lines = args.lines or 30
    filter_str = getattr(args, "filter", None) or ""
    since_str = getattr(args, "since", None) or ""
    if not LOG_FILE.is_file() and not CRON_LOG.is_file():
        echo(f"  {Y}Belum ada log. Jalankan 'gaet push' dulu.{NC}")
        return

    sources = [LOG_FILE]
    # Include cron.log when user filters for CRON entries (or always merge it,
    # since cron entries use the same timestamp format)
    if CRON_LOG.is_file():
        sources.append(CRON_LOG)

    all_lines = []
    for src in sources:
        with open(str(src), "r", encoding="utf-8", errors="replace") as f:
            all_lines.extend(f.readlines())

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
    if not filtered and (filter_str or since_str):
        # Helpful context when a filter yields nothing
        if filter_str.upper() == "CRON" and not CRON_LOG.is_file():
            echo(f"  {Y}Filter '{filter_str}' → 0 baris.{NC}")
            echo(f"  {D}Cron log belum ada — auto-backup mungkin belum pernah berjalan.{NC}")
            echo(f"  {D}Aktifkan dengan: gaet push --auto{NC}")
        else:
            echo(f"  {Y}Tidak ada baris yang cocok dengan filter '{filter_str or since_str}'.{NC}")
        return
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
            if key.lower().endswith("password") or "pass" in key.lower() or key.lower().endswith("url") or key == "GAET_REMOTE_URL":
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
      gaet set KEY=           # empty value = delete key
    """
    if not args.variables:
        box_title(f"{NAME} set")
        echo(f"  {B}Set environment variables{NC}")
        echo()
        echo(f"  {D}Contoh:{NC}")
        echo(f"    gaet set GAET_LOCAL_URL=postgresql://user:***@127.0.0.1:5432/db")
        echo(f"    gaet set GAET_REMOTE_URL=postgresql://user:***@db.xxx.supabase.co:5432/postgres")
        echo(f"    gaet set GAET_RETENTION_DAYS=14")
        echo(f"    gaet set GAET_TABLES=users,posts,comments")
        echo()
        echo(f"  {D}Bisa beberapa sekaligus:{NC}")
        echo(f"    gaet set KEY1=v1 KEY2=v2")
        echo()
        echo(f"  {D}Hapus key:{NC}")
        echo(f"    gaet set KEY=")
        echo()
        echo(f"  {D}Lihat semua: gaet get   |   Edit interaktif: gaet init{NC}")
        return

    # Ensure .env directory exists
    GAET_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing env
    env = load_env()

    # Parse and update variables
    updates = {}
    deletions = set()
    for var in args.variables:
        if "=" not in var:
            die(f"Invalid format: {var}. Use KEY=value")
        key, value = var.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            die("Key cannot be empty")
        if value == "":
            # Empty value = delete
            deletions.add(key)
        else:
            updates[key] = value
            env[key] = value

    # If setting individual local DB vars, clear GAET_LOCAL_URL to avoid priority confusion
    local_db_keys = {"GAET_LOCAL_DB_HOST", "GAET_LOCAL_DB_PORT", "GAET_LOCAL_DB_USER",
                     "GAET_LOCAL_DB_NAME", "GAET_LOCAL_DB_PASS"}
    if updates.keys() & local_db_keys:
        deletions.add("GAET_LOCAL_URL")

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
                    if key in deletions:
                        # Skip this line (delete the key)
                        continue
                    if key in updates:
                        lines.append(f"export {key}={updates[key]}\n")
                    else:
                        lines.append(original_line + "\n")
                else:
                    # Keep comments and empty lines
                    lines.append(original_line + "\n")

    # Second pass: add new keys
    for key, value in updates.items():
        if key not in existing_keys and key not in deletions:
            lines.append(f"export {key}={value}\n")

    # Write back
    with open(str(ENV_FILE), "w", encoding="utf-8") as f:
        f.writelines(lines)
    try:
        os.chmod(str(ENV_FILE), 0o600)
    except OSError:
        pass

    # Display result
    box_title(f"{NAME} set")
    for key, value in updates.items():
        # Mask sensitive values in display
        display_value = value
        if key.lower().endswith("password") or "pass" in key.lower() or key.lower().endswith("url") or key == "GAET_REMOTE_URL":
            if len(value) > 20:
                display_value = value[:10] + "***" + value[-5:]
            else:
                display_value = "***"
        status_ok(f"{C}{key}{NC}  =  {display_value}")
    for key in deletions:
        if key in updates:
            continue  # already shown above
        status_ok(f"{C}{key}{NC}  =  {Y}(deleted){NC}")
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
        confirm = safe_input(f"  Ketik 'yes' untuk konfirmasi: ").strip().lower()
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
            dash_files = ["package.json", "next.config.ts", "next-env.d.ts", "tsconfig.json", "postcss.config.js",
                          "app/layout.tsx", "app/page.tsx", "app/globals.css", "app/error.tsx",
                          "app/api/utils.ts",
                          "app/api/status/route.ts", "app/api/push/route.ts",
                          "app/api/fetch/route.ts", "app/api/stop/route.ts",
                          "public/gaet-logo.png"]

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

    # CLI overrides (gaet serve --port N / --no-browser)
    if getattr(args, "port", 0):
        port = int(args.port)
    no_browser = getattr(args, "no_browser", False)

    assert dashboard_dir is not None  # already checked above
    box_title(f"{NAME} serve")

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
        if not no_browser:
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
            Examples:
              gaet init                 First-time setup wizard
              gaet push                 Backup local database → cloud
              gaet status               Show sync status
              gaet check --json | jq   Machine-readable health check (CI)

            Global flags (work before OR after the command):
              -q, --quiet   Suppress non-essential output
              --plain       Decoration-free, pipe-safe output (grep/awk/jq)
              --json        Structured JSON output (on check/push/fetch)

            Get help for a command:
              gaet help <command>        e.g.  gaet help push

            Docs & support:
              GitHub: https://github.com/ghanirahmans/gaet
              Issues: https://github.com/ghanirahmans/gaet/issues
        """),
    )

    # Override error() so unknown commands get a friendly "Did you mean?" hint
    # (clig.dev §Errors: be empathetic, suggest corrections) instead of a raw
    # argparse usage dump.
    _orig_error = parser.error

    def _error_with_suggestion(message: str) -> None:
        # Extract the offending token from argparse's message if present
        tok = None
        m = re.search(r"'([^']+)'", message)
        if m:
            tok = m.group(1)
        # Only suggest when the token looks like a command name (no flag dashes)
        if tok and not tok.startswith("-"):
            import difflib
            matches = difflib.get_close_matches(tok, _SUGGEST_NAMES, n=1, cutoff=0.5)
            if matches:
                sys.stderr.write(f"gaet: error: unknown command '{tok}'\n")
                sys.stderr.write(f"  Did you mean: gaet {matches[0]} ?\n")
                sys.stderr.write(f"  Run 'gaet --help' for the full list.\n")
                sys.exit(2)
        _orig_error(message)

    parser.error = _error_with_suggestion
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"{NAME} v{VERSION}",
    )
    # Global output-control flags (industry standard: -q quiet, --plain scripting)
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-essential output (for scripts/CI)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain, decoration-free output (no box-drawing chars) — pipe-safe for grep/awk/jq",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")
    globals()["subparsers"] = subparsers  # expose for emit_help_json()

    # Common flags shared by all subcommands (so `gaet status --quiet` works too)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-essential output (for scripts/CI)",
    )
    common.add_argument(
        "--plain",
        action="store_true",
        help="Plain, decoration-free output (pipe-safe for grep/awk/jq)",
    )

    # init
    init_parser = subparsers.add_parser("init", help="Interactive setup wizard", parents=[common])
    init_parser.add_argument(
        "preset", nargs="*", default=None,
        help="Preset database (contoh: hindsight, hindsight hermes)",
    )
    init_parser.add_argument(
        "--preset", dest="preset_flag", default=None,
        help="Preset database (contoh: --preset hindsight)",
    )

    # check
    check_parser = subparsers.add_parser("check", help="Validate config & connections", parents=[common])
    check_parser.add_argument("--json", action="store_true", help="Output JSON (machine-readable)")

    # status
    status_parser = subparsers.add_parser("status", help="Show sync status", parents=[common])
    status_parser.add_argument("--json", action="store_true", help="Output JSON")

    # push
    push_parser = subparsers.add_parser("push", help="Backup local → cloud", parents=[common])
    push_parser.add_argument(
        "--auto", nargs="?", const=0, type=int,
        help="Aktifkan auto-backup (opsional: interval jam, default 6)",
    )
    push_parser.add_argument("--cron", action="store_true", help="Jalankan dari scheduler (internal)")
    push_parser.add_argument("--dry-run", action="store_true", help="Simulasi tanpa mengeksekusi")
    push_parser.add_argument("--json", action="store_true", help="Output JSON result")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Restore cloud → local", parents=[common])
    fetch_parser.add_argument("--dry-run", action="store_true", help="Simulasi tanpa mengeksekusi")
    fetch_parser.add_argument("--yes", "-y", action="store_true", help="Skip konfirmasi (untuk non-interaktif/dashboard)")
    fetch_parser.add_argument("--json", action="store_true", help="Output JSON result")

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop auto-backup &/or dashboard", parents=[common])
    stop_parser.add_argument("--scheduler", action="store_true", help="Stop auto-backup saja")
    stop_parser.add_argument("--dashboard", action="store_true", help="Hentikan dashboard saja")

    # log
    log_parser = subparsers.add_parser("log", help="View backup log", parents=[common])
    log_parser.add_argument("lines", nargs="?", type=int, default=30, help="Jumlah baris (default 30)")
    log_parser.add_argument("--filter", "-f", type=str, default="", help="Filter log berdasarkan keyword")
    log_parser.add_argument("--since", "-s", type=str, default="", help="Filter sejak tanggal (YYYY-MM-DD)")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start web dashboard", parents=[common])
    serve_parser.add_argument("--port", type=int, default=0, help="Custom port (default: 9191 or GAET_DASHBOARD_PORT)")
    serve_parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")

    # get
    get_parser = subparsers.add_parser("get", help="Get environment variables", parents=[common])
    get_parser.add_argument(
        "keys", nargs="*", default=[],
        help="Keys to retrieve (if empty, shows all)"
    )

    # set
    set_parser = subparsers.add_parser("set", help="Set environment variables", parents=[common])
    set_parser.add_argument(
        "variables", nargs="*", default=[],
        help="Variables to set (format: KEY=value). Empty → show examples."
    )

    # install
    install_parser = subparsers.add_parser("install", help="Setup/install dependencies & config", parents=[common])
    install_parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve")
    install_parser.add_argument("--skip-deps", action="store_true", help="Skip cek dependencies")
    install_parser.add_argument("--skip-build", action="store_true", help="Skip build dashboard")
    install_parser.add_argument("--skip-config", action="store_true", help="Skip config wizard")
    install_parser.add_argument("--skip-service", action="store_true", help="Skip setup service")
    install_parser.add_argument("--interval", type=int, default=0, help="Interval auto-backup (jam)")

    # update
    update_parser = subparsers.add_parser("update", help="Update to latest version", parents=[common])
    update_parser.add_argument("--force", action="store_true", help="Force update (skip local changes check)")
    update_parser.add_argument("--skip-build", action="store_true", help="Skip build dashboard")

    # uninstall
    uninstall_parser = subparsers.add_parser("uninstall", help="Remove gaet from system", parents=[common])
    uninstall_parser.add_argument("--purge", action="store_true", help="Remove everything including config and backups")

    # help <command> (git-style)
    help_parser = subparsers.add_parser("help", help="Show help for a command (e.g. gaet help push)", parents=[common])
    help_parser.add_argument("topic", nargs="?", default=None, help="Command name to show help for")
    help_parser.add_argument("--json", action="store_true", help="Machine-readable command schema (agent-friendly)")

    # completion
    completion_parser = subparsers.add_parser("completion", help="Generate shell completions", parents=[common])
    completion_parser.add_argument("--shell", "-s", choices=["bash", "zsh", "fish"], default=None, help="Shell (auto-detect if omitted)")

    # doctor
    subparsers.add_parser("doctor", help="Check gaet health and connections", parents=[common])

    args = parser.parse_args()

    # Configure global output modes (--quiet / --plain) before any echo()
    set_output_modes(getattr(args, "quiet", False), getattr(args, "plain", False))

    # git-style: `gaet help <command>`
    if args.command == "help":
        topic = getattr(args, "topic", None)
        if getattr(args, "json", False):
            emit_help_json(topic)
            return
        if topic and topic in subparsers.choices:
            # Re-parse to print that subcommand's help
            parser.parse_args([topic, "--help"])
        else:
            # No topic or unknown → print top-level help
            parser.print_help()
            if topic:
                echo(f"\n  {Y}Unknown command:{NC} {topic}")
                suggest_command(topic)
        return

    # Default command: status
    if args.command is None:
        if not ENV_FILE.is_file():
            # No config yet — show friendly intro + step-by-step onboarding
            box_title(f"{NAME}")
            echo(f"  {Y}Belum dikonfigurasi.{NC}")
            echo()
            echo(f"  {B}Mulai dalam 3 langkah:{NC}")
            echo(f"    {C}1.{NC} gaet init          Setup wizard (local + cloud DB)")
            echo(f"    {C}2.{NC} gaet push          Backup lokal → cloud")
            echo(f"    {C}3.{NC} gaet status        Lihat ringkasan sinkronisasi")
            echo()
            echo(f"  {D}Butuh bantuan?{NC}")
            echo(f"    gaet check         Validasi config & koneksi")
            echo(f"    gaet status        Cek seberapa sinkron DB kamu")
            echo(f"    gaet --help        Daftar semua perintah")
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
                env = load_env()
                args.auto = get_env_int(env, "GAET_AUTO_INTERVAL", DEF_AUTO_INTERVAL)
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
        "completion": lambda: cmd_completion(args),
        "doctor": lambda: cmd_doctor(args),
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
