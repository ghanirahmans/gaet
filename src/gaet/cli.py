from __future__ import annotations

"""CLI entry point — the command registry ("gaetway").

Every command registers itself here via gaet/registry.py:

    @command("mycmd", help="Do my thing", build=_build_mycmd_parser)
    def cmd_mycmd(args): ...

The registry is the single source of truth for argparse subparsers,
`gaet help` output, help --json introspection, and dispatch.
"""
import argparse
import datetime
import os
import re
import signal
import sys
import textwrap

from .core import (
    DEF_AUTO_INTERVAL,
    ENV_FILE,
    NAME,
    VERSION,
    _SUGGEST_NAMES,
    box_title,
    echo,
    emit_help_json,
    get_env_int,
    load_env,
    set_output_modes,
    status_info,
    suggest_command,
)
from .registry import COMMANDS, build_parsers
from .export import cmd_export  # noqa: F401  (registry side-effect import)
from .init import cmd_init  # noqa: F401
from .config import cmd_get, cmd_set  # noqa: F401
from .status import cmd_check, cmd_completion, cmd_diff, cmd_doctor, cmd_status  # noqa: F401
from .backup import cmd_fetch, cmd_push, cmd_push_cron  # noqa: F401
from .scheduler import cmd_auto_on, cmd_stop_auto  # noqa: F401
from .log import cmd_log  # noqa: F401
from .serve import cmd_serve  # noqa: F401
from .update import cmd_install, cmd_uninstall, cmd_update  # noqa: F401


def main() -> None:
    """CLI entry point. Handles signals and exceptions gracefully without breaking the terminal."""
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    try:
        _run_cli()
    except (KeyboardInterrupt, EOFError):
        sys.stdout.write("\n  \033[36mℹ\033[0m  gaet: dibatalkan oleh pengguna.\n")
        sys.stdout.flush()
        sys.exit(130)
    except SystemExit as e:
        sys.exit(e.code if e.code is not None else 0)
    except Exception as e:
        sys.stderr.write(f"\n  \033[31m✗\033[0m  gaet error: {e}\n")
        sys.stderr.flush()
        sys.exit(1)


def _run_cli() -> None:
    """Internal CLI argument parser and command router."""
    parser = argparse.ArgumentParser(
        prog=NAME,
        description=f"{NAME} — Database Backup & Sync CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              gaet init                 First-time setup wizard
              gaet push                 Backup local database → cloud
              gaet status               Show sync status
              gaet check --json | jq   Machine-readable health check (CI)

            Global flags (work before OR after the command):
              -q, --quiet   Suppress non-essential output
              --plain       Decoration-free, pipe-safe output (grep/awk/jq)
              --json        Structured JSON output (on check/push/fetch)

            Get help for a command:
              gaet help <command>        e.g.  gaet help push

            Docs & support:
              GitHub: https://github.com/ghanirahmans/gaet
              Issues: https://github.com/ghanirahmans/gaet/issues
        """),
    )

    # Override error() so unknown commands get a friendly "Did you mean?" hint
    # (clig.dev §Errors: be empathetic, suggest corrections) instead of a raw
    # argparse usage dump.
    _orig_error = parser.error

    def _error_with_suggestion(message: str) -> None:
        tok = None
        m = re.search(r"'([^']+)'", message)
        if m:
            tok = m.group(1)
        if tok and not tok.startswith("-"):
            import difflib
            matches = difflib.get_close_matches(tok, _SUGGEST_NAMES, n=1, cutoff=0.5)
            if matches:
                sys.stderr.write(f"gaet: error: unknown command '{tok}'\n")
                sys.stderr.write(f"  Did you mean: gaet {matches[0]} ?\n")
                sys.stderr.write(f"  Run 'gaet --help' for the full list.\n")
                sys.exit(2)
        _orig_error(message)

    parser.error = _error_with_suggestion
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"{NAME} v{VERSION}",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-essential output (for scripts/CI)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Plain, decoration-free output (no box-drawing chars) — pipe-safe for grep/awk/jq",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")
    # expose to core.emit_help_json (which introspects argparse internals)
    import gaet.core as _core_mod
    _core_mod.subparsers = subparsers

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-essential output (for scripts/CI)",
    )
    common.add_argument(
        "--plain",
        action="store_true",
        help="Plain, decoration-free output (pipe-safe for grep/awk/jq)",
    )

    build_parsers(subparsers, common)

    # git-style `help <command>` — special-cased in dispatch below
    help_parser = subparsers.add_parser("help", help="Show help for a command (e.g. gaet help push)", parents=[common])
    help_parser.add_argument("topic", nargs="?", default=None, help="Command name to show help for")
    help_parser.add_argument("--json", action="store_true", help="Machine-readable command schema (agent-friendly)")

    args = parser.parse_args()

    # Configure global output modes (--quiet / --plain) before any echo()
    set_output_modes(getattr(args, "quiet", False), getattr(args, "plain", False))

    # git-style: `gaet help <command>`
    if args.command == "help":
        topic = getattr(args, "topic", None)
        if getattr(args, "json", False):
            emit_help_json(topic)
            return
        if topic and topic in subparsers.choices:
            parser.parse_args([topic, "--help"])
        else:
            parser.print_help()
            if topic:
                echo(f"\n  {Y}Unknown command:{NC} {topic}")
                suggest_command(topic)
        return

    # Default command: show welcome menu (not status)
    if args.command is None:
        box_title(f"{NAME} {VERSION}")
        echo()
        if ENV_FILE.is_file():
            echo(f"  {G}✓ Konfigurasi ditemukan.{NC}")
            echo(f"  {D}Last backup:{NC} {datetime.fromtimestamp(os.path.getmtime(ENV_FILE)).strftime('%Y-%m-%d %H:%M')}")
            echo()
        else:
            echo(f"  {Y}Belum dikonfigurasi.{NC}")
            echo(f"  {D}Mulai dalam 3 langkah:{NC}")
            echo(f"    {C}1.{NC} gaet init          Setup wizard (local + cloud DB)")
            echo(f"    {C}2.{NC} gaet push          Backup lokal → cloud")
            echo(f"    {C}3.{NC} gaet status        Lihat ringkasan sinkronisasi")
            echo()

        echo(f"  {B}Perintah populer:{NC}")
        echo(f"    {C}gaet init{NC}           Setup database")
        echo(f"    {C}gaet push{NC}           Backup ke cloud")
        echo(f"    {C}gaet fetch{NC}          Restore dari cloud")
        echo(f"    {C}gaet status{NC}         Cek sinkronisasi")
        echo(f"    {C}gaet check{NC}          Validasi koneksi")
        echo(f"    {C}gaet serve{NC}          Buka dashboard web")
        echo()
        echo(f"  {D}Butuh bantuan?{NC}")
        echo(f"    {C}gaet --help{NC}        Daftar semua perintah")
        echo(f"    {C}gaet help push{NC}     Detail perintah push")
        echo(f"    {C}gaet doctor{NC}        Health check lengkap")
        echo()
        sys.exit(0)

    # Set defaults for attributes that may not exist on main parser
    if not hasattr(args, "json"):
        args.json = False
    if not hasattr(args, "cron"):
        args.cron = False
    if not hasattr(args, "auto"):
        args.auto = None
    if not hasattr(args, "dry_run"):
        args.dry_run = False

    # ── auto mode (push --auto = enable scheduler) ──
    if args.command == "push":
        if args.cron:
            env = load_env()
            cmd_push_cron(env)
            return
        if args.auto is not None:
            if args.auto == 0:
                env = load_env()
                args.auto = get_env_int(env, "GAET_AUTO_INTERVAL", DEF_AUTO_INTERVAL)
            cmd_auto_on(args)
            return
        cmd_push(args)
        return

    # ── Route commands via registry ──
    cmd_entry = COMMANDS.get(args.command)
    if cmd_entry:
        cmd_entry.run(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()