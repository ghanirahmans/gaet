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
