# Support Policy for Gaet (LTS Lifecycle)

This document outlines the support policy and maintenance lifecycle for **Gaet**.

---

## Active LTS Releases

| Version | Engine | Status | Release Date | Support Until | Notes |
|:---|:---|:---|:---|:---|:---|
| **`v1.1.0 LTS`** | **Golang** | 🟢 **Active LTS** | August 2026 | **August 2027** | Official Production Single Binary Release & Active Development |
| **`v1.0.0 LTS`** | Python | 🟡 **Maintenance** | August 2026 | **August 2027** | Legacy Python Engine (Critical Security & Bug Fixes Only) |

---

## Architecture Transition & Support Policy

1. **Golang Engine (`v1.1.0 LTS`+)**:
   - Starting with `v1.1.0 LTS`, all active feature development, performance enhancements, and new CLI/Dashboard capabilities are powered exclusively by the Golang single-binary runtime.

2. **Legacy Python Engine (`v1.0.0 LTS`)**:
   - The legacy Python-based version (`v1.0.x`) has entered **Maintenance Mode**.
   - Support for the Python engine will end in **August 2027**. During this maintenance period, it will receive critical security patches and high-severity bug fixes only. Users are strongly encouraged to upgrade to `v1.1.0 LTS`.

---

## Scope of Support for `v1.1.0 LTS`

During the 1-year LTS support window (August 2026 – August 2027), `v1.1.0 LTS` will receive:

1. 🛡️ **Critical Security Patches**: Immediate patch updates for any security vulnerabilities or credential handling bugs.
2. 🐛 **Bug Fixes**: Patch releases for unexpected CLI errors, cross-platform compatibility issues (Linux, macOS, Windows), or database backup/sync failures.
3. 🐘 **PostgreSQL Version Compatibility**: Routine compatibility updates for new PostgreSQL server versions and client tools (`psql`, `pg_dump`, `pg_restore`).

---

## Reporting Issues & Vulnerabilities

- **Bug Reports**: Open an issue on GitHub at [https://github.com/ghanirahmans/gaet/issues](https://github.com/ghanirahmans/gaet/issues).
- **Security Vulnerabilities**: Please review our [SECURITY.md](SECURITY.md) for responsible disclosure guidelines.
