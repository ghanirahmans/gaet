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
- Every new subcommand, flag, or bugfix must include dedicated test coverage in `pkg/*/*_test.go` or `cmd/gaet/main_test.go`.

### 4. Git Branching Strategy

- **`main`**: Primary development branch.
- **`lts/v1.1`**: Production / LTS release branch.
- Changes are merged into `main`, tested, and then merged to `lts/v1.1`.
