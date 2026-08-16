"""cmd_get / cmd_set — environment config access."""

import argparse
import os
import re
from .core import B, C, D, ENV_FILE, GAET_DIR, IS_WINDOWS, NAME, NC, Y, argparse, box_title, die, echo, load_env, os, re, status_info, status_ok, status_warn

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
        status_ok(f"{C}{key}{NC}  =  {display_value}")
    for key in deletions:
        if key in updates:
            continue  # already shown above
        status_ok(f"{C}{key}{NC}  =  {Y}(deleted){NC}")
    echo()
    status_info(f"Config saved: {ENV_FILE}")
    echo()

# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_get_parser(subparsers, common):
    p = subparsers.add_parser("get", help="Get environment variables", parents=[common])
    p.add_argument("keys", nargs="*", default=[], help="Keys to retrieve (if empty, shows all)")
    return p


def _build_set_parser(subparsers, common):
    p = subparsers.add_parser("set", help="Set environment variables", parents=[common])
    p.add_argument("variables", nargs="*", default=[],
                   help="Variables to set (format: KEY=value). Empty to show examples.")
    return p


command("get", "Get environment variables", build=_build_get_parser)(cmd_get)
command("set", "Set environment variables", build=_build_set_parser)(cmd_set)

