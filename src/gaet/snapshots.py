"""List local backup snapshots (git tag / git stash list parity)."""

import argparse
import json
from datetime import datetime
from typing import Dict, Any, List

from .core import (
    BACKUP_DIR,
    load_env,
    get_env_int,
    echo,
    box_title,
    box_section,
    status_arrow,
    status_info,
    set_output_modes,
    C, G, Y, D, B, NC,
    DEF_RETENTION_DAYS,
)
from .registry import command


def cmd_snapshots(args: argparse.Namespace) -> None:
    """List local backup snapshots in ~/.gaet/backups/."""
    want_json = getattr(args, "json", False)

    if want_json:
        set_output_modes(quiet=True, plain=True)

    env = load_env()
    retention = get_env_int(env, "GAET_RETENTION_DAYS", DEF_RETENTION_DAYS)

    dump_files = sorted(BACKUP_DIR.glob("*.dump"), key=lambda f: f.stat().st_mtime, reverse=True)

    snapshots_data: List[Dict[str, Any]] = []
    total_bytes = 0

    for f in dump_files:
        st = f.stat()
        size_mb = st.st_size / (1024 * 1024)
        total_bytes += st.st_size
        mtime = datetime.fromtimestamp(st.st_mtime)

        snapshots_data.append({
            "filename": f.name,
            "path": str(f),
            "size_mb": round(size_mb, 1),
            "created_at": mtime.strftime("%Y-%m-%d %H:%M:%S"),
        })

    total_mb = total_bytes / (1024 * 1024)

    if want_json:
        result = {
            "command": "snapshots",
            "count": len(snapshots_data),
            "total_size_mb": round(total_mb, 1),
            "retention_days": retention,
            "snapshots": snapshots_data,
        }
        print(json.dumps(result, indent=2))
        return

    box_title("gaet snapshots")

    if not snapshots_data:
        echo(f"  {Y}No local backup snapshots found in {BACKUP_DIR}.{NC}")
        echo(f"  Run: {C}gaet push{NC} to create your first snapshot.")
        echo()
        return

    box_section(f"Local Snapshots ({len(snapshots_data)} files, {total_mb:.1f} MB total)")
    echo(f"  {B}{'No':<4} {'Snapshot File':<32} {'Size':<10} {'Created At':<20}{NC}")
    echo(f"  {D}{'─'*4} {'─'*32} {'─'*10} {'─'*20}{NC}")

    for idx, snap in enumerate(snapshots_data, 1):
        latest_tag = f" {G}(latest){NC}" if idx == 1 else ""
        echo(f"  {C}[{idx}]{NC:<4} {snap['filename']:<32} {snap['size_mb']:<4.1f} MB   {snap['created_at']:<20}{latest_tag}")

    echo()
    status_info(f"Auto-retention: {retention} days")
    status_info(f"Run: {C}gaet restore <filename.dump>{NC} to restore a snapshot")
    echo()


def _build_snapshots_parser(subparsers, common):
    p = subparsers.add_parser("snapshots", help="List local backup snapshots", parents=[common])
    p.add_argument("--json", action="store_true", help="Output JSON result")
    return p


command("snapshots", "List local backup snapshots", build=_build_snapshots_parser)(cmd_snapshots)
