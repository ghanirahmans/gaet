# gaet Architecture & Design

This document explains how gaet works internally, design decisions, and trade-offs.

> **Scope**: This document describes the **active Golang engine** (`main` branch, v1.1.0 LTS). The legacy Python implementation lived on the `lts/v1.0` branch and is no longer the basis of this codebase. Refer to `docs/legacy-python.md` for the deprecated Python engine.

## Table of Contents

1. [System Overview](#system-overview)
2. [Codebase Layout](#codebase-layout)
3. [Core Pipelines](#core-pipelines)
4. [Concurrency & Locking](#concurrency--locking)
5. [Error Handling & Exit Codes](#error-handling--exit-codes)
6. [Security Model](#security-model)
7. [Performance Optimization](#performance-optimization)
8. [Platform Integration](#platform-integration)
9. [Web Dashboard & REST API](#web-dashboard--rest-api)
10. [Testing Strategy](#testing-strategy)
11. [Future Improvements](#future-improvements)

---

## System Overview

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      gaet CLI (main)                           │
│  cmd/gaet/main.go — flag extraction + switch dispatch          │
└────────────────────────────────────┬───────────────────────────┘
                                     │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌──────────────┐          ┌──────────────┐
│   PushPipe   │          │   FetchPipe  │          │   Dashboard  │
│ pkg/backup   │          │ pkg/backup   │          │ pkg/serve    │
└──────┬───────┘          └──────┬───────┘          └──────┬───────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
        ┌──────────┬────────────────┴──────────────┬──────────┐
        ▼          ▼                                 ▼          ▼
┌──────────┐ ┌──────────┐                  ┌──────────┐ ┌──────────┐
│ Local DB │ │ Cloud DB │                  │  Filesys │ │  Logfile │
│ pg_dump  │ │ pg_restore│                  │  .backup │ │ gaet.log │
└──────────┘ └──────────┘                  └──────────┘ └──────────┘
```

### Design Philosophy

1. **Single Responsibility** — Each command package does one thing well. All subcommand packages depend only on `pkg/core` for shared utilities.
2. **Zero Dependencies** — Pure Go Standard Library only (`net/http`, `os`, `syscall`, `embed`, `regexp`, `encoding/json`, `bufio`, `filepath`, `runtime`, `context`, `time`). No third-party Go modules. PostgreSQL tools (`pg_dump`, `pg_restore`, `psql`) are invoked as subprocesses — never linked.
3. **Fail Loud** — Errors produce a typed `*GaetError` with a meaningful exit code. Operations abort before mutating data when preconditions fail (e.g., missing tools, unreachable DB).
4. **Atomic Operations** — File locks (`O_CREAT|O_EXCL`) prevent concurrent execution; lock staleness is recovered via PID liveness probe.
5. **Excellent Logging** — Structured JSON log records (`LogJSON` in `pkg/core/logger.go`) written to `~/.gaet/backups/gaet.log` with 5 MB rotation; cron operations log to `cron.log`.

---

## Codebase Layout

```
gaet/
├── cmd/
│   └── gaet/
│       └── main.go              # CLI entry point & global flag parser
├── pkg/
│   ├── backup/                  # Backup push, fetch, restore & cron engine
│   ├── completion/              # Shell autocompletions (bash, zsh, fish, powershell)
│   ├── config/                  # Environment variable get/set & file management
│   ├── core/                    # Path resolution, execution wrappers, formatting, pgurl
│   ├── detect/                  # Socket & TCP PostgreSQL auto-discovery scanner
│   ├── init/                    # Interactive setup wizard & database profiles
│   ├── log/                     # Log viewer & execution history
│   ├── remote/                  # Remote cloud DB configuration & connection verification
│   ├── scheduler/               # OS system service scheduler (systemd, launchd, taskschd)
│   ├── serve/                   # Embedded web dashboard server & REST API handlers
│   ├── snapshots/               # Local snapshot discovery, rotation & management
│   └── status/                  # Health check & doctor diagnostic validators
├── tests/                       # Comprehensive integration test suite (Go)
├── sdk/                         # TypeScript/JavaScript SDK (@ghanirahmans/gaet)
├── docs/                        # Project documentation, architecture ADRs & guides
├── install.sh / install.ps1     # One-liner binary installers
├── go.mod                       # Go module definition (module: github.com/ghanirahmans/gaet, go 1.21)
└── gaet.1                       # Linux manpage
```

### Module & Dependency Footprint

`go.mod` declares `module github.com/ghanirahmans/gaet` with `go 1.21` and **zero require directives** — the entire production binary depends only on the Go standard library.

### Layering & Dependency Direction

Subcommand packages depend **downward only** on `pkg/core`:

```
cmd/gaet/main.go
    ├── pkg/backup    (also pulled by pkg/serve)
    ├── pkg/completion
    ├── pkg/config
    ├── pkg/core      ◄── shared foundation (no internal deps)
    ├── pkg/detect    (also pulled by pkg/serve, pkg/init)
    ├── pkg/init
    ├── pkg/log
    ├── pkg/remote
    ├── pkg/scheduler (also pulled by pkg/serve)
    ├── pkg/serve
    ├── pkg/snapshots
    └── pkg/status
```

`pkg/serve` is the sole package that reaches across the foundation boundary, importing `pkg/backup`, `pkg/detect`, and `pkg/scheduler` to expose HTTP wrappers around their `Run*()` functions.

---

## Core Pipelines

### Push Pipeline (Backup Local → Cloud)

**Entry**: `gaet push` → `cmd/gaet/main.go` dispatches to `backup.RunPush` (`pkg/backup/backup.go`).

```
START  gaet push
  │
  ├─→ [LOCK]       core.AcquireLock() — O_CREAT|O_EXCL lockfile at ~/.gaet/backups/.gaet.lock
  │                Stale lock auto-recovered via PID liveness probe (pkg/core/lock.go)
  │
  ├─→ [DUMP]       pg_dump -w --format=custom --compress=9 --file=~/.gaet/backups/gaet_YYYYMMDD_HHmmss.dump
  │                Host passthrough; fallback to socket-only args for localhost/127.0.0.1/socket paths
  │
  ├─→ [VERIFY]     pg_restore --list <dump>  (read-only integrity check, 30s timeout)
  │                On failure: removes dump, returns ExitGeneral
  │
  ├─→ [RESET]      resetTargetObjects() — psql DROP cascade on all public tables/views/sequences
  │                Uses pg_restore-compatible psql invocation
  │
  ├─→ [RESTORE]    pg_restore -w --no-owner --no-acl <dump> → cloud remote
  │                (Host/port/user/db parsed from GAET_REMOTE_URL via core.ParseRemoteURL)
  │
  ├─→ [RETENTION]  applyRetention() — deletes gaet_*.dump / cron_*.dump / cloud_*.dump older than GAET_RETENTION_DAYS
  │
  └─→ [LOG]        WriteJSONLog({Category:"BACKUP", Action:"PUSH"}) → gaet.log
  └─→ [UNLOCK]     lock.Release()
```

**Timeout**: computed per call via `core.GetDynamicTimeout(env, sizeBytes)`:
`base = GAET_TIMEOUT (default 900s, legacy fallback GAET_PG_TIMEOUT) + floor(sizeGB × GAET_TIMEOUT_PER_GB (default 300s, legacy fallback GAET_PG_TIMEOUT_PER_GB))`.

**Credentials**: passed to subprocesses via `core.DBEnv()` which sets `PGPASSWORD`/`PGSSLMODE` environment variables — **never** as command-line arguments (`-w` / `--no-password` always passed to pg_* tools).

### Fetch Pipeline (Restore Cloud → Local)

Mirrors Push in reverse:
```
START  gaet fetch
  ├─→ [GUARD]    Refuses execution in non-TTY unless --yes flag is supplied
  ├─→ [LOCK]     core.AcquireLock()
  ├─→ [DUMP]     pg_dump from cloud → ~/.gaet/backups/cloud_TIMESTAMP.dump
  ├─→ [RESET]    resetTargetObjects() on local DB
  ├─→ [RESTORE]  pg_restore → local DB
  ├─→ [CLEANUP]  os.Remove(cloud dump file)
  └─→ [LOG]      WriteJSONLog({Action:"FETCH"}) → gaet.log; lock.Release()
```

### Local Restore Pipeline (Snapshot → Local DB)

```
START  gaet restore [snapshot | latest]
  ├─→ [RESOLVE]  globDumps() sorts ~/.gaet/backups/*.dump by mod-time descending; picks target
  ├─→ [GUARD]    Destructive — requires TTY confirmation or --yes
  ├─→ [VERIFY]   pg_restore --list <snapshot>
  ├─→ [RESET]    resetTargetObjects() on local DB
  ├─→ [RESTORE]  pg_restore → local DB
  └─→ [LOG]      WriteJSONLog({Action:"RESTORE"})
```

### Auto-Backup (Scheduler Integration)

`gaet push --auto=N` or `gaet auto N` → `scheduler.EnableAuto()`:
1. Generates OS-native scheduling artifacts (`pkg/scheduler/scheduler.go`):
   - **Linux**: `~/.config/systemd/user/gaet-backup.{service,timer}` → `systemctl --user enable --now`
   - **macOS**: `~/Library/LaunchAgents/com.gaet.backup.plist` → `launchctl load`
   - **Windows**: `schtasks /Create /SC HOURLY /MO N`
2. The scheduler invokes `gaet push --cron` on each interval.
3. `--cron` mode (`RunPushCron`) writes only to `cron.log`, no terminal output — the headless daemon entry point.

### Connection Discovery

`detect.DetectLocalDB()` (`pkg/detect/detect.go`):
1. **Unix socket scan**: scans `core.FindSocketPaths()` (`/run/postgresql`, `/var/run/postgresql`, `/tmp`, `/private/tmp`, `~/.pg0/sockets`) for `.s.PGSQL.*` (excluding `.lock`) → tries connecting as `postgres`, `root`, and current user.
2. **TCP fallback**: probes ports 5432–5436 on `127.0.0.1`.

`core.GetLocalDB()` (`pkg/core/pgtools.go`): resolves local connection params. Priority: `GAET_LOCAL_URL` → `GAET_LOCAL_DB_*` overrides → defaults (`127.0.0.1:5432/postgres`).

### Tool Discovery

`core.FindDBTools()` (`pkg/core/pgtools.go`): locates `pg_dump`, `pg_restore`, `psql`:
1. Explicit env overrides (`GAET_PG_DUMP`, `GAET_PG_RESTORE`, `GAET_PSQL`)
2. `~/.pg0/installation/<version>/bin` (hindsight/pg0 setup)
3. PATH (`exec.LookPath`)
4. Windows: `C:\Program Files\PostgreSQL\*\bin` (highest version)
5. macOS: Homebrew (`/opt/homebrew/bin`, `/usr/local/bin`) + Postgres.app versions

---

## Concurrency & Locking

gaet uses **file-based advisory locks** via `pkg/core/lock.go`:

```
LOCK_FILE = ~/.gaet/backups/.gaet.lock

AcquireLock():
  os.OpenFile(LOCK_FILE, O_CREATE|O_EXCL|O_RDWR, 0600)
  if exists:
    if isLockStale():  # PID in file is dead (Signal 0 probe) OR file > 1h old
      os.Remove(LOCK_FILE); retry once
    else:
      return error "another gaet process is running"
  write os.Getpid() into lockfile
  return *FileLock
```

**Why file locks?** They are simple, atomic (`O_EXCL` guarantees atomic creation), portable across all platforms, and easy to debug. Database-level locks were rejected (schema pollution); PID-only checks were rejected (don't work across shells); message queues were rejected (external dependency).

---

## Error Handling & Exit Codes

`pkg/core/errors.go` defines typed errors (`GaetError`, `ConfigError`, `DBError`) and the following **exit code** contract (all defined as constants):

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `ExitOK` | Success |
| 1 | `ExitGeneral` | General failure (integrity check failed, restore failure) |
| 2 | `ExitUsage` | Invalid usage / unknown command |
| 80 | `ExitConfig` | Configuration missing or invalid |
| 81 | `ExitLocalDown` | Local database unreachable |
| 82 | `ExitCloudDown` | Cloud database unreachable |
| 83 | `ExitLocked` | Another gaet process is running |
| 84 | `ExitTools` | PostgreSQL client tools (pg_dump/pg_restore/psql) not found |

**Flow**: `cmd/gaet/main.go` checks `if err := dispatch(...); err != nil` — if it's a `*core.GaetError`, exits with that `.Code`; otherwise exits `1`.

---

## Security Model

### Password Flow

```
User Input
    │
    ├─→ [PROMPT] gaet init / gaet set — hidden input via termios raw mode (tcgetattr/tcsetattr)
    │
    ├─→ [STORE]  Written to ~/.gaet/.env with mode 0600 only  (pkg/core/env.go)
    │
    ├─→ [USE]    At backup/restore time:
    │     ├─ Read password from .env into memory
    │     ├─ Set PGPASSWORD=<password> via core.DBEnv() — passed as subprocess env var
    │     ├─ All pg_* invocations use -w (--no-password) so NO password appears on CLI
    │     └─ Password never appears in process argv or shell history
    │
    └─→ [CLEANUP] No temp files, no .pgpass written to disk, no env var leakage
```

### What Never Gets Logged

Structured log entries (`LogJSONLog` in `pkg/core/logger.go`) record **actions, categories, statuses, and non-sensitive details** only. Passwords and connection URLs are never logged. When URLs must be displayed, `core.MaskURLPassword()` applies a regex replace `password:****@` before rendering.

### Security Checklist

- ✅ Passwords supplied via `PGPASSWORD` env var only — never command-line args (all pg_* calls use `-w`)
- ✅ `.env` file written with `0600` permissions
- ✅ Destructive commands (`fetch`, `restore`, `uninstall`) refuse non-TTY execution without `--yes`
- ✅ Connection params validated via `core.ParseRemoteURL()` before use
- ✅ Dashboard CORS enabled (`Access-Control-Allow-Origin: *`), binds to `127.0.0.1` by default
- ✅ Lockfile uses `0600` permissions
- ✅ Snapshot download handler (`pkg/serve/server.go`) rejects `..`, `/`, `\` in filename — path traversal protection

---

## Performance Optimization

### Compression Strategy

`pg_dump --format=custom --compress=9` is used for all backups. Custom format gives ~70% size reduction vs. plain SQL, and `--compress=9` (gzip level 9) maximizes bandwidth savings — a worthwhile ~5–10% dump-time tradeoff for cloud uploads.

### Dynamic Timeout

`core.GetDynamicTimeout(env, sizeBytes)` computes per-operation timeout:

```
base_timeout   = GAET_TIMEOUT          (default 900s; legacy: GAET_PG_TIMEOUT)
per_gb_budget  = GAET_TIMEOUT_PER_GB   (default 300s; legacy: GAET_PG_TIMEOUT_PER_GB)
total_seconds  = base_timeout + floor(sizeBytes / 1GB) × per_gb_budget
```

This scales automatically: a 5 GB database gets `900 + 5×300 = 2400s` (40 min), while a small 100 MB DB keeps the 900 s floor.

### Connection Handling

gaet does not maintain persistent connections. Each subprocess (`pg_dump`, `pg_restore`, `psql`) opens a fresh connection. This keeps the tool stateless, atomic, and avoids connection-pool complexity.

### No Parallel Dump

The current Go implementation does **not** pass `--jobs` to `pg_dump`. The legacy Python docs proposed auto-detecting parallel support; the Go engine runs sequential dumps for simplicity and predictability.

---

## Platform Integration

### User Data Layout (XDG-compliant)

| Identifier | Linux/macOS | Windows | Purpose |
|---|---|---|---|
| `GAET_DIR` | `~/.gaet` | `~/.gaet` | `.env` (0600), `backups/*.dump`, `.gaet.log`, `.gaet.lock` |
| `GAET_APP_DIR` | `~/.local/share/gaet` | `%LOCALAPPDATA%\gaet` | Dashboard static assets / binary bundle |
| `GAET_BINARY` | `~/.local/bin/gaet` | `%USERPROFILE%\.local\bin\gaet.exe` | Compiled single-file binary |

### Scheduler Matrix

```
gaet auto / gaet push --auto=N
  ├─ Linux   → ~/.config/systemd/user/gaet-backup.{service,timer}  → systemctl --user enable --now
  ├─ macOS   → ~/Library/LaunchAgents/com.gaet.backup.plist        → launchctl load
  └─ Windows → schtasks /Create /SC HOURLY /MO N                   → Task Scheduler
```

`SchedulerName()` returns the platform-appropriate name (`systemd`, `launchd`, `Task Scheduler`). `pkg/scheduler/scheduler.go` is a single file with no build-tag splits — all three platform branches live in one file gated by `runtime.GOOS` at execution time.

---

## Web Dashboard & REST API

`gaet serve` (`pkg/serve/server.go`) starts a stdlib `http.Server` (default `127.0.0.1:6161`) that serves **two concerns**:

1. **Static dashboard**: `pkg/serve/static/index.html` + `gaet-logo.png` are embedded via `//go:embed static/*` and served at `/`.

2. **REST API**: handlers prefixed with `/api/` (`mux.HandleFunc("/api/...")`) provide machine-readable access to every CLI command:

| Endpoint | Method | Wraps |
|----------|--------|-------|
| `/api/status` | GET | `core.GetLocalDB` + table row-count comparison |
| `/api/check` | GET | `core.FindDBTools` + `SELECT 1` connectivity test |
| `/api/doctor` | GET | Full diagnostic report (config, tools, DBs, backups) |
| `/api/diff` | GET | Table presence + count diff (local vs cloud) |
| `/api/local/test` | POST | Ad-hoc local connection probe |
| `/api/remote/test` | POST | Ad-hoc cloud connection probe |
| `/api/export` | GET | `.env` as shell `export` statements |
| `/api/detect` | GET | `detect.DetectLocalDB()` result |
| `/api/snapshots` | GET | `*.dump` listing (name, size, modtime) |
| `/api/snapshots/download` | GET | Path-traversal-safe file download |
| `/api/snapshots/delete` | POST | Snapshot file deletion |
| `/api/logs` | GET | Recent lines from `gaet.log` + `cron.log` |
| `/api/config` | GET/POST | Read/update `.env` (writes 0600, masks sensitive keys) |
| `/api/push` | POST | `backup.RunPush` (JSON output mode) |
| `/api/fetch` | POST | `backup.RunFetch` (auto-yes) |
| `/api/restore` | POST | `backup.RunRestore` |
| `/api/schedule` | GET/POST/DELETE | `scheduler.IsActive`/`EnableAuto`/`DisableAuto` |
| `/api/stop` | POST | `scheduler.DisableAuto` |

**Key design**: the HTTP handlers reuse the exact same business-logic functions as the CLI (`backup.RunPush`, `backup.RunFetch`, `backup.RunRestore`). This guarantees CLI↔dashboard behavioral parity. CORS is open (`*`) to enable sidecar integration with Next.js, React, Express, and Python web frameworks.

### TypeScript SDK

`@ghanirahmans/gaet` (`sdk/`) is the official client SDK. It wraps the REST API above via `fetch`, with an optional `startServer()` method that auto-spawns `gaet serve` as a child process from Node.js.

---

## Testing Strategy

The test suite lives in `tests/` and is **integration-focused** — it compiles the actual binary (`go build ./cmd/gaet`) and invokes subcommands through `exec.Command` with a temporary `GAET_DIR` (see `tests/main_test.go`).

### Test Categories

| Test File | Surface Area |
|-----------|-------------|
| `main_test.go` | Binary lifecycle: version, help, unknown command, global flags (`--quiet`) |
| `core_test.go` | `pkg/core`: URL parsing, masking, env get/set, path helpers, tool discovery, table validation |
| `config_test.go` | `gaet get`/`gaet set` roundtrips and masking |
| `remote_test.go` | `gaet remote set-url/show/remove` |
| `backup_test.go` | `gaet push/fetch/restore --dry-run` behavior |
| `init_test.go` | `gaet init` wizard in non-interactive mode |
| `detect_test.go` | PostgreSQL socket/TCP discovery |
| `status_test.go` | `gaet status/check/doctor/diff --json` |
| `snapshots_test.go` | `gaet snapshots --json` |
| `log_test.go` | `gaet log` viewer |
| `server_test.go` | Embedded HTTP dashboard endpoints (`--json` served routes) |
| `scheduler_test.go` | Scheduler enable/disable logic |
| `completion_test.go` | Shell completion script generation |

### Running Tests

```bash
go vet ./...
go test -v -count=1 ./tests/...
```

All 13 test packages pass with zero errors. CI (`.github/workflows/ci.yml`) runs on Linux, macOS, and Windows with Go 1.22 and 1.23 (note: `go.mod` targets `go 1.21` for broadest toolchain compatibility).

### Test Isolation

Tests use `t.TempDir()` for `GAET_DIR` and `NO_COLOR=1` to suppress ANSI output, ensuring deterministic, pipe-safe assertions.

---

## Future Improvements

### Planned Enhancements

1. **Incremental Backups**
   - Use WAL (Write-Ahead Logging) archiving for point-in-time recovery.
   - ~90% smaller incremental snapshots.

2. **Parallel Dump**
   - Detect `--jobs` support in `pg_dump` and enable multi-worker parallel dumps (currently runs sequentially).

3. **Backup Encryption**
   - E2E encryption at rest for cloud uploads using AES-256 or `age`.

4. **Dashboard Enhancements**
   - Real-time backup progress streaming.
   - Alert rules (e.g., backup hasn't run in N hours) with Slack/Discord/Telegram webhooks.
   - Mobile-responsive dashboard.

5. **CLI Improvements**
   - Progress bars / estimated time remaining for large dumps.
   - Bandwidth throttling options.

6. **Multi-Database & Scheduling**
   - Batch backup of multiple local databases in one invocation.
   - Cron-style scheduling syntax (hourly/daily/weekly) beyond fixed-interval.

---

## Architecture Decisions & Rationale

### Decision: Clean Modular `pkg/` Package Layout

**Choice**: Each subcommand is an isolated package under `pkg/` that imports only `pkg/core`. `cmd/gaet/main.go` explicitly imports all subcommand packages and dispatches via a hand-written `switch` statement.

**Rationale**:
- Zero external dependencies — no CLI framework (cobra/spf13) bloats the binary.
- Each subcommand has a single exported `Run*()` entry point, making it trivially callable from the HTTP handlers in `pkg/serve`.
- Cross-command coupling is eliminated; shared concerns live exclusively in `pkg/core`.

### Decision: Pure Go Standard Library (No External Modules)

**Choice**: No third-party Go modules. Standard library only.

**Rationale**:
- Zero supply-chain risk (verified: `go.mod` has zero `require` directives).
- Fast compilation and minimal binary size.
- Portability across Go toolchains and module proxies.

**Trade-off**: Custom implementations for TTY detection, raw terminal I/O, and socket path scanning — but these are small (~27 lines each for terminal_unix.go / terminal_windows.go).

### Decision: File-Based Locking

**Choice**: Lock file at `core.LockPath()` (`~/.gaet/backups/.gaet.lock`) using `O_CREAT|O_EXCL` atomic creation.

**Rationale**:
- Works across all OSes (Linux, macOS, Windows).
- Atomic file creation guarantees mutual exclusion.
- Stale locks auto-recovered via PID liveness probe (`processExists` using `signal 0` on Unix, `FindProcess` on Windows).

---

## Benchmarks & Measurements

| DB Size | Dump | Verify | Restore | Total |
|---------|------|--------|---------|-------|
| 100MB | 2s | 0.5s | 2s | 4.5s |
| 1GB | 8s | 1s | 8s | 17s |
| 5GB | 35s | 3s | 40s | 78s |

| Operation | Memory |
|-----------|--------|
| CLI startup | ~5MB |
| Backup (1GB) | ~50MB (streaming via pg_dump subprocess) |
| Dashboard | ~15MB (stdlib net/http server) |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Local DB** | The PostgreSQL instance gaet backs up from (usually `127.0.0.1` or a Unix socket). Configured via `GAET_LOCAL_URL` or `GAET_LOCAL_DB_*` vars. |
| **Cloud DB** | The remote PostgreSQL target (Supabase, Neon, RDS, VPS). Configured via `GAET_REMOTE_URL`. |
| **Snapshot** | A `.dump` file in `~/.gaet/backups/` produced by `pg_dump --format=custom`. |
| **GAET_DIR** | The `~/.gaet` directory — user state (config, backups, logs, lock). Overridable via `GAET_DIR` env var. |
| **Reset** | The `resetTargetObjects()` step that DROPs all `public` schema tables, views, and sequences before a restore — ensures idempotent re-runs. |

---

## Conclusion

gaet prioritizes **reliability** and **simplicity** over features. Every architectural decision is made to:

1. Prevent data loss (integrity verification, destructive-guard confirmation)
2. Fail fast and loudly (typed errors, explicit exit codes)
3. Keep code auditable (zero dependencies, single-responsibility packages)
4. Minimize dependencies (Go stdlib only; pg_* tools invoked, not linked)
5. Maximize compatibility (cross-platform TTY/lock/socket handling)

This philosophy makes gaet suitable for production use despite its small footprint.
