# Contributing to Gaet

Thank you for your interest in contributing to **Gaet**! To ensure the project remains lightweight, fast, maintainable, and reliable across all operating systems, all contributors (humans and AI agents) are required to follow these development standards.

---

## Core Guidelines & Architectural Principles

Before writing any code, please review our core architectural rules documented in detail in [AGENTS.md](AGENTS.md) and [docs/adr/](docs/adr/):

1. **Zero External Dependencies**: Core CLI relies 100% on standard library Python 3.8+ and standard system PostgreSQL binaries (`pg_dump`, `pg_restore`, `psql`). Do not introduce third-party PyPI packages.
2. **Strict App & User Isolation**: Application logic lives in `GAET_APP_DIR` (`~/.local/share/gaet`), while user config and backup dumps live in `GAET_DIR` (`~/.gaet`).
3. **Pure ASCII Standard**: Output tags must strictly use `[ OK ]`, `[FAIL]`, `[WARN]`, `[INFO]`, and `[NOTE]`. Do not use raw Unicode emojis in CLI output.
4. **Empathetic Error UX**: Always provide actionable hint remediation steps and troubleshooting links on failure.
5. **Cross-Platform Compatibility**: Always use `os.path` / `pathlib` for cross-platform path handling (Linux, macOS, Windows).

---

## Development Workflow

### 1. Setting Up Development Environment

Clone the repository and verify the test suite:

```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
python3 -m unittest discover -s tests -v
```

### 2. Subcommand Registration

Subcommands are registered declaratively in `src/gaet/` using the `@command` decorator from `src/gaet/registry.py`:

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

### 3. Testing Requirements

- All pull requests must pass the complete unit test suite (`python3 -m unittest discover -s tests -v`).
- Every new subcommand, flag, or bugfix must include dedicated unit test coverage under `tests/`.

### 4. Git Branching Strategy

- **`main`**: Primary development branch.
- **`lts/v1.0`**: Production / LTS release branch.
- Changes are merged into `main`, tested, and then fast-forward merged to `lts/v1.0`.
