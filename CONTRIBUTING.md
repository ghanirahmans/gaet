# Contributing to Gaet

Thank you for your interest in contributing to **Gaet**! To ensure the project remains lightweight, fast, maintainable, and reliable across all operating systems, all contributors (humans and AI agents) are required to follow these development standards.

---

## Core Guidelines & Architectural Principles

Before writing any code, please review our core architectural rules documented in detail in [AGENTS.md](AGENTS.md) and [docs/architecture.md](docs/architecture.md):

1. **Zero External Dependencies**: Core CLI relies 100% on standard library Go 1.22+ (`net/http`, `os`, `syscall`, `embed`) and standard system PostgreSQL binaries (`pg_dump`, `pg_restore`, `psql`). Do not introduce third-party Go modules.
2. **Strict Single Binary Distribution**: CLI runtime, backup engine, and web operations dashboard are compiled into a single binary.
3. **Pure ASCII Standard**: Output tags must strictly use `[ OK ]`, `[FAIL]`, `[WARN]`, `[INFO]`, and `[NOTE]`. Do not use raw Unicode emojis in CLI output.
4. **Empathetic Error UX**: Always provide actionable hint remediation steps and troubleshooting links on failure.
5. **Cross-Platform Compatibility**: Always use `filepath.Join` or `os.PathSeparator` for cross-platform path handling (Linux, macOS, Windows).

---

## Development Workflow

### 1. Setting Up Development Environment

Clone the repository and verify the Go test suite:

```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
go test ./... -count=1
```

### 2. Building the Binary

```bash
go build -ldflags="-s -w" -o gaet ./cmd/gaet
```

### 3. Testing Requirements

- All pull requests must pass the complete Go test suite (`go test ./... -count=1`).
- Every new subcommand, flag, or bugfix must include dedicated test coverage in `tests/*_test.go` (the suite is integration-focused: it compiles the binary and drives subcommands; see `tests/main_test.go`).

### 4. Git Branching Strategy

- **`main`**: Primary development branch.
- **`lts/v1.1`**: Production / LTS release branch.
- Changes are merged into `main`, tested, and then merged to `lts/v1.1`.

### 5. Documentation Maintenance

Documentation is held to the same standard as code: **the code is the single
source of truth**, and docs must describe what the code actually does today.

**Before committing any documentation change**, run the drift detector:

```bash
bash sandbox/verify-docs.sh
```

It must exit `0`. The CI `docs-consistency` job runs the identical script, so a
local pass means the check will pass in CI. It verifies:

1. Every `gaet <command>` in the README exists in `cmd/gaet/main.go`'s dispatch.
2. Every `.env.example` key is backed by source (`pkg/config/config.go` / `pkg/`).
3. `go.mod`'s Go version matches the version cited in `AGENTS.md`.
4. Every relative Markdown link and `#anchor` resolves.
5. Every live `docs/*.md` file is listed in `docs/README.md`.
6. No live doc presents the retired Python engine as current.
7. The SDK README's methods and response fields match `sdk/src/client.ts` and
   the server's `sendJSON` payloads.
8. Every documented `~/.gaet/<path>` is defined in `pkg/core/paths.go`.

**How to fix drift:** update the **doc**, never the gate. If a doc describes a
feature that does not exist in code, either implement it (with tests) or remove
the claim. Deliberately historical files (Python-era guides, audits) are listed
in `sandbox/historical-docs.txt` and are exempt from checks 4–6.

**Cadence:** gates run on every PR; a full manual audit (see
`.kilo/plans/*-docs-audit-*.md`) is run per minor release and quarterly.
