"""cmd_init interactive wizard + preset database definitions."""

import argparse
import datetime
import os
import shutil
import sys
from typing import Dict, Optional, Tuple

from .core import (
    _build_env_content,
    _ensure_git_workspace,
    _print_summary,
    _save_init_config,
    _write_env_file,
    argparse,
    B,
    BACKUP_DIR,
    box_section,
    box_title,
    C,
    cleanup_pg_env,
    D,
    datetime,
    DEF_RETENTION_DAYS,
    Dict,
    die,
    echo,
    ENV_FILE,
    find_pg_tools,
    G,
    GAET_DIR,
    get_env_str,
    get_local_db,
    load_env,
    mask_url_password,
    NAME,
    NC,
    Optional,
    os,
    parse_remote_url,
    pg_env,
    print_docs_footer,
    R,
    run_cmd,
    safe_getpass,
    safe_input,
    shutil,
    status_fail,
    status_info,
    status_ok,
    sys,
    Tuple,
    Y,
)
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


def _explain_connection_failure(err: str, host: str, port: str, user: str, db: str) -> str:
    """Translate psql stderr output into friendly, actionable human explanation."""
    err_lower = err.lower()
    if "no password supplied" in err_lower or "password authentication failed" in err_lower:
        return f"Password for user '{user}' is incorrect or missing."
    elif "role" in err_lower and "does not exist" in err_lower:
        return f"User '{user}' does not exist on this PostgreSQL system."
    elif "database" in err_lower and "does not exist" in err_lower:
        return f"Database '{db}' does not exist. Create it first using: createdb -U {user} {db}"
    elif "could not connect to server" in err_lower or "connection refused" in err_lower or "name or service not known" in err_lower:
        return f"PostgreSQL server is down or host/port '{host}:{port}' is unreachable."
    elif "peer authentication failed" in err_lower:
        return f"OS user authentication failed for user '{user}'. Try specifying a password manually."
    elif err.strip():
        return err.strip()
    return "Connection to PostgreSQL failed."


def _test_connection(psql: str, h: str, p: str, u: str, n: str, w: str) -> Tuple[bool, str]:
    """Test local PostgreSQL database connection safely using PGPASSFILE."""
    env_dict = pg_env(u, w)
    out, err, rc = run_cmd(
        [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
        env=env_dict,
        timeout=5,
    )
    cleanup_pg_env(env_dict)
    ok = (rc == 0 and out.strip() == "1")
    return ok, err


def _select_db_from_instance(inst: Dict[str, str]) -> str:
    """Prompt user to choose a database from detected databases in the chosen instance."""
    dbs_raw = inst.get("databases", "")
    db_list = [d.strip() for d in dbs_raw.split(",") if d.strip()]
    if not db_list:
        return inst.get("default_db", "postgres")
    if len(db_list) == 1:
        return db_list[0]

    default_db = inst.get("default_db", "")
    default_idx = "1"
    if default_db in db_list:
        default_idx = str(db_list.index(default_db) + 1)

    echo()
    echo(f"  {B}Select database to gaet:{NC}")
    for idx, dname in enumerate(db_list, 1):
        mark = f" {G}(default){NC}" if dname == default_db else ""
        echo(f"  {C}[{idx}]{NC}  {dname}{mark}")
    echo(f"  {C}[M]{NC}  Type another database name")
    echo()

    choice = safe_input(f"  Select database [1-{len(db_list)}] (default: [{default_idx}] {db_list[int(default_idx)-1]}): ").strip()
    if not choice:
        return db_list[int(default_idx) - 1]
    if choice.isdigit():
        d_idx = int(choice) - 1
        if 0 <= d_idx < len(db_list):
            return db_list[d_idx]
    if choice.upper() == "M":
        custom = safe_input("  Database name: ").strip()
        if custom:
            return custom
    return choice if choice else db_list[int(default_idx) - 1]


def _local_db_menu(detected, cur_host, cur_port, cur_user, cur_db, cur_pass) -> Tuple[str, str, str, str, str]:
    """Interactive single-tier menu for local DB setup with direct numbered selection."""
    while True:
        echo()
        box_section("Step 1/3: Local Database Setup")

        num_detected = len(detected)
        if num_detected > 0:
            echo(f"  {B}Detected PostgreSQL instances:{NC}")
            for i, inst in enumerate(detected, 1):
                host_display = inst['host']
                if host_display.startswith('/'):
                    host_display = f"socket:{host_display}"
                echo(f"  {C}[{i}]{NC}  {inst['user']}@{host_display}:{inst['port']}")
                echo(f"       {D}Databases: {inst['databases']}{NC}")
            echo()
            echo(f"  {B}Other options:{NC}")

        if cur_host:
            echo(f"  {C}[E]{NC}  Use current configuration ({cur_user}@{cur_host}:{cur_port}/{cur_db})")
        echo(f"  {C}[U]{NC}  Paste connection URL (postgresql://user:pass@host:port/db)")
        echo(f"  {C}[M]{NC}  Manual input (host, port, user, db, password)")
        echo(f"  {C}[D]{NC}  Use default (127.0.0.1:5432, user: postgres, db: postgres)")
        echo(f"  {C}[Q]{NC}  Quit setup wizard")
        echo()

        default_choice = "1" if num_detected > 0 else ("E" if cur_host else "D")
        choice = safe_input(f"  Select option [{default_choice}]: ").strip()
        if not choice:
            choice = default_choice

        # Directly select numbered instance if user typed a number
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < num_detected:
                inst = detected[idx]
                h = inst["host"]
                p = inst["port"]
                u = inst["user"]
                n = _select_db_from_instance(inst)
                w = ""
                host_disp = f"socket:{h}" if h.startswith('/') else h
                echo(f"  {G}✓{NC} Selected: {u}@{host_disp}:{p}/{n}")
                return h, p, u, n, w
            else:
                echo(f"  {R}Invalid number option (choose 1-{num_detected}).{NC}")
                continue

        ch = choice.upper()
        if ch == "Q":
            echo(f"  {Y}Init cancelled by user.{NC}")
            sys.exit(0)
        elif ch == "E" and cur_host:
            echo(f"  {G}✓{NC} Using current config: {cur_user}@{cur_host}:{cur_port}/{cur_db}")
            return cur_host, cur_port, cur_user, cur_db, cur_pass
        elif ch == "U":
            return _url_input()
        elif ch == "M":
            return _manual_db_input()
        elif ch == "D":
            h = "127.0.0.1"
            p = "5432"
            u = cur_user or "postgres"
            n = cur_db or "postgres"
            w = cur_pass or ""
            echo(f"  {G}✓{NC} Selected default: {u}@{h}:{p}/{n}")
            return h, p, u, n, w
        else:
            echo(f"  {R}Invalid option '{choice}'.{NC}")


def _url_input() -> Tuple[str, str, str, str, str]:
    """Input via connection URL. Returns (host, port, user, db, passwd)."""
    echo(f"  {D}Format: postgresql://user:password@host:5432/dbname{NC}")
    url = safe_input("  URL: ").strip()
    if url:
        parsed = parse_remote_url(url)
        if parsed:
            return parsed["host"], parsed["port"], parsed["user"], parsed["db"], parsed["pass"]
        else:
            echo(f"  {Y}Could not parse URL, falling back to manual input.{NC}")
    return _manual_db_input()


def _manual_db_input() -> Tuple[str, str, str, str, str]:
    """Manual field-by-field input with smart defaults."""
    echo(f"  {B}Local Database Parameters Input:{NC}")
    h = safe_input(f"    Host [127.0.0.1]: ").strip() or "127.0.0.1"
    p = safe_input(f"    Port [5432]: ").strip() or "5432"
    u = safe_input(f"    User [postgres]: ").strip() or "postgres"
    n = safe_input(f"    Database [postgres]: ").strip() or "postgres"
    w = safe_getpass(f"    Password []: ").strip()
    return h, p, u, n, w


def _cmd_init_inner(args: argparse.Namespace) -> None:
    """Internal setup wizard execution."""
    env = load_env()
    box_title(f"{NAME} init — Setup Wizard")

    # Non-interactive mode: use existing config or detected defaults, skip prompts
    _is_hermes = any(k.startswith("HERMES_") for k in os.environ.keys())
    _is_ci = os.environ.get("CI") == "true" or os.environ.get("CONTAINER") == "1"
    is_interactive = sys.stdin.isatty() and not _is_hermes and not _is_ci

    if not is_interactive:
        echo(f"  {Y}⚠ Non-interactive mode detected — applying configuration.{NC}")
        echo()

        # Preserve existing local DB config if present
        cur_host, cur_port, cur_user, cur_db, cur_pass = get_local_db(env)
        if cur_host:
            h, p, u, n, w = cur_host, cur_port, cur_user, cur_db, cur_pass
            echo(f"  {G}✓{NC} Preserved existing local DB config: {u}@{h}:{p}/{n}")
        else:
            # Fallback to detection or 127.0.0.1
            h, p, u, n, w = "127.0.0.1", "5432", "postgres", "postgres", ""
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
                    echo(f"  {G}✓{NC} Auto-detected local PG: {u}@{h}:{p}/{n}")
                else:
                    echo(f"  {Y}⚠{NC} No local PostgreSQL detected, using default 127.0.0.1:5432")
            else:
                echo(f"  {Y}⚠{NC} psql tool not found, using default 127.0.0.1:5432")

        old_remote = env.get("GAET_REMOTE_URL") or env.get("GAET_SUPABASE_URL") or ""
        remote_url = old_remote if old_remote else ""

        default_ret = env.get("GAET_RETENTION_DAYS", str(DEF_RETENTION_DAYS))

        _save_init_config(h, p, u, n, w, remote_url, default_ret)
        status_ok(f"Config initialized at {ENV_FILE}")
        return

    # --- Interactive Wizard Flow ---
    preset_name = getattr(args, "preset_flag", None)
    if not preset_name:
        preset_raw = getattr(args, "preset", None)
        preset_name = "-".join(preset_raw) if preset_raw else None
    preset: Optional[Dict[str, str]] = None
    if preset_name:
        preset = PRESETS.get(preset_name.lower())
        if not preset:
            die(f"Preset '{preset_name}' not found. Available presets: {', '.join(PRESETS.keys())}")
        echo(f"  {C}📋{NC}  Preset: {preset.get('description', preset_name)}")

    # Check PostgreSQL Client Tools
    box_section("PostgreSQL Tools Check")
    tools = find_pg_tools(env)
    all_tools_ok = True
    for name in ("pg_dump", "pg_restore", "psql"):
        path = tools.get(name, "")
        if path:
            status_ok(f"{name:12} {D}\"{path}\"{NC}")
        else:
            status_fail(f"{name:12} not found in PATH")
            all_tools_ok = False

    if not all_tools_ok:
        echo(f"  {Y}Warning: Install postgresql-client so gaet can perform dumps & restores.{NC}")

    GAET_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Backup existing config before overwriting
    if ENV_FILE.is_file():
        backup_path = GAET_DIR / f".env.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copy2(str(ENV_FILE), str(backup_path))
            status_info(f"Existing config backed up to: {backup_path.name}")
        except OSError:
            pass

    # Step 1: Local Database
    psql = tools.get("psql", "")
    detected = []
    if psql:
        status_info("Scanning local PostgreSQL instances...")
        detected = detect_local_pg(psql)

    cur_host, cur_port, cur_user, cur_db, cur_pass = get_local_db(env)
    old_remote = env.get("GAET_REMOTE_URL") or env.get("GAET_SUPABASE_URL") or ""

    h, p, u, n, w = "", "", "", "", ""

    if preset:
        u = preset.get("local_user", "postgres")
        n = preset.get("local_db", "postgres")
        w = preset.get("local_pass", "")
        echo(f"  {D}Preset '{preset_name}': user={u}, db={n}{NC}")

        if detected:
            echo()
            for i, inst in enumerate(detected, 1):
                echo(f"  {C}[{i}]{NC}  {inst['user']}@{inst['host']}:{inst['port']} (Databases: {inst['databases']})")
            echo(f"  {C}[0]{NC}  Default (127.0.0.1:5432)")
            echo()

            choice = safe_input(f"  Select instance [1]: ").strip() or "1"
            if choice.isdigit() and 1 <= int(choice) <= len(detected):
                inst = detected[int(choice) - 1]
                h = inst["host"]
                p = inst["port"]
            else:
                h = "127.0.0.1"
                p = "5432"
        else:
            h = "127.0.0.1"
            p = "5432"
        echo(f"  {G}✓{NC} Preset target: {u}@{h}:{p}/{n}")

    else:
        # Standard interactive selection
        h, p, u, n, w = _local_db_menu(detected, cur_host, cur_port, cur_user, cur_db, cur_pass)

    # Test Local DB Connection
    echo()
    conn_ok = False
    if psql and h:
        host_disp = f"socket:{h}" if h.startswith('/') else f"{h}:{p}"
        echo(f"  {C}💾{NC}  Testing connection to {u}@{host_disp}/{n}... ", end="")
        ok, err_msg = _test_connection(psql, h, p, u, n, w)
        if ok:
            echo(f"{G}OK{NC}")
            conn_ok = True
        else:
            echo(f"{R}FAIL{NC}")
            explanation = _explain_connection_failure(err_msg, h, p, u, n)
            echo(f"  {Y}└─ Explanation: {explanation}{NC}")

            if sys.stdin.isatty():
                retry = safe_input(f"  Fix local connection input now? [Y/n]: ").strip().lower()
                if retry in ("", "y", "yes"):
                    h, p, u, n, w = _manual_db_input()
                    echo(f"  {C}💾{NC}  Retesting {u}@{h}:{p}/{n}... ", end="")
                    ok2, err_msg2 = _test_connection(psql, h, p, u, n, w)
                    if ok2:
                        echo(f"{G}OK{NC}")
                        conn_ok = True
                    else:
                        echo(f"{R}FAIL{NC}")
                        echo(f"  {Y}└─ Explanation: {_explain_connection_failure(err_msg2, h, p, u, n)}{NC}")

            if not conn_ok:
                echo(f"  {Y}Warning: Configuration saved despite connection failure.{NC}")
                echo(f"  {D}You can fix it anytime via 'gaet set' or 'gaet init'.{NC}")

    # Step 2: Remote / Cloud Database Setup
    echo()
    box_section("Step 2/3: Cloud / Remote Database (Optional)")
    echo(f"  {D}Enter target cloud PostgreSQL connection URL (Supabase/Neon/RDS/VPS).{NC}")
    echo(f"  {D}Leave blank (press Enter) if you don't want to configure it yet.{NC}")
    cur_remote_prompt = 'already set' if old_remote else 'empty'
    remote_url = safe_input(f"  GAET_REMOTE_URL [{cur_remote_prompt}]: ").strip()
    if not remote_url:
        remote_url = old_remote

    # Step 3: Retention & Backup Settings
    echo()
    box_section("Step 3/3: Backup & Retention Settings")
    default_ret = env.get("GAET_RETENTION_DAYS", str(DEF_RETENTION_DAYS))
    ret_inp = safe_input(f"  Backup Retention Period (days) [{default_ret}]: ").strip()
    ret = ret_inp or default_ret

    tables_line = ""
    if preset and "tables" in preset:
        tables_line = f"GAET_TABLES={preset['tables']}"

    env_content = _build_env_content(
        h, p, u, n, w, remote_url, ret, tables_line=tables_line,
        header="Gaet Main Configuration",
    )

    _write_env_file(env_content)
    echo()
    status_ok(f"Configuration saved successfully to: {ENV_FILE}")

    if _ensure_git_workspace():
        status_ok(f"Git-versioned gaet workspace activated ({GAET_DIR})")

    echo()
    box_section("Initialization Summary")
    env = load_env()
    tools = find_pg_tools(env)
    _print_summary(env, tools)
    echo()
    status_ok("Gaet init complete! Run 'gaet status' to check synchronization.")
    print_docs_footer()


def cmd_init(args: argparse.Namespace) -> None:
    """Interactive setup wizard with global signal guard."""
    try:
        _cmd_init_inner(args)
    except (KeyboardInterrupt, EOFError):
        echo()
        echo(f"  {Y}gaet init cancelled by user.{NC}")
        sys.exit(0)


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
