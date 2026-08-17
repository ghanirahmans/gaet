from __future__ import annotations

"""Shared core: constants, logging, env access, I/O helpers, socket detection, config building."""

import difflib

"""
gaet — Database Backup & Sync CLI (Cross-Platform)
===================================================
Backup local PostgreSQL to cloud (Supabase, Neon, RDS, VPS).

Usage:
  gaet init              Setup wizard
  gaet push              Local -> Cloud
  gaet push --dry-run    Simulasi push
  gaet fetch             Cloud -> Local
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


import argparse

import base64

import getpass

import json

import os

import re

import shutil

import signal

import subprocess

import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import tempfile

import textwrap

import threading

import time

import urllib.request

from datetime import datetime

from pathlib import Path

from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.0.0"

NAME = "gaet"

SYSTEM = sys.platform

IS_LINUX = SYSTEM.startswith("linux")

IS_MACOS = SYSTEM == "darwin"

IS_WINDOWS = SYSTEM == "win32" or SYSTEM.startswith("msys") or SYSTEM.startswith("cygwin")

HOME = Path.home()

GAET_DIR = Path(os.environ.get("GAET_DIR", HOME / ".gaet"))

def get_app_dir() -> Path:
    if "GAET_APP_DIR" in os.environ:
        return Path(os.environ["GAET_APP_DIR"])
    if IS_WINDOWS:
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "gaet"
        return HOME / "AppData" / "Local" / "gaet"
    return HOME / ".local" / "share" / "gaet"

GAET_APP_DIR = get_app_dir()

BACKUP_DIR = GAET_DIR / "backups"

LOG_FILE = BACKUP_DIR / "gaet.log"

CRON_LOG = BACKUP_DIR / "cron.log"

LOCK_PATH = BACKUP_DIR / ".gaet.lock"

ENV_FILE = GAET_DIR / ".env"

DEF_LOCAL_HOST = "127.0.0.1"

DEF_LOCAL_PORT = "5432"

DEF_LOCAL_USER = "postgres"

DEF_LOCAL_DB = "postgres"

DEF_LOCAL_PASS = ""

DEF_RETENTION_DAYS = 7

DEF_AUTO_INTERVAL = 6

DEF_DASHBOARD_PORT = 9191

subparsers: Any = None

DEF_DASHBOARD_HOST = "127.0.0.1"

DEF_REMOTE_SSLMODE = "prefer"

DEF_PG_TIMEOUT = 120

DEF_SERVICE_PREFIX = "gaet"

_FORCE_COLOR = os.environ.get("CLICOLOR_FORCE") == "1"

_NO_COLOR = os.environ.get("NO_COLOR") is not None

_USE_COLOR = (sys.stdout.isatty() or _FORCE_COLOR) and not _NO_COLOR

if _USE_COLOR:
    R = "\033[0;31m"
    BR = "\033[1;31m"
    G = "\033[0;32m"
    BG = "\033[1;32m"
    Y = "\033[1;33m"
    BY = "\033[1;33m"
    C = "\033[0;36m"
    BC = "\033[1;36m"
    M = "\033[0;35m"
    BM = "\033[1;35m"
    BL = "\033[0;34m"
    BBL = "\033[1;34m"
    B = "\033[1m"
    D = "\033[2m"
    W = "\033[1;37m"
    NC = "\033[0m"
    ICON_OK = f"{BG}[ OK ]{NC}"
    ICON_FAIL = f"{BR}[FAIL]{NC}"
    ICON_WARN = f"{BY}[WARN]{NC}"
    ICON_INFO = f"{BC}[INFO]{NC}"
    ICON_ARROW = f"{BM}[NOTE]{NC}"
    ICON_STAR = f"{BY}[STAR]{NC}"
else:
    R = BR = G = BG = Y = BY = C = BC = M = BM = BL = BBL = B = D = W = NC = ""
    ICON_OK = "[ OK ]"
    ICON_FAIL = "[FAIL]"
    ICON_WARN = "[WARN]"
    ICON_INFO = "[INFO]"
    ICON_ARROW = "[NOTE]"
    ICON_STAR = "[STAR]"

QUIET = False

PLAIN = False

EXIT_CONFIG = 80

EXIT_LOCAL_DOWN = 81

EXIT_CLOUD_DOWN = 82

EXIT_LOCKED = 83

EXIT_TOOLS = 84

DOCS_URL = "https://github.com/ghanirahmans/gaet"

TROUBLESHOOTING_URL = "https://github.com/ghanirahmans/gaet/blob/main/TROUBLESHOOTING.md"

def print_docs_footer(doc_type: str = "main") -> None:
    """Print clean CLI documentation footer unless output is quiet/plain/piped."""
    if is_plain() or QUIET:
        return
    echo()
    if doc_type == "troubleshooting":
        echo(f"  {D}💡 Troubleshooting guide:{NC} {C}{TROUBLESHOOTING_URL}{NC}")
    else:
        echo(f"  {D}📖 Documentation & Support:{NC} {C}{DOCS_URL}{NC}")

def set_output_modes(quiet: bool, plain: bool) -> None:
    """Configure global QUIET/PLAIN from parsed args."""
    global QUIET, PLAIN
    QUIET = bool(quiet)
    PLAIN = bool(plain)

def is_plain() -> bool:
    """True when --plain is active OR stdout is not a TTY (pipe/file)."""
    return PLAIN or not sys.stdout.isatty()

def die(msg: str, code: int = 1) -> None:
    """Print error and exit."""
    print(f"  {R}{ICON_FAIL}{NC}  {msg}", file=sys.stderr)
    if not is_plain() and not QUIET:
        print(f"  {D}💡 Troubleshooting guide:{NC} {C}{TROUBLESHOOTING_URL}{NC}\n", file=sys.stderr)
    sys.exit(code)

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
                shutil.rmtree(LOCK_PATH, ignore_errors=True)
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
    Parse postgresql://user:pw@host:port/db or postgresql://user:pw@/socket_dir:port/db.
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
    if not sep or not userinfo or not hostpart:
        return None

    # user:pass — user cannot contain ':', password may
    if ":" in userinfo:
        user, _, passwd = userinfo.partition(":")
    else:
        user, passwd = userinfo, ""

    # host:port/db — split at the LAST '/' to support unix socket paths (e.g. /tmp:5433/db)
    slash_idx = hostpart.rfind("/")
    if slash_idx == -1:
        return None
    hostport = hostpart[:slash_idx]
    db = hostpart[slash_idx + 1:].split("?", 1)[0]  # strip query string (e.g. ?sslmode=)
    if not db or not hostport:
        return None

    if ":" in hostport:
        host, _, port = hostport.rpartition(":")
        if not port.isdigit():
            host = hostport
            port = "5432"
    else:
        host = hostport
        port = "5432"

    if not host:
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

def _socket_port(sock_path: str) -> str:
    """Extract the port from a PostgreSQL socket filename (.s.PGSQL.<port>).

    The port lives in the file name, not in the directory — hardcoding
    '5432' while probing a socket on another port fails every connection.
    """
    name = os.path.basename(sock_path)
    if name.startswith(".s.PGSQL."):
        port = name[len(".s.PGSQL."):]
        if port.isdigit():
            return port
    return "5432"

def _find_socket_paths() -> List[str]:
    """Scan known socket directories for every .s.PGSQL.* file (any port)."""
    paths: List[str] = []
    socket_dirs = ["/run/postgresql", "/var/run/postgresql", "/tmp", "/private/tmp", str(HOME / ".pg0" / "sockets")]
    if IS_WINDOWS:
        # Common Windows PostgreSQL data directories
        for prog_dir in ["C:/Program Files/PostgreSQL", "C:/Program Files (x86)/PostgreSQL"]:
            if os.path.exists(prog_dir):
                try:
                    for version in os.listdir(prog_dir):
                        data_dir = Path(prog_dir) / version / "data"
                        if data_dir.is_dir():
                            socket_dirs.append(str(data_dir))
                except OSError:
                    pass
    for sdir in socket_dirs:
        try:
            for name in sorted(os.listdir(sdir)):
                if name.startswith(".s.PGSQL.") and not name.endswith(".lock"):
                    paths.append(os.path.join(sdir, name))
        except OSError:
            continue
    return paths

def discover_tables(psql: str, h: str, p: str, u: str, n: str, w: str) -> List[str]:
    """Auto-discover tables from information_schema.tables (public schema)."""
    query = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    env_dict = pg_env(u, w)
    out, _, rc = run_cmd(
        [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", query],
        env=env_dict,
        timeout=10,
    )
    cleanup_pg_env(env_dict)
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

    # macOS: common Homebrew & Postgres.app install paths
    if IS_MACOS:
        mac_dirs = [
            Path("/opt/homebrew/bin"),
            Path("/usr/local/bin"),
            Path("/opt/homebrew/opt/libpq/bin"),
            Path("/usr/local/opt/libpq/bin"),
        ]
        for base in [Path("/opt/homebrew/opt"), Path("/usr/local/opt")]:
            if base.is_dir():
                try:
                    for d in base.glob("postgresql*"):
                        if (d / "bin").is_dir():
                            mac_dirs.append(d / "bin")
                except OSError:
                    pass
        app_base = Path("/Applications/Postgres.app/Contents/Versions")
        if app_base.is_dir():
            try:
                for v in sorted(app_base.glob("*"), reverse=True):
                    if (v / "bin").is_dir():
                        mac_dirs.append(v / "bin")
            except OSError:
                pass

        for bin_dir in mac_dirs:
            if not pg_dump and (bin_dir / "pg_dump").is_file():
                pg_dump = str(bin_dir / "pg_dump")
            if not pg_restore and (bin_dir / "pg_restore").is_file():
                pg_restore = str(bin_dir / "pg_restore")
            if not psql and (bin_dir / "psql").is_file():
                psql = str(bin_dir / "psql")

    return {"pg_dump": pg_dump, "pg_restore": pg_restore, "psql": psql}

def echo(msg: str = "", end: str = "\n", flush: bool = False) -> None:
    """Print with our formatting conventions.

    Respects --quiet: when QUIET is set, non-essential output is suppressed
    (stdout stays silent for humans, but data/JSON should be printed directly
    with print()/json.dumps, not via echo()).
    """
    if QUIET:
        return
    try:
        print(msg, end=end, flush=flush)
    except UnicodeEncodeError:
        try:
            sys.stdout.buffer.write((msg + end).encode("utf-8", errors="replace"))
            if flush:
                sys.stdout.buffer.flush()
        except Exception:
            print(msg.encode("ascii", errors="replace").decode("ascii"), end=end, flush=flush)
    except BrokenPipeError:
        # Silently ignore broken pipe (e.g., `gaet status | head`)
        pass
    except KeyboardInterrupt:
        raise

def safe_input(prompt: str, default: str = "") -> str:
    """input() that degrades gracefully when there is no TTY (pipes, cron, SSH).

    When stdin is not a terminal, we still try to read it (piped input works
    with input()). Only fallback to default when stdin is exhausted (EOF).
    In non-interactive mode, does NOT print the prompt (avoid output pollution).
    """
    if not sys.stdin.isatty():
        try:
            return input(prompt)
        except EOFError:
            # Don't echo prompt + default in non-interactive mode
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

def _is_socket_host(h: str) -> bool:
    """True when the host value is a Unix socket directory (starts with '/').

    Socket paths cannot be encoded in a postgres:// URL — they must be
    stored as individual GAET_LOCAL_DB_* variables instead (git's config is
    also path-aware: `.git/config` is never a URL for local paths).
    """
    return bool(h) and h.startswith("/")

def _local_config_lines(h, p, u, n, w) -> Tuple[List[str], str, str]:
    """Build the local-database section of ~/.gaet/.env as a line list.

    Returns (lines, pass_line, tables_note):
      - Host is a socket dir  → individual GAET_LOCAL_DB_* vars (URL can't
        encode a path with '/'); connection keeps working via psql -h <dir>.
      - Host is TCP/IP        → compact GAET_LOCAL_URL (git-style default).
    No indentation is applied here — callers must emit plain KEY=value lines
    (textwrap.dedent cannot handle multi-line interpolated values).
    """
    if _is_socket_host(h):
        # Socket path: cannot live in a connection URL. Write individual
        # variables so load_env/get_local_db round-trips correctly.
        local_lines = [
            f"GAET_LOCAL_DB_HOST={h}",
            f"GAET_LOCAL_DB_PORT={p}",
            f"GAET_LOCAL_DB_USER={u}",
            f"GAET_LOCAL_DB_NAME={n}",
        ]
    else:
        local_url = f"postgresql://{u}@{h}:{p}/{n}"
        local_lines = [f"GAET_LOCAL_URL={local_url}"]
    if w:
        pass_line = f"GAET_LOCAL_DB_PASS={w}"
    else:
        pass_line = "# GAET_LOCAL_DB_PASS="
    return local_lines, pass_line, ""

def _build_env_content(
    h, p, u, n, w, remote_url, retention_days, tables_line="", header="Konfigurasi"
) -> str:
    """Build the full ~/.gaet/.env content as plain KEY=value lines.

    No textwrap.dedent and no indentation anywhere — .env files must be
    sourceable by POSIX shells (`source ~/.gaet/.env`), so every line is
    flush-left.
    """
    local_lines, pass_line, _ = _local_config_lines(h, p, u, n, w)
    lines = [
        "# ══════════════════════════════════════════════════════════════",
        f"# gaet — {header}",
        "# ══════════════════════════════════════════════════════════════",
        f"# Dibuat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ══════════════════════════════════════════════════════════════",
        "",
        "# Local Database",
        *local_lines,
        pass_line,
        "",
        "# Remote Database (Cloud)",
        f"GAET_REMOTE_URL={remote_url}",
        "",
        "# Backup",
        f"GAET_RETENTION_DAYS={retention_days}",
    ]
    if tables_line:
        lines.append(tables_line)
    return "\n".join(lines) + "\n"

def _write_env_file(content: str) -> None:
    """Atomically write ~/.gaet/.env with 0600 permissions."""
    fd = os.open(str(ENV_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(content)


def set_env_key(key: str, value: str) -> None:
    """Set or update a single KEY=value in ~/.gaet/.env safely preserving 0600 permissions."""
    GAET_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    found = False

    if ENV_FILE.is_file():
        with open(str(ENV_FILE), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                original_line = line.rstrip("\n")
                m = re.match(r"^(?:export\s+)?([^=]+)=", original_line)
                if m and m.group(1).strip() == key:
                    if value != "":
                        lines.append(f"export {key}={value}\n")
                    found = True
                else:
                    lines.append(original_line + "\n")

    if not found and value != "":
        lines.append(f"export {key}={value}\n")

    _write_env_file("".join(lines))

def _ensure_git_workspace() -> bool:
    """Make ~/.gaet a versioned workspace the way `git init` sets up a repo.

    Secrets live in .env, which is git-ignored (exactly like .git/config is
    local-only), so initializing a repo here never leaks credentials. The
    repo tracks .gitignore + any non-secret scaffolding, giving config
    history and `gaet update` a clean baseline.

    Returns True when git is available and the workspace is (or was made
    into) a repository; False otherwise (git missing — non-fatal).
    """
    git = shutil.which("git")
    if not git:
        return False
    try:
        # Workspace dir must exist before `git init` (like `git init` in a
        # fresh directory — gaet init ensures both dir and repo).
        GAET_DIR.mkdir(parents=True, exist_ok=True)
        git_dir = GAET_DIR / ".git"
        if not git_dir.exists():
            run_cmd([git, "-C", str(GAET_DIR), "init", "-q"], timeout=10)
        gi = GAET_DIR / ".gitignore"
        gi_content = (
            "# gaet workspace — secrets & data stay local (like .git/config)\n"
            ".env\n"
            ".env.backup.*\n"
            "backups/\n"
            "*.dump\n"
            "*.log\n"
            ".gaet.lock/\n"
        )
        if not gi.is_file() or gi.read_text(encoding="utf-8") != gi_content:
            gi.write_text(gi_content, encoding="utf-8")
        # Ensure git user identity exists BEFORE any commit so fresh
        # environments (no global user.name/email) don't abort it.
        ident = run_cmd(
            [git, "-C", str(GAET_DIR), "config", "user.email"], timeout=5
        )[0].strip()
        if not ident:
            run_cmd([git, "-C", str(GAET_DIR), "config", "user.name", "gaet"], timeout=5)
            run_cmd(
                [git, "-C", str(GAET_DIR), "config", "user.email", "gaet@localhost"],
                timeout=5,
            )
        # Commit only tracked scaffolding; .env is ignored so nothing
        # sensitive ever lands in history.
        out, _, rc = run_cmd([git, "-C", str(GAET_DIR), "status", "--porcelain"], timeout=10)
        if rc == 0 and out.strip():
            run_cmd([git, "-C", str(GAET_DIR), "add", ".gitignore"], timeout=10)
            run_cmd(
                [git, "-C", str(GAET_DIR), "commit", "-q", "-m", "chore: init gaet workspace"],
                timeout=10,
            )
        return True
    except OSError:
        return False

def _save_init_config(h, p, u, n, w, remote_url, retention_days):
    """Save config from non-interactive init mode."""
    GAET_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Backup existing config if present
    if ENV_FILE.is_file():
        backup_path = GAET_DIR / f".env.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copy2(str(ENV_FILE), str(backup_path))
            status_info(f"Old config backed up to: {backup_path}")
        except OSError:
            pass

    env_content = _build_env_content(
        h, p, u, n, w, remote_url, retention_days, header="Konfigurasi (auto-generated)"
    )

    _write_env_file(env_content)

    echo()
    status_ok(f"Config saved to {ENV_FILE}")
    if _ensure_git_workspace():
        status_ok(f"Workspace versioned with git ({GAET_DIR})")
    echo()
    box_section("Summary")
    env = load_env()
    tools = find_pg_tools(env)
    _print_summary(env, tools)

_SUGGEST_NAMES = [
    "init", "check", "status", "push", "fetch", "stop", "log",
    "serve", "get", "set", "install", "update", "uninstall", "help",
    "completion", "doctor", "diff", "export",
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
    echo(f"  {ICON_OK}  {msg}")

def status_fail(msg: str) -> None:
    echo(f"  {ICON_FAIL}  {msg}")

def status_warn(msg: str) -> None:
    echo(f"  {ICON_WARN}  {msg}")

def status_info(msg: str) -> None:
    echo(f"  {ICON_INFO}  {msg}")

def status_arrow(msg: str) -> None:
    echo(f"  {ICON_ARROW}  {msg}")

def draw_table(headers: str, rows: List[str]) -> None:
    """
    Draw a table similar to Bash version.
    headers: colon-separated header names (e.g., "Table:Local:Cloud:Status")
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
    box_section("Summary")
    if synced:
        status_ok(f"All {table_count} tables in sync ({local_count} rows)")
    else:
        status_warn(f"Tables out of sync — {table_count} tables checked")
    status_arrow(f"Local: {local_count} rows")
    status_arrow(f"Cloud: {remote_count} rows")

def print_push_summary(backup_file: str, size_mb: float, tables_synced: int) -> None:
    """Print summary after successful push."""
    echo()
    box_section("Push Complete")
    status_ok(f"Backups stored: {backup_file} ({size_mb:.1f} MB)")
    status_ok(f"Synced tables: {tables_synced}")
    status_arrow("Run 'gaet status' for details")

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
        os.chmod(pgpass_path, 0o600) if not IS_WINDOWS else None
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

try:
    from scripts.scheduler import (  # type: ignore[import-not-found,import-untyped] # pyright: ignore[reportMissingImports]
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

try:
    from scripts import service_manager as _svc_mod  # type: ignore[import-not-found,import-untyped] # pyright: ignore[reportMissingImports]
    _svc_available = True
except ImportError:
    _svc_available = False

GITHUB_API = "https://api.github.com/repos/ghanirahmans/gaet/contents"
GITHUB_RAW = "https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.0"


def _raw_download(url: str, timeout: int = 15) -> bytes:
    """Download a file from a raw URL (e.g. raw.githubusercontent.com).

    Unlike _gh_download (which hits the GitHub API and its 60 req/h
    unauthenticated rate limit), raw URLs are served by the CDN with no
    API quota — so `gaet update` works even right after a fresh install that
    already burned the API budget. Retries transient failures.
    """
    last_err: Exception | None = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"download failed for {url}: {last_err}")


def _gh_download(url: str, timeout: int = 15) -> bytes:
    """Download file from GitHub API, decoding base64 content.

    Kept for backward compat; _update_download now uses _raw_download instead
    (raw URLs, no API rate limit).
    """
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    if isinstance(data, dict) and "content" in data:
        return base64.b64decode(data["content"])
    raise RuntimeError(f"GitHub API: {data.get('message', 'unknown error')}")

def _print_summary(env: Dict[str, str], tools: Dict[str, str]) -> None:
    """Print config summary after init."""
    h, p, u, n, w = get_local_db(env)
    psql = tools.get("psql", "")

    # Local DB status
    echo(f"  {C}💾{NC}  Local:  {u}@{h}:{p}/{n}", end="")
    if psql:
        env_dict = pg_env(u, w)
        out, _, rc = run_cmd(
            [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
            env=env_dict, timeout=5,
        )
        cleanup_pg_env(env_dict)
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


