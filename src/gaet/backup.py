"""cmd_push / cmd_fetch — backup & restore between local and cloud."""

import argparse
import datetime
import json
import sys
import time
import urllib
from typing import Any, Dict, Optional, Tuple
from .core import Any, B, BACKUP_DIR, C, D, DEF_AUTO_INTERVAL, DEF_PG_TIMEOUT, DEF_REMOTE_SSLMODE, DEF_RETENTION_DAYS, Dict, ENV_FILE, EXIT_CLOUD_DOWN, EXIT_CONFIG, EXIT_LOCAL_DOWN, G, ICON_FAIL, ICON_OK, NC, Optional, Path, R, Spinner, Tuple, Y, acquire_lock, argparse, box_section, box_title, cleanup_pg_env, cronlog, datetime, die, echo, find_pg_tools, get_env_int, get_env_str, get_local_db, get_tables, json, load_env, log, parse_remote_url, pg_env, print_push_summary, release_lock, run_cmd, safe_input, set_output_modes, status_arrow, status_info, status_ok, status_warn, sys, time, urllib
from .status import check_local_db, check_tools
from .scheduler import cmd_auto_on

def _reset_target_objects(
    psql: str, host: str, port: str, user: str, db: str, passwd: str,
    ssl_mode: Optional[str] = None,
) -> Tuple[bool, str]:
    """Drop all user objects (tables, views, sequences) in the target DB.

    Uses DROP ... CASCADE so partitioned tables and inherited constraints
    are removed cleanly — unlike pg_restore --clean --if-exists, which
    fails on partitioned tables ("cannot drop inherited constraint").

    Returns (ok, error_message).
    """
    sql = (
        "DO $$ DECLARE r record; BEGIN "
        "FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname='public') "
        "LOOP EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename); END LOOP; "
        "FOR r IN (SELECT viewname FROM pg_views WHERE schemaname='public') "
        "LOOP EXECUTE format('DROP VIEW IF EXISTS public.%I CASCADE', r.viewname); END LOOP; "
        "FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public') "
        "LOOP EXECUTE format('DROP SEQUENCE IF EXISTS public.%I CASCADE', r.sequence_name); END LOOP; "
        "FOR r IN (SELECT typname FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
        "WHERE n.nspname='public' AND t.typtype IN ('e','c','d','r') "
        "AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=t.oid AND d.deptype='e')) "
        "LOOP EXECUTE format('DROP TYPE IF EXISTS public.%I CASCADE', r.typname); END LOOP; "
        "FOR r IN (SELECT p.oid::regprocedure AS sig FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='public' AND p.prokind IN ('f','p')) "
        "LOOP EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.sig); END LOOP; "
        "END $$;"
    )
    env = pg_env(user, passwd, ssl_mode)
    try:
        out, err, rc = run_cmd(
            [psql, "-w", "-h", host, "-p", port, "-U", user, "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql],
            env=env,
            timeout=30,
        )
        if rc != 0:
            return False, err or out
        return True, ""
    finally:
        cleanup_pg_env(env)

def cmd_push(args: argparse.Namespace) -> None:
    """Backup local → cloud."""
    dry_run = getattr(args, "dry_run", False)
    want_json = getattr(args, "json", False)
    if want_json:
        set_output_modes(quiet=True, plain=True)
    result: Dict[str, Any] = {"command": "push", "ok": False}

    # ── auto / cron modes (mirrors the former monolith dispatch) ──
    if getattr(args, "cron", False):
        env = load_env()
        cmd_push_cron(env)
        return
    if getattr(args, "auto", None) is not None:
        # --auto without value defaults to GAET_AUTO_INTERVAL
        if args.auto == 0:
            env = load_env()
            args.auto = get_env_int(env, "GAET_AUTO_INTERVAL", DEF_AUTO_INTERVAL)
        cmd_auto_on(args)
        return

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
        psql = tools["psql"]

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

        log("🚀 Push: local -> cloud")
        box_title("gaet push")
        pg_dump = tools["pg_dump"]
        pg_restore = tools["pg_restore"]

        # Step 1: Local dump
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        echo(f"  {C}📦{NC}  {B}Dumping local database...{NC}")
        backup_file = str(BACKUP_DIR / f"gaet_{timestamp}.dump")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        spinner = Spinner("Dumping local database").start()
        env_dict = pg_env(u, w)
        try:
            out, err, rc = run_cmd(
                [pg_dump, "-w", "-h", h, "-p", p, "-U", u, "-d", n,
                 "--format=custom", "--compress=9", f"--file={backup_file}"],
                env=env_dict,
                timeout=get_env_int(env, "GAET_PG_TIMEOUT", DEF_PG_TIMEOUT),
            )
        finally:
            cleanup_pg_env(env_dict)
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
        # Drop existing objects first (handles partitioned tables; --clean can't)
        ok_reset, reset_err = _reset_target_objects(
            psql, parsed["host"], parsed["port"], parsed["user"],
            parsed["db"], parsed["pass"], ssl,
        )
        if not ok_reset:
            echo(f"    {R}{ICON_FAIL}{NC}  Gagal membersihkan cloud database")
            if reset_err:
                echo(f"    {D}{reset_err[:200]}{NC}")
            result["sync"] = {"ok": False, "error": "reset"}
            die("Sinkronisasi cloud gagal (reset target)", EXIT_CLOUD_DOWN)
        spinner = Spinner("Syncing to cloud").start()
        env_cloud = pg_env(parsed["user"], parsed["pass"], ssl)
        try:
            out3, err3, rc3 = run_cmd(
                [pg_restore, "-w", "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"],
                 "--no-owner", "--no-acl",
                 backup_file],
                env=env_cloud,
                timeout=get_env_int(env, "GAET_PG_TIMEOUT", DEF_PG_TIMEOUT),
            )
        finally:
            cleanup_pg_env(env_cloud)
            spinner.stop()
        if rc3 == 0:
            echo(f"    {G}{ICON_OK}{NC}  Sinkronisasi selesai!")
            result["sync"] = {"ok": True}
        elif rc3 == 2 or "connection" in (err3 or "").lower() or "ssl" in (err3 or "").lower():
            # Connection-level failure (server unreachable, SSL mismatch)
            echo(f"    {R}{ICON_FAIL}{NC}  Gagal terhubung ke cloud database")
            if err3:
                first_err = err3.strip().splitlines()[-1] if err3.strip() else ""
                echo(f"    {D}{first_err}{NC}")
            echo(f"    {D}Periksa GAET_REMOTE_URL dan coba 'gaet check'{NC}")
            result["sync"] = {"ok": False, "error": "connection"}
            die("Sinkronisasi cloud gagal (koneksi)", EXIT_CLOUD_DOWN)
        else:
            # Restore ran but reported errors (e.g. missing objects)
            echo(f"    {R}{ICON_FAIL}{NC}  Sinkronisasi gagal ({rc3})")
            if err3:
                for line in err3.strip().splitlines()[-3:]:
                    echo(f"    {D}{line}{NC}")
            result["sync"] = {"ok": False, "error": "restore"}
            die("Sinkronisasi cloud gagal (restore error)", EXIT_CLOUD_DOWN)

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

        # Webhook notification
        notify_url = getattr(args, "notify", "") or ""
        if notify_url:
            try:
                payload = json.dumps({
                    "text": f"gaet push complete: {tables_synced} tables, {size_mb:.1f} MB",
                    "file": str(backup_file),
                }).encode("utf-8")
                req = urllib.request.Request(
                    notify_url, data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=10)
                echo(f"  {G}Webhook notified{NC}")
            except Exception as e:
                echo(f"  {Y}Webhook failed: {e}{NC}")
    finally:
        release_lock()

def cmd_fetch(args: argparse.Namespace) -> None:
    """Restore cloud -> local."""
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
        echo(f"  {C}☁️{NC}   {B}Simulasi fetch cloud -> local{NC}")
        echo()
        cloud_info = f"Cloud:  {parsed['user']}@{parsed['host']}:{parsed['port']}/{parsed['db']}" if parsed else "Cloud: not configured"
        status_arrow(cloud_info)
        status_arrow(f"Local:  {u}@{h}:{p}/{n}")
        status_arrow(f"Aksi:   Dump cloud -> restore ke local (overwrite)")
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

        log("⬇️ Fetch: cloud -> local")
        box_title("gaet fetch")

        # Confirmation before overwriting local DB
        if getattr(args, "yes", False):
            # Non-interactive mode (--yes flag)
            pass
        elif not sys.stdin.isatty():
            die(
                "Perintah 'gaet fetch' di lingkungan non-interaktif memerlukan flag --yes untuk overwrite database lokal.\n"
                f"  Contoh: {C}gaet fetch --yes{NC}",
                EXIT_CONFIG,
            )
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
        env_cloud = pg_env(parsed["user"], parsed["pass"], ssl)
        try:
            out, err, rc = run_cmd(
                [pg_dump, "-w", "-h", parsed["host"], "-p", parsed["port"],
                 "-U", parsed["user"], "-d", parsed["db"],
                 "--format=custom", "--compress=9", f"--file={fetch_file}"],
                env=env_cloud,
                timeout=get_env_int(env, "GAET_PG_TIMEOUT", DEF_PG_TIMEOUT),
            )
        finally:
            cleanup_pg_env(env_cloud)
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
        env_local = pg_env(u, w)
        run_cmd(
            [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-v", f"dbname={n}", "-tAc",
             "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
             "WHERE datname = :'dbname' AND pid <> pg_backend_pid();"],
            env=env_local,
            timeout=10,
        )

        # Drop existing objects first (handles partitioned tables; --clean can't)
        ok_reset, reset_err = _reset_target_objects(psql, h, p, u, n, w)
        if not ok_reset:
            cleanup_pg_env(env_local)
            echo(f"    {R}{ICON_FAIL}{NC}  Gagal membersihkan database lokal")
            if reset_err:
                echo(f"    {D}{reset_err[:200]}{NC}")
            result["restore"] = {"ok": False, "error": "reset"}
            die("Restore lokal gagal (reset target)")

        spinner = Spinner("Restoring to local database").start()
        try:
            out3, err3, rc3 = run_cmd(
                [pg_restore, "-w", "-h", h, "-p", p, "-U", u, "-d", n,
                 fetch_file],
                env=env_local,
                timeout=get_env_int(env, "GAET_PG_TIMEOUT", DEF_PG_TIMEOUT),
            )
        finally:
            cleanup_pg_env(env_local)
            spinner.stop()
        if rc3 == 0:
            echo(f"    {G}{ICON_OK}{NC}  Local restore complete!")
            result["restore"] = {"ok": True}
        elif rc3 == 2 or "connection" in (err3 or "").lower() or "ssl" in (err3 or "").lower():
            # Connection-level failure
            echo(f"    {R}{ICON_FAIL}{NC}  Gagal terhubung ke database lokal")
            if err3:
                first_err = err3.strip().splitlines()[-1] if err3.strip() else ""
                echo(f"    {D}{first_err}{NC}")
            echo(f"    {D}Periksa GAET_LOCAL_DB_* dan coba 'gaet check'{NC}")
            result["restore"] = {"ok": False, "error": "connection"}
            die("Restore lokal gagal (koneksi)", EXIT_LOCAL_DOWN)
        else:
            # Restore ran but reported errors
            echo(f"    {R}{ICON_FAIL}{NC}  Restore gagal ({rc3})")
            if err3:
                for line in err3.strip().splitlines()[-3:]:
                    echo(f"    {D}{line}{NC}")
            result["restore"] = {"ok": False, "error": "restore"}
            die("Restore lokal gagal (restore error)")

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

        env_local = pg_env(u, w)
        try:
            out, err, rc = run_cmd(
                [pg_dump, "-w", "-h", h, "-p", p, "-U", u, "-d", n,
                 "--format=custom", "--compress=9", f"--file={cron_file}"],
                env=env_local,
                timeout=get_env_int(env, "GAET_PG_TIMEOUT", DEF_PG_TIMEOUT),
            )
        finally:
            cleanup_pg_env(env_local)

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

            env_cloud = pg_env(parsed["user"], parsed["pass"], ssl)
            try:
                out2, err2, rc2 = run_cmd(
                    [pg_restore, "-w", "-h", parsed["host"], "-p", parsed["port"],
                     "-U", parsed["user"], "-d", parsed["db"],
                     "--clean", "--if-exists", "--no-owner", "--no-acl", cron_file],
                    env=env_cloud,
                    timeout=get_env_int(env, "GAET_PG_TIMEOUT", DEF_PG_TIMEOUT),
                )
            finally:
                cleanup_pg_env(env_cloud)

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

def cmd_restore(args: argparse.Namespace) -> None:
    """Restore local database from a local snapshot (.dump file).

    Usage:
      gaet restore               (restores the latest local backup)
      gaet restore latest        (restores the latest local backup)
      gaet restore gaet_20260816_190000.dump
    """
    dry_run = getattr(args, "dry_run", False)
    skip_confirm = getattr(args, "yes", False)
    want_json = getattr(args, "json", False)
    target_arg = getattr(args, "target", None) or "latest"

    if want_json:
        set_output_modes(quiet=True, plain=True)
    result: Dict[str, Any] = {"command": "restore", "ok": False}

    env = load_env()
    tools = find_pg_tools(env)
    check_tools(env)

    # 1. Locate specified dump file
    dump_files = sorted(BACKUP_DIR.glob("*.dump"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not dump_files:
        die(f"Tidak ada file backup ditemukan di {BACKUP_DIR}.\n  Jalankan 'gaet push' terlebih dahulu untuk membuat backup.")

    target_file: Optional[Path] = None
    if target_arg.lower() in ("latest", "last", "newest"):
        target_file = dump_files[0]
    else:
        # Check if argument is absolute/relative path or filename in BACKUP_DIR
        candidate = Path(target_arg)
        if candidate.is_file():
            target_file = candidate
        elif (BACKUP_DIR / target_arg).is_file():
            target_file = BACKUP_DIR / target_arg
        else:
            # Match by substring
            matches = [f for f in dump_files if target_arg in f.name]
            if matches:
                target_file = matches[0]
            else:
                die(f"File backup '{target_arg}' tidak ditemukan di {BACKUP_DIR}")

    size_mb = target_file.stat().st_size / (1024 * 1024)
    h, p, u, n, w = check_local_db(env)

    if dry_run:
        if want_json:
            result.update({
                "dry_run": True,
                "target_file": str(target_file),
                "size_mb": round(size_mb, 1),
                "destination": {"host": h, "port": p, "user": u, "db": n},
                "ok": True,
            })
            print(json.dumps(result, indent=2))
            return
        box_title("gaet restore --dry-run")
        box_section("Simulation Details")
        status_arrow(f"Snapshot File: {target_file.name}")
        status_arrow(f"Full Path:     {target_file}")
        status_arrow(f"Size:          {size_mb:.1f} MB")
        status_arrow(f"Target DB:     {u}@{h}:{p}/{n}")
        echo()
        status_info("Dry-run mode: No database changes will be made")
        echo()
        status_info(f"To proceed: gaet restore {target_file.name}")
        echo()
        return

    # Safety Guard for TTY & Non-TTY
    if not skip_confirm:
        if not sys.stdin.isatty():
            die(
                "Perintah destruktif 'gaet restore' di lingkungan non-interaktif membutuhkan flag --yes / -y",
                EXIT_CONFIG,
            )
        echo()
        box_title("gaet restore")
        status_warn(f"⚠️ PERINGATAN DESTRUKTIF: Seluruh tabel di database lokal '{n}' akan DIHAPUS dan DIPULIHKAN dari snapshot!")
        status_arrow(f"File Snapshot: {target_file.name} ({size_mb:.1f} MB)")
        status_arrow(f"Target Database: {u}@{h}:{p}/{n}")
        echo()
        ans = safe_input(f"  Apakah Anda yakin ingin memulihkan snapshot ini? Ketik 'yes' untuk melanjutkan: ").strip().lower()
        if ans not in ("yes", "y"):
            echo(f"  {Y}Restore dibatalkan oleh pengguna.{NC}")
            return

    acquire_lock()
    try:
        log(f"🔄 Restore local DB from snapshot: {target_file.name}")
        box_title("gaet restore")
        pg_restore = tools["pg_restore"]
        psql = tools["psql"]

        # Step 1: Verify integrity of dump
        echo(f"  {C}🔍{NC}  {B}Memeriksa integritas file snapshot...{NC}")
        _, _, rc_check = run_cmd([pg_restore, "--list", str(target_file)], timeout=30)
        if rc_check != 0:
            die(f"File snapshot '{target_file.name}' korup atau tidak valid.", EXIT_CONFIG)
        status_ok("Integritas snapshot valid")

        # Step 2: Terminate active connections to local DB
        status_warn("Menutup koneksi aktif ke database lokal...")
        env_local = pg_env(u, w)
        run_cmd(
            [psql, "-w", "-h", h, "-p", p, "-U", u, "-d", n, "-v", f"dbname={n}", "-tAc",
             "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
             "WHERE datname = :'dbname' AND pid <> pg_backend_pid();"],
            env=env_local,
            timeout=10,
        )

        # Step 3: Reset target objects
        ok_reset, reset_err = _reset_target_objects(psql, h, p, u, n, w)
        if not ok_reset:
            cleanup_pg_env(env_local)
            echo(f"    {R}{ICON_FAIL}{NC}  Gagal membersihkan database lokal")
            if reset_err:
                echo(f"    {D}{reset_err[:200]}{NC}")
            result["restore"] = {"ok": False, "error": "reset"}
            die("Restore lokal gagal (reset target)")

        # Step 4: Execute pg_restore
        echo(f"  {C}💾{NC}  {B}Memulihkan database dari snapshot...{NC}")
        spinner = Spinner("Restoring snapshot to local DB").start()
        try:
            out3, err3, rc3 = run_cmd(
                [pg_restore, "-w", "-h", h, "-p", p, "-U", u, "-d", n, str(target_file)],
                env=env_local,
                timeout=get_env_int(env, "GAET_PG_TIMEOUT", DEF_PG_TIMEOUT),
            )
        finally:
            cleanup_pg_env(env_local)
            spinner.stop()

        if rc3 == 0:
            echo(f"    {G}{ICON_OK}{NC}  Pemulihan snapshot selesai!")
            result["restore"] = {"ok": True, "file": str(target_file)}
        else:
            echo(f"    {R}{ICON_FAIL}{NC}  Restore gagal ({rc3})")
            if err3:
                for line in err3.strip().splitlines()[-3:]:
                    echo(f"    {D}{line}{NC}")
            result["restore"] = {"ok": False, "error": "restore"}
            die("Restore snapshot lokal gagal")

        echo()
        box_section("Ringkasan Pemulihan")
        status_ok(f"Database lokal '{n}' berhasil dipulihkan")
        status_arrow(f"Snapshot File: {target_file.name}")
        status_arrow(f"Target DB:     {u}@{h}:{p}/{n}")
        echo()

        result["ok"] = True
        if want_json:
            print(json.dumps(result, indent=2))
            return
        log(f"✅ Restore local DB complete ({target_file.name})")
    finally:
        release_lock()


# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_push_parser(subparsers, common):
    p = subparsers.add_parser("push", help="Backup local to cloud", parents=[common])
    p.add_argument("--auto", nargs="?", const=0, type=int,
                   help="Aktifkan auto-backup (opsional: interval jam, default 6)")
    p.add_argument("--cron", action="store_true", help="Jalankan dari scheduler (internal)")
    p.add_argument("--dry-run", action="store_true", help="Simulasi tanpa mengeksekusi")
    p.add_argument("--json", action="store_true", help="Output JSON result")
    p.add_argument("--notify", type=str, default="", help="Webhook URL to notify after push")
    return p


def _build_fetch_parser(subparsers, common):
    p = subparsers.add_parser("fetch", help="Restore cloud to local", parents=[common])
    p.add_argument("--dry-run", action="store_true", help="Simulasi tanpa mengeksekusi")
    p.add_argument("--yes", "-y", action="store_true", help="Skip konfirmasi (untuk non-interaktif/dashboard)")
    p.add_argument("--json", action="store_true", help="Output JSON result")
    return p


def _build_restore_parser(subparsers, common):
    p = subparsers.add_parser("restore", help="Restore local DB from a local snapshot file", parents=[common])
    p.add_argument("target", nargs="?", default="latest",
                   help="Nama file dump atau 'latest' (default: latest)")
    p.add_argument("--dry-run", action="store_true", help="Simulasi pemulihan tanpa mengubah data")
    p.add_argument("--yes", "-y", action="store_true", help="Skip konfirmasi (untuk non-interaktif/dashboard)")
    p.add_argument("--json", action="store_true", help="Output JSON result")
    return p


command("push", "Backup local to cloud", build=_build_push_parser)(cmd_push)
command("fetch", "Restore cloud to local", build=_build_fetch_parser)(cmd_fetch)
command("restore", "Restore local DB from a local snapshot file", build=_build_restore_parser)(cmd_restore)

