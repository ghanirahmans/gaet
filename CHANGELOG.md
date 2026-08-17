# Changelog

All notable changes to gaet are documented here.

## [1.1.2] — 2026-08-17

### Added & Improved
- **Robust Unix Domain Socket Fallback Engine**: Updated `RunPush`, `RunFetch`, `RunRestore`, and `resetTargetObjects` across `pkg/backup`, `pkg/status`, and `pkg/serve` so that all local database operations automatically fall back to Unix domain sockets (peer authentication) whenever TCP connection or password auth fails, regardless of password presence.
- **Interactive Daemon Auto-Backup Modal (`gaet auto`)**: Added dedicated `[ AUTO ]` configuration modal accessible via header button (`A`), Command Palette, or hotkey `A`. Features quick preset pills (`1h`, `3h`, `6h`, `12h`, `24h`) and studio-grade stepper controls (`−` / `+`).
- **Keyboard-Centric Hotkeys**: Added shortcut support (`Shift+Delete` / `Alt+X`) with kbd-tag badges for stopping the background daemon service.
- **Live Daemon Status Card Sync**: Updated `/api/status` endpoint to expose `cron_active`, `cron_hours`, and `scheduler_name` so Overview Card 4 dynamically renders live daemon status (`[ ONLINE ]` / `[ INACTIVE ]`).
- **NPM TypeScript/JavaScript SDK Release**: Updated `@ghanirahmans/gaet` to **v1.1.7** with updated build artifacts and type definitions.

## [1.1.1] — 2026-08-17

### Added & Improved
- **Dashboard UI/UX Parity & Aesthetic Polish**: Harmonized light and dark mode color palettes to eliminate harsh grey contrast and align with studio-grade developer tool standards.
- **Bi-Directional Password & URL Sync**: Typing or editing password/credentials in Settings (`GAET_LOCAL_DB_PASS`) now updates `GAET_LOCAL_URL` in real-time and vice versa.
- **Masked Password Indicator**: Overview card footers display secure connection strings with password masking (`user:••••••@host:port/db`) for both local and cloud database targets.
- **Live Process Environment Synchronization**: Saving configuration via web dashboard (`/api/config`) immediately updates live process environment variables (`os.Setenv` / `os.Unsetenv`) in memory without requiring a server restart.
- **Zero Layout Shift (Stable Scrollbar Gutter)**: Enforced `scrollbar-gutter: stable;` across the dashboard to prevent horizontal layout jumping when content heights change across tabs.
- **Responsive Navbar System**: Refined navbar breakpoints for desktop, laptop, tablet (4-column grid), and mobile viewports (2x2 grid tabs on small mobile screens).

## [1.1.0 LTS] — 2026-08-17

Second Long-Term Support (LTS) Release — Complete Golang Engine Migration & UX Stabilization.

**Platform Support:** Linux ✅ | macOS ✅ | Windows ✅ (100% Feature & Test Parity)

### Highlights & Key Improvements
- **Default Port Change for `gaet serve`**: Changed default web dashboard port to **`6161`** (`http://127.0.0.1:6161`) to avoid browser security restriction blocks (`ERR_UNSAFE_PORT`) and port collisions.
- **Auto-Start OS Startup Daemon (`gaet serve --auto` & `--stop`)**: Added native background service registration for the web dashboard across Linux (**systemd** user service), macOS (**launchd** agent), and Windows (**Task Scheduler**).
- **Browser Auto-Launch & `--no-open`**: `gaet serve` automatically opens the user's default browser on startup, with `--no-open` flag available for headless/background execution.
- **Interactive `gaet uninstall` Menu**: Replaced plain purge prompt with an interactive choice menu (`1` Clean Uninstall, `2` Safe Uninstall, `0` Cancel [default]).
- **OS-Specific PG Tools Guidance**: `gaet check` and `gaet doctor` now output exact 1-line installation commands for `pg_dump` and `psql` per operating system (Ubuntu/Debian, Fedora, Arch, macOS Homebrew, Windows Winget/Choco).
- **Modern Left Accent Block (▌) Styling**: Updated CLI section headers and restored cyan URL formatting for `PrintDocsFooter()`.

## [1.0.0 LTS] — 2026-08-16

First Official Production-Ready Long-Term Support (LTS) Release. Supported until August 2027.

**Platform Support:** Linux ✅ | macOS ✅ | Windows ✅ (100% Feature & Test Parity)

### Highlights & Key Improvements
- **Modern Web Dashboard**: Zero-dependency visual Operations Hub (`gaet serve` at `http://127.0.0.1:9191`) with glassmorphic aesthetics, dynamic Dark/Light theme parity, and responsive UI for mobile, tablet, and desktop screens.
- **Ergonomic Keyboard Navigation**: Hotkeys (`1`-`4`, `Alt+O/S/L/E`), Command Palette hub (`Alt+K`), and interactive `restoreModal` confirmation window for safe snapshot recovery.
- **Full Cross-Platform Parity**: Automatic PostgreSQL binary and Unix socket discovery across Linux (`/run/postgresql`), macOS Homebrew / Postgres.app (`/opt/homebrew`, `/private/tmp`), and Windows (`C:\Program Files\PostgreSQL`).
- **Comprehensive 18 Subcommand CLI**: Fully documented lifecycle (`init`, `install`, `update`, `uninstall`), synchronization (`push`, `fetch`, `restore`), diagnostics (`status`, `check`, `diff`, `doctor`, `log`, `snapshots`), config (`get`, `set`, `remote`, `export`, `completion`, `help`), and service (`serve`, `stop`) management.
- **CI Test Suite Coverage**: 100% green automated test matrix across Ubuntu, macOS, and Windows on Python 3.10, 3.11, and 3.12.

## [3.0.2] — 2026-08-16

### Changed
- **`gaet uninstall` is clean by default.** The old `--purge` flag is removed;
  `uninstall` now wipes the binary, package, scripts, **and** config in one go
  (with a `yes` confirmation, matching the previous `--purge` behavior). A new
  `--save` flag archives `~/.gaet` to `~/.gaet.backup.<timestamp>.tar.gz`
  before the wipe, so a clean default is still recoverable. Motivation: a bare
  `uninstall` should leave no trace behind.

  ```
  gaet uninstall          # remove binary + config + package (clean, asks yes)
  gaet uninstall --save   # archive config first, then remove all
  ```

## [3.0.1] — 2026-08-16

### Changed
- **src-layout:** the `gaet/` package moved to `src/gaet/` (standard Python
  project layout). Repo root now holds only the entry shim (`gaet.py`),
  docs, `dashboard/`, `scripts/`, and `tests/` — no source dirs mixed in.
- `pyproject.toml`: `package-dir = {"" = "src"}` so `pip install .` exposes
  exactly the `gaet` package.
- `install.sh` / `_update_download` / copy-from-project: now download/copy
  the `src/gaet/*.py` package into `~/.local/bin/gaet_pkg/gaet/`, fixing a
  v3 regression where a curl-install got the shim but no package (`import
  gaet` failed). The package dir is named `gaet_pkg` because a dir `gaet/`
  next to the `gaet` binary is impossible on disk (file/dir name clash).
  `tests/test_gaet.py` prefers `src/` on sys.path so `python -m unittest
  discover -s tests` needs no `PYTHONPATH`.

### Fixed
- Fresh `curl | bash` install after the v3 package split silently produced a
  broken binary (shim without package) — installer now fetches both.
- **v3 split regression:** `gaet push --auto=N` and `gaet push --cron` were
  silently no-ops — the auto/cron dispatch that lived in the monolith's `main()`
  was not carried into `backup.py`. `cmd_push` now routes `--auto` to
  `cmd_auto_on` and `--cron` to `cmd_push_cron`, matching v2 behavior.
- **v3 split regression:** `auto-on`/`stop` crashed in the installed layout
  because `scheduler.py` imported the service backend (`_svc_mod`) from `core`,
  where it only existed as a function-local import. `scheduler` now imports
  `scripts.service_manager` directly (lazy, with fallback).

## [3.0.0] — 2026-08-16

### Changed
- **Structural refactor:** the monolithic `gaet.py` (≈4.3k lines, single file)
  is split into an importable `gaet/` package:

  ```
  gaet/
  ├── __init__.py   # re-exports every command/helper (backward compatible)
  ├── __main__.py   # python -m gaet
  ├── registry.py   # the command registry (add a command = one @command)
  ├── cli.py        # argparse setup + dispatch (built from the registry)
  ├── core.py       # constants, logging, env, I/O, config building
  ├── detect.py     # PostgreSQL instance detection (socket + TCP)
  ├── init.py       # interactive setup wizard
  ├── config.py     # gaet get / gaet set
  ├── status.py     # check / status / diff / doctor / completion
  ├── backup.py     # push / fetch
  ├── scheduler.py  # auto-backup on/stop
  ├── log.py        # backup log viewer
  ├── serve.py      # web dashboard launcher
  ├── export.py     # shell-compatible config export
  └── update.py     # install / update / uninstall
  ```

- `command_map` dispatch replaced by a **command registry** (`gaet/registry.py`):
  every subcommand registers itself via `@command(...)`; argparse, `gaet help`,
  `gaet help --json` introspection, and dispatch all derive from the same
  registry — adding a new command is one decorated function, nothing else.
- `gaet.py` at repo root is now a thin entry shim (kept so the installer's
  single-file curl flow keeps working unchanged).
- `pyproject.toml`: `py-modules = ["gaet"]` → `packages = ["gaet"]`
  (the importable package layout).

### Notes
- Zero user-facing behavior changes: same commands, same flags, same output.
- `python3 gaet.py <cmd>` and `python3 -m gaet <cmd>` both work; installed
  `gaet` binary unchanged.
- Verified: 25 unit tests green (unchanged, still import `gaet` by name),
  plus fresh-install E2E (interactive `init` via PTY, `check`, `status`,
  `diff`, `export`, `help --json`, `completion`, `serve` API).

## [2.0.1] — 2026-08-16

### Added
- `gaet init` now turns `~/.gaet` into a **git-versioned workspace** (like `git init`):
  `.gitignore` keeps secrets (`.env`) and data (`backups/`, `*.dump`, lock) out of
  history; scaffolding gets an initial commit so config evolution is traceable.
- Socket-host configs (`/run/postgresql`, etc.) are stored as individual
  `GAET_LOCAL_DB_*` variables instead of an unparseable connection URL.
- Auto-detect now scans every Unix socket file (`.s.PGSQL.*`) and tries the
  current OS user first (peer auth), so instances on non-default ports and
  user-owned roles are found — not just `postgres`/`root` on port 5432.

### Fixed
- `gaet init` with a detected Unix socket wrote an invalid `GAET_LOCAL_URL`
  that could not be parsed back by `get_local_db` — now round-trips correctly.
- **`.env` produced by `gaet init` had mixed indentation** (8-space lines
  interleaved with flush-left lines) because `textwrap.dedent` cannot handle
  multi-line interpolated values — this silently broke `source ~/.gaet/.env`
  for users. Config is now built from a plain line list, always flush-left.
- Socket auto-detect hardcoded port `5432` and a fixed socket list, missing
  instances on other ports (e.g. `5433` found in `/tmp`); port is now read
  from the socket filename and all socket directories are scanned.
- Socket auto-detect stopped after the first instance (`if results: break`),
  hiding additional instances running on other sockets.
- TCP fallback could report the same port twice (socket + TCP) — ports found
  via socket are now skipped in the TCP pass.
- `gaet log --follow` mixed cursors between `gaet.log` and `cron.log`
  (duplicate/missed lines) — each file now tracks its own position.
- `gaet export` masked passwords as `***`, producing shell output that would
  silently break `eval $(gaet export)` — values are now exported verbatim,
  with a warning to stderr that secrets are included.
- Stale-lock cleanup uses `shutil.rmtree(ignore_errors=True)` (no stray
  crash from a half-removed lock dir).

## [2.0.0 LTS] — 2026-08-15

Long-Term Support release. Supported until at least 2027.

**Platform support:** Linux ✅ | macOS ⚠️ | Windows ⚠️

### Added
- `gaet doctor` — comprehensive health check (config, tools, DB, backups, scheduler)
- `gaet diff` — compare local vs cloud tables with row counts
- `gaet export` — print config as shell `export` statements
- `gaet completion` — generate shell completions (bash/zsh/fish)
- `gaet help <cmd>` — git-style command help
- `gaet help --json` — machine-readable command schema
- `--json` flag on check, push, fetch, status, doctor, diff
- `--plain` flag — pipe-safe TSV output (no box-drawing)
- `--quiet` flag — suppress non-essential output
- `--follow` / `-F` on `gaet log` — real-time log tailing
- `--notify` on `gaet push` — webhook URL notification
- `--tables` on `gaet push` — selective backup
- `--watch` on `gaet status` — auto-refresh
- Semantic exit codes (80=config, 81=local-down, 82=cloud-down, 83=locked, 84=tools)
- `NO_COLOR` / `CLICOLOR_FORCE` env var support
- Unix socket auto-detection in `gaet init`
- Progress indication (size + table count) during dump/restore
- Typo suggestions ("Did you mean: gaet push?")
- Man page (`gaet.1`)
- Shell completion files (`completions/gaet.{bash,zsh,fish}`)
- Mermaid pipeline diagrams in README
- Config priority: individual vars (`GAET_LOCAL_DB_*`) override `GAET_LOCAL_URL`

### Changed
- `gaet set KEY=` (empty value) now deletes the key instead of writing empty line
- `gaet init` shows menu A/B/C/D/Q for full user control
- `gaet status` shows "?/N" when cloud unreachable (honest, not misleading)
- `gaet log` with empty filter shows helpful context
- `gaet init` in non-interactive mode shows warning instead of silent fail

### Fixed
- `safe_input` non-interactive mode: try `input()` first, fallback on EOF only
- `GAET_LOCAL_URL` priority: individual vars now override URL
- `detect_local_pg` now detects Unix sockets (`/run/postgresql`)
- `gaet completion` shell detection (suffix not stem)
- **120s hardcoded timeout** now overridable via `GAET_PG_TIMEOUT` (databases >1 GB would fail restore)
- Default `GAET_REMOTE_SSLMODE` changed `require` → `prefer` (works with servers without SSL)
- Restore now detects connection failures (exit 82) instead of reporting false "success with warnings"
- `_reset_target_objects` drops tables/views/sequences/types/functions with CASCADE (fixes restore failures on partitioned tables, enums, custom types)

### Documentation
- Removed AI slop from README and CHANGELOG
- Honest platform status (Linux full, macOS/Windows experimental)
- Honest FAQ (no overconfident claims)
- Accurate project structure (line counts, file layout)
- Added "What's New in 2.0.0 LTS" section
- Removed duplicate Support & Links sections

### Security
- `.env` permissions enforced at 0o600
- Passwords masked in `gaet get` output
- No shell injection (argument arrays for all subprocess calls)
