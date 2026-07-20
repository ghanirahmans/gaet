"""status.py — Modul status untuk gaet.

Digunakan oleh `gaet status --json` dan dashboard.
Membaca config dari ~/.gaet/.env.
"""

import subprocess, os, json, glob, re
from pathlib import Path

HOME = os.path.expanduser("~")
GAET_DIR = f"{HOME}/.gaet"
BACKUP_DIR = f"{GAET_DIR}/backups"
ENV_FILE = f"{GAET_DIR}/.env"

TABLES = [
    "memory_units", "banks", "chunks", "entities", "documents",
    "async_operations", "audit_log", "file_storage", "memory_links"
]

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
            m = re.match(r'^export\s+([^=]+)=\"?(.*?)\"?\s*(?:#.*)?$', line)
            if m:
                d[m.group(1)] = m.group(2).strip('"')
                continue
            m = re.match(r'^([^=]+)=(.*)$', line)
            if m:
                d[m.group(1)] = m.group(2).strip('" ')
    return d

def find_psql():
    """Cari psql — sama seperti di bash gaet."""
    # Cek env var
    psql = os.environ.get("GAET_PSQL")
    if psql and os.path.isfile(psql):
        return psql
    # pg0
    for ver in ["18.1.0", "17", "16", "15"]:
        p = f"{HOME}/.pg0/installation/{ver}/bin/psql"
        if os.path.isfile(p):
            return p
    # PATH
    try:
        p = subprocess.run(["which", "psql"], capture_output=True, text=True, timeout=5)
        if p.returncode == 0:
            return p.stdout.strip()
    except:
        pass
    return "psql"

def get_config():
    """Baca .env, return dict konfigurasi."""
    env = load_env(ENV_FILE)
    return {
        "local_host": env.get("GAET_LOCAL_DB_HOST", "127.0.0.1"),
        "local_port": env.get("GAET_LOCAL_DB_PORT", "5432"),
        "local_user": env.get("GAET_LOCAL_DB_USER", "hindsight"),
        "local_name": env.get("GAET_LOCAL_DB_NAME", "hindsight"),
        "local_pass": env.get("GAET_LOCAL_DB_PASS", "hindsight"),
        "remote_url": env.get("GAET_REMOTE_URL") or env.get("GAET_SUPABASE_URL", ""),
        "retention_days": env.get("GAET_RETENTION_DAYS", "7"),
        "psql": find_psql(),
    }

def parse_url(url):
    """Parse postgresql://user:pass@host:port/db -> tuple."""
    if not url:
        return None, None, None, None, None
    m = re.match(r'postgres(?:ql)?://([^:]+):([^@]+)@([^:]+):(\d+)/([^?\s]+)', url)
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

def get_table_counts(psql, host, port, user, db, passwd, ssl_mode=None):
    """Hitung semua tabel dalam 1 query."""
    union = " UNION ALL ".join(
        f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}" for t in TABLES
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

def get_status():
    """Ambil status lengkap backup."""
    cfg = get_config()
    psql = cfg["psql"]

    # Cek koneksi lokal
    lok_env = {"PGPASSWORD": cfg["local_pass"]}
    ok, _, _ = sh([psql, "-h", cfg["local_host"], "-p", cfg["local_port"],
                    "-U", cfg["local_user"], "-d", cfg["local_name"],
                    "-tAc", "SELECT 1"], env=lok_env, timeout=5)
    if ok != "1":
        return {
            "memories": 0, "synced": False,
            "local_size": "?",
            "remote_size": "?",
            "tables": [{"table": t, "local": 0, "supabase": 0, "ok": False}
                       for t in TABLES],
            "backup_count": 0, "last_backup": None,
            "cron_active": False,
            "error": f"Lokal DB tidak terjangkau ({cfg['local_host']}:{cfg['local_port']})"
        }

    # Hitung tabel lokal + remote
    local_counts = get_table_counts(psql, cfg["local_host"], cfg["local_port"],
                                     cfg["local_user"], cfg["local_name"], cfg["local_pass"])
    remote_counts = {}
    su = parse_url(cfg["remote_url"])
    if all(su):
        user, pw, host, port, db = su
        remote_counts = get_table_counts(psql, host, port, user, db, pw, ssl_mode="require")

    result_tables = []
    all_ok = True
    for t in TABLES:
        lo = local_counts.get(t, 0)
        re = remote_counts.get(t, 0)
        synced = lo == re
        result_tables.append({"table": t, "local": lo, "supabase": re, "ok": synced})
        if not synced:
            all_ok = False

    memories = next((t["local"] for t in result_tables if t["table"] == "memory_units"), 0)

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
    cron_active = False
    out, _, _ = sh(["systemctl", "--user", "is-active", "gaet-backup.timer"])
    cron_active = out.strip() == "active"

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
        "memories": memories,
        "local_size": local_size,
        "remote_size": remote_size,
        "tables": result_tables,
        "synced": all_ok,
        "backup_count": bak_count,
        "last_backup": last_bak,
        "cron_active": cron_active
    }

if __name__ == "__main__":
    print(json.dumps(get_status()))
