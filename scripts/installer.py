"""
scripts/installer.py — Cross-platform gaet universal installer

Detects OS, checks/installs dependencies, sets up config,
builds dashboard, enables auto-backup & dashboard service.

Usage:
    python install.py              # interactive
    python install.py --yes        # non-interactive, auto
    python install.py --help       # full options
"""

import os, sys, shutil, subprocess, textwrap, json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─── Paths ───────────────────────────────────────────────────────────────

HOME = Path.home()
GAET_DIR = HOME / ".gaet"
ENV_FILE = GAET_DIR / ".env"
BACKUP_DIR = GAET_DIR / "backups"


# ─── Platform detection ──────────────────────────────────────────────────

IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"


def detect_os() -> Dict[str, str]:
    """Return OS details for display/install decisions."""
    if IS_LINUX:
        # Try /etc/os-release
        info: Dict[str, str] = {"os": "linux", "distro": "unknown", "version": "unknown"}
        osrel = Path("/etc/os-release")
        if osrel.exists():
            for line in osrel.read_text().splitlines():
                if line.startswith("ID="):
                    info["distro"] = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("VERSION_ID="):
                    info["version"] = line.split("=", 1)[1].strip().strip('"')
        return info
    elif IS_MACOS:
        out, _, _ = _run(["sw_vers", "-productVersion"])
        return {"os": "macos", "distro": "macOS", "version": out.strip() or "unknown"}
    elif IS_WINDOWS:
        ver = sys.getwindowsversion()
        return {"os": "windows", "distro": "Windows", "version": f"{ver.major}.{ver.minor}.{ver.build}"}
    return {"os": "unknown", "distro": "unknown", "version": "unknown"}


# ─── Helpers ─────────────────────────────────────────────────────────────

def _run(cmd: List[str], timeout: int = 30) -> Tuple[str, str, int]:
    """Run command, return (stdout, stderr, returncode)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", 1
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", 1
    except Exception as e:
        return "", str(e), 1


def _run_interactive(cmd: List[str]) -> int:
    """Run command showing live output."""
    return subprocess.run(cmd).returncode


def echo(msg: str = "") -> None:
    """Print with style."""
    print(msg)


def color(s: str, code: str) -> str:
    """Colorize string for terminal."""
    if IS_WINDOWS:
        return s  # Windows Git Bash handles ANSI
    return f"{code}{s}\033[0m"


G = "\033[32m"  # green
R = "\033[31m"  # red
Y = "\033[33m"  # yellow
C = "\033[36m"  # cyan
B = "\033[1m"   # bold
D = "\033[2m"   # dim
NC = "\033[0m"  # reset

ICON_OK = "\u2713"
ICON_FAIL = "\u2717"
ICON_WARN = "\u26a0"
ICON_ARROW = "\u2192"


def status_ok(msg: str) -> None:
    print(f"  {G}{ICON_OK}{NC}  {msg}")


def status_fail(msg: str) -> None:
    print(f"  {R}{ICON_FAIL}{NC}  {msg}")


def status_warn(msg: str) -> None:
    print(f"  {Y}{ICON_WARN}{NC}  {msg}")


def status_info(msg: str) -> None:
    print(f"  {C}i{NC}  {msg}")


# Try to use NC
try:
    NC = "\033[0m"
except NameError:
    pass


def prompt(msg: str, default: str = "") -> str:
    """Ask user for input."""
    if default:
        val = input(f"  {C}?{NC}  {msg} [{default}]: ").strip()
        return val if val else default
    return input(f"  {C}?{NC}  {msg}: ").strip()


def yesno(msg: str, default: bool = True) -> bool:
    """Ask yes/no question."""
    hint = "Y/n" if default else "y/N"
    val = input(f"  {C}?{NC}  {msg} [{hint}]: ").strip().lower()
    if not val:
        return default
    return val.startswith("y")


def box_title(title: str) -> None:
    """Draw boxed title."""
    width = max(len(title) + 4, 50)
    tl = "\u250c"
    h = "\u2500"
    tr = "\u2510"
    v = "\u2502"
    br = "\u2518"
    bl = "\u2514"
    echo(f"  {tl}{h * (width - 2)}{tr}")
    echo(f"  {v}{title:^{width - 2}}{v}")
    echo(f"  {bl}{h * (width - 2)}{br}")


# ─── Package managers ────────────────────────────────────────────────────

def detect_pkg_manager() -> Optional[str]:
    """Detect available package manager."""
    if IS_LINUX:
        for mgr in ["apt-get", "apt", "dnf", "yum", "pacman", "zypper"]:
            if _run(["which", mgr])[2] == 0:
                return mgr
        return None
    elif IS_MACOS:
        return "brew" if _run(["which", "brew"])[2] == 0 else None
    elif IS_WINDOWS:
        for mgr in ["choco", "winget", "scoop"]:
            if _run(["where", mgr])[2] == 0:
                return mgr
        return None
    return None


def install_psql_cmd(pkg_mgr: str) -> Optional[List[str]]:
    """Return install command for PostgreSQL client."""
    if pkg_mgr in ("apt-get", "apt"):
        return ["sudo", pkg_mgr, "install", "-y", "postgresql-client"]
    elif pkg_mgr == "dnf":
        return ["sudo", "dnf", "install", "-y", "postgresql"]
    elif pkg_mgr == "yum":
        return ["sudo", "yum", "install", "-y", "postgresql"]
    elif pkg_mgr == "pacman":
        return ["sudo", "pacman", "-S", "--noconfirm", "postgresql"]
    elif pkg_mgr == "zypper":
        return ["sudo", "zypper", "install", "-y", "postgresql"]
    elif pkg_mgr == "brew":
        return ["brew", "install", "postgresql"]
    elif pkg_mgr == "choco":
        return ["choco", "install", "-y", "postgresql"]
    elif pkg_mgr == "winget":
        return ["winget", "install", "-e", "--id", "PostgreSQL.PostgreSQL"]
    elif pkg_mgr == "scoop":
        return ["scoop", "install", "postgresql"]
    return None


def install_node_cmd(pkg_mgr: str) -> Optional[List[str]]:
    """Return install command for Node.js."""
    if pkg_mgr in ("apt-get", "apt"):
        # Ubuntu/Debian: use NodeSource or distro package
        return ["sudo", pkg_mgr, "install", "-y", "nodejs", "npm"]
    elif pkg_mgr == "dnf":
        return ["sudo", "dnf", "install", "-y", "nodejs", "npm"]
    elif pkg_mgr == "yum":
        return ["sudo", "yum", "install", "-y", "nodejs", "npm"]
    elif pkg_mgr == "pacman":
        return ["sudo", "pacman", "-S", "--noconfirm", "nodejs", "npm"]
    elif pkg_mgr == "zypper":
        return ["sudo", "zypper", "install", "-y", "nodejs", "npm"]
    elif pkg_mgr == "brew":
        return ["brew", "install", "node"]
    elif pkg_mgr == "choco":
        return ["choco", "install", "-y", "nodejs"]
    elif pkg_mgr == "winget":
        return ["winget", "install", "-e", "--id", "OpenJS.NodeJS"]
    elif pkg_mgr == "scoop":
        return ["scoop", "install", "nodejs"]
    return None


# ─── Dependency checks ───────────────────────────────────────────────────

class DepInfo:
    name: str
    found: bool
    version: str
    required: bool
    auto_install: bool

    def __init__(self, name: str, version: str = "", found: bool = False, required: bool = True):
        self.name = name
        self.found = found
        self.version = version
        self.required = required
        self.auto_install = False


def check_python() -> DepInfo:
    """Check Python version."""
    v = sys.version_info
    found = v.major >= 3 and v.minor >= 8
    return DepInfo(
        name="Python",
        version=f"{v.major}.{v.minor}.{v.micro}",
        found=found,
        required=True,
    )


def check_psql() -> DepInfo:
    """Check PostgreSQL client availability."""
    out, _, rc = _run(["psql", "--version"])
    if rc == 0 and out:
        ver = out.split()[-1] if out.split() else "?"
        return DepInfo(name="psql (PostgreSQL)", version=ver, found=True, required=False)
    return DepInfo(name="psql (PostgreSQL)", found=False, required=False)


def check_node() -> DepInfo:
    """Check Node.js availability."""
    out, _, rc = _run(["node", "--version"])
    if rc == 0 and out:
        return DepInfo(name="Node.js", version=out.strip(), found=True, required=False)
    return DepInfo(name="Node.js", found=False, required=False)


def check_npm() -> DepInfo:
    """Check npm availability."""
    out, _, rc = _run(["npm", "--version"])
    if rc == 0 and out:
        return DepInfo(name="npm", version=out.strip(), found=True, required=False)
    return DepInfo(name="npm", found=False, required=False)


def check_all(auto_install: bool = False) -> List[DepInfo]:
    """Check all dependencies."""
    deps = [
        check_python(),
        check_psql(),
        check_node(),
        check_npm(),
    ]
    for d in deps:
        d.auto_install = auto_install
    return deps


# ─── Installer logic ─────────────────────────────────────────────────────

def attempt_install(dep: DepInfo) -> bool:
    """Attempt to install a missing dependency."""
    pkg_mgr = detect_pkg_manager()
    if not pkg_mgr:
        status_warn(f"Tidak ada package manager terdeteksi untuk install {dep.name}")
        return False

    if dep.name.startswith("psql") or dep.name == "PostgreSQL client":
        cmd = install_psql_cmd(pkg_mgr)
    elif dep.name == "Node.js":
        cmd = install_node_cmd(pkg_mgr)
    elif dep.name == "npm":
        # npm comes with Node.js
        status_info("npm akan terinstall otomatis bersama Node.js")
        return attempt_install(check_node())
    else:
        return False

    if not cmd:
        status_warn(f"Tidak tahu cara install {dep.name} via {pkg_mgr}")
        return False

    print(f"    {D}→{NC}  {' '.join(cmd)}")
    rc = _run_interactive(cmd)
    success = rc == 0

    if success:
        status_ok(f"{dep.name} berhasil diinstall")
        # Re-check
        if dep.name.startswith("psql"):
            result = check_psql()
        elif dep.name == "Node.js":
            result = check_node()
        else:
            result = dep
        dep.found = result.found
        dep.version = result.version
    else:
        status_fail(f"Gagal install {dep.name} (exit code {rc})")

    return success


# ─── Config setup ────────────────────────────────────────────────────────

def setup_config() -> Dict[str, str]:
    """Interactive config wizard. Returns config dict."""
    box_title("Konfigurasi Database")

    echo(f"  {D}Database ini akan digunakan untuk backup.{NC}")
    echo()

    host = prompt("Host PostgreSQL", "127.0.0.1")
    port = prompt("Port", "5432")
    db = prompt("Nama database", "postgres")
    user = prompt("User", "postgres")
    passwd = prompt("Password")

    interval = prompt("Interval backup otomatis (jam)", "6")
    remote_url = prompt("Remote storage URL (optional)", "")

    echo()
    box_title("Ringkasan")

    echo(f"""
  {B}Database:{NC}      {host}:{port}/{db} as {user}
  {B}Backup:{NC}        Every {interval}h
  {B}Remote:{NC}        {remote_url or '(none)'}
""")

    if not yesno("Simpan konfigurasi ini?", True):
        status_info("Dibatalkan")
        return {}

    GAET_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    config = {
        "host": host,
        "port": port,
        "name": db,
        "user": user,
        "password": passwd,
        "interval": interval,
        "remote_url": remote_url,
    }

    # Write .env
    env_lines = [
        f'GAET_DB_HOST={host}',
        f'GAET_DB_PORT={port}',
        f'GAET_DB_NAME={db}',
        f'GAET_DB_USER={user}',
        f'GAET_DB_PASSWORD={passwd}',
        f'GAET_BACKUP_INTERVAL={interval}',
        f'GAET_DASHBOARD_PORT=9191',
        f'GAET_DASHBOARD_HOST=0.0.0.0',
    ]
    if remote_url:
        env_lines.append(f'GAET_REMOTE_URL={remote_url}')
    # Add backup schedule
    env_lines.append(f'GAET_SERVICE_PREFIX=gaet')

    ENV_FILE.write_text("\n".join(env_lines) + "\n")
    status_ok(f"Konfigurasi tersimpan di {ENV_FILE}")

    return config


# ─── Dashboard build ─────────────────────────────────────────────────────

def find_dashboard_dir() -> Optional[Path]:
    """Locate the dashboard directory."""
    script_dir = Path(sys.argv[0]).resolve().parent
    candidates = [
        script_dir / "dashboard",
        script_dir.parent / "dashboard",
        HOME / "Projects/gaet/dashboard",
        GAET_DIR / "dashboard",
        Path.cwd() / "dashboard",
    ]
    if "GAET_PROJECT_DIR" in os.environ:
        candidates.insert(0, Path(os.environ["GAET_PROJECT_DIR"]) / "dashboard")
    for c in candidates:
        if c.is_dir() and (c / "package.json").is_file():
            return c
    return None


def build_dashboard(dashboard_dir: Path) -> bool:
    """Run npm install + npm run build."""
    box_title("Build Dashboard")

    if (dashboard_dir / ".next").is_dir():
        echo(f"  {D}Dashboard sudah di-build sebelumnya.{NC}")
        if yesno("Build ulang?", False):
            shutil.rmtree(dashboard_dir / ".next")
        else:
            status_ok("Menggunakan build yang sudah ada")
            return True

    echo(f"  {D}Dashboard: {dashboard_dir}{NC}")

    # npm install
    if not (dashboard_dir / "node_modules").is_dir():
        status_info("Menginstall dependencies (npm install)...")
        rc = _run_interactive(["npm", "install", "--silent"], cwd=str(dashboard_dir))
        if rc != 0:
            status_fail("npm install gagal")
            return False
        status_ok("Dependencies terinstall")
    else:
        status_ok("node_modules sudah ada")

    # npm run build
    status_info("Membangun dashboard (npm run build)...")
    rc = _run_interactive(["npm", "run", "build"], cwd=str(dashboard_dir))
    if rc != 0:
        status_fail("Build dashboard gagal")
        return False
    status_ok("Dashboard siap!")

    return True


# ─── Scheduler setup ─────────────────────────────────────────────────────

def setup_auto_backup(interval_hours: int) -> bool:
    """Enable auto-backup with given interval."""
    box_title("Setup Auto-Backup")

    # Import scheduler (from installed package or inline)
    try:
        from scripts.scheduler import scheduler_enable, get_scheduler_name
        name = get_scheduler_name()
    except ImportError:
        from gaet import scheduler_enable, get_scheduler_name
        name = get_scheduler_name()

    status_info(f"Mengaktifkan auto-backup via {name} setiap {interval_hours} jam...")
    scheduler_enable("gaet", interval_hours)
    status_ok(f"Auto-backup aktif setiap {interval_hours} jam")
    return True


def setup_dashboard_service(dashboard_dir: Path) -> bool:
    """Enable dashboard service via service_manager."""
    box_title("Setup Dashboard Service")

    try:
        from scripts.service_manager import service_start, service_is_running
    except ImportError:
        from gaet import _svc_start as service_start
        from gaet import _svc_is_running as service_is_running

    if service_is_running():
        status_ok("Dashboard sudah berjalan")
        return True

    status_info("Memulai dashboard service...")
    ok, msg = service_start(dashboard_dir=dashboard_dir)
    if ok:
        status_ok("Dashboard service aktif")
        return True
    else:
        status_warn(f"Gagal: {msg}")
        return False


# ─── Main installer ──────────────────────────────────────────────────────

def run(
    yes: bool = False,
    skip_deps: bool = False,
    skip_build: bool = False,
    skip_config: bool = False,
    skip_service: bool = False,
    interval: int = 0,
) -> int:
    """
    Run the installer.

    Returns 0 on success, 1 on failure.
    """
    os_info = detect_os()
    pkg_mgr = detect_pkg_manager()

    box_title(f"gaet Installer — {os_info['distro']} {os_info['version']}")

    echo(f"""
  {B}Platform:{NC}   {os_info['os']} ({os_info['distro']})
  {B}Package:{NC}    {pkg_mgr or '(none detected)'}
  {B}Auto-mode:{NC}  {'YES' if yes else 'interactive'}
""")

    # ── Step 1: Check deps ──────────────────────────────────────────
    if not skip_deps:
        box_title("Cek Dependencies")

        deps = check_all()
        all_ok = True
        needs_shell = False

        for dep in deps:
            if dep.found:
                echo(f"  {G}{ICON_OK}{NC}  {dep.name:20s} {D}{dep.version}{NC}")
            else:
                label = f"{'[optional]' if not dep.required else '[required]'}"
                echo(f"  {R}{ICON_FAIL}{NC}  {dep.name:20s} {R}{label}{NC}")
                all_ok = False

                # Auto-install?
                if dep.required or (not dep.required and yes):
                    should_install = yes
                elif dep.auto_install:
                    should_install = True
                else:
                    should_install = yesno(f"Install {dep.name}?", True)

                if should_install:
                    if attempt_install(dep):
                        continue
                    elif not dep.required:
                        status_warn(f"{dep.name} tidak wajib, lanjut saja")
                    else:
                        status_fail(f"{dep.name} wajib tapi gagal diinstall")
                        return 1
                else:
                    needs_shell = True

        if not all_ok:
            echo()
            if needs_shell:
                echo(f"  {Y}Beberapa dependencies tidak terinstall.{NC}")
                echo(f"  {Y}Kamu bisa install manual atau jalankan ulang dengan --yes{NC}")
                if not yesno("Lanjutkan?", False):
                    return 1

    # ── Step 2: Setup config ────────────────────────────────────────
    if not skip_config:
        if ENV_FILE.exists() and not yes:
            echo()
            echo(f"  {D}Config sudah ada di {ENV_FILE}{NC}")
            if not yesno("Konfigurasi ulang?", False):
                config = _read_existing_config()
            else:
                config = setup_config()
        else:
            config = setup_config()

        if not config:
            status_warn("Konfigurasi tidak lengkap")
            if not yes:
                return 1
    else:
        config = _read_existing_config() or {}

    # ── Step 3: Find & build dashboard ──────────────────────────────
    dashboard_dir = find_dashboard_dir()

    if not dashboard_dir:
        status_warn("Dashboard directory tidak ditemukan. Dashboard akan di-skip.")
        echo(f"  {D}Cari di dalam folder proyek gaet atau set GAET_PROJECT_DIR{NC}")
    elif not skip_build:
        if not build_dashboard(dashboard_dir):
            status_warn("Build dashboard gagal, lanjut tanpa dashboard")
            dashboard_dir = None
    else:
        echo(f"  {D}Build dashboard di-skip (--skip-build){NC}")

    # ── Step 4: Setup scheduler ─────────────────────────────────────
    if interval > 0:
        setup_auto_backup(interval)

    # ── Step 5: Setup dashboard service ─────────────────────────────
    if dashboard_dir and not skip_service:
        setup_dashboard_service(dashboard_dir)

    # ── Done ────────────────────────────────────────────────────────
    echo()
    box_title("Instalasi Selesai!")

    echo(f"""
  {G}{ICON_OK}{NC}  gaet siap digunakan!

  {B}Perintah:{NC}
    python gaet.py --help      Bantuan
    python gaet.py check       Cek koneksi database
    python gaet.py push        Backup manual
    python gaet.py push --auto Auto-backup
    python gaet.py serve       Dashboard web
    python gaet.py stop        Hentikan service

  {D}Config:{NC}      {ENV_FILE}
  {D}Dashboard:{NC}   http://localhost:9191
""")

    return 0


def _read_existing_config() -> Dict[str, str]:
    """Read existing .env file into dict."""
    config: Dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                config[k] = v
    return config


# ─── CLI ─────────────────────────────────────────────────────────────────

def main_cli():
    """CLI entry point for `python install.py`."""
    import argparse

    parser = argparse.ArgumentParser(
        description="gaet universal installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python install.py              interactive
              python install.py --yes        auto-install missing deps
              python install.py --skip-deps  hanya setup config & build
        """),
    )
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve semua (non-interactive)")
    parser.add_argument("--skip-deps", action="store_true", help="Skip pengecekan dependencies")
    parser.add_argument("--skip-build", action="store_true", help="Skip build dashboard")
    parser.add_argument("--skip-config", action="store_true", help="Skip config wizard")
    parser.add_argument("--skip-service", action="store_true", help="Skip dashboard service setup")
    parser.add_argument("--interval", type=int, default=0, help="Set auto-backup interval (jam), 0 = skip")
    args = parser.parse_args()

    sys.exit(run(
        yes=args.yes,
        skip_deps=args.skip_deps,
        skip_build=args.skip_build,
        skip_config=args.skip_config,
        skip_service=args.skip_service,
        interval=args.interval,
    ))


if __name__ == "__main__":
    main_cli()
