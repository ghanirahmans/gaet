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

### Phase 10: Next-Gen Peer-to-Peer & High-Availability Engine
- [ ] **P2P Machine-to-Machine DB Clone (`gaet clone <peer>`)**: Direct encrypted database streaming between developer machines over Tailscale/WireGuard or LAN without cloud intermediaries.
- [ ] **Continuous WAL Replication & Point-In-Time Recovery (PITR)**: Write-Ahead Log (WAL) archiving for second-accurate database restoration before incidents occur.
- [ ] **Mobile PWA & Push Notifications (`gaet serve`)**: Progressive Web App dashboard with real-time push alerts to mobile devices on backup status.

### Phase 11: Compliance, Intelligence & Multi-Engine Bridge
- [ ] **Cryptographic Verification & Attestation (`gaet verify`)**: Digital GPG/SSH signature signing for backup dumps to provide tamper-proof compliance audit trails.
- [ ] **Automated Index & Schema Optimizer (`gaet optimize`)**: Static analysis of table bloat and query statistics to generate `CREATE INDEX` recommendations.
- [ ] **Cross-Database Migration Bridge (`gaet export --to-sqlite`)**: Data format translation engine for migrating legacy DBs or seeding SQLite for local testing.

### Phase 12: High-Performance Streams & Intelligent Workflows
- [ ] **Parallel Chunked Upload Engine (`gaet push --parallel 4`)**: Multi-threaded parallel stream chunking (`pg_dump -F d -j N`) for ultra-fast multi-gigabyte uploads and fetches.
- [ ] **Instant Ephemeral Sandbox (`gaet sandbox`)**: One-command disposable PostgreSQL environments pre-loaded with snapshot data that self-destruct upon exit.
- [ ] **Zero-Downtime Live Migration (`gaet migrate --live`)**: Seamless live replication pipeline between database providers (e.g. AWS RDS to Supabase/Neon) without application downtime.
- [ ] **Natural Language CLI Assistant (`gaet ask "<query>"`)**: Natural language command parser for intuitive operations and database queries.

### Phase 13: Data Synthesis, Tenant Isolation & Automated Verification
- [ ] **Smart Synthetic Seed Generator (`gaet seed --synthetic 1000`)**: Schema analysis and realistic synthetic PII-safe data generation for testing environments.
- [ ] **Automated Restore Verification Test (CI Smoke Test)**: Automated CI/CD pipeline step that provisions isolated temporary DB containers to restore and validate snapshot integrity.
- [ ] **Multi-Tenant DB Isolator (`gaet tenant backup <tenant-id>`)**: Extract, backup, or restore isolated data for specific SaaS tenants from shared multi-tenant databases.
- [ ] **One-Click Disaster Failover (`gaet failover`)**: Automated failover to standby cloud database instances during primary provider outages.

### Phase 14: Enterprise Ransomware Defense & Edge Synchronization
- [ ] **Immutable WORM Storage (Ransomware Protection)**: Support for S3 Object Lock / WORM mode preventing snapshot deletion or tampering even during admin credential compromises.
- [ ] **Edge Database Sync Bridge**: Offline-first synchronization engine bridging local edge DBs (SQLite, PGLite, WASM, Turso) with central PostgreSQL instances.
- [ ] **Automated Time-Series Partitioning (`gaet partition`)**: Automated table partitioning for giant audit log and time-series tables.
- [ ] **Financial & Compliance Audit Export (`gaet audit-export`)**: Structured Parquet/CSV data exports formatted for SOC2, ISO27001, and HIPAA compliance audits.

### Phase 15: AI Vector Storage, Plugin Ecosystem & TUI
- [ ] **AI Vector Backup Support (`gaet pgvector`)**: Dedicated handling for `pgvector` extensions preserving HNSW/IVFFlat index structures across backups and restores.
- [ ] **Extensible Plugin Architecture (`gaet plugin`)**: Standard-library-based hook and plugin system for third-party storage adapters, notification channels, and data transformers.
- [ ] **Geo-Redundant Multi-Cloud Mirroring**: Parallel backup mirroring across multiple international cloud regions and providers.
- [ ] **Interactive Terminal UI (`gaet tui`)**: Rich curses-based text interface for SSH power users to inspect snapshots, logs, and sync status without starting a web server.
