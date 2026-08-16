# Gaet CLI — Architecture & Comprehensive Command Scope Specification

This document strictly defines the scope, responsibilities, input/output behaviors, and boundaries for **all 18 CLI commands in `gaet`** to ensure total transparency, reliability, and consistent *Git-style* command-line aesthetics.

---

## 📐 4 Core Pillars of Gaet Command Architecture

1. **Single Responsibility Principle (SRP)**: Each command handles exactly one specific task. `check` never runs the `init` wizard, `push` never prompts for interactive setup, etc.
2. **Zero Surprises (Git Parity)**: Read-only commands (`status`, `check`, `diff`, `doctor`, `log`, `snapshots`, `get`, `export`) are **STRICTLY NON-INTERACTIVE**. They never prompt for input, modify `.env` files, or hang the terminal.
3. **Graceful Failures**: If an error occurs (such as database connection failure or invalid credentials), the CLI terminates immediately (< 0.1s) with appropriate exit codes and human-readable explanation badges.
4. **Safety Guards**: Destructive operations (`fetch` overwriting local database, `restore` dropping tables, `uninstall` purging system files) **MUST** require explicit interactive confirmation or demand the `--yes` flag in non-TTY / CI environments.

---

## 📋 Comprehensive Command Scope Matrix (18 Commands)

### 🚀 Category 1: Setup & Lifecycle

| Command | Scope & Responsibility | Command Type | Interactive Input? | Failure & Exit Code Expectation | Strict Boundaries |
|---|---|---|---|---|---|
| **`gaet init`** | Interactive setup wizard, `.env` file initialization, and git-versioned workspace setup (`~/.gaet` or `GAET_DIR`). | Setup / Wizard | **YES** (Numbered selection menu) | Non-zero on user cancel (Ctrl+C) / IO error | **Only** command allowed to execute interactive wizard prompts and write new `.env` templates. |
| **`gaet install`** | Installs `gaet` executable binary and symlinks to system PATH (`/usr/local/bin`). | System Install | **NO** (Unless sudo required) | Non-zero if permission denied | Never touches database connections. Handles binary installation only. |
| **`gaet update`** | Updates `gaet` CLI source code/package to latest version from GitHub/PyPI. | System Update | **NO** | Non-zero if git/network fails | Updates CLI code only; never mutates `.env` variables. |
| **`gaet uninstall`**| Removes `gaet` binary, symlinks, auto-backup timers, and config directory. | Destructive System | **YES** (`y/N` prompt) / `--yes` flag | Non-zero if cancelled | Requires explicit confirmation before removing files/services. |

---

### 🔄 Category 2: Data Synchronization

| Command | Scope & Responsibility | Command Type | Interactive Input? | Failure & Exit Code Expectation | Strict Boundaries |
|---|---|---|---|---|---|
| **`gaet push`** | Executes `pg_dump` on local DB and restores to Remote Cloud DB. | Data Sync (Mutate Remote) | **NO** (Except `--auto` option) | `EXIT_LOCAL_DOWN` (81) / `EXIT_CLOUD_DOWN` (82) | Aborts immediately if local/cloud DB is unreachable. **Never** triggers `init` wizard. |
| **`gaet fetch`** | Executes `pg_dump` on Remote Cloud DB and restores to Local DB (overwrites!). | Data Sync (Mutate Local) | **YES** (Type `yes`) / `--yes` in CI | `EXIT_LOCAL_DOWN` (81) / `EXIT_CLOUD_DOWN` (82) | **Destructive to local DB**. Requires `yes` in TTY. Rejects execution in non-TTY without `--yes`. |
| **`gaet restore`** | Restores local DB from a specific local snapshot `.dump` file (default: latest). | Local Snapshot Restore | **YES** (Type `yes`) / `--yes` in CI | `EXIT_LOCAL_DOWN` (81) / `EXIT_CONFIG` (80) | **Destructive to local DB**. Instant offline rollback from local snapshot. Requires confirmation in TTY. |

---

### 📊 Category 3: Status, Diagnostics & History (Read-Only)

| Command | Scope & Responsibility | Command Type | Interactive Input? | Failure & Exit Code Expectation | Strict Boundaries |
|---|---|---|---|---|---|
| **`gaet status`** | Displays sync status summary, table count, DB size, and auto-backup state. | Read-Only Summary | **NO** (100% Non-interactive) | `0` (or `EXIT_CONFIG` if missing `.env`) | 100% read-only. Never prompts for input or passwords. |
| **`gaet check`** | Instant diagnostic check for PostgreSQL tools, `.env`, DB connections, and backup folder. | Read-Only Diagnostic | **NO** (100% Non-interactive) | Non-zero if any check FAILS | Uses `-w` (`--no-password`). Suggests `gaet init` without running wizard. |
| **`gaet diff`** | Per-table row count comparison between Local DB and Cloud DB. | Read-Only Comparison | **NO** (100% Non-interactive) | Non-zero if connection fails | Safely queries table metadata without modifying data. |
| **`gaet doctor`** | In-depth system health report (OS, file permissions, connection, tool dependencies). | Read-Only Diagnostic | **NO** (100% Non-interactive) | Returns issue count | Provides actionable technical suggestions. |
| **`gaet log`** | Views execution log and backup history from `.gaet/logs/`. | Read-Only History | **NO** (100% Non-interactive) | `0` | Displays log file output (`--follow` for tailing). |
| **`gaet snapshots`**| Lists all local `.dump` backup snapshots in a structured table. | Read-Only Snapshots | **NO** (100% Non-interactive) | `0` | Lists local snapshot file names, dates, sizes, and retention policies. |

---

### ⚙️ Category 4: Configuration & Utilities

| Command | Scope & Responsibility | Command Type | Interactive Input? | Failure & Exit Code Expectation | Strict Boundaries |
|---|---|---|---|---|---|
| **`gaet get`** | Reads and prints specific or all `.env` configuration variables. | Config Read | **NO** (100% Non-interactive) | `0` (or `1` if key missing) | 100% read-only to `.env` file. `--list` shows schema reference. |
| **`gaet set`** | Sets or updates `KEY=VALUE` variables directly in `.env`. | Config Write | **NO** (100% Non-interactive) | `0` / `1` (Invalid format) | Updates specified key cleanly without invoking setup wizard. |
| **`gaet remote`** | Git-style management for Remote Cloud DB URL (`show`, `set-url`, `remove`). | Config / Remote Mgmt | **NO** (100% Non-interactive) | `0` / Non-zero if URL invalid | Manages cloud URL cleanly with connectivity test. |
| **`gaet export`** | Exports `.env` variables as shell environment statements (`export GAET_...`). | Config Export | **NO** (100% Non-interactive) | `0` | Utility for bash/zsh scripting environment. |
| **`gaet completion`**| Generates shell auto-completion scripts (bash, zsh, fish, ps1). | Shell Tool | **NO** (100% Non-interactive) | `0` | Outputs completion script to stdout. |
| **`gaet help`** | Displays technical help documentation for specific commands or options. | Information | **NO** (100% Non-interactive) | `0` | Prints command usage manual. |

---

### 🌐 Category 5: Background Services & Dashboard

| Command | Scope & Responsibility | Command Type | Interactive Input? | Failure & Exit Code Expectation | Strict Boundaries |
|---|---|---|---|---|---|
| **`gaet serve`** | Launches local web dashboard HTTP server for real-time monitoring. | Service Run | **NO** (Blocking process / Ctrl+C) | Non-zero if port in use | Serves monitoring dashboard on configured port. |
| **`gaet stop`** | Stops auto-backup daemon (cron/systemd) or web dashboard process. | Service Control | **NO** (100% Non-interactive) | `0` / Non-zero if service absent | Terminates background tasks safely. |

---

## 🔒 Code Enforcement Guidelines

1. **`pg_env()` and `-w` Flag**: All invocations of `psql`, `pg_dump`, and `pg_restore` must supply `-w` (`--no-password`) and utilize temporary `PGPASSFILE` environments generated by `pg_env()`.
2. **Dynamic Config Pathing**: Always reference the `ENV_FILE` path constant (which respects `GAET_DIR`). Never hardcode `~/.gaet/.env` in string outputs.
3. **Non-Interactive Guard**: When `sys.stdin.isatty()` returns `False`, destructive commands like `fetch` or `restore` **MUST** require `--yes` or abort immediately via `die()`.
