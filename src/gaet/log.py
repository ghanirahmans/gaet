"""cmd_log — backup log viewer."""

import argparse
import time
from .core import CRON_LOG, D, LOG_FILE, NAME, NC, Y, argparse, box_title, echo, time

def cmd_log(args: argparse.Namespace) -> None:
    """View backup log (includes cron log when filtered)."""
    lines = args.lines or 30
    filter_str = getattr(args, "filter", None) or ""
    since_str = getattr(args, "since", None) or ""
    follow = getattr(args, "follow", False)

    if follow:
        # tail -f style: poll log files and print new lines (each file
        # keeps its own cursor — LOG_FILE and CRON_LOG advance separately)
        echo(f"  {D}Following log (Ctrl+C to stop){NC}")
        echo()
        positions = {str(LOG_FILE): 0, str(CRON_LOG): 0}
        try:
            while True:
                for src in [LOG_FILE, CRON_LOG]:
                    if src.is_file():
                        with open(str(src), "r", encoding="utf-8", errors="replace") as f:
                            f.seek(positions[str(src)])
                            new_lines = f.readlines()
                            positions[str(src)] = f.tell()
                            for line in new_lines:
                                if filter_str and filter_str.lower() not in line.lower():
                                    continue
                                if since_str and not (line.startswith(f"[{since_str}") or since_str in line):
                                    continue
                                echo(f"  {D}│{NC} {line.rstrip()}")
                time.sleep(1)
        except KeyboardInterrupt:
            echo(f"\n  {D}Follow stopped.{NC}")
        return

    if not LOG_FILE.is_file() and not CRON_LOG.is_file():
        echo(f"  {Y}Belum ada log. Jalankan 'gaet push' dulu.{NC}")
        return

    sources = [LOG_FILE]
    # Include cron.log when user filters for CRON entries (or always merge it,
    # since cron entries use the same timestamp format)
    if CRON_LOG.is_file():
        sources.append(CRON_LOG)

    all_lines = []
    for src in sources:
        with open(str(src), "r", encoding="utf-8", errors="replace") as f:
            all_lines.extend(f.readlines())

    # Apply filters
    filtered = all_lines
    if filter_str:
        filtered = [l for l in filtered if filter_str.lower() in l.lower()]
    if since_str:
        filtered = [l for l in filtered if l.startswith(f"[{since_str}") or since_str in l]

    total = len(all_lines)
    total_filtered = len(filtered)
    start = max(0, total_filtered - lines)

    box_title(f"{NAME} log")
    echo(f"  {D}{total} total lines", end="")
    if filter_str or since_str:
        echo(f" ({total_filtered} filtered)", end="")
    echo(f" (showing {min(lines, total_filtered)}){NC}")
    echo()
    if not filtered and (filter_str or since_str):
        # Helpful context when a filter yields nothing
        if filter_str.upper() == "CRON" and not CRON_LOG.is_file():
            echo(f"  {Y}Filter '{filter_str}' -> 0 baris.{NC}")
            echo(f"  {D}Cron log belum ada — auto-backup mungkin belum pernah berjalan.{NC}")
            echo(f"  {D}Aktifkan dengan: gaet push --auto{NC}")
        else:
            echo(f"  {Y}Tidak ada baris yang cocok dengan filter '{filter_str or since_str}'.{NC}")
        return
    for line in filtered[start:]:
        echo(f"  {D}│{NC} {line.rstrip()}")

# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_log_parser(subparsers, common):
    p = subparsers.add_parser("log", help="View backup log", parents=[common])
    p.add_argument("lines", nargs="?", type=int, default=30, help="Number of lines (default 30)")
    p.add_argument("--filter", "-f", type=str, default="", help="Filter by keyword")
    p.add_argument("--since", "-s", type=str, default="", help="Filter since date (YYYY-MM-DD)")
    p.add_argument("--follow", "-F", action="store_true", help="Follow log (tail -f style)")
    return p


command("log", "View backup log", build=_build_log_parser)(cmd_log)

