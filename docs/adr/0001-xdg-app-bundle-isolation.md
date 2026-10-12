# ADR-0001: XDG Base Directory Standard & App Bundle Isolation

## Status
Accepted (applies to Golang engine v1.1.0+ on `main`)

## Context
Previously, Gaet files were scattered across user home directories or installed directly inside `~/.gaet/app`. This legacy approach created several problems:
1. Updating application code risked accidentally touching or wiping user configurations (`.env`) or local backup snapshots (`backups/*.dump`).
2. Uninstalling the app had no clean boundary between application code and user state.
3. The layout did not comply with platform standards (XDG Base Directory Specification on Linux/macOS, LocalAppData on Windows).

## Decision
We adopted a strict isolation architecture based on the **XDG Base Directory Specification**, implemented for the **Golang engine** (`pkg/core/paths.go`):

1. **`GAET_DIR`** *(User State)*:
   - Location: `~/.gaet` (Linux/macOS) / `~/.gaet` (Windows).
   - Purpose: Contains user configuration (`.env`, mode 0600), database backup snapshots (`backups/*.dump`), lockfiles (`backups/.gaet.lock`), and log files (`backups/gaet.log`, `backups/cron.log`).
   - Lifecycle: Persists across application updates. Purged only during an explicit `gaet uninstall --save=false`.
   - Overridable at runtime via the `GAET_DIR` environment variable.

2. **`GAET_APP_DIR`** *(Application Bundle)*:
   - Location: `~/.local/share/gaet` (Linux/macOS) or `%LOCALAPPDATA%\gaet` (Windows).
   - Purpose: Contains the compiled application binary and dashboard assets.
   - Lifecycle: Safe to overwrite or purge during updates/uninstalls without affecting user data.
   - Note: Unlike the legacy Python engine, the Go engine ships as a **single compiled binary** (`cmd/gaet/main.go`) — there is no interpreter or multi-file application bundle to manage.

3. **`GAET_BINARY`** *(PATH Launcher)*:
   - Location: `~/.local/bin/gaet` (Linux/macOS) or `%USERPROFILE%\.local\bin\gaet.exe` (Windows).
   - Purpose: The compiled single-file Go binary containing the entire CLI runtime and embedded dashboard. Installed by `install.sh` / `install.ps1`.

## Consequences
- **Positive**: App updates and uninstalls are 100% safe and deterministic. Zero risk of backup data loss from binary replacement.
- **Positive**: Full compliance with Linux/macOS XDG standards and Windows AppData conventions.
- **Positive**: The single-binary Go model eliminates the "which Python interpreter" and "app bundle sync" problems entirely — `GAET_APP_DIR` is only used for the dashboard static assets fallback, not for application code.
- **Positive**: Clean upgrade path — replacing the binary at `GAET_BINARY` is atomic; `~/.gaet/` user state is never touched.

## Reference Implementation
- `pkg/core/paths.go`: `GaetDir()`, `GaetAppDir()`, `BackupDir()`, `EnvFile()`, `LogFile()`, `CronLogFile()`, `LockPath()`.
