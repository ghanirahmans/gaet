# Documentation Index — gaet

In-depth guides and reference material for the gaet CLI.

> **Principle: code is truth.** Every claim in these guides must be traceable to
> the source in this repository. Run `bash sandbox/verify-docs.sh` before
> committing doc changes; the CI `docs-consistency` job runs the same script.

---

## Guides (live)

- [Quickstart](quickstart.md) — install and run your first backup.
- [Architecture & Design](architecture.md) — engine internals and data flow.
- [CI/CD Integration](ci-cd-integration.md) — run gaet in pipelines.
- [REST API & Sidecar Integration](rest-api-integration.md) — HTTP API for dashboards and services.
- [Troubleshooting](troubleshooting.md) — common failures and fixes.
- [Command Scopes](command_scopes.md) — comprehensive command specification.
- [Dashboard Design System](desain_dashboard.md) — operations hub UI reference.
- [Roadmap](roadmap.md) — strategic direction.

## Architecture Decision Records (ADRs)

- [ADR index](adr/README.md)
- [0001 — XDG app bundle isolation](adr/0001-xdg-app-bundle-isolation.md)
- [0002 — Pure ASCII CLI standard](adr/0002-pure-ascii-cli-standard.md)
- [0003 — Declarative command registry](adr/0003-declarative-command-registry.md)
- [0004 — Importable Python SDK (superseded)](adr/0004-importable-python-sdk-architecture.md)

## Historical / Archived

These describe past states of the project (Python engine `v1.0.0 LTS`) and are
kept for historical context only. Do **not** treat them as current behavior —
see [architecture.md](architecture.md) for the active Golang engine.

- [Legacy Python Engine](legacy-python.md) — deprecation & archival guide.
- [Python → Go Migration Blueprint](migrasi_to_golang.md) — migration spec (Indonesian).
- [Security & Code Quality Audit Report](audit_report.md) — Python-era audit.
- [Audit: Command & Architecture](audit_commands.md) — Python-era audit.
