"""status.py — Modul status untuk gaet.

Digunakan oleh `gaet status --json` dan dashboard.
Membaca config dari ~/.gaet/.env.

Supports dynamic table discovery:
  - GAET_TABLES config (manual override)
  - Auto-discover from information_schema.tables
  - Preset fallback (backward compatible)
"""

import subprocess, os, sys, json, glob, re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HOME = os.path.expanduser("~")
GAET_DIR = f"{HOME}/.gaet"
BACKUP_DIR = f"{GAET_DIR}/backups"
ENV_FILE = f"{GAET_DIR}/.env"

# Backward-compatible fallback (used only if discovery fails)
FALLBACK_TABLES = [
    "memory_units", "banks", "chunks", "entities", "documents",
    "async_operations", "audit_log", "file_storage", "memory_links"
]

PRESETS = {
    "hindsight": {
        "local_user": "hindsight",
        "local_db": "hindsight",
        "local_pass": "hindsight",
        "tables": FALLBACK_TABLES,
    },
}


def load_env(path):
    """Parse .env file, return dict."""
    d = {}
    if not os.path.isfile(path):
        return d
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^export\s+([^=]+)="?(.*?)"?\s*(?:#.*)?$', line)
            if m:
                d[m.group(1)] = m.group(2).strip('"')
                continue
            m = re.match(r'^([^=]+)=(.*)$', line)
            if m:
                d[m.group(1)] = m.group(2).strip('" ')
    return d


def find_psql():
    """Cari psql — cross-platform."""
    psql = os.environ.get("GAET_PSQL")
    if psql and os.path.isfile(psql):
        return psql
    # pg0
    for ver in ["18.1.0", "17", "16", "15"]:
        p = f"{HOME}/.pg0/installation/{ver}/bin/psql"
        if os.path.isfile(p):
            return p
    # Windows
    if sys.platform.startswith("win"):
        for base in [r"C:\Program Files\PostgreSQL", r"C:\Program Files (x86)\PostgreSQL"]:
            if os.path.isdir(base):
                try:
                    vers = sorted(
                        (v for v in os.listdir(base) if os.path.isdir(os.path.join(base, v))),
                        key=lambda v: [int(x) for x in v.split(".") if x.isdigit()] or [0],
                        reverse=True
                    )
                    for ver in vers:
                        p = os.path.join(base, ver, "bin", "psql.exe")
                        if os.path.isfile(p):
                            return p
                except PermissionError:
                    pass
    # PATH
    try:
        p = subprocess.run(["which", "psql"], capture_output=True, text=True, timeout=5)
        if p.returncode == 0:
            return p.stdout.strip()
    except:
        pass
    return "psql"


def get_config() -> Dict:
    """Baca .env, return dict konfigurasi."""
    env = load_env(ENV_FILE)
    local_url = env.get("GAET_LOCAL_URL", "")
    if local_url:
        p = parse_url(local_url)
        if p:
            lh, lp, lu, ln, lw = p
        else:
            lh, lp, lu, ln, lw = "127.0.0.1", "5432", "postgres", "postgres", ""
    else:
        lh = env.get("GAET_LOCAL_DB_HOST", "127.0.0.1")
        lp = env.get("GAET_LOCAL_DB_PORT", "5432")
        lu = env.get("GAET_LOCAL_DB_USER", "postgres")
        ln = env.get("GAET_LOCAL_DB_NAME", "postgres")
        lw = env.get("GAET_LOCAL_DB_PASS", "")
    return {
        "local_host": lh,
        "local_port": lp,
        "local_user": lu,
        "local_name": ln,
        "local_pass": lw,
        "remote_url": env.get("GAET_REMOTE_URL") or env.get("GAET_SUPABASE_URL", ""),
        "retention_days": env.get("GAET_RETENTION_DAYS", "7"),
        "tables_config": env.get("GAET_TABLES", ""),
        "psql": find_psql(),
    }


def parse_url(url):
    """Parse postgresql://user:***@host:port/db -> tuple."""
    if not url:
        return None, None, None, None, None
    m = re.match(r'postgres(?:ql)?://([^:]+):([^@]+)@([^:]+):(\d+)/([^\?\s]+)', url)
    if m:
        return m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    return None, None, None, None, None


def sh(cmd, env=None, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", 1
    except Exception as e:
        return "", str(e), 1


# ─── Table Discovery ──────────────────────────────────────────────────

def discover_tables(psql, host, port, user, db, passwd) -> List[str]:
    """Auto-discover tables from information_schema (public schema)."""
    query = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    env = {"PGPASSWORD": passwd}
    out, _, rc = sh([psql, "-h", host, "-p", port, "-U", user, "-d", db,
                      "-tAc", query], env=env, timeout=10)
    if rc == 0 and out.strip():
        return [t.strip() for t in out.strip().split("\n") if t.strip()]
    return []


def get_tables(cfg) -> List[str]:
    """Get table list: config override > auto-discover > fallback."""
    # 1. GAET_TABLES config
    tables_str = cfg.get("tables_config", "")
    if tables_str:
        return [t.strip() for t in tables_str.split(",") if t.strip()]

    # 2. Auto-discover from local DB
    psql = cfg.get("psql", "")
    if psql:
        tables = discover_tables(
            psql, cfg["local_host"], cfg["local_port"],
            cfg["local_user"], cfg["local_name"], cfg["local_pass"]
        )
        if tables:
            return tables

    # 3. Fallback
    return list(FALLBACK_TABLES)


# ─── Table Counts ─────────────────────────────────────────────────────

def get_table_counts(psql, host, port, user, db, passwd, tables, ssl_mode=None):
    """Hitung semua tabel dalam 1 query."""
    if not tables:
        return {}
    union = " UNION ALL ".join(
        f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}" for t in tables
    )
    env = {"PGPASSWORD": passwd}
    if ssl_mode:
        env["PGSSLMODE"] = ssl_mode
    cmd = [psql, "-h", host, "-p", port, "-U", user, "-d", db, "-tAc", union]
    out, _, rc = sh(cmd, env=env, timeout=30)
    counts = {}
    for line in out.strip().split("\n"):
        line = line.strip()
        if "|" in line:
            parts = line.split("|")
            try:
                counts[parts[0].strip()] = int(parts[1].strip())
            except ValueError:
                pass
    return counts


# ─── Cron/Scheduler Status ───────────────────────────────────────────

def is_cron_active():
    """Cek status cron/timer cross-platform."""
    platform = sys.platform
    try:
        if platform.startswith("linux"):
            out, _, rc = sh(["systemctl", "--user", "is-active", "gaet-backup.timer"])
            return out.strip() == "active"
        elif platform == "darwin":
            out, _, rc = sh(["launchctl", "list", "gaet-backup"])
            return rc == 0 and "gaet-backup" in out
        elif platform == "win32":
            _, _, rc = sh(["schtasks", "/Query", "/TN", "gaet-backup"])
            return rc == 0
        else:
            return False
    except Exception:
        return False


# ─── Main Status ──────────────────────────────────────────────────────

def get_status():
    """Ambil status lengkap backup."""
    cfg = get_config()
    psql = cfg["psql"]
    tables = get_tables(cfg)

    # Cek koneksi lokal
    lok_env = {"PGPASSWORD": cfg["local_pass"]}
    ok, _, _ = sh([psql, "-h", cfg["local_host"], "-p", cfg["local_port"],
                    "-U", cfg["local_user"], "-d", cfg["local_name"],
                    "-tAc", "SELECT 1"], env=lok_env, timeout=5)
    if ok != "1":
        return {
            "total_rows": 0, "synced": False,
            "local_size": "?",
            "remote_size": "?",
            "tables": [{"table": t, "local": 0, "supabase": 0, "ok": False}
                       for t in tables],
            "backup_count": 0, "last_backup": None,
            "cron_active": is_cron_active(),
            "error": f"Lokal DB tidak terjangkau ({cfg['local_host']}:{cfg['local_port']})"
        }

    # Hitung tabel lokal + remote
    local_counts = get_table_counts(psql, cfg["local_host"], cfg["local_port"],
                                     cfg["local_user"], cfg["local_name"], cfg["local_pass"],
                                     tables)
    remote_counts = {}
    su = parse_url(cfg["remote_url"])
    if all(su):
        user, pw, host, port, db = su
        remote_counts = get_table_counts(psql, host, port, user, db, pw,
                                          tables, ssl_mode="require")

    result_tables = []
    all_ok = True
    for t in tables:
        lo = local_counts.get(t, 0)
        re = remote_counts.get(t, 0)
        synced = lo == re
        result_tables.append({"table": t, "local": lo, "supabase": re, "ok": synced})
        if not synced:
            all_ok = False

    total_rows = sum(local_counts.values())

    # Info backup
    last_bak = None
    bak_count = 0
    try:
        files = sorted(glob.glob(os.path.join(BACKUP_DIR, "gaet_*.dump")), reverse=True)
        if files:
            bak_count = len(files)
            f = files[0]
            last_bak = {"file": os.path.basename(f), "size": os.path.getsize(f),
                        "date": os.path.getmtime(f)}
    except:
        pass

    # Cron status
    cron_active = is_cron_active()

    # DB sizes
    local_size = "?"
    out, _, _ = sh([psql, "-h", cfg["local_host"], "-p", cfg["local_port"],
                     "-U", cfg["local_user"], "-d", cfg["local_name"], "-tAc",
                     "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1)"],
                    env=lok_env)
    if out:
        local_size = out + " MB"

    remote_size = "?"
    if all(su) and remote_counts:
        user, pw, host, port, db = su
        env_rm = {"PGPASSWORD": pw, "PGSSLMODE": "require"}
        out, _, _ = sh([psql, "-h", host, "-p", port, "-U", user, "-d", db, "-tAc",
                         "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1)"],
                        env=env_rm, timeout=15)
        if out:
            remote_size = out + " MB"

    return {
        "total_rows": total_rows,
        "local_size": local_size,
        "remote_size": remote_size,
        "tables": result_tables,
        "synced": all_ok,
        "backup_count": bak_count,
        "last_backup": last_bak,
        "cron_active": cron_active,
    }


if __name__ == "__main__":
    print(json.dumps(get_status()))
