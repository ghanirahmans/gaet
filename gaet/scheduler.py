"""cmd_auto_on / cmd_stop_auto + service helpers — auto-backup scheduling."""

import argparse
import sys
from .core import C, DEF_AUTO_INTERVAL, DEF_SERVICE_PREFIX, NC, Path, _svc_available, _svc_mod, argparse, box_title, die, echo, get_env_int, get_env_str, get_scheduler_name, load_env, scheduler_disable, scheduler_enable, status_arrow, status_fail, status_info, status_ok, status_warn, sys

def _svc_start(dashboard_dir=None, port=9191, host="0.0.0.0", foreground=False):
    if _svc_available:
        return _svc_mod.service_start(dashboard_dir, port, host, foreground)
    print("  ⚠  service_manager module tidak tersedia. Jalankan dari folder proyek.")
    return False, "module not found"

def _svc_stop():
    if _svc_available:
        return _svc_mod.service_stop()
    return True, "module not loaded"

def _svc_is_running():
    if _svc_available:
        return _svc_mod.service_is_running()
    return False

def _svc_status():
    if _svc_available:
        return _svc_mod.service_status()
    return {"running": False, "platform": "unknown", "pid": None}

def cmd_auto_on(args: argparse.Namespace) -> None:
    """Enable auto-backup."""
    env = load_env()
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)
    interval = args.auto if args.auto is not None else get_env_int(env, "GAET_AUTO_INTERVAL", DEF_AUTO_INTERVAL)

    # Validate interval
    if interval is None or interval <= 0:
        die("Interval must be a positive number (hours).\n"
            f"  Example: {C}gaet push --auto=4{NC}  (auto-backup every 4 hours)")
    if interval > 24:
        die("Maximum interval is 24 hours.\n"
            f"  Example: {C}gaet push --auto=12{NC}  (auto-backup every 12 hours)")

    box_title("Auto-backup")
    status_info(f"Enabling auto-backup every {interval} hours (scheduler: {get_scheduler_name()})")

    # Determine cli_path for the scheduler to call
    cli_path = str(Path(sys.argv[0]).resolve())

    if scheduler_enable(prefix, interval, cli_path):
        status_ok(f"Auto-backup enabled every {interval} hours!")
        status_arrow(f"Interval: {interval} hours")
        status_arrow(f"Scheduler: {get_scheduler_name()}")
        echo()
    else:
        status_fail("Failed to enable auto-backup")
        status_warn("On this system, enable auto-backup manually.")
        echo()

def cmd_stop_auto(args: argparse.Namespace) -> None:
    """Stop auto-backup &/or dashboard."""
    env = load_env()
    prefix = get_env_str(env, "GAET_SERVICE_PREFIX", DEF_SERVICE_PREFIX)

    if getattr(args, "dashboard", False):
        # Only stop dashboard
        status_info("Menghentikan dashboard...")
        if _svc_is_running():
            ok, msg = _svc_stop()
            if ok:
                status_ok("Dashboard dihentikan")
            else:
                status_warn(f"Gagal menghentikan dashboard: {msg}")
        else:
            status_warn("Dashboard tidak aktif")
        return

    if getattr(args, "scheduler", False):
        # Only stop auto-backup
        status_info("Menghentikan auto-backup...")
        scheduler_disable(prefix)
        status_ok("Auto-backup dihentikan")
        return

    # Default: stop both
    status_info("Menghentikan auto-backup...")
    scheduler_disable(prefix)
    status_ok("Auto-backup dihentikan")

    if _svc_is_running():
        status_info("Menghentikan dashboard...")
        ok, msg = _svc_stop()
        if ok:
            status_ok("Dashboard dihentikan")
        else:
            status_warn(f"Gagal menghentikan dashboard: {msg}")

# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_stop_parser(subparsers, common):
    p = subparsers.add_parser("stop", help="Stop auto-backup or dashboard", parents=[common])
    p.add_argument("--scheduler", action="store_true", help="Stop auto-backup saja")
    p.add_argument("--dashboard", action="store_true", help="Hentikan dashboard saja")
    return p


command("stop", "Stop auto-backup or dashboard", build=_build_stop_parser)(cmd_stop_auto)

