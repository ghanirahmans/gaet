"""
scripts/service_manager.py — Cross-platform dashboard service manager

Platform strategy (best practice, minimal resource):
  - Linux:    systemd --user service (built-in, zero overhead)
  - macOS:    launchd plist (built-in, zero overhead)
  - Windows:  PID file + subprocess.DETACHED_PROCESS (zero deps, < 1 KB)

All platforms:
  - start()   → build + start dashboard sebagai background service
  - stop()    → stop dashboard (systemd/launchctl/taskkill)
  - is_running() → cek apakah dashboard aktif
  - status()  → dict dengan info service
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─── Platform detection ───────────────────────────────────────────────
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
PLATFORM = "linux" if IS_LINUX else "macos" if IS_MACOS else "windows" if IS_WINDOWS else "unknown"

# ─── Paths ─────────────────────────────────────────────────────────────
HOME = Path.home()
GAET_DIR = HOME / ".gaet"
BACKUP_DIR = GAET_DIR / "backups"
LOG_DIR = BACKUP_DIR
PID_FILE = GAET_DIR / "dashboard.pid"
LOG_FILE = LOG_DIR / "dashboard.log"

# ─── Helpers ────────────────────────────────────────────────────────────

def _run(cmd, timeout: int = 15, cwd: Optional[str] = None) -> Tuple[str, str, int]:
    """Run command, return (stdout, stderr, returncode)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT", 1
    except FileNotFoundError:
        return "", "NOT_FOUND", 127
    except Exception as e:
        return "", str(e), 1


def _find_node() -> Optional[str]:
    """Find node/npm executables."""
    for exe in ["node", "node.exe"]:
        p = shutil.which(exe)
        if p:
            return p
    return None


def _find_npm() -> Optional[str]:
    for exe in ["npm", "npm.cmd"]:
        p = shutil.which(exe)
        if p:
            return p
    return None


def _ensure_dirs() -> None:
    GAET_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _write_pid(pid: int) -> None:
    _ensure_dirs()
    PID_FILE.write_text(str(pid))


def _read_pid() -> Optional[int]:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def _delete_pid() -> None:
    PID_FILE.unlink(missing_ok=True)


def _next_cmd(dashboard_dir: Path) -> Optional[List[str]]:
    """Return the next start command as a list.
    Returns a list of arguments suitable for subprocess.Popen.
    """
    # Try to find next.js binary
    candidates = [
        dashboard_dir / "node_modules" / ".bin" / "next",
        dashboard_dir / "node_modules" / "next" / "dist" / "bin" / "next.js",
    ]
    for c in candidates:
        if c.exists():
            # Use node to execute next.js (avoids shebang/symlink issues in systemd)
            node = _find_node()
            if node:
                return [node, str(c)]
            return [str(c)]
    return None


# ─── Platform implementations ──────────────────────────────────────────

def _linux_is_running() -> bool:
    out, _, rc = _run(["systemctl", "--user", "is-active", "gaet-dashboard.service"])
    return rc == 0 and out.strip() == "active"


def _linux_start(dashboard_dir: Path, port: int, host: str, node: str) -> Tuple[bool, str]:
    """Create & start systemd user service for the dashboard."""
    log = str(LOG_FILE)
    next_cmd = _next_cmd(dashboard_dir)
    if not next_cmd:
        return False, "next executable tidak ditemukan"
    exec_cmd = " ".join(next_cmd + ["start", "-p", str(port), "-H", host])

    user_systemd = HOME / ".config" / "systemd" / "user"
    user_systemd.mkdir(parents=True, exist_ok=True)

    svc_content = textwrap.dedent(f"""\
    [Unit]
    Description=gaet dashboard
    After=network.target

    [Service]
    Type=simple
    ExecStart={exec_cmd}
    WorkingDirectory={dashboard_dir}
    Restart=on-failure
    RestartSec=5
    StandardOutput=append:{log}
    StandardError=append:{log}

    [Install]
    WantedBy=default.target
    """)

    svc_path = user_systemd / "gaet-dashboard.service"
    svc_path.write_text(svc_content)

    # Stop existing service first if running
    _run(["systemctl", "--user", "stop", "gaet-dashboard.service"], timeout=5)
    _run(["systemctl", "--user", "daemon-reload"], timeout=10)
    _, _, rc = _run(["systemctl", "--user", "enable", "--now", "gaet-dashboard.service"], timeout=15)

    if rc == 0:
        time.sleep(1)  # biar systemd settle
        return True, "systemd service started"
    return False, "systemctl enable --now failed"


def _linux_stop() -> Tuple[bool, str]:
    _, _, rc1 = _run(["systemctl", "--user", "stop", "gaet-dashboard.service"], timeout=10)
    _, _, rc2 = _run(["systemctl", "--user", "disable", "gaet-dashboard.service"], timeout=10)
    svc_path = HOME / ".config" / "systemd" / "user" / "gaet-dashboard.service"
    svc_path.unlink(missing_ok=True)
    _run(["systemctl", "--user", "daemon-reload"], timeout=5)
    ok = rc1 == 0 or rc2 == 0
    return ok, "stopped" if ok else "stop failed"


def _macos_is_running() -> bool:
    plist = HOME / "Library" / "LaunchAgents" / "com.gaet.dashboard.plist"
    if not plist.exists():
        return False
    out, _, rc = _run(["launchctl", "list", "com.gaet.dashboard"])
    return rc == 0


def _macos_start(dashboard_dir: Path, port: int, host: str, node: str) -> Tuple[bool, str]:
    """Create & load launchd plist for the dashboard."""
    log = str(LOG_FILE)
    next_cmd = _next_cmd(dashboard_dir)
    if not next_cmd:
        return False, "next executable tidak ditemukan"
    # launchd plist uses individual array elements (no shell escaping needed)
    plist_args = next_cmd + ["start", "-p", str(port), "-H", host]

    launch_agents = HOME / "Library" / "LaunchAgents"
    launch_agents.mkdir(parents=True, exist_ok=True)

    plist_content = textwrap.dedent(f"""\
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
      "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.gaet.dashboard</string>
        <key>ProgramArguments</key>
        <array>
            <string>{"</string><string>".join(plist_args)}</string>
        </array>
        <key>WorkingDirectory</key>
        <string>{dashboard_dir}</string>
        <key>KeepAlive</key>
        <true/>
        <key>RunAtLoad</key>
        <true/>
        <key>StandardOutPath</key>
        <string>{log}</string>
        <key>StandardErrorPath</key>
        <string>{log}</string>
    </dict>
    </plist>
    """)

    plist_path = launch_agents / "com.gaet.dashboard.plist"
    plist_path.write_text(plist_content)

    # Unload first if exists
    _run(["launchctl", "unload", str(plist_path)], timeout=5)
    _, _, rc = _run(["launchctl", "load", str(plist_path)], timeout=10)

    if rc == 0:
        time.sleep(1)
        return True, "launchd plist loaded"
    return False, f"launchctl load failed (rc={rc})"


def _macos_stop() -> Tuple[bool, str]:
    plist_path = HOME / "Library" / "LaunchAgents" / "com.gaet.dashboard.plist"
    if plist_path.exists():
        _run(["launchctl", "unload", str(plist_path)], timeout=10)
        plist_path.unlink(missing_ok=True)
        return True, "stopped"
    return True, "not running"


def _windows_is_running() -> bool:
    """Check PID file + verify process still exists via tasklist."""
    pid = _read_pid()
    if pid is None:
        return False
    # tasklist returns "INFO: No tasks ..." if PID not found
    out, _, rc = _run(["tasklist", "/FI", f"PID eq {pid}", "/NH"])
    if str(pid) in out:
        return True
    # Stale PID
    _delete_pid()
    return False


def _windows_start(dashboard_dir: Path, port: int, host: str, node: str) -> Tuple[bool, str]:
    """Start dashboard as detached background process + save PID."""
    log = str(LOG_FILE)

    next_cmd = _next_cmd(dashboard_dir)
    if not next_cmd:
        return False, "next executable tidak ditemukan di node_modules"

    cmd = next_cmd + ["start", "-p", str(port), "-H", host]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(dashboard_dir),
            stdout=open(log, "a"),
            stderr=subprocess.STDOUT,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        _write_pid(proc.pid)
        time.sleep(2)  # Wait for startup
        if _windows_is_running():
            return True, f"started (PID {proc.pid})"
        return False, "process exited immediately"
    except Exception as e:
        return False, str(e)


def _windows_stop() -> Tuple[bool, str]:
    pid = _read_pid()
    if pid is None:
        return True, "not running"
    # Graceful first, then force
    _, _, rc = _run(["taskkill", "/PID", str(pid), "/T"], timeout=5)
    if rc != 0:
        _, _, rc = _run(["taskkill", "/F", "/PID", str(pid), "/T"], timeout=5)
    _delete_pid()
    return rc == 0, "stopped" if rc == 0 else f"failed to kill PID {pid}"


# ─── Public API ────────────────────────────────────────────────────────

def is_running() -> bool:
    """Check if the gaet dashboard service is currently running."""
    if IS_LINUX:
        return _linux_is_running()
    elif IS_MACOS:
        return _macos_is_running()
    elif IS_WINDOWS:
        return _windows_is_running()
    return False


def start(
    dashboard_dir: Optional[Path] = None,
    port: int = 9191,
    host: str = "0.0.0.0",
    foreground: bool = False,
) -> Tuple[bool, str]:
    """
    Start the dashboard server.

    Args:
        dashboard_dir: Path to the dashboard project (auto-detect if None).
        port: HTTP port (default 9191).
        host: Bind address (default 0.0.0.0).
        foreground: If True, run in foreground (for dev).

    Returns:
        (success, message)
    """
    node = _find_node()
    if not node:
        return False, "node.js tidak ditemukan di PATH"

    if dashboard_dir is None:
        dashboard_dir = _find_dashboard_dir()
    if dashboard_dir is None:
        return False, "dashboard directory tidak ditemukan"

    _ensure_dirs()

    # Build if needed
    if not (dashboard_dir / ".next").is_dir():
        npm = _find_npm()
        if not npm:
            return False, "npm tidak ditemukan (required untuk build)"
        log(f"Building dashboard di {dashboard_dir}...")
        _, err, rc = _run([npm, "install", "--silent"], timeout=120, cwd=str(dashboard_dir))
        if rc != 0:
            return False, f"npm install gagal: {err[:200]}"
        _, err, rc = _run([npm, "run", "build"], timeout=120, cwd=str(dashboard_dir))
        if rc != 0:
            return False, f"npm run build gagal: {err[:200]}"

    if foreground:
        # Run in foreground (for dev / debugging)
        return _start_foreground(dashboard_dir, port, host, node)

    if IS_LINUX:
        return _linux_start(dashboard_dir, port, host, node)
    elif IS_MACOS:
        return _macos_start(dashboard_dir, port, host, node)
    elif IS_WINDOWS:
        return _windows_start(dashboard_dir, port, host, node)
    return False, f"unsupported platform: {sys.platform}"


def stop() -> Tuple[bool, str]:
    """Stop the dashboard service."""
    if IS_LINUX:
        return _linux_stop()
    elif IS_MACOS:
        return _macos_stop()
    elif IS_WINDOWS:
        return _windows_stop()
    return False, f"unsupported platform: {sys.platform}"


def status() -> Dict:
    """Return dict dengan info service dashboard."""
    running = is_running()
    result: Dict = {
        "running": running,
        "platform": PLATFORM,
        "pid": None,
        "port": None,
        "log_file": str(LOG_FILE),
    }
    if IS_WINDOWS and running:
        result["pid"] = _read_pid()
    return result


# ─── Internal ──────────────────────────────────────────────────────────

def log(msg: str) -> None:
    """Append ke dashboard.log + stderr."""
    _ensure_dirs()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)
    print(msg, file=sys.stderr)


def _find_dashboard_dir() -> Optional[Path]:
    """Auto-detect dashboard directory."""
    # Check relative to common locations
    candidates = [
        Path.cwd() / "dashboard",
        Path(sys.argv[0]).resolve().parent / "dashboard",
        Path(sys.argv[0]).resolve().parent.parent / "dashboard",
        HOME / "Projects" / "gaet" / "dashboard",
    ]
    for d in candidates:
        if d.is_dir() and (d / "package.json").is_file():
            return d.resolve()
    return None


def _start_foreground(dashboard_dir: Path, port: int, host: str, node: str) -> Tuple[bool, str]:
    """Start dashboard in foreground (blocking)."""
    cmd = _next_cmd(dashboard_dir)
    if not cmd:
        return False, "next executable tidak ditemukan"
    try:
        subprocess.run(cmd, cwd=str(dashboard_dir))
        return True, "foreground process exited"
    except KeyboardInterrupt:
        return True, "foreground process stopped"
    except Exception as e:
        return False, str(e)


# Export for 'from scripts.service_manager import _run' compatibility
if __name__ == "__main__":
    # Quick test
    print(f"Platform: {PLATFORM}")
    print(f"Node: {_find_node()}")
    print(f"Running: {is_running()}")
    print(f"PID file: {PID_FILE}")

# ─── Aliases for gaet.py imports ────────────────────────────
service_is_running = is_running
service_start = start
service_stop = stop
service_status = status
