# Changelog

All notable changes to gaet are documented here.

## [2.0.0 LTS] — 2026-08-09

Long-Term Support release for Linux. Supported until at least 2027.

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
