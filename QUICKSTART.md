# Quickstart — gaet

Get your first backup running in 5 minutes.

---

## Prerequisites

- PostgreSQL client tools (`pg_dump`, `pg_restore`, `psql`)
- Python 3.8+
- A local PostgreSQL database
- A cloud PostgreSQL instance (Supabase, Neon, AWS RDS, or self-hosted)

---

## Step 1: Install

```bash
curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
```

Verify installation:
```bash
gaet --version
# Output: gaet v2.0.0
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
🚀 Push: local → cloud
== gaet push ==
  📦  Dumping local database...
    OK  Dump tersimpan (37.7 MB)
  ☁️   Mensinkronkan ke cloud...
    OK  Sinkronisasi selesai!

-- Push Selesai --
  OK  Backups stored: /home/user/.gaet/backups/gaet_20240815.dump (37.7 MB)
  OK  Tabel sinkron: 19
  >  Jalankan 'gaet status' untuk detail
[2024-08-15 10:30:00] ✅ Push complete
```

---

## Step 4: Verify Sync

```bash
gaet status
```

Shows per-table row counts and sync status. All tables should show `✓` (synced).

```
-- Sinkronisasi --
Tabel	        Lokal	  Cloud	Status
api_keys	       5000	  5000	✓
comments	   250000	250000	✓
posts	           45000	 45000	✓
...
```

---

## Step 5: Enable Auto-Backup (Optional)

```bash
# Run every 6 hours (default)
gaet push --auto

# Or custom interval (hours)
gaet push --auto=24
```

This creates a systemd timer (Linux), launchd job (macOS), or Task Scheduler task (Windows).

Check status:
```bash
gaet log --filter CRON
```

---

## Next Steps

- [Commands Reference](README.md#commands-reference) — all CLI commands
- [Configuration](README.md#configuration) — env vars explained
- [Troubleshooting](TROUBLESHOOTING.md) — common errors
- [Dashboard](README.md#dashboard-web-ui) — web UI for monitoring

---

## Need Help?

- Run `gaet doctor` for comprehensive health check
- Run `gaet check` for quick connectivity test
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common errors
- Open an issue: https://github.com/ghanirahmans/gaet/issues
