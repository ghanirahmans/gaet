# ADR-0001: XDG Base Directory Standard & App Bundle Isolation

## Status
Accepted

## Context
Previously, Gaet files were scattered across user home directories or installed directly inside `~/.gaet/app`. This legacy approach created several problems:
1. Updating application code risked accidentally touching or wiping user configurations (`.env`) or local backup snapshots (`backups/*.dump`).
2. Uninstalling the app had no clean boundary between application code and user state.
3. The layout did not comply with platform standards (XDG Base Directory Specification on Linux/macOS, LocalAppData on Windows).

## Decision
We decided to adopt a strict isolation architecture based on the **XDG Base Directory Specification**:

1. **`GAET_APP_DIR`** *(App Bundle Engine)*:
   - Location: `~/.local/share/gaet` (Linux/macOS) or `%LOCALAPPDATA%\gaet` (Windows).
   - Purpose: Contains application code (`gaet.py`, `src/gaet/`, `scripts/`, `dashboard/`, `completions/`).
   - Lifecycle: Safe to overwrite or purge during updates/uninstalls without affecting user data.

2. **`GAET_DIR`** *(User State & Backups)*:
   - Location: `~/.gaet` (Linux/macOS/Windows).
   - Purpose: Contains user configuration (`.env`), database backup snapshots (`backups/`), and lockfiles.
   - Lifecycle: Persists across application updates. Purged only during an explicit `gaet uninstall --purge`.

3. **`GAET_LAUNCHER`** *(PATH Binary)*:
   - Location: `~/.local/bin/gaet` (Linux/macOS) or `%USERPROFILE%\.local\bin\gaet.cmd` (Windows).
   - Purpose: Lightweight single-file wrapper pointing to `GAET_APP_DIR/gaet.py`.

## Consequences
- **Positive**: App updates and uninstalls are 100% safe and deterministic. Zero risk of backup data loss.
- **Positive**: Full compliance with Linux/macOS XDG standards and Windows AppData conventions.
- **Negative**: Clean separation requires installers (`install.sh`, `install.ps1`) to copy files into `GAET_APP_DIR` rather than a single home subfolder.
