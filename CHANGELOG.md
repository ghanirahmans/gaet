# Changelog

All notable changes to gaet are documented here.

## [1.0.0] — 2026-07-21

### Added
- **Preset: `hindsight-hermes`** — Hindsight memory preset for Nous Research Hermes Agent (18 tables).
- **Security: Password separation** — `GAET_LOCAL_DB_PASS` stored separately from URL. Passwords never appear in connection strings in `.env`. URLs without passwords fully supported.
- **Security: PGPASSFILE cleanup** — Temp password files auto-deleted after each command via `cleanup_pg_env()`. No more credential leak on disk.
- **Security: execFileSync** — All dashboard API routes use `execFileSync` with argument arrays. No shell injection possible.
- **Security: CORS validation** — Dashboard validates `Origin` header on every request.
- **Security: URL masking** — Passwords masked as `****` in all display output.
- **Feature: `push --dry-run`** — Simulate push without acquiring locks or touching data.
- **Feature: `fetch --dry-run`** — Simulate fetch without acquiring locks or touching data.
- **Feature: `log --filter` / `log --since`** — Filter backup log by keyword or date.
- **Feature: Dashboard loading states** — Button text changes to "Pushing...", "Fetching...", etc. during operations.
- **Feature: Dashboard ErrorBoundary** — Graceful error handling for runtime crashes.
- **Feature: Update from curl install** — `gaet update` now downloads from GitHub for non-git users.
- **Feature: Interval validation** — Auto-backup interval validated (1-24 hours) with clear error messages.
- **Feature: pg_terminate_backend warning** — Warning shown before closing active connections during fetch.
- **Testing: 17 unit tests** — Core utilities covered (`parse_remote_url`, `mask_url_password`, `get_env_str`, `get_env_int`).

### Fixed
- **Security: Command injection** — Dashboard API no longer uses `execSync` with template literals.
- **Security: PGPASSFILE leak** — Three temp file creation sites in `scripts/status.py` now properly clean up.
- **Bug: Exit code inconsistency** — `sys.exit(2)` replaced with `die()` (exit code 1) for consistency.
- **Bug: Unused re-imports** — Three `import re as _re` inside functions removed (re already at top level).
- **Bug: Unused imports** — `import signal` removed.
- **Bug: Dead code** — Unused `zip_url` variable removed from `_update_download()`.
- **Bug: Race condition** — Dashboard polling changed from `setInterval` to recursive `setTimeout`.
- **Bug: File encoding** — `scripts/status.py`, `installer.py`, `service_manager.py` now use explicit `encoding="utf-8"`.
- **Bug: Duplicate code** — `PRESETS` removed from `scripts/status.py` (unused there).
- **Bug: Config variable name** — `.env.example` uses correct `GAET_AUTO_INTERVAL` instead of `GAET_BACKUP_INTERVAL`.
- **Bug: Cron integrity** — Auto-backup cron path now runs `pg_restore --list` integrity check before restore.
- **Bug: Password in URL regex** — `parse_remote_url()` now supports URLs without password component.

### Changed
- **`cmd_init()`** — Local URL written without password. Password stored as `GAET_LOCAL_DB_PASS`.
- **`_update_download()`** — Added GitHub download fallback for curl-install users.
- **`mask_url_password()`** — Regex updated to only mask when password is present.
- **`cmd_auto_on()`** — Enhanced validation (positive, ≤24), detailed success output.
- **`cmd_fetch()`** — Shows "Menutup koneksi aktif" warning before `pg_terminate_backend`.

---

## [0.9.0] — 2026-07-15

### Added
- `gaet uninstall` command with `--purge` mode
- `gaet update` command for git-based updates
- `gaet push --cron` internal mode for scheduler
- Windows Task Scheduler support
- launchd support for macOS
- `--json` flag for `gaet status`
- Dashboard: one-click push/fetch/stop buttons
- Dashboard: auto-refresh (8 seconds)
- Dashboard: dark/light mode toggle
- Dashboard: per-table sync status

### Fixed
- Windows PostgreSQL path detection
- Systemd timer syntax validation
- `.env` file parser edge cases
- PGPASSWORD → PGPASSFILE migration for /proc leak prevention
- Dashboard CORS validation
- Error messages now actionable

### Changed
- Full English translation of CLI output
- Dashboard redesigned with Tailwind CSS v4
- `install.sh` rewritten for cross-platform

---

## [0.8.0] — 2026-06-01

### Added
- Initial public release
- `gaet init` interactive setup wizard
- `gaet push` local → cloud backup
- `gaet fetch` cloud → local restore
- `gaet status` sync status display
- `gaet check` configuration validation
- `gaet log` backup log viewer
- `gaet serve` web dashboard
- `gaet push --auto` auto-backup via systemd
- Preset system (hindsight)
- Table auto-discovery
- Backup retention policy
- Concurrent operation lock
- Custom format compressed dumps
- Integrity checks via `pg_restore --list`
