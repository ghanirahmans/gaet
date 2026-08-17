# AGENTS.md — Gaet Architecture & Development Guidelines

This document provides essential architectural context, design standards, and coding conventions for AI agents and human contributors working on the **Gaet** codebase.

---

## 1. Executive Summary & Core Philosophy

**Gaet** is a zero-dependency, cross-platform PostgreSQL Database Backup & Cloud Sync CLI tool built with Python 3.8+.

### Core Principles
- **Cross-Platform Standard Compliance**: Adheres to the **XDG Base Directory Specification** on Linux/macOS and **Windows AppData** standard.
- **Strict Isolation**: Application logic (`GAET_APP_DIR`) is strictly separated from user state and backups (`GAET_DIR`).
- **Full ASCII UI Standard**: No emojis or raw Unicode glyphs in CLI outputs. Clean ASCII status tags (`[ OK ]`, `[FAIL]`, `[WARN]`, `[INFO]`, `[NOTE]`) ensure 100% compatibility across legacy terminals, pipes, and CI/CD pipelines.
- **Empathetic UX**: Always provide actionable correction hints, troubleshooting URLs, and suggestion matches (`Did you mean gaet <cmd>?`) for user errors (conforming to `clig.dev`).

---

## 2. Directory & Storage Architecture

| Identifier | Platform Location | Purpose |
| :--- | :--- | :--- |
| **`GAET_APP_DIR`** *(App Bundle)* | `~/.local/share/gaet` *(Linux/macOS)*<br>`%LOCALAPPDATA%\gaet` *(Windows)* | Application engine: `gaet.py`, `src/gaet/`, `scripts/`, `dashboard/`, `completions/` |
| **`GAET_DIR`** *(User Data)* | `~/.gaet` | User configuration (`.env`), backup snapshots (`backups/*.dump`), lockfiles |
| **`GAET_LAUNCHER`** *(PATH)* | `~/.local/bin/gaet` *(Linux/macOS)*<br>`%USERPROFILE%\.local\bin\gaet.cmd` *(Windows)* | Lightweight single-file wrapper pointing to `GAET_APP_DIR/gaet.py` |

> [!IMPORTANT]
> Updating or purging the application bundle (`GAET_APP_DIR`) **must never delete** user configuration or backup snapshots in `GAET_DIR` unless an explicit full purge (`gaet uninstall --purge`) is executed.

---

## 3. Codebase Structure

```text
gaet/
├── gaet.py                  # Entry point shim (resolves sys.path and dispatches to src/gaet)
├── install.sh               # One-liner Linux/macOS bash installer
├── install.ps1              # One-liner Windows PowerShell installer
├── pyproject.toml           # Package metadata & build configuration
├── src/gaet/                # Core Python package
│   ├── __init__.py          # Package initialization
│   ├── cli.py               # Main CLI argument router & signal handler
│   ├── registry.py          # Command registration decorator (@command)
│   ├── core.py              # Path constants, env loader, execution helpers, status output
│   ├── detect.py            # Local PostgreSQL socket & TCP instance auto-discovery
│   ├── init.py              # Interactive first-run setup wizard (`gaet init`)
│   ├── config.py            # Environment variable getters/setters (`gaet get` / `gaet set`)
│   ├── status.py            # Database health & connection validator (`gaet status`, `gaet check`)
│   ├── backup.py            # Backup push & fetch commands (`gaet push`, `gaet fetch`)
│   ├── restore.py           # Snapshot restoration with safety guards (`gaet restore`)
│   ├── snapshots.py         # Local backup snapshot management (`gaet snapshots`)
│   ├── remote.py            # Remote cloud database configuration (`gaet remote`)
│   ├── scheduler.py         # Automated background timer/cron scheduler (`gaet auto`)
│   ├── serve.py             # Web dashboard launcher (`gaet serve`)
│   ├── log.py               # Execution history & backup log viewer (`gaet log`)
│   ├── export.py            # Export configuration / data helper
│   └── update.py            # App bundle updater & uninstaller (`gaet update`, `gaet uninstall`)
├── scripts/                 # Platform service managers & background helpers
│   ├── installer.py         # Internal bundle deployment helper
│   ├── scheduler.py         # Systemd (Linux), Launchd (macOS), Task Scheduler (Windows) bridge
│   ├── service_manager.py   # Dashboard service daemon manager
│   └── status.py            # Health check scripts
├── dashboard/               # Web UI assets
│   ├── server.py            # Lightweight Python HTTP server for dashboard
│   ├── static/              # HTML / CSS / JS frontend
│   └── public/              # Logo & static assets
├── completions/             # Shell completion scripts (.bash, .zsh, .fish, .ps1)
└── tests/                   # Complete unittest suite (`test_gaet.py`, `test_init_ux.py`, etc.)
```

---

## 4. Development & Coding Rules

### 4.1. Command Registration (`registry.py`)
All CLI subcommands must be registered declaratively via the `@command` decorator:
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

### 4.2. Status Output & Styling Standards
- Always use status functions from `src/gaet/core.py`: `status_ok`, `status_fail`, `status_warn`, `status_info`, `status_arrow`.
- Do **NOT** introduce Unicode emojis or symbols in CLI print statements.
- Standard Tag Reference:
  - `[ OK ]` — Successful operation
  - `[FAIL]` — Fatal failure or error
  - `[WARN]` — Warning or missing optional tool
  - `[INFO]` — Informational status message
  - `[NOTE]` — Auxiliary note or parameter details

### 4.3. Type Hinting & Linting Warnings
- Import paths from `scripts/` outside `src/` must include type ignore annotations to prevent static analyzer false positives:
  ```python
  from scripts.scheduler import scheduler_enable  # type: ignore[import-not-found] # pyright: ignore[reportMissingImports]
  ```
- `subparsers` is declared at module level in `src/gaet/core.py` (`subparsers: Any = None`) and initialized dynamically in `src/gaet/cli.py`.

### 4.4. Destructive Command Safeguards
Commands that modify or overwrite data (e.g. `gaet restore`, `gaet uninstall --purge`):
- Must prompt for explicit confirmation in interactive TTY mode (`safe_input`).
- Must require `--yes` / `-y` flag when executed in non-interactive (non-TTY) environments or CI/CD pipelines.

---

## 5. Testing & Branch Synchronization

### Running Unit Tests
Before pushing any change, execute the complete test suite:
```bash
python3 -m unittest discover -s tests -v
```
All **48/48 tests** (or more as features are added) must pass with zero errors.

### Git Branching Strategy
- **`main`**: Active development branch.
- **`lts/v1.0`**: Long-Term Support / Production deployment branch (used by raw CDN installers).
- **Workflow**:
  1. Commit and push changes to `main`.
  2. Merge `main` into `lts/v1.0` (fast-forward merge).
  3. Push `lts/v1.0` to remote `origin`.

```bash
git checkout main
# ... make edits and commit ...
git push origin main
git checkout lts/v1.0
git merge main
git push origin lts/v1.0
git checkout main
```

---

## 6. Installer & UX Consistency

When modifying `install.sh` or `install.ps1`:
- Ensure itemized outputs match line-by-line between Bash and PowerShell installers.
- Always display itemized status tags (`[ OK ]`) for:
  1. Prerequisites checks (`curl`, `Python`, `pg_dump`)
  2. Downloaded bundle components (`gaet.py`, `src/gaet/`, `scripts/`, `completions/`, `dashboard/`)
  3. CLI Launcher creation (`gaet` / `gaet.cmd`)
  4. Configuration state (`.env`)
  5. PATH verification

---

## 7. Mandatory Architectural & Scaling Principles (Non-Negotiable)

To ensure Gaet remains maintainable, highly readable, and infinitely scalable, all code changes **MUST** strictly comply with the following 6 core architectural constraints:

### 7.1. Zero-Dependency Constraint
- Core CLI runtime must remain **100% standard library Python 3.8+**.
- Never introduce third-party PyPI dependencies (`requests`, `rich`, `click`, etc.) to core CLI packages.
- Future integrations (e.g. S3 uploads, GPG encryption) must rely on standard Python modules (`urllib.request`, `subprocess`, `hashlib`) or optional subprocess tool detection with graceful degradation.

### 7.2. Strict Subcommand & Business Logic Isolation
- Subcommand modules in `src/gaet/` must never import business logic directly from sibling subcommand modules.
- Shared utilities, configuration getters, subprocess wrappers, and status formatters **MUST** reside in `src/gaet/core.py` or dedicated helper modules (`detect.py`, `registry.py`).

### 7.3. Empathetic Error Handling & Fail-Safe Defaults
- Never display raw Python tracebacks to end users unless `--debug` is explicitly supplied.
- Every error message must be formatted via `status_fail()` or `die()` and must contain:
  1. **Clear Problem Description**: What failed.
  2. **Contextual Rationale**: Why it failed.
  3. **Actionable Remediation Hint**: Exact CLI command or setting to fix the issue.
  4. **Documentation / Troubleshooting Link**: Pointing to docs or `TROUBLESHOOTING.md`.

### 7.4. Scripting & CI/CD First-Class Support
Every CLI command MUST respect global flags:
- `--json`: Output machine-readable JSON payloads for automation.
- `--plain` / Non-TTY stdout: Automatically strip ANSI colors and formatting.
- `--quiet` (`-q`): Suppress non-error output.
- `--yes` (`-y`): Auto-confirm interactive prompts in automated CI/CD pipelines.

### 7.5. Test-Driven Development (TDD) & Regression Prevention
- Every new feature, bug fix, or CLI flag **MUST** include corresponding unit tests in `tests/`.
- Unit tests must be fast, completely self-contained, and mock external system calls (`pg_dump`, network calls).
- Pipeline invariant: `python3 -m unittest discover -s tests -v` **MUST** pass 100% with 0 errors before any commit or merge.

### 7.6. Cross-Platform Path Invariance
- Never hardcode POSIX slashes (`/`) or Windows backslashes (`\`) directly in string paths.
- Always use `pathlib.Path` or `os.path.join()` for cross-platform filesystem operations.

