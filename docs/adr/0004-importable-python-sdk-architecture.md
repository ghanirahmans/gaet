# ADR-0004: Dual-Personality Architecture (CLI Tool & Importable SDK)

## Status
**Superseded** — by ADR-0003 decision (Go engine) and the TypeScript SDK (`sdk/`)

## Context
The legacy Python-era ADR proposed a Dual-Personality Architecture where Gaet would function both as a standalone CLI tool and as a clean, importable Python Library SDK (`import gaet`), exposing high-level programmatic interfaces (`GaetEngine`, `backup()`, `restore()`, `get_status()`, `list_snapshots()`) as a PyPI package.

## Why This Was NOT Adopted
The Golang migration (completed per `docs/migrasi_to_golang.md`) changed the design direction:

1. **Go single binary model**: The primary engine is now a compiled Go binary. Go does not have a Python-style `import gaet` module distribution model.
2. **TypeScript SDK chosen**: Instead of a Python SDK, the team built a **TypeScript/JavaScript SDK** (`@ghanirahmans/gaet`, in `sdk/`) that wraps the `gaet serve` REST API. This enables integration with Node.js, Next.js, React, Express, and Python web backends via HTTP — no direct library import required.
3. **No `sys.exit()` in business functions**: The Go engine returns typed `*core.GaetError` values (with exit codes) rather than calling `os.Exit` inside helper functions. CLI handlers propagate these errors; HTTP handlers map them to JSON error responses.

## Current State (Golang Engine)
- **CLI**: `gaet push`, `gaet fetch`, `gaet restore`, etc. — single binary at `~/.local/bin/gaet`.
- **REST API**: `gaet serve` — stdlib HTTP server at `http://127.0.0.1:6161` serving `pkg/serve/server.go` handlers.
- **TypeScript SDK**: `@ghanirahmans/gaet` wraps the REST API via `fetch` (`sdk/src/client.ts`), with an optional `startServer()` that auto-spawns the daemon.

## Consequences
- **Retained Positive**: Clean separation of business logic from CLI/HTTP presentation — `pkg/backup.RunPush()` is callable from both `main.go` and `pkg/serve/server.go`.
- **Retained Positive**: SDK integration remains possible for Python web backends — they call the REST API over HTTP from any language (see `docs/rest-api-integration.md`).
- **Not Adopted**: A native `pip install gaet` Python library. Web integration is HTTP-first, not library-import-first.

## See Also
- `sdk/` — the implemented TypeScript SDK.
- `pkg/serve/server.go` — the REST API surface the SDK consumes.
- `docs/rest-api-integration.md` — examples for Next.js, React, Express, and Python (Flask/FastAPI) HTTP clients.
