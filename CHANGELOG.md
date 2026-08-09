# Changelog

All notable changes to gaet are documented here.

## [2.0.0] — 2026-07-22

### Added
- README.md rewrite with benchmarks, troubleshooting, FAQ
- ARCHITECTURE.md — system design, pipeline flows, platform integration
- CONTRIBUTING.md — contributor guide with code of conduct
- Consistent UX across all 13 commands (title boxes, status functions, summaries)
- English translation for all CLI output
- `push --dry-run` and `fetch --dry-run`
- `log --filter` and `log --since`
- Dashboard loading states and error handling
- Interval validation for auto-backup (1-24 hours)
- Database connection warnings before destructive operations

### Fixed
- Command injection in dashboard API (`execSync` → `execFileSync`)
- PGPASSFILE temp file leak in `scripts/status.py`
- Exit code inconsistency (`sys.exit(2)` → `die()`)
- Race condition in dashboard polling (`setInterval` → `setTimeout`)
- File encoding issues in `scripts/status.py`, `installer.py`
- Cron integrity check before auto-backup restore
- Password regex in `parse_remote_url()`

### Changed
- `cmd_init()`: password stored separately from URL
- `mask_url_password()`: only mask when password present
- `cmd_auto_on()`: validation for interval (positive, ≤24)
- `cmd_fetch()`: warning before terminating active connections
- VERSION bumped to 2.0.0

---

## [1.0.0] — 2026-07-21

### Added
- Preset `hindsight-hermes` for Nous Research Hermes Agent (18 tables)
- `GAET_LOCAL_DB_PASS` stored separately from URL
- PGPASSFILE temp files auto-deleted after each command
- `execFileSync` in all dashboard API routes (no shell injection)
- CORS validation on dashboard API
- URL masking in all display output
- Dashboard loading states and ErrorBoundary
- `gaet update` from curl install (GitHub download fallback)
- Interval validation for auto-backup
- 17 unit tests

### Fixed
- Dashboard API command injection
- PGPASSFILE leak in `scripts/status.py`
- Exit code inconsistency
- Unused `re` imports
- File encoding in Python scripts
- Race condition in dashboard polling
- Password regex for URLs without password

### Changed
- Password stored separately from URL in `.env`
- Full English translation of CLI output

---

## [0.9.0] — 2026-07-15

### Added
- `gaet uninstall` with `--purge` mode
- `gaet update` for git-based updates
- `gaet push --cron` for scheduler
- Windows Task Scheduler support
- launchd support for macOS
- `--json` flag for `gaet status`
- Dashboard: push/fetch/stop buttons
- Dashboard: auto-refresh (8 seconds)
- Dashboard: dark/light mode
- Dashboard: per-table sync status

### Fixed
- Windows PostgreSQL path detection
- Systemd timer syntax validation
- `.env` parser edge cases
- PGPASSWORD → PGPASSFILE for /proc leak prevention
- Dashboard CORS validation

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
