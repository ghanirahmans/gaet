"""Management of remote cloud database configuration (git remote parity)."""

import argparse
import json
import sys
from typing import Dict, Any, Optional

from .core import (
    load_env,
    set_env_key,
    get_env_str,
    parse_remote_url,
    find_pg_tools,
    pg_env,
    cleanup_pg_env,
    run_cmd,
    echo,
    die,
    box_title,
    box_section,
    status_ok,
    status_arrow,
    status_warn,
    set_output_modes,
    C, G, Y, R, D, B, NC,
    DEF_REMOTE_SSLMODE,
)
from .registry import command


def cmd_remote(args: argparse.Namespace) -> None:
    """Manage remote cloud DB settings (show / set-url / remove)."""
    subaction = getattr(args, "remote_action", None) or "show"
    url_arg = getattr(args, "url", None)
    want_json = getattr(args, "json", False)

    if want_json:
        set_output_modes(quiet=True, plain=True)

    env = load_env()

    if subaction == "set-url":
        if not url_arg:
            die("Usage: gaet remote set-url <postgresql://user:pass@host:port/db>")
        parsed = parse_remote_url(url_arg)
        if not parsed:
            die("Invalid remote URL format. Expected: postgresql://user:pass@host:port/dbname")
        set_env_key("GAET_REMOTE_URL", url_arg)
        status_ok(f"GAET_REMOTE_URL updated successfully ({parsed['user']}@{parsed['host']}:{parsed['port']}/{parsed['db']})")
        return

    if subaction in ("remove", "unset", "rm"):
        set_env_key("GAET_REMOTE_URL", "")
        status_ok("GAET_REMOTE_URL removed successfully from .env")
        return

    # Default / 'show' action
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)

    if want_json:
        result = {
            "command": "remote",
            "configured": bool(parsed),
            "remote": parsed if parsed else None,
        }
        print(json.dumps(result, indent=2))
        return

    box_title("gaet remote")
    if not parsed:
        echo(f"  {Y}No Remote Cloud DB configured yet.{NC}")
        echo(f"  Usage: {C}gaet remote set-url postgresql://user:pass@host:port/db{NC}")
        return

    masked_pass = "*****" if parsed["pass"] else ""
    masked_url = f"postgresql://{parsed['user']}:{masked_pass}@{parsed['host']}:{parsed['port']}/{parsed['db']}"

    box_section("Remote Configuration")
    status_arrow(f"Host:     {parsed['host']}")
    status_arrow(f"Port:     {parsed['port']}")
    status_arrow(f"User:     {parsed['user']}")
    status_arrow(f"Database: {parsed['db']}")
    status_arrow(f"URL:      {masked_url}")

    # Connectivity Check
    echo()
    echo(f"  {C}☁️{NC}   Testing remote cloud connection... ", end="", flush=True)
    tools = find_pg_tools(env)
    psql = tools.get("psql", "")
    if psql:
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        env_remote = pg_env(parsed["user"], parsed["pass"], ssl)
        try:
            out, _, rc = run_cmd(
                [psql, "-w", "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"], "-tAc", "SELECT 1;"],
                env=env_remote, timeout=5,
            )
        finally:
            cleanup_pg_env(env_remote)
        if rc == 0 and out.strip() == "1":
            echo(f"{G}OK{NC}")
        else:
            echo(f"{R}FAIL{NC}")
            status_warn("Cannot connect to remote cloud DB. Check your connection URL or network.")
    else:
        echo(f"{Y}SKIPPED (psql not found){NC}")
    echo()


def _build_remote_parser(subparsers, common):
    p = subparsers.add_parser("remote", help="Manage remote cloud database configuration", parents=[common])
    p.add_argument("remote_action", nargs="?", default="show", choices=["show", "set-url", "remove", "unset", "rm"],
                   help="Action: show (default), set-url, remove")
    p.add_argument("url", nargs="?", default=None, help="Connection URL (for set-url)")
    p.add_argument("--json", action="store_true", help="Output JSON result")
    return p


command("remote", "Manage remote cloud database configuration", build=_build_remote_parser)(cmd_remote)
