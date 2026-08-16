"""cmd_update / cmd_install / cmd_uninstall — version & installer management."""

import argparse
import shutil
import sys
import time
from .core import C, D, DEF_SERVICE_PREFIX, G, GAET_DIR, GITHUB_API, HOME, IS_LINUX, IS_MACOS, IS_WINDOWS, NAME, NC, Path, Y, _gh_download, argparse, box_section, box_title, die, echo, get_env_str, load_env, run_cmd, safe_input, scheduler_disable, scheduler_is_active, shutil, status_arrow, status_fail, status_info, status_ok, status_warn, sys, time
from .scheduler import _svc_is_running, _svc_stop

def cmd_install(args: argparse.Namespace) -> None:
    """Setup/install dependencies & config."""
    try:
        from scripts.installer import run as installer_run
    except ImportError:
        box_title(f"{NAME} install")
        status_fail("installer module not found")
        status_warn("Run from project root: pip install -e .")
        echo()
        sys.exit(1)

    box_title(f"{NAME} install")
    status_info("Starting installation process...")
    echo()
    
    rc = installer_run(
        yes=args.yes,
        skip_deps=getattr(args, "skip_deps", False),
        skip_build=getattr(args, "skip_build", False),
        skip_config=getattr(args, "skip_config", False),
        skip_service=getattr(args, "skip_service", False),
        interval=getattr(args, "interval", 0),
    )
    
    echo()
    if rc == 0:
        status_ok("Installation complete")
    else:
        status_fail(f"Installation failed (exit code: {rc})")
    echo()
    
    sys.exit(rc)

def cmd_uninstall(args: argparse.Namespace) -> None:
    """Uninstall gaet. Safe mode keeps config, purge removes everything."""
    purge = getattr(args, "purge", False)
    mode = "purge" if purge else "safe"
    
    box_title(f"{NAME} uninstall ({mode})")
    
    if purge:
        echo(f"  {Y}⚠  PURGE MODE: Akan menghapus gaet DAN semua config/backup{NC}")
        echo("")
        confirm = safe_input(f"  Ketik 'yes' untuk konfirmasi: ").strip().lower()
        if confirm != "yes":
            echo(f"  {G}Dibatalkan.{NC}")
            return
    
    # ── 1. Stop services ──────────────────────────────────────────────
    echo(f"  {C}▸{NC} Menghentikan service...")
    
    # Stop scheduler
    try:
        if scheduler_is_active(DEF_SERVICE_PREFIX):
            scheduler_disable(DEF_SERVICE_PREFIX)
            echo(f"    {G}✓{NC} Scheduler dihentikan")
        else:
            echo(f"    {D}  Scheduler tidak aktif{NC}")
    except Exception as e:
        echo(f"    {Y}⚠  Scheduler error: {e}{NC}")
    
    # Stop dashboard
    try:
        if _svc_is_running():
            ok, msg = _svc_stop()
            if ok:
                echo(f"    {G}✓{NC} Dashboard dihentikan")
            else:
                echo(f"    {Y}⚠  Dashboard gagal dihentikan: {msg}{NC}")
        else:
            echo(f"    {D}  Dashboard tidak aktif{NC}")
    except Exception as e:
        echo(f"    {Y}⚠  Dashboard error: {e}{NC}")
    
    # ── 2. Disable services ──────────────────────────────────────────
    echo(f"  {C}▸{NC} Menonaktifkan service...")
    
    if IS_LINUX:
        # Disable systemd services
        try:
            prefix = DEF_SERVICE_PREFIX
            timer = f"{prefix}-backup.timer"
            svc = f"{prefix}-backup.service"
            
            run_cmd(["systemctl", "--user", "disable", "--now", timer], timeout=10)
            echo(f"    {G}✓{NC} Timer dinonaktifkan: {timer}")
            
            run_cmd(["systemctl", "--user", "disable", "--now", svc], timeout=10)
            echo(f"    {G}✓{NC} Service dinonaktifkan: {svc}")
        except Exception as e:
            echo(f"    {Y}⚠  Disable error: {e}{NC}")
    
    elif IS_MACOS:
        # Unload launchd plists
        try:
            plist_dir = Path.home() / "Library" / "LaunchAgents"
            for pattern in ["com.gaet.dashboard.plist", f"{DEF_SERVICE_PREFIX}-backup.plist"]:
                plist_path = plist_dir / pattern
                if plist_path.exists():
                    run_cmd(["launchctl", "unload", str(plist_path)], timeout=10)
                    plist_path.unlink()
                    echo(f"    {G}✓{NC} Unloaded: {pattern}")
        except Exception as e:
            echo(f"    {Y}⚠  Unload error: {e}{NC}")
    
    elif IS_WINDOWS:
        # Remove Task Scheduler tasks
        try:
            _, _, rc = run_cmd(["schtasks", "/Query", "/TN", f"{DEF_SERVICE_PREFIX}-backup"], timeout=10)
            if rc == 0:
                run_cmd(["schtasks", "/Delete", "/TN", f"{DEF_SERVICE_PREFIX}-backup", "/F"], timeout=10)
                echo(f"    {G}✓{NC} Task Scheduler dihapus")
        except Exception as e:
            echo(f"    {Y}⚠  Task removal error: {e}{NC}")
    
    # ── 3. Remove CLI and scripts ────────────────────────────────────
    echo(f"  {C}▸{NC} Menghapus gaet CLI...")
    
    bin_dir = Path.home() / ".local" / "bin"
    
    # Remove gaet CLI
    gaet_bin = bin_dir / "gaet"
    if gaet_bin.exists():
        gaet_bin.unlink()
        echo(f"    {G}✓{NC} Dihapus: {gaet_bin}")
    
    # Remove scripts directory
    scripts_dir = bin_dir / "scripts"
    if scripts_dir.exists():
        shutil.rmtree(scripts_dir)
        echo(f"    {G}✓{NC} Dihapus: {scripts_dir}")
    
    # ── 4. Purge mode: remove service files + config ────────────────
    if purge:
        echo(f"  {C}▸{NC} Menghapus service files...")
        
        prefix = DEF_SERVICE_PREFIX
        if IS_LINUX:
            # Remove systemd unit files
            systemd_dir = HOME / ".config" / "systemd" / "user"
            for pattern in [f"{prefix}-dashboard.service", f"{prefix}-backup.service",
                          f"{prefix}-backup.timer", "gaet-dashboard.service"]:
                unit_path = systemd_dir / pattern
                if unit_path.exists():
                    unit_path.unlink()
                    echo(f"    {G}✓{NC} Dihapus: {unit_path}")
            
            # Reload systemd daemon
            try:
                run_cmd(["systemctl", "--user", "daemon-reload"], timeout=10)
                echo(f"    {G}✓{NC} Systemd daemon reloaded")
            except Exception:
                pass
        
        elif IS_MACOS:
            # Plists already removed in step 2 (unload + unlink)
            echo(f"    {D}  Plist sudah dihapus{NC}")
        
        elif IS_WINDOWS:
            # Tasks already removed in step 2
            echo(f"    {D}  Task sudah dihapus{NC}")
        
        echo(f"  {C}▸{NC} Menghapus config dan data...")
        
        config_dir = GAET_DIR
        if config_dir.exists():
            shutil.rmtree(config_dir)
            echo(f"    {G}✓{NC} Dihapus: {config_dir}")
        else:
            echo(f"    {D}  Config directory tidak ditemukan{NC}")
    
    # ── 5. Summary ───────────────────────────────────────────────────
    echo("")
    echo(f"  {G}✓ Uninstall selesai ({mode} mode){NC}")
    echo("")
    
    if purge:
        echo(f"  Semua sudah dihapus.")
    else:
        echo(f"  Config disimpan di: {GAET_DIR}/")
        echo(f"  Untuk hapus config juga, jalankan: gaet uninstall --purge")
    
    echo(f"  Untuk reinstall: curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash")
    echo("")

def _update_download(install_dir: Path, skip_build: bool = False) -> None:
    """Update gaet by downloading files from GitHub (for curl-install users)."""

    status_info("Downloading latest gaet from GitHub...")

    files = [
        ("gaet.py", "gaet"),
    ]
    script_files = ["__init__.py", "status.py", "scheduler.py", "service_manager.py", "installer.py"]

    for src, dst in files:
        url = f"{GITHUB_API}/{src}?ref=master"
        try:
            data = _gh_download(url)
            dest_path = install_dir / dst
            dest_path.write_bytes(data)
            dest_path.chmod(0o755) if not IS_WINDOWS else None
            status_ok(f"{dst} → {dest_path}")
        except Exception as e:
            die(f"Failed to download {src}: {e}")

    # Download scripts
    scripts_dst = install_dir / "scripts"
    scripts_dst.mkdir(parents=True, exist_ok=True)
    for sf in script_files:
        url = f"{GITHUB_API}/scripts/{sf}?ref=master"
        try:
            data = _gh_download(url)
            (scripts_dst / sf).write_bytes(data)
            status_ok(f"scripts/{sf} → {scripts_dst}/")
        except Exception as e:
            status_warn(f"Failed to download scripts/{sf}: {e}")

    # Download shell completions (gaet completion reads them from here)
    completions_dst = install_dir / "completions"
    completions_dst.mkdir(parents=True, exist_ok=True)
    for cf in ["gaet.bash", "gaet.zsh", "gaet.fish", "gaet.ps1"]:
        url = f"{GITHUB_API}/completions/{cf}?ref=master"
        try:
            data = _gh_download(url)
            (completions_dst / cf).write_bytes(data)
            status_ok(f"completions/{cf} -> {completions_dst}")
        except Exception:
            status_warn(f"Failed to download completions/{cf}")


    # Download and build dashboard
    if not skip_build:
        try:
            dashboard_dst = install_dir / "dashboard"
            # Pure Python HTTP server — no Node.js/npm build step required (v2.0.1+).
            # server.py runs from ~/.local/bin/dashboard/ (the install dir),
            # so it is downloaded there, NOT to ~/.gaet/dashboard.
            dash_files = [
                "server.py",
                "static/index.html",
                "public/gaet-logo.png",
            ]

            for df in dash_files:
                url = f"{GITHUB_API}/dashboard/{df}?ref=master"
                try:
                    data = _gh_download(url)
                    df_path = dashboard_dst / df
                    df_path.parent.mkdir(parents=True, exist_ok=True)
                    df_path.write_bytes(data)
                    status_ok(f"dashboard/{df} -> {dashboard_dst}")
                except Exception:
                    status_warn(f"Failed to download dashboard/{df}")
        except Exception as e:
            status_warn(f"Dashboard update skipped: {e}")

    echo()
    status_ok("Update complete!")

def cmd_update(args: argparse.Namespace) -> None:
    """Update gaet to latest version from GitHub."""
    box_title(f"{NAME} update")

    install_dir = Path.home() / ".local" / "bin"
    
    # Find project directory (where .git exists)
    script_dir = Path(sys.argv[0]).resolve().parent
    candidates = [
        script_dir.parent,  # installed from project root
        script_dir / "..",
        HOME / "Projects/gaet",
        HOME / ".local/share/gaet",
    ]
    
    project_dir = None
    for cand in candidates:
        if (cand / ".git").is_dir() and (cand / "gaet.py").is_file():
            project_dir = cand.resolve()
            break
    
    if not project_dir:
        # No git repo found — use download fallback for curl-install users
        status_info("Mode: curl-install (download from GitHub)")
        _update_download(install_dir, skip_build=args.skip_build)
        return
    
    echo(f"  {C}📁{NC}  Project: {D}{project_dir}{NC}")
    
    # Check if git is available
    git = shutil.which("git") or ""
    if not git:
        die("git not found. Please install git first.")
    
    # Check if there are local changes
    out, _, rc = run_cmd([git, "-C", str(project_dir), "status", "--porcelain"], timeout=10)
    if out.strip():
        status_warn("Local changes detected in project")
        if not args.force:
            status_info("Commit changes first or use --force")
            echo(f"    {D}git -C {project_dir} stash{NC}")
            echo(f"    {D}gaet update --force{NC}")
            return
    
    # Fetch and pull
    echo()
    box_section("Fetching update")
    
    status_info("Fetching from remote...")
    out, err, rc = run_cmd([git, "-C", str(project_dir), "fetch", "origin"], timeout=30)
    if rc != 0:
        die(f"Fetch failed: {err}")
    status_ok("Fetch complete")
    
    # Check current vs remote
    out_local, _, _ = run_cmd([git, "-C", str(project_dir), "rev-parse", "HEAD"], timeout=5)
    out_remote, _, _ = run_cmd([git, "-C", str(project_dir), "rev-parse", "origin/master"], timeout=5)
    
    is_up_to_date = out_local.strip() == out_remote.strip()
    
    if not is_up_to_date:
        # Show what will be updated
        out_log, _, _ = run_cmd([git, "-C", str(project_dir), "log", "--oneline", f"{out_local.strip()}..{out_remote.strip()}"], timeout=10)
        if out_log.strip():
            echo()
            box_section("New commits")
            for line in out_log.strip().split("\n")[:5]:
                status_arrow(line)
        
        # Pull
        echo()
        box_section("Pulling update")
        out, err, rc = run_cmd([git, "-C", str(project_dir), "pull", "origin", "master"], timeout=30)
        if rc != 0:
            die(f"Pull failed: {err}")
        status_ok("Pull complete")
    else:
        status_ok("Already up to date!")
    
    # Always copy to install location (even if already up to date)
    echo()
    box_section("Installing")
    install_dir = Path.home() / ".local" / "bin"
    install_dir.mkdir(parents=True, exist_ok=True)
    
    src = project_dir / "gaet.py"
    dst = install_dir / "gaet"
    
    if src.is_file():
        shutil.copy2(str(src), str(dst))
        dst.chmod(0o755) if not IS_WINDOWS else None
        status_ok(f"gaet → {dst}")
    
    # Copy scripts if exists
    scripts_src = project_dir / "scripts"
    if scripts_src.is_dir():
        scripts_dst = install_dir / "scripts"
        scripts_dst.mkdir(parents=True, exist_ok=True)
        for f in scripts_src.glob("*.py"):
            shutil.copy2(str(f), str(scripts_dst / f.name))
        status_ok(f"scripts → {scripts_dst}/")
    
    # Copy dashboard if exists and rebuild
    dashboard_src = project_dir / "dashboard"
    if dashboard_src.is_dir() and not args.skip_build:
        echo()
        box_section("Building dashboard")
        node = shutil.which("node")
        npm = shutil.which("npm")
        if node and npm:
            status_info("Installing dependencies...")
            run_cmd([npm, "install"], cwd=str(dashboard_src), timeout=120)
            status_info("Building...")
            run_cmd([npm, "run", "build"], cwd=str(dashboard_src), timeout=120)
            status_ok("Dashboard built")
            
            # Restart dashboard service if running
            try:
                from scripts.service_manager import service_is_running, service_start, service_stop
                if service_is_running():
                    status_info("Restarting dashboard service...")
                    service_stop()
                    time.sleep(1)
                    port = int(get_env_str(load_env(), "GAET_DASHBOARD_PORT", "9191"))
                    host = get_env_str(load_env(), "GAET_DASHBOARD_HOST", "0.0.0.0")
                    ok, msg = service_start(dashboard_dir=dashboard_src, port=port, host=host, foreground=False)
                    if ok:
                        status_ok("Dashboard service restarted")
                    else:
                        status_warn(f"Restart failed: {msg}")
            except Exception:
                pass
        else:
            status_warn("Node.js/npm not found — skipping dashboard build")
    
    # Show version
    echo()
    box_section("Version")
    try:
        r = run_cmd([sys.executable, str(dst), "--version"], timeout=5)
        if r[2] == 0 and r[0].strip():  # rc == 0 and stdout
            status_ok(f"Version: {r[0].strip()}")
        else:
            status_ok("Update complete - version check skipped")
    except Exception as e:
        status_warn(f"Version check failed: {e}")
        status_ok("Update complete")
    
    echo()
    status_ok("Update complete!")

# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_install_parser(subparsers, common):
    p = subparsers.add_parser("install", help="Setup/install dependencies & config", parents=[common])
    p.add_argument("--yes", "-y", action="store_true", help="Auto-approve")
    p.add_argument("--skip-deps", action="store_true", help="Skip cek dependencies")
    p.add_argument("--skip-build", action="store_true", help="Skip build dashboard")
    p.add_argument("--skip-config", action="store_true", help="Skip config wizard")
    p.add_argument("--skip-service", action="store_true", help="Skip setup service")
    p.add_argument("--interval", type=int, default=0, help="Interval auto-backup (jam)")
    return p


def _build_update_parser(subparsers, common):
    p = subparsers.add_parser("update", help="Update to latest version", parents=[common])
    p.add_argument("--force", action="store_true", help="Force update (skip local changes check)")
    p.add_argument("--skip-build", action="store_true", help="Skip build dashboard")
    return p


def _build_uninstall_parser(subparsers, common):
    p = subparsers.add_parser("uninstall", help="Remove gaet from system", parents=[common])
    p.add_argument("--purge", action="store_true", help="Remove everything including config and backups")
    return p


command("install", "Setup/install dependencies & config", build=_build_install_parser)(cmd_install)
command("update", "Update to latest version", build=_build_update_parser)(cmd_update)
command("uninstall", "Remove gaet from system", build=_build_uninstall_parser)(cmd_uninstall)

