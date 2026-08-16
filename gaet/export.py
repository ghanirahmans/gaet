"""cmd_export — shell-compatible config export."""

import argparse
import sys
from .core import NC, Y, argparse, echo, load_env, sys

def cmd_export(args: argparse.Namespace) -> None:
    """Export config as shell-compatible env vars.

    Values are exported verbatim so `eval $(gaet export)` works (like
    `git config --list` returns real values): an exported but masked
    password would silently break every downstream command. A warning is
    printed to stderr so the secret never lands in a captured stdout log
    without the user knowing.
    """
    env = load_env()
    if not env:
        echo(f"  {Y}No config found. Run: gaet init{NC}")
        return
    sensitive = [k for k in env if "pass" in k.lower() and env[k]]
    if sensitive:
        print(
            f"gaet: warning — exporting {len(sensitive)} secret(s); "
            "keep this output private (use `> file` with 0600 perms).",
            file=sys.stderr,
        )
    for key in sorted(env.keys()):
        val = env[key]
        echo(f"export {key}={val}")

# -- registry (gaetway) ------------------------------------------------------------------
from .registry import command


def _build_export_parser(subparsers, common):
    return subparsers.add_parser("export", help="Export config as shell env vars", parents=[common])


command("export", "Export config as shell env vars", build=_build_export_parser)(cmd_export)

