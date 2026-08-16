# Changelog

All notable changes to gaet are documented here.

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
