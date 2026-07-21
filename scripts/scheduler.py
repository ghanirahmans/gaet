"""
scheduler.py — Platform scheduler abstraction for gaet

Provides a unified interface to enable, disable, and check periodic
backup schedules across Linux (systemd --user), macOS (launchd),
and Windows (Task Scheduler / schtasks).

Uses only Python standard library — no external dependencies.
"""

import os
import re
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

# ── Platform detection ──────────────────────────────────────────────────────

IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

HOME = Path.home()

# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _run(
    cmd: List[str], timeout: int = 10
) -> Tuple[str, str, int]:
    """Run *cmd* and return ``(stdout, stderr, returncode)``.

    Silently catches all exceptions so callers never have to handle
    ``FileNotFoundError``, ``TimeoutExpired``, etc. — failures are
    reflected as a non-zero return code.
    """
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {timeout}s", -1
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", -1
    except Exception as exc:
        return "", str(exc), -1


def _log_path(prefix: str) -> Path:
    """
    Return the filesystem path for the backup log file.

    Konsisten dengan konfigurasi gaet: semua log di ~/.gaet/backups/.
    """
    base = HOME / ".gaet" / "backups"
    base.mkdir(parents=True, exist_ok=True)
    return base / "cron.log"  # semuanya pakai 1 file cron.log


# ═══════════════════════════════════════════════════════════════════════════════
# Linux  – systemd --user  (service + timer units)
# ═══════════════════════════════════════════════════════════════════════════════


def _linux_is_active(prefix: str) -> bool:
    """Return ``True`` when the systemd user timer is active."""
    stdout, _, rc = _run(
        ["systemctl", "--user", "is-active", f"{prefix}-backup.timer"]
    )
    return rc == 0 and stdout == "active"


def _linux_enable(prefix: str, interval: int, cli_path: str) -> bool:
    """Install and start a systemd --user service + timer pair."""
    systemd_dir = HOME / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    log = _log_path(prefix)
    cli = shutil.which(cli_path) or cli_path

    # ── Service unit ─────────────────────────────────────────────────────
    service_unit = systemd_dir / f"{prefix}-backup.service"
    service_content = f"""\
[Unit]
Description=gaet backup to remote database
After=network.target

[Service]
Type=oneshot
ExecStart="{cli}" push --cron
StandardOutput=append:{log}
StandardError=append:{log}
"""
    try:
        service_unit.write_text(service_content, encoding="utf-8")
    except OSError:
        return False

    # ── Timer unit ───────────────────────────────────────────────────────
    timer_unit = systemd_dir / f"{prefix}-backup.timer"
    timer_content = f"""\
[Unit]
Description=gaet periodic backup (every {interval}h)

[Timer]
OnCalendar=*-*-* 00/{interval}:00:00
Persistent=true
RandomizedDelaySec=30

[Install]
WantedBy=timers.target
"""
    try:
        timer_unit.write_text(timer_content, encoding="utf-8")
    except OSError:
        return False

    # Reload systemd user daemon, enable & start the timer
    _run(["systemctl", "--user", "daemon-reload"])
    _, _, rc = _run(
        ["systemctl", "--user", "enable", "--now", f"{prefix}-backup.timer"]
    )
    return rc == 0


def _linux_disable(prefix: str) -> bool:
    """Stop and remove the systemd --user timer (and its service unit)."""
    systemd_dir = HOME / ".config" / "systemd" / "user"

    # Stop + disable timer first
    _, _, rc = _run(
        ["systemctl", "--user", "disable", "--now", f"{prefix}-backup.timer"]
    )

    # Remove unit files
    for name in (f"{prefix}-backup.timer", f"{prefix}-backup.service"):
        unit = systemd_dir / name
        if unit.exists():
            unit.unlink()

    _run(["systemctl", "--user", "daemon-reload"])
    _run(["systemctl", "--user", "reset-failed"])

    return rc == 0


# ═══════════════════════════════════════════════════════════════════════════════
# macOS – launchd  (LaunchAgent plist)
# ═══════════════════════════════════════════════════════════════════════════════


def _macos_is_active(prefix: str) -> bool:
    """Return ``True`` when the launchd plist is loaded.

    ``launchctl list`` exits 0 and prints info when the job is loaded;
    it exits non-zero or prints nothing when the job is unknown.
    """
    stdout, _, rc = _run(["launchctl", "list", f"{prefix}-backup"])
    if rc != 0:
        return False
    # A loaded job whose last exit status is 0 will show something like:
    #   "PID"  "status"  "label"
    # If the job is not found launchctl still exits 0 but returns empty.
    return bool(stdout) and f"{prefix}-backup" in stdout


def _macos_enable(prefix: str, interval: int, cli_path: str) -> bool:
    """Write a LaunchAgent plist and load it via ``launchctl``."""
    agents_dir = HOME / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    log = _log_path(prefix)
    cli = shutil.which(cli_path) or cli_path

    plist_path = agents_dir / f"{prefix}-backup.plist"
    seconds = interval * 3600

    plist_content = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{xml_escape(f"{prefix}-backup")}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{xml_escape(cli)}</string>
        <string>push</string>
        <string>--cron</string>
    </array>
    <key>StartInterval</key>
    <integer>{seconds}</integer>
    <key>StandardOutPath</key>
    <string>{xml_escape(str(log))}</string>
    <key>StandardErrorPath</key>
    <string>{xml_escape(str(log))}</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
    try:
        plist_path.write_text(plist_content, encoding="utf-8")
    except OSError:
        return False

    _, _, rc = _run(["launchctl", "load", str(plist_path)])
    return rc == 0


def _macos_disable(prefix: str) -> bool:
    """Unload and remove the launchd plist."""
    plist_path = HOME / "Library" / "LaunchAgents" / f"{prefix}-backup.plist"

    if plist_path.exists():
        _run(["launchctl", "unload", str(plist_path)])
        try:
            plist_path.unlink()
        except OSError:
            return False

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Windows – Task Scheduler (schtasks.exe)
# ═══════════════════════════════════════════════════════════════════════════════


def _windows_is_active(prefix: str) -> bool:
    """Return ``True`` when the scheduled task exists."""
    _, _, rc = _run(["schtasks", "/Query", "/TN", f"{prefix}-backup"])
    return rc == 0


def _windows_enable(prefix: str, interval: int, cli_path: str) -> bool:
    """Create a scheduled task via ``schtasks /Create``."""
    # Resolve full path for reliability — schtasks needs absolute paths
    cli = cli_path
    if not cli_path.endswith(".py") and not cli_path.startswith(sys.executable):
        which_result = shutil.which(cli_path)
        if which_result:
            cli = which_result

    log = _log_path(prefix)

    # schtasks /Create accepts:
    #   /SC HOURLY /MO {interval}
    #   /TR "{cli} push --cron"
    cmd = [
        "schtasks",
        "/Create",
        "/SC", "HOURLY",
        "/MO", str(interval),
        "/TN", f"{prefix}-backup",
        "/TR", f'"{cli}" push --cron',
        "/F",  # force overwrite if exists
    ]
    _, _, rc = _run(cmd, timeout=15)
    return rc == 0


def _windows_disable(prefix: str) -> bool:
    """Delete the scheduled task via ``schtasks /Delete``."""
    _, _, rc = _run(
        ["schtasks", "/Delete", "/F", "/TN", f"{prefix}-backup"],
        timeout=15,
    )
    return rc == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════


def scheduler_is_active(prefix: str) -> bool:
    """Check whether the periodic backup scheduler is currently active.

    Parameters
    ----------
    prefix : str
        Unique prefix for the backup schedule (e.g. ``"myapp"``).

    Returns
    -------
    bool
        ``True`` if the scheduler is active/enabled/loaded on the current
        platform.

    Platform details
    ----------------
    - **Linux**  — ``systemctl --user is-active {prefix}-backup.timer``
    - **macOS**  — ``launchctl list {prefix}-backup``
    - **Windows** — ``schtasks /Query /TN {prefix}-backup``
    """
    if IS_LINUX:
        return _linux_is_active(prefix)
    elif IS_MACOS:
        return _macos_is_active(prefix)
    elif IS_WINDOWS:
        return _windows_is_active(prefix)
    else:
        return False


def scheduler_enable(prefix: str, interval: int, cli_path: str) -> bool:
    """Enable a periodic backup schedule.

    Parameters
    ----------
    prefix : str
        Unique prefix for the backup schedule.
    interval : int
        Number of **hours** between backups (e.g. ``6`` = every 6 hours).
    cli_path : str
        Path (or name resolvable via ``shutil.which``) to the ``gaet`` CLI
        executable.

    Returns
    -------
    bool
        ``True`` on success.

    Platform details
    ----------------
    - **Linux**  — creates ``~/.config/systemd/user/{prefix}-backup.{service,timer}``
                  and runs ``systemctl --user enable --now``.
    - **macOS**  — creates ``~/Library/LaunchAgents/{prefix}-backup.plist``
                  and runs ``launchctl load``.
    - **Windows** — runs ``schtasks /Create /SC HOURLY /MO {interval} /TN {prefix}-backup``.
    """
    if IS_LINUX:
        return _linux_enable(prefix, interval, cli_path)
    elif IS_MACOS:
        return _macos_enable(prefix, interval, cli_path)
    elif IS_WINDOWS:
        return _windows_enable(prefix, interval, cli_path)
    else:
        return False


def scheduler_disable(prefix: str) -> bool:
    """Disable and remove the periodic backup schedule.

    Parameters
    ----------
    prefix : str
        Unique prefix for the backup schedule to remove.

    Returns
    -------
    bool
        ``True`` on success.

    Platform details
    ----------------
    - **Linux**  — ``systemctl --user disable --now`` + remove unit files.
    - **macOS**  — ``launchctl unload`` + remove plist file.
    - **Windows** — ``schtasks /Delete /F /TN {prefix}-backup``.
    """
    if IS_LINUX:
        return _linux_disable(prefix)
    elif IS_MACOS:
        return _macos_disable(prefix)
    elif IS_WINDOWS:
        return _windows_disable(prefix)
    else:
        return False


def get_scheduler_name() -> str:
    """Return a human-readable name for the current platform's scheduler.

    Returns
    -------
    str
        One of ``"systemd (user)"``, ``"launchd"``, ``"Task Scheduler"``,
        or ``"unknown"``.
    """
    if IS_LINUX:
        return "systemd (user)"
    elif IS_MACOS:
        return "launchd"
    elif IS_WINDOWS:
        return "Task Scheduler"
    else:
        return "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entry point  (python -m scripts.scheduler ...)
# ═══════════════════════════════════════════════════════════════════════════════


def _main() -> None:
    """Minimal CLI for testing scheduler operations directly."""
    import argparse

    parser = argparse.ArgumentParser(description="gaet scheduler manager")
    parser.add_argument("action", choices=["status", "enable", "disable"])
    parser.add_argument("--prefix", default="gaet")
    parser.add_argument("--interval", type=int, default=6)
    parser.add_argument("--cli-path", default="gaet")

    args = parser.parse_args()

    if not re.match(r'^[a-zA-Z0-9_-]+$', args.prefix):
        print(f"Error: prefix '{args.prefix}' contains invalid characters")
        sys.exit(1)

    if args.action == "status":
        name = get_scheduler_name()
        active = scheduler_is_active(args.prefix)
        print(f"Scheduler platform : {name}")
        print(f"Active             : {'yes' if active else 'no'}")
        sys.exit(0 if active else 1)

    elif args.action == "enable":
        ok = scheduler_enable(args.prefix, args.interval, args.cli_path)
        print(f"Scheduler enabled  : {'yes' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)

    elif args.action == "disable":
        ok = scheduler_disable(args.prefix)
        print(f"Scheduler disabled : {'yes' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    _main()
