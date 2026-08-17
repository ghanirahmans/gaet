# Gaet CLI — Architecture & Comprehensive Command Scope Specification

This document defines the scope, responsibilities, input/output behaviors, and operational boundaries for the **subcommands in `gaet`** to ensure reliability, predictability, and Git-style CLI consistency.

---

## Core Principles of Gaet Command Architecture

1. **Single Responsibility Principle (SRP)**: Each command performs one specific task. `check` never runs the `init` wizard, and `push` never prompts for interactive setup.
2. **Zero Surprises (Git Parity)**: Read-only commands (`status`, `check`, `diff`, `doctor`, `log`, `snapshots`, `get`, `export`) are **strictly non-interactive**. They never prompt for user input or mutate environment files.
3. **Deterministic Failures**: If an error occurs (such as an unreachable database host or invalid credentials), the CLI exits immediately with standard exit codes and actionable diagnostic messages.
4. **Safety Guards**: Destructive operations (`fetch` overwriting local database, `restore` dropping local schema, `uninstall` purging configuration/backups) **require explicit confirmation in interactive TTY mode** or demand the `-y` / `--yes` flag in non-interactive/CI pipelines.

---

## Command Scope Matrix

### Category 1: Setup & System Lifecycle

| Command | Scope & Responsibility | Type | Interactive Input? | Exit Codes | Boundaries |
|:---|:---|:---|:---|:---|:---|
| **`gaet init`** | Interactive setup wizard, `.env` file creation, and database profile configuration. | Setup Wizard | **Yes** | `0` / `1` (User Cancel) | Only command allowed to prompt interactive configuration questions. |
| **`gaet update`** | Checks GitHub Releases API and updates `gaet` binary via the release installer. | System Update | **No** | `0` / `1` (Network Error) | Updates binary executable; never mutates `.env` variables. |
| **`gaet uninstall`** | Removes `gaet` binary, scheduled service timers, and configuration files. | Destructive System | **Yes** (`-y` to skip) | `0` / `1` (Cancel) | Requires explicit confirmation before removing local snapshots or configuration files. |

---

### Category 2: Data Synchronization & Restore

| Command | Scope & Responsibility | Type | Interactive Input? | Exit Codes | Boundaries |
|:---|:---|:---|:---|:---|:---|
| **`gaet push`** | Dumps local database (`pg_dump`) and restores to Remote Cloud DB. | Data Sync (Mutate Remote) | **No** | `0` / `81` / `82` | Aborts immediately if local or remote DB is unreachable. |
| **`gaet fetch`** | Dumps Remote Cloud DB and restores to local database (overwrites local schema). | Data Sync (Mutate Local) | **Yes** (`-y` to skip) | `0` / `81` / `82` | **Destructive to local DB**. Requires `-y` in non-interactive/CI environments. |
| **`gaet restore`** | Restores local DB from a local `.dump` snapshot file (default: latest). | Snapshot Restore | **Yes** (`-y` to skip) | `0` / `80` / `81` | **Destructive to local DB**. Performs offline rollback from local snapshot file. |

---

### Category 3: Status, Diagnostics & History (Read-Only)

| Command | Scope & Responsibility | Type | Interactive Input? | Exit Codes | Boundaries |
|:---|:---|:---|:---|:---|:---|
| **`gaet status`** | Displays sync status summary, table counts, DB sizes, and snapshot counts. | Read-Only Summary | **No** | `0` / `80` | Read-only. Never prompts for input or passwords. |
| **`gaet check`** | Validates database client tools (`pg_dump`, `psql`), `.env` config, and DB connectivity. | Read-Only Diagnostic | **No** | `0` / `1` (Checks Fail) | Uses `-w` (`--no-password`). Returns structured JSON with `--json`. |
| **`gaet diff`** | Compares table structures and row counts between Local DB and Cloud DB. | Read-Only Comparison | **No** | `0` / `1` | Queries metadata only; never mutates database schemas. |
| **`gaet doctor`** | Performs in-depth diagnostic health audit (permissions, tool paths, connectivity). | Read-Only Audit | **No** | `0` / `1` | Provides technical troubleshooting recommendations. |
| **`gaet log`** | Displays execution history and audit log from `.gaet/logs/`. | Read-Only History | **No** | `0` | Displays log records; supports `-F` (`--follow`) for tailing. |
| **`gaet snapshots`** | Lists all local `.dump` backup snapshots in a structured table. | Read-Only Snapshots | **No** | `0` | Displays snapshot names, timestamps, sizes, and retention status. |

---

### Category 4: Configuration & Utilities

| Command | Scope & Responsibility | Type | Interactive Input? | Exit Codes | Boundaries |
|:---|:---|:---|:---|:---|:---|
| **`gaet get`** | Reads and displays `.env` configuration keys. | Config Read | **No** | `0` | Read-only. Supports `--list` to view configuration schema reference. |
| **`gaet set`** | Sets or updates `KEY=VALUE` variables in `.env` using single-pass atomic file writes. | Config Write | **No** | `0` / `2` (Invalid Format) | Modifies specified keys without launching interactive setup wizard. |
| **`gaet remote`** | Manages Cloud DB connection URL (`show`, `set-url`, `remove`). | Config Management | **No** | `0` / `80` | Validates PostgreSQL URL formatting and tests connectivity. |
| **`gaet export`** | Exports `.env` variables as shell environment statements (`export GAET_...`). | Config Utility | **No** | `0` | Outputs shell-compatible export statements to stdout. |
| **`gaet completion`** | Generates shell autocompletion scripts (bash, zsh, fish, powershell). | Shell Utility | **No** | `0` | Outputs shell autocompletion logic to stdout. |

---

### Category 5: Background Services & Dashboard

| Command | Scope & Responsibility | Type | Interactive Input? | Exit Codes | Boundaries |
|:---|:---|:---|:---|:---|:---|
| **`gaet auto`** | Enables automated backup scheduler using native OS service daemons (systemd/launchd/cron). | Service Control | **No** | `0` / `1` | Configures OS background service timers for periodic backups. |
| **`gaet stop`** | Disables background automated backup service daemons. | Service Control | **No** | `0` | Removes registered background service daemons cleanly. |
| **`gaet serve`** | Launches local web dashboard HTTP server (default port `6161`). Supports `--no-open` and `--auto` (OS startup daemon). | Service Run | **No** (Blocking process) | `0` / `1` | Serves monitoring dashboard UI and REST API on configured port. |

---

## Security & Execution Rules

1. **Passwordless Executions (`-w`)**: All PostgreSQL tools (`psql`, `pg_dump`, `pg_restore`) execute with `-w` (`--no-password`) alongside short-lived, isolated `PGPASSFILE` buffers (`0600` permissions). Passwords are never exposed in process lists or CLI arguments.
2. **Path Standard Compliance**: All runtime configurations respect `GAET_DIR` and adhere to standard user paths (`~/.gaet/.env`).
3. **Non-Interactive Guard**: In non-TTY / CI environments, destructive operations (`fetch`, `restore`, `uninstall`) require `-y` / `--yes` flag to proceed.
