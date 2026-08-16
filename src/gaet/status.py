"""cmd_check / cmd_status / cmd_diff / cmd_doctor — health & sync reporting."""

import argparse
import datetime
import json
import re
import sys
import time
from typing import Any, Dict, Tuple
from pathlib import Path
from .core import Any, B, BACKUP_DIR, C, D, DEF_REMOTE_SSLMODE, DEF_SERVICE_PREFIX, Dict, ENV_FILE, EXIT_CONFIG, EXIT_LOCAL_DOWN, EXIT_TOOLS, G, ICON_FAIL, ICON_OK, ICON_WARN, NAME, NC, R, Tuple, Y, _validate_table_name, argparse, box_section, box_title, cleanup_pg_env, datetime, die, draw_colored_table, echo, find_pg_tools, get_env_str, get_local_db, get_tables, json, load_env, parse_remote_url, pg_env, re, run_cmd, scheduler_is_active, set_output_modes, status_arrow, status_fail, status_ok, status_warn, sys, time

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
        [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
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

def cmd_doctor(args: argparse.Namespace) -> None:
    """Check gaet health: config, DB connections, tools, recent backups."""
    want_json = getattr(args, "json", False)
    issues = 0
    result = {"checks": {}, "ok": True}

    env = load_env()

    # 1. Config
    config_ok = ENV_FILE.is_file()
    result["checks"]["config"] = {"ok": config_ok, "path": str(ENV_FILE)}
    if not config_ok:
        issues += 1

    # 2. PostgreSQL tools
    tools = find_pg_tools(env)
    tools_ok = all(tools.get(t) for t in ("pg_dump", "pg_restore", "psql"))
    result["checks"]["tools"] = {
        "ok": tools_ok,
        "pg_dump": tools.get("pg_dump", ""),
        "pg_restore": tools.get("pg_restore", ""),
        "psql": tools.get("psql", ""),
    }
    if not tools_ok:
        issues += 1

    # 3. Local DB connection
    h, p, u, n, w = get_local_db(env)
    psql = tools.get("psql", "")
    local_ok = False
    local_size = ""
    if psql and h:
        env_dict = pg_env(u, w)
        out, _, rc = run_cmd(
            [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
            env=env_dict, timeout=5,
        )
        if rc == 0 and out.strip() == "1":
            local_ok = True
            size_out, _, _ = run_cmd(
                [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1)||' MB';"],
                env=env_dict, timeout=5,
            )
            local_size = size_out.strip()
        cleanup_pg_env(env_dict)
    result["checks"]["local_db"] = {
        "ok": local_ok,
        "host": h, "port": p, "user": u, "database": n,
        "size": local_size,
    }
    if not local_ok:
        issues += 1

    # 4. Cloud DB connection
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)
    cloud_ok = False
    cloud_size = ""
    cloud_configured = bool(parsed)
    if parsed:
        ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
        env_dict = pg_env(parsed["user"], parsed["pass"], ssl)
        out, _, rc = run_cmd(
            [psql, "-w", "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc", "SELECT 1;"],
            env=env_dict, timeout=10,
        )
        if rc == 0 and out.strip() == "1":
            cloud_ok = True
            size_out, _, _ = run_cmd(
                [psql, "-w", "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"], "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1)||' MB';"],
                env=env_dict, timeout=10,
            )
            cloud_size = size_out.strip()
        cleanup_pg_env(env_dict)
    result["checks"]["cloud_db"] = {
        "ok": cloud_ok,
        "configured": cloud_configured,
        "size": cloud_size,
    }
    if not cloud_ok:
        issues += 1

    # 5. Recent backups
    backup_count = 0
    backup_newest = ""
    backup_total_mb = 0.0
    backup_age_days = 0
    try:
        backups = sorted(BACKUP_DIR.glob("gaet_*.dump"), reverse=True)
        backup_count = len(backups)
        if backups:
            newest = backups[0]
            backup_age_days = (time.time() - newest.stat().st_mtime) / 86400
            backup_total_mb = sum(f.stat().st_size for f in backups) / (1024 * 1024)
            backup_newest = newest.name
            if backup_age_days > 7:
                issues += 1
        else:
            issues += 1
    except OSError:
        issues += 1
    result["checks"]["backups"] = {
        "ok": backup_count > 0,
        "count": backup_count,
        "newest": backup_newest,
        "age_days": round(backup_age_days, 1),
        "total_mb": round(backup_total_mb, 1),
    }

    # 6. Auto-backup
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
    auto_active = scheduler_is_active(prefix)
    result["checks"]["auto_backup"] = {"ok": auto_active, "active": auto_active}
    if not auto_active:
        issues += 1

    result["ok"] = issues == 0
    result["issues"] = issues

    if want_json:
        print(json.dumps(result, indent=2))
        return

    # Human-readable output
    box_title(f"{NAME} doctor")

    box_section("Config")
    if config_ok:
        status_ok(f"Config file: {ENV_FILE}")
    else:
        echo(f"    {R}{ICON_FAIL}{NC} Config file not found")
        echo(f"    {D}Run: gaet init{NC}")

    box_section("PostgreSQL Tools")
    for name in ("pg_dump", "pg_restore", "psql"):
        if tools.get(name):
            status_ok(f"{name} found")
        else:
            echo(f"    {R}{ICON_FAIL}{NC} {name} not found")
    if not tools_ok:
        echo(f"    {D}Install PostgreSQL client tools: apt install postgresql-client{NC}")

    box_section("Local Database")
    if local_ok:
        echo(f"    {G}Testing {u}@{h}:{p}/{n}...{NC} {G}OK{NC}")
        if local_size:
            status_arrow(f"Size: {local_size}")
    else:
        echo(f"    {R}Cannot connect{NC}")
        echo(f"    {D}Check PostgreSQL is running and credentials are correct{NC}")

    box_section("Cloud Database")
    if cloud_ok:
        echo(f"    {G}Testing cloud connection...{NC} {G}OK{NC}")
        if cloud_size:
            status_arrow(f"Size: {cloud_size}")
    elif cloud_configured:
        echo(f"    {R}FAIL{NC}")
        echo(f"    {D}Check GAET_REMOTE_URL and cloud database status{NC}")
    else:
        echo(f"    {Y}Not configured{NC}")
        status_arrow("Set GAET_REMOTE_URL to enable cloud backup")

    box_section("Backups")
    if backup_count:
        echo(f"    {G}Found {backup_count} backup(s){NC}")
        status_arrow(f"Newest: {backup_newest} ({backup_age_days:.0f} days ago)")
        status_arrow(f"Total: {backup_total_mb:.1f} MB")
    else:
        echo(f"    {Y}No backups found{NC}")
        status_arrow("Run 'gaet push' to create your first backup")

    box_section("Auto-backup")
    if auto_active:
        status_ok("Auto-backup is active")
    else:
        echo(f"    {D}Auto-backup not active (run 'gaet push --auto' to enable){NC}")

    echo()
    if issues == 0:
        echo(f"  {G}{ICON_OK}{NC}  All checks passed!")
    else:
        echo(f"  {Y}{ICON_WARN}{NC}  {issues} issue(s) found")

def cmd_diff(args: argparse.Namespace) -> None:
    """Compare local vs cloud database tables and row counts."""
    want_json = getattr(args, "json", False)
    env = load_env()
    tools = find_pg_tools(env)
    psql = tools.get("psql", "")
    if not psql:
        die("psql not found")

    h, p, u, n, w = get_local_db(env)
    remote_url = get_env_str(env, "GAET_REMOTE_URL") or get_env_str(env, "GAET_SUPABASE_URL") or ""
    parsed = parse_remote_url(remote_url)
    if not parsed:
        die("GAET_REMOTE_URL not configured. Run: gaet init", EXIT_CONFIG)

    # Collect local counts
    local_counts = {}
    tables = get_tables(env, tools)
    if tables and psql:
        safe = [t for t in tables if _validate_table_name(t)]
        if safe:
            union = " UNION ALL ".join(
                f"SELECT '{t}'::text as tbl, count(*)::int FROM public.{t}" for t in safe
            )
            out, _, rc = run_cmd(
                [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", union],
                env={"PGPASSWORD": w}, timeout=30,
            )
            if rc == 0:
                for line in out.strip().split("\n"):
                    if "|" in line:
                        parts = line.split("|")
                        try:
                            local_counts[parts[0].strip()] = int(parts[1].strip())
                        except ValueError:
                            pass

    # Collect remote counts
    remote_counts = {}
    ssl = get_env_str(env, "GAET_REMOTE_SSLMODE", DEF_REMOTE_SSLMODE)
    if tables and psql:
        safe = [t for t in tables if _validate_table_name(t)]
        if safe:
            union = " UNION ALL ".join(
                f"SELECT '{t}'::text as tbl, count(*)::int FROM public.{t}" for t in safe
            )
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

    all_tables = sorted(set(list(local_counts.keys()) + list(remote_counts.keys())))

    # Build result
    tables_result = []
    synced = 0
    for t in all_tables:
        lo = local_counts.get(t, 0)
        re = remote_counts.get(t, 0)
        diff = lo - re
        if diff == 0:
            synced += 1
        tables_result.append({
            "table": t,
            "local": lo,
            "remote": re,
            "diff": diff,
            "in_sync": diff == 0,
        })

    result = {
        "tables": tables_result,
        "total": len(all_tables),
        "synced": synced,
        "unsynced": len(all_tables) - synced,
    }

    if want_json:
        print(json.dumps(result, indent=2))
        return

    # Human-readable
    box_title(f"{NAME} diff")

    if not all_tables:
        echo(f"  {Y}No tables found.{NC}")
        return

    rows = []
    for t in all_tables:
        lo = local_counts.get(t, 0)
        re = remote_counts.get(t, 0)
        diff = lo - re
        if diff == 0:
            icon = f"{G}= same{NC}"
        elif diff > 0:
            icon = f"{Y}+{diff} local{NC}"
        else:
            icon = f"{R}{diff} cloud{NC}"
        rows.append(f"{t}|{lo}|{re}|{icon}")

    echo(f"  {B}Table          Local    Cloud    Diff{NC}")
    echo(f"  {D}\u2500" * 45)
    for row in rows:
        parts = row.split("|")
        echo(f"  {parts[0]:14} {parts[1]:>6}  {parts[2]:>6}  {parts[3]}")

    echo()
    echo(f"  {D}{synced}/{len(all_tables)} tables in sync{NC}")

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
        env_dict = pg_env(u, w)
        out, _, rc = run_cmd(
            [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
            env=env_dict,
            timeout=5,
        )
        if rc == 0 and out.strip() == "1":
            echo(f"{G}OK{NC}")
            size_out, _, _ = run_cmd(
                [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1) || ' MB';"],
                env=env_dict,
                timeout=5,
            )
            status_arrow(f"Size: {size_out}")
        else:
            echo(f"{R}FAIL{NC}")
            status_arrow(f"Tidak dapat terhubung ke {h}:{p}/{n} (jalankan 'gaet init' untuk perbarui)")
            result["ok"] = False
        cleanup_pg_env(env_dict)
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
        env_dict = pg_env(parsed["user"], parsed["pass"], ssl)
        out, _, rc = run_cmd(
            [psql, "-w", "-h", parsed["host"], "-p", parsed["port"],
             "-U", parsed["user"], "-d", parsed["db"], "-tAc", "SELECT 1;"],
            env=env_dict,
            timeout=10,
        )
        if rc == 0 and out.strip() == "1":
            echo(f"{G}OK{NC}")
            size_out, _, _ = run_cmd(
                [psql, "-w", "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"], "-tAc",
                 "SELECT round(pg_database_size(current_database())/1024.0/1024.0,1) || ' MB';"],
                env=env_dict,
                timeout=10,
            )
            status_arrow(f"Size: {size_out}")
        else:
            echo(f"{R}FAIL{NC}")
            result["ok"] = False
        cleanup_pg_env(env_dict)
    else:
        echo(f"{Y}LEWAT{NC}")
        status_arrow(f"Set GAET_REMOTE_URL di {ENV_FILE}")
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

def cmd_completion(args: argparse.Namespace) -> None:
    """Generate shell completions."""
    shell = args.shell
    # completions live beside the install root: ~/.local/bin/completions when
    # installed, <repo>/completions when running from a source checkout
    # (src-layout: __file__ = <root>/src/gaet/status.py, so candidates are
    # .parent.parent for installed and .parent.parent.parent for source).
    _here = Path(__file__).resolve().parent
    script_dir = next(
        (c / "completions" for c in (_here.parent, _here.parent.parent)
         if (c / "completions").is_dir()),
        _here.parent / "completions",
    )
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
            shell_name = comp_file.suffix.lstrip(".")
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

# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_status_parser(subparsers, common):
    p = subparsers.add_parser("status", help="Show sync status", parents=[common])
    p.add_argument("--json", action="store_true", help="Output JSON")
    return p


def _build_check_parser(subparsers, common):
    p = subparsers.add_parser("check", help="Validate config & connections", parents=[common])
    p.add_argument("--json", action="store_true", help="Output JSON (machine-readable)")
    return p


def _build_diff_parser(subparsers, common):
    p = subparsers.add_parser("diff", help="Compare local vs cloud tables", parents=[common])
    p.add_argument("--json", action="store_true", help="JSON output")
    return p


def _build_doctor_parser(subparsers, common):
    p = subparsers.add_parser("doctor", help="Check gaet health and connections", parents=[common])
    p.add_argument("--json", action="store_true", help="JSON output")
    return p


def _build_completion_parser(subparsers, common):
    p = subparsers.add_parser("completion", help="Generate shell completions", parents=[common])
    p.add_argument("--shell", "-s", choices=["bash", "zsh", "fish"], default=None,
                   help="Shell (auto-detect if omitted)")
    return p


command("status", "Show sync status", build=_build_status_parser)(cmd_status)
command("check", "Validate config & connections", build=_build_check_parser)(cmd_check)
command("diff", "Compare local vs cloud tables", build=_build_diff_parser)(cmd_diff)
command("doctor", "Check gaet health and connections", build=_build_doctor_parser)(cmd_doctor)
command("completion", "Generate shell completions", build=_build_completion_parser)(cmd_completion)


