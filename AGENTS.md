# AGENTS.md — Gaet Architecture & Development Guidelines (v2.0 Golang Engine)

This document provides essential architectural context, design standards, and coding conventions for AI agents and human contributors working on the **Gaet** codebase.

---

## 1. Executive Summary & Core Philosophy

**Gaet** is a zero-dependency, high-performance cross-platform PostgreSQL Database Backup & Cloud Sync CLI tool built with **Golang 1.22+**.

### Core Principles
- **Single Binary Distribution**: Compiled into a fast, portable single binary without external runtime dependencies (no Python or Node.js runtime required).
- **Cross-Platform Standard Compliance**: Adheres to the **XDG Base Directory Specification** on Linux/macOS and **Windows AppData** standard.
- **Full ASCII UI Standard**: No emojis or raw Unicode glyphs in CLI outputs. Clean ASCII status tags (`[ OK ]`, `[FAIL]`, `[WARN]`, `[INFO]`, `[NOTE]`) ensure 100% compatibility across legacy terminals, pipes, and CI/CD pipelines.
- **Embedded Web Dashboard**: Static web assets (`static/index.html`, `gaet-logo.png`) are compiled directly into the binary using Go `//go:embed`.

---

## 2. Directory & Storage Architecture

| Identifier | Platform Location | Purpose |
| :--- | :--- | :--- |
| **`GAET_DIR`** *(User Data)* | `~/.gaet` | User configuration (`.env`), backup snapshots (`backups/*.dump`), lockfiles |
| **`GAET_BINARY`** *(PATH)* | `~/.local/bin/gaet` *(Linux/macOS)*<br>`%USERPROFILE%\.local\bin\gaet.exe` *(Windows)* | Compiled single-file binary containing CLI runtime & dashboard |

---

## 3. Codebase Structure

```text
gaet/
├── cmd/
│   └── gaet/
│       └── main.go              # Primary CLI entry point & global flag parser
├── pkg/
│   ├── backup/                  # Backup push, fetch, restore & target reset engine
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
├── tests/                       # Comprehensive unit & integration test suite
├── docs/                        # Project documentation, architecture ADRs & guides
├── install.sh                   # One-liner Linux/macOS binary installer
├── install.ps1                  # One-liner Windows PowerShell installer
├── go.mod                       # Go module definition
└── gaet.1                       # Linux manpage documentation
```

---

## 4. Development & Testing Rules

### Running Unit & Integration Tests
Before pushing any change, execute the complete Go test suite:
```bash
go test ./... -count=1
```
All **13/13 packages** MUST pass with zero errors.

### Building the Binary
```bash
go build -ldflags="-s -w" -o gaet ./cmd/gaet
```

---

## 5. Mandatory Architectural Principles

1. **Zero-Dependency Constraint**: Standard library Go only (`net/http`, `os`, `syscall`, `embed`). No external PyPI or Go third-party dependencies.
2. **Strict Subcommand Isolation**: Subcommand packages in `pkg/` interact via shared utilities in `pkg/core`.
3. **CI/CD First-Class Support**: Every command must support `--json`, `--plain`, `-q/--quiet`, and `-y/--yes`.
4. **Cross-Platform Invariance**: Always use `filepath.Join` or `os.PathSeparator`.
