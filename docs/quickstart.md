# Quickstart — gaet

Get your first backup running in 5 minutes.

---

## Prerequisites

- PostgreSQL client tools (`pg_dump`, `pg_restore`, `psql`)
- A local PostgreSQL database
- A cloud PostgreSQL instance (Supabase, Neon, AWS RDS, or self-hosted)

---

## Step 1: Install

```bash
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/main/install.sh | bash
```

Verify installation:
```bash
gaet --version
# Output: gaet v1.1.0
```

---

## Step 2: Configure

Run the interactive wizard:
```bash
gaet init
```

You'll be asked:
1. **Local database** — host, port, name, user (press Enter for defaults)
2. **Cloud database** — connection URL
3. **Retention** — how many days to keep backups (default: 7)

Config saved to `~/.gaet/.env` (permissions: `0600`).

---

## Step 3: First Backup

```bash
# Verify everything is connected
gaet check

# Dry-run (simulate without executing)
gaet push --dry-run

# Actual backup
gaet push
```

Expected output:
```
[2026-08-17 15:50:25] Push: local -> cloud

  ┌────────────────────────────────────────────────────────────┐
  │ gaet push                                                 │
  └────────────────────────────────────────────────────────────┘

  [INFO]  Dumping local database...
  [ OK ]  Dump saved (37.7 MB)
  [INFO]  Syncing to cloud...
  [ OK ]  Synchronization complete!
  [ OK ]  Push complete — 37.7 MB synced to cloud
[2026-08-17 15:50:26] Push complete
```

---

## Step 4: Verify Sync

```bash
gaet status
```

Shows per-table row counts and sync status. All tables should match.

---

## Step 5: Enable Auto-Backup (Optional)

```bash
# Run every 6 hours (default)
gaet auto 6
```

This creates a systemd timer (Linux), launchd job (macOS), or Task Scheduler task (Windows).

Check status:
```bash
gaet log --filter CRON
```

---

## Next Steps

- [Commands Reference](../README.md#command-specifications) — all CLI commands
- [Configuration](../README.md#configuration-reference) — env vars explained
- [Troubleshooting](troubleshooting.md) — common errors
- [Dashboard](desain_dashboard.md) — web UI for monitoring

---

## Need Help?

- Run `gaet doctor` for comprehensive health check
- Run `gaet check` for quick connectivity test
- Check [troubleshooting.md](troubleshooting.md) for common errors
- Open an issue: https://github.com/ghanirahmans/gaet/issues
