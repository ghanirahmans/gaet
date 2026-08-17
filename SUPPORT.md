# Support Policy for Gaet (LTS Lifecycle)

This document outlines the support policy and maintenance lifecycle for **Gaet**.

---

## Active LTS Releases

| Version | Engine | Recommendation | Status | Release Date | Support Until | Notes |
|:---|:---|:---|:---|:---|:---|:---|
| **`v1.1.0 LTS`** | **Golang** | 🟢 **RECOMMENDED** | 🟢 **Active LTS** | August 2026 | **August 2027+** | Engine Utama Single-Binary Rilis Produksi & Pengembangan Berkelanjutan |
| **`v1.0.0 LTS`** | Python | 🟡 **ALTERNATIVE** | 🟡 **Maintenance** | August 2026 | **August 2027** | Engine Alternative/Legacy dengan Dukungan Hingga Tahun Depan |

---

## Architecture Transition & Support Policy

1. 🚀 **Golang Engine (`v1.1.0 LTS`+) — Mesin Utama Utama & Berkelanjutan**:
   - Mulai versi `v1.1.0 LTS`, seluruh pengembangan fitur baru, peningkatan performa biner tunggal, dan optimasi CLI/Dashboard **akan terus menggunakan dan dikembangkan dengan Golang**.
   - Golang menjadi standar arsitektur permanen untuk ekosistem Gaet.

2. 🐍 **Python Legacy Engine (`v1.0.0 LTS`) — Dukungan Hingga Tahun Depan**:
   - Versi berbasis Python (`v1.0.x`) **tetap mendapat dukungan perbaikan bug & keamanan kritis hingga tahun depan (Agustus 2027)**.
   - Setelah masa dukungan tersebut berakhir di tahun depan, dukungan versi Python akan dihentikan sepenuhnya (EOL) dan seluruh pengguna wajib menggunakan versi **Golang**.

---

## Scope of Support for `v1.1.0 LTS`

During the 1-year LTS support window (August 2026 – August 2027+), `v1.1.0 LTS` will receive:

1. 🛡️ **Critical Security Patches**: Immediate patch updates for any security vulnerabilities or credential handling bugs.
2. 🐛 **Bug Fixes**: Patch releases for unexpected CLI errors, cross-platform compatibility issues (Linux, macOS, Windows), or database backup/sync failures.
3. 🐘 **PostgreSQL Version Compatibility**: Routine compatibility updates for new PostgreSQL server versions and client tools (`psql`, `pg_dump`, `pg_restore`).

---

## Reporting Issues & Vulnerabilities

- **Bug Reports**: Open an issue on GitHub at [https://github.com/ghanirahmans/gaet/issues](https://github.com/ghanirahmans/gaet/issues).
- **Security Vulnerabilities**: Please review our [SECURITY.md](SECURITY.md) for responsible disclosure guidelines.
