# ROADMAP.md — Gaet Strategic Future Roadmap

## Vision
> **"Gaet: Simple for Developers, Resilient for SysAdmins, Embeddable for Python Applications."**

Gaet aims to evolve from a zero-dependency CLI database backup tool into the **de-facto open-source PostgreSQL Backup, Cloud Sync & Disaster Recovery Engine** for standalone CLI usage, Python applications, and containerized infrastructure.

---

## 🎯 Strategic Milestones

### Phase 1: Dual-Personality Engine & Python SDK (`import gaet`)
- [ ] **Exception Refactoring**: Refactor core business functions in `src/gaet/` to raise typed exceptions (`GaetError`, `GaetConfigError`, `GaetBackupError`) instead of calling `sys.exit()`.
- [ ] **Programmatic API Client (`gaet.Client`)**: Expose clean Python SDK methods (`client.push()`, `client.restore()`, `client.status()`).
- [ ] **PyPI Package Release**: Publish Gaet to PyPI so developers can `pip install gaet` and use it inside FastAPI, Django, Flask, or backend automation scripts.

### Phase 2: Security & Production Hardening
- [ ] **Client-Side Zero-Knowledge Encryption**: Optional client-side AES-256 GPG/Age encryption for backup dump snapshots before disk saving or cloud uploading.
- [ ] **Dashboard Authentication (`gaet serve`)**: Token/Secret-key authentication for the Web Dashboard to secure access over local networks.
- [ ] **OS Keyring Integration**: Support for native OS credential stores (Linux Secret Service, macOS Keychain, Windows Credential Manager).

### Phase 3: Multi-Storage & Hybrid Cloud Engine
- [ ] **Object Storage Engine (S3 / R2 / GCS / MinIO)**: Direct snapshot uploads to AWS S3, Cloudflare R2, Google Cloud Storage, or self-hosted MinIO buckets.
- [ ] **Multi-Target Disaster Recovery**: Redundant backup synchronization (simultaneous upload to Cloud PostgreSQL + Object Storage).
- [ ] **Stream Compression**: Configurable compression support (`zstd` / `gzip`) for dump snapshots.

### Phase 4: Observability, Alerting & Integrations
- [ ] **Webhook Notifications**: Instant backup status alerts sent to Slack, Discord, Telegram, and custom Webhooks on backup success or failure.
- [ ] **Heartbeat Monitoring (Healthchecks.io)**: Automated deadman's switch pings after scheduled timer/cron backup completion.
- [ ] **Prometheus Metrics**: Expose snapshot metrics (duration, size, status) for Grafana monitoring dashboards.

### Phase 5: Global Distribution & Container Ecosystem
- [ ] **Package Managers**: Official Homebrew Formula (`brew install gaet`), WinGet package (`winget install gaet`), and Debian/RPM packages.
- [ ] **Official Docker Image**: Ultra-lightweight Scratch/Alpine container (`docker run ghanirahmans/gaet`) tailored for Kubernetes CronJobs and Docker Compose setups.

### Phase 6: Database Time Travel & Schema Intelligence
- [ ] **Snapshot Difference Inspector (`gaet diff`)**: Compare schema structure and row count drift between snapshots, or local vs cloud databases.
- [ ] **Database Time Travel (`gaet checkout <snapshot>`)**: Spin up temporary isolated preview databases initialized from any past backup snapshot.
- [ ] **Snapshot Tagging (`gaet tag <snapshot> <name>`)**: Human-readable naming and tagging for important milestones (e.g. `pre-migration-v2`, `month-end-jan`).

### Phase 7: Privacy Guard & Data Sanitization Engine
- [ ] **PII Data Masking (`gaet push --sanitize`)**: Automatic anonymization of emails, phone numbers, and hashes before cloud sync or team sharing.
- [ ] **Selective Table Restoration**: Ability to extract and restore specific tables from multi-gigabyte backup dumps (`gaet restore --tables users,orders`).

### Phase 8: Intelligent Health Diagnostics & Forecasting
- [ ] **Auto-Remediation Wizard (`gaet doctor --fix`)**: Interactive automated repair for environment variables, path exports, and database socket permissions.
- [ ] **Predictive Capacity Analytics (`gaet stats`)**: Storage growth forecasting to predict disk space exhaustion before it occurs.

### Phase 9: Developer Ecosystem & IDE Integrations
- [ ] **Official GitHub Action (`ghanirahmans/gaet-action@v1`)**: Pre-built CI/CD step for database backups prior to automated deployment or migration tasks.
- [ ] **VS Code Extension**: Lightweight extension for monitoring Gaet status, triggering backups, and launching `gaet serve` directly inside VS Code.
