"""Command registry — the gaetway.

Every command registers itself here via the `@command()` decorator or the
`register_command()` API. `gaet/cli.py` builds argparse from this registry
and dispatches to handlers from it. Adding a command = one decorated
function in a gaet/<module>.py; nothing else needs to change.

This module is imported by BOTH command modules (to register) and cli.py
(to build/dispatch), so it must never import from gaet.* itself.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional


class Command:
    """One registered CLI command."""

    __slots__ = ("name", "help", "build", "run")

    def __init__(self, name: str, help: str, build, run):
        self.name = name
        self.help = help
        self.build = build  # callable(subparsers, common) -> subparser
        self.run = run      # callable(args) -> None


COMMANDS: Dict[str, Command] = {}


def register_command(
    name: str,
    help: str,
    build: Optional[Callable] = None,
    run: Optional[Callable] = None,
) -> Callable:
    """Register a command. Usable as decorator or plain API."""

    def deco(fn: Callable) -> Callable:
        def default_build(subparsers, common):
            return subparsers.add_parser(name, help=help, parents=[common])

        COMMANDS[name] = Command(
            name,
            help,
            build if build is not None else default_build,
            run if run is not None else fn,
        )
        return fn

    return deco


def command(name: str, help: str, build: Optional[Callable] = None) -> Callable:
    """Shorthand decorator: @command('name', 'help')."""
    return register_command(name, help, build=build)


def build_parsers(subparsers, common) -> None:
    """Call every registered command's parser factory."""
    for cmd in COMMANDS.values():
        cmd.build(subparsers, common)