"""cmd_init interactive wizard + preset database definitions."""

import argparse
import datetime
import os
import shutil
import sys
from typing import Dict, Optional, Tuple
from .core import _print_summary, B, BACKUP_DIR, C, D, DEF_RETENTION_DAYS, Dict, ENV_FILE, G, GAET_DIR, NAME, NC, Optional, R, Tuple, Y, _build_env_content, _ensure_git_workspace, _save_init_config, _write_env_file, argparse, box_section, box_title, datetime, die, echo, find_pg_tools, get_env_str, get_local_db, load_env, mask_url_password, os, parse_remote_url, run_cmd, safe_getpass, safe_input, shutil, status_fail, status_info, status_ok, sys
from .detect import detect_local_pg

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

    # Non-interactive mode: use defaults and skip prompts
    # Detect constrained environments: no TTY, CI, or Hermes desktop app
    _is_hermes = any(k.startswith("HERMES_") for k in os.environ.keys())
    _is_ci = os.environ.get("CI") == "true" or os.environ.get("CONTAINER") == "1"
    is_interactive = sys.stdin.isatty() and not _is_hermes and not _is_ci
    if not is_interactive:
        echo(f"  {Y}⚠ Non-interactive mode detected — using defaults.{NC}")
        echo()
        
        # Use sensible defaults
        h, p, u, n, w = "127.0.0.1", "5432", "postgres", "postgres", ""
        
        # Try to detect local PostgreSQL if tools available
        tools = find_pg_tools(env)
        psql = tools.get("psql", "")
        if psql:
            detected = detect_local_pg(psql)
            if detected:
                inst = detected[0]
                h = inst["host"]
                p = inst["port"]
                u = inst["user"]
                n = inst.get("default_db", "postgres")
                echo(f"  {G}✓{NC} Auto-detected: {u}@{h}:{p}/{n}")
            else:
                echo(f"  {Y}⚠{NC} No PostgreSQL detected, using defaults")
        else:
            echo(f"  {Y}⚠{NC} pg_tool not found, using defaults")
        
        # Get remote URL from existing config or prompt for it
        old_remote = env.get("GAET_REMOTE_URL") or env.get("GAET_SUPABASE_URL") or ""
        if old_remote:
            echo(f"  {G}✓{NC} Using existing remote URL from config")
            remote_url = old_remote
        else:
            echo(f"  {D}Note: Set GAET_REMOTE_URL to enable cloud backup.{NC}")
            echo(f"      Example: gaet set GAET_REMOTE_URL=postgresql://...")
            remote_url = ""
        
        # Get retention days
        default_ret = env.get("GAET_RETENTION_DAYS", str(DEF_RETENTION_DAYS))
        
        # Build and save config
        _save_init_config(h, p, u, n, w, remote_url, default_ret)
        return

    # Interactive mode continues below...

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

        # Build config content — socket hosts become individual vars
        # (see _local_config_lines); plain KEY=value lines, no indentation.
        env_content = _build_env_content(
            h, p, u, n, w, remote_url, ret, tables_line=tables_line,
            header="Konfigurasi",
        )

        _write_env_file(env_content)
        echo()
        status_ok(f"Config saved to {ENV_FILE}")

    if _ensure_git_workspace():
        status_ok(f"Workspace versioned with git ({GAET_DIR})")

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

# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_init_parser(subparsers, common):
    p = subparsers.add_parser("init", help="Interactive setup wizard", parents=[common])
    p.add_argument("preset", nargs="*", default=None,
                   help="Preset database (contoh: hindsight, hindsight hermes)")
    p.add_argument("--preset", dest="preset_flag", default=None,
                   help="Preset database (contoh: --preset hindsight)")
    return p


command("init", "Interactive setup wizard", build=_build_init_parser)(cmd_init)

