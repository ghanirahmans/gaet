"""cmd_get / cmd_set — environment config access with clean schema reference."""

import argparse
import os
import re
from typing import Dict, Any, List

from .core import (
    B, C, D, ENV_FILE, GAET_DIR, IS_WINDOWS, NAME, NC, Y, G, R,
    box_title, box_section, die, echo, load_env, status_info, status_ok, status_warn, status_arrow,
)

CONFIG_CATEGORIES: List[Dict[str, Any]] = [
    {
        "category": "💾 Database Lokal",
        "keys": [
            ("GAET_LOCAL_URL", "URL", "URL koneksi lengkap (postgresql://user:pass@host:port/db)"),
            ("GAET_LOCAL_DB_HOST", "String", "Host / socket path PostgreSQL (default: 127.0.0.1)"),
            ("GAET_LOCAL_DB_PORT", "Int", "Port listener PostgreSQL (default: 5432)"),
            ("GAET_LOCAL_DB_USER", "String", "Username database lokal (default: postgres)"),
            ("GAET_LOCAL_DB_NAME", "String", "Nama database lokal yang di-backup (default: postgres)"),
            ("GAET_LOCAL_DB_PASS", "String", "Password autentikasi PostgreSQL lokal"),
        ],
    },
    {
        "category": "☁️ Cloud Remote",
        "keys": [
            ("GAET_REMOTE_URL", "URL", "URL PostgreSQL Cloud (Supabase, Neon, RDS, VPS)"),
            ("GAET_REMOTE_SSLMODE", "String", "Mode SSL koneksi cloud (default: require)"),
        ],
    },
    {
        "category": "⚙️ Backup & Opsi",
        "keys": [
            ("GAET_RETENTION_DAYS", "Int", "Retensi simpan file backup .dump (default: 7 hari)"),
            ("GAET_PG_TIMEOUT", "Int", "Timeout maksimal (detik) pg_dump & pg_restore (default: 3600)"),
            ("GAET_TABLES", "String", "Filter nama tabel spesifik dipisah koma (default: semua)"),
        ],
    },
]

# Quick lookup schema dict for single key lookup
CONFIG_SCHEMA: Dict[str, Dict[str, str]] = {
    "GAET_LOCAL_URL": {"type": "URL", "default": "127.0.0.1:5432", "desc": "URL koneksi lengkap ke PostgreSQL lokal", "example": "postgresql://user:pass@127.0.0.1:5432/mydb"},
    "GAET_LOCAL_DB_HOST": {"type": "String", "default": "127.0.0.1", "desc": "Host atau path Unix domain socket PostgreSQL lokal", "example": "127.0.0.1"},
    "GAET_LOCAL_DB_PORT": {"type": "Integer", "default": "5432", "desc": "Port listener PostgreSQL lokal", "example": "5432"},
    "GAET_LOCAL_DB_USER": {"type": "String", "default": "postgres", "desc": "Username database PostgreSQL lokal", "example": "postgres"},
    "GAET_LOCAL_DB_NAME": {"type": "String", "default": "postgres", "desc": "Nama database PostgreSQL lokal yang di-sync/backup", "example": "my_app_db"},
    "GAET_LOCAL_DB_PASS": {"type": "String", "default": "(kosong)", "desc": "Password autentikasi PostgreSQL lokal", "example": "mysecretpass"},
    "GAET_REMOTE_URL": {"type": "URL", "default": "(kosong)", "desc": "Connection String PostgreSQL Remote Cloud (Supabase/Neon/RDS)", "example": "postgresql://user:pass@ep-host.region.aws.neon.tech:5432/neondb"},
    "GAET_REMOTE_SSLMODE": {"type": "String", "default": "require", "desc": "Mode SSL/TLS koneksi cloud (require / verify-full / disable)", "example": "require"},
    "GAET_RETENTION_DAYS": {"type": "Integer", "default": "7", "desc": "Jumlah hari simpan file backup .dump sebelum auto-cleanup", "example": "14"},
    "GAET_PG_TIMEOUT": {"type": "Integer", "default": "3600", "desc": "Timeout maksimal (detik) eksekusi pg_dump & pg_restore", "example": "1800"},
    "GAET_TABLES": {"type": "String", "default": "(semua)", "desc": "Filter nama tabel spesifik dipisah koma", "example": "users,orders,products"},
}


def show_config_schema() -> None:
    """Print a clean, grouped visual reference table of all supported configuration keys."""
    box_title(f"{NAME} Config Reference")

    for group in CONFIG_CATEGORIES:
        box_section(group["category"])
        for key, ktype, desc in group["keys"]:
            echo(f"  {C}{key:<22}{NC} {Y}[{ktype:<6}]{NC} {desc}")
        echo()

    status_info(f"Cara ubah: {C}gaet set KEY=value{NC}  |  Contoh: {D}gaet set GAET_RETENTION_DAYS=14{NC}")
    echo()


def cmd_get(args: argparse.Namespace) -> None:
    """Get environment variables from .env file.

    Usage:
      gaet get                 Show all configured variables
      gaet get --list          List all available configuration keys & descriptions
      gaet get KEY             Show specific key
    """
    if getattr(args, "list", False):
        show_config_schema()
        return

    env = load_env()

    if not env:
        status_warn(f"Belum ada file config di {ENV_FILE}")
        echo(f"  {D}Jalankan 'gaet init' atau 'gaet get --list' untuk melihat opsi key.{NC}")
        echo()
        return

    box_title(f"{NAME} get")

    # Determine which keys to show
    if hasattr(args, "keys") and args.keys:
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
            status_ok(f"{C}{key:<22}{NC} = {display_value}")
            found_count += 1
        else:
            not_found.append(key)

    # Report not found keys with helpful hints from schema if available
    if not_found:
        echo()
        for key in not_found:
            if key in CONFIG_SCHEMA:
                schema = CONFIG_SCHEMA[key]
                echo(f"  {Y}[INFO] {key:<20}{NC} {D}(belum diset — default: {schema['default']}){NC}")
                status_arrow(f"Set dengan: gaet set {key}={schema['example']}")
            else:
                status_warn(f"Key '{key}' tidak ditemukan di .env")

    echo()
    if hasattr(args, "keys") and args.keys:
        if found_count > 0:
            status_info(f"Menampilkan {found_count} dari {len(keys_to_show)} variabel")
    else:
        status_info(f"Total {found_count} variabel dikonfigurasi di {ENV_FILE}")
        echo(f"  {D}Ketik 'gaet get --list' untuk melihat referensi seluruh key.{NC}")
    echo()


def cmd_set(args: argparse.Namespace) -> None:
    """Set environment variables in .env file.

    Usage:
      gaet set KEY=value
      gaet set KEY1=value1 KEY2=value2
      gaet set GAET_REMOTE_URL=postgres://...
      gaet set KEY=           # empty value = delete key
    """
    if getattr(args, "list", False) or not args.variables:
        show_config_schema()
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
            die(f"Format tidak valid: {var}. Gunakan format KEY=value (contoh: gaet set GAET_RETENTION_DAYS=14)")
        key, value = var.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            die("Key tidak boleh kosong")
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
        os.chmod(str(ENV_FILE), 0o600) if not IS_WINDOWS else None
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
        status_ok(f"{C}{key:<22}{NC} = {display_value}")
    for key in deletions:
        if key in updates:
            continue  # already shown above
        status_ok(f"{C}{key:<22}{NC} = {Y}(deleted){NC}")
    echo()
    status_info(f"Config tersimpan di: {ENV_FILE}")
    echo()


# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_get_parser(subparsers, common):
    p = subparsers.add_parser("get", help="Get environment variables", parents=[common])
    p.add_argument("keys", nargs="*", default=[], help="Keys to retrieve (if empty, shows all)")
    p.add_argument("--list", "-l", action="store_true", help="Tampilkan seluruh daftar key konfigurasi yang didukung")
    return p


def _build_set_parser(subparsers, common):
    p = subparsers.add_parser("set", help="Set environment variables", parents=[common])
    p.add_argument("variables", nargs="*", default=[],
                   help="Variables to set (format: KEY=value). Run without args to see reference.")
    p.add_argument("--list", "-l", action="store_true", help="Tampilkan seluruh daftar key konfigurasi yang didukung")
    return p


command("get", "Get environment variables", build=_build_get_parser)(cmd_get)
command("set", "Set environment variables", build=_build_set_parser)(cmd_set)
