# Changelog

All notable changes to gaet are documented here.

## [2.0.1] — 2026-08-16

### Added
- `gaet init` now turns `~/.gaet` into a **git-versioned workspace** (like `git init`):
  `.gitignore` keeps secrets (`.env`) and data (`backups/`, `*.dump`, lock) out of
  history; scaffolding gets an initial commit so config evolution is traceable.
- Socket-host configs (`/run/postgresql`, etc.) are stored as individual
  `GAET_LOCAL_DB_*` variables instead of an unparseable connection URL.

### Fixed
- `gaet init` with a detected Unix socket wrote an invalid `GAET_LOCAL_URL`
  that could not be parsed back by `get_local_db` — now round-trips correctly.
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
