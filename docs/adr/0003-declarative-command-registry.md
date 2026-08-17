# ADR-0003: Declarative Command Registration Pattern

## Status
Accepted

## Context
As Gaet grew in subcommands (`init`, `push`, `fetch`, `status`, `restore`, `snapshots`, `remote`, `auto`, `serve`, `log`, `export`, `update`, `uninstall`), maintaining a giant central `argparse` parser inside `cli.py` or `core.py` resulted in tightly coupled, hard-to-maintain code. Adding a new subcommand required modifying multiple files.

## Decision
We implemented a **Declarative Command Registry Pattern** using a `@command` decorator in `src/gaet/registry.py`:

```python
from .registry import command

def _build_mycmd_parser(subparsers, common):
    p = subparsers.add_parser("mycmd", help="Do my command", parents=[common])
    p.add_argument("--flag", action="store_true", help="Option flag")
    return p

@command("mycmd", help="Do my command", build=_build_mycmd_parser)
def cmd_mycmd(args: argparse.Namespace) -> None:
    ...
```

1. **Self-Contained Subcommands**: Each module in `src/gaet/` defines both its CLI parser setup function and its handler function.
2. **Dynamic Discovery & Binding**: When `cli.py` loads modules, subcommands register themselves automatically.
3. **Automated Help & Schema Generation**: Enables clean `gaet help <cmd>` and `gaet help --json` introspection.

## Consequences
- **Positive**: Modular codebase where adding/removing subcommands requires zero edits to `cli.py`.
- **Positive**: Isolated unit testing for each command module.
- **Negative**: Subcommand modules must be imported in `cli.py` to trigger registration.
