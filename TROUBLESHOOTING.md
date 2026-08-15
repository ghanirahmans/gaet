# Troubleshooting — gaet

Common errors and how to fix them.

---

## Connection Errors

### `connection to server at "..." failed: Connection refused`

**Cause:** Database not running or wrong port.

**Fix:**
```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# Start PostgreSQL (Linux systemd)
sudo systemctl start postgresql

# Or check custom port
psql -h localhost -p 5433 -U postgres
```

### `FATAL: password authentication failed for user "..."`

**Cause:** Wrong password in config or `.env` file.

**Fix:**
```bash
# Reset password via psql
psql -U postgres
ALTER USER postgres PASSWORD 'newpassword';

# Then update gaet config
gaet set GAET_LOCAL_DB_PASS=newpassword
```

### `database "..." does not exist`

**Cause:** Database name typo or database not created.

**Fix:**
```bash
# List available databases
psql -U postgres -l

# Create missing database
psql -U postgres -c "CREATE DATABASE mydb;"
```

---

## Permission Errors

### `Permission denied: /home/user/.gaet/.env`

**Cause:** `.env` file has wrong permissions.

**Fix:**
```bash
chmod 600 ~/.gaet/.env
ls -la ~/.gaet/.env  # Should show -rw-------
```

### `permission denied while trying to connect to the database server`

**Cause:** Unix socket permission issue or wrong user.

**Fix:**
```bash
# Check socket path
psql -h /var/run/postgresql -U postgres

# If using custom socket directory
gaet set GAET_LOCAL_DB_HOST=/path/to/socket/dir
```

---

## Timeout Errors

### `timeout expired` during push/fetch

**Cause:** Large database (>1GB) takes longer than default 120s timeout.

**Fix:**
```bash
# Increase timeout to 600 seconds (10 minutes)
gaet set GAET_PG_TIMEOUT=600

# Or use environment variable
export GAET_PG_TIMEOUT=600
gaet push
```

---

## Lock File Errors

### `Another gaet operation is in progress`

**Cause:** Lock file from crashed/stale process.

**Fix:**
```bash
# Check for stale lock
cat ~/.gaet/backups/.gaet.lock

# If PID is dead, remove lock manually
rm ~/.gaet/backups/.gaet.lock

# Verify no other gaet processes running
pgrep -f "python.*gaet" || echo "No gaet processes"
```

---

## Restore Errors

### `cannot drop inherited constraint ... of relation "..."`

**Cause:** Partitioned tables fail with `--clean` flag.

**Fix:** Already fixed in v2.0.0 LTS. Ensure you're on latest version:
```bash
gaet update
```

### `type "event_type" already exists`

**Cause:** Custom types not dropped before restore.

**Fix:** Same as above — v2.0.0+ handles this automatically via `_reset_target_objects`.

---

## SSL/TLS Errors

### `server does not support SSL, but SSL was required`

**Cause:** SSL mode set to `require` but server doesn't support SSL.

**Fix:**
```bash
# Change to 'prefer' (tries SSL, falls back to plain)
gaet set GAET_REMOTE_SSLMODE=prefer

# Or disable SSL for local testing only
gaet set GAET_REMOTE_SSLMODE=disable
```

---

## Dashboard Issues

### `Address already in use` when starting dashboard

**Cause:** Another process using port 9191.

**Fix:**
```bash
# Find process using the port
lsof -i :9191

# Kill it or use different port
gaet serve --port 8080
```

### Dashboard shows "cloud tidak terjangkau"

**Cause:** Cloud database unreachable (paused instance, wrong URL, network issue).

**Fix:**
```bash
# Test cloud connectivity
gaet check

# Verify connection string
gaet get GAET_REMOTE_URL

# For Supabase: check if project is paused
# Login to https://supabase.com → Settings → API → Project URL
```

---

## Push/Fetch Failures

### `Dump local database failed`

**Possible causes:**
- Insufficient disk space in `/tmp` or backup directory
- Database locked by another process
- Dump too large for memory

**Fix:**
```bash
# Check disk space
df -h /tmp
df -h ~/.gaet/backups

# Check for locked tables
psql -U postgres -c "SELECT * FROM pg_locks WHERE NOT granted;"

# Try with explicit temp directory
export PGTMPDIR=/path/to/large/disk
gaet push
```

### `Gagal membersihkan cloud database`

**Cause:** Cloud database permissions issue or network timeout.

**Fix:**
```bash
# Test cloud connection directly
psql "$GAET_REMOTE_URL" -c "SELECT 1;"

# Check cloud database size
psql "$GAET_REMOTE_URL" -c "SELECT pg_size_pretty(pg_database_size(current_database()));"

# If cloud DB is locked, terminate connections
psql "$GAET_REMOTE_URL" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();"
```

---

## Auto-Backup Issues

### `Auto-backup timer... tidak aktif`

**Cause:** Auto-backup not enabled.

**Fix:**
```bash
# Enable auto-backup (every 6 hours by default)
gaet push --auto

# Or set custom interval (hours)
gaet push --auto=24
```

### `cron.log not found` or empty

**Cause:** Auto-backup never ran or log rotated.

**Fix:**
```bash
# Check if cron service is running
systemctl status gaet-auto-backup  # Linux
launchctl list | grep gaet        # macOS
schtasks /query /fo table         # Windows

# Check manual backup logs
gaet log --filter CRON
```

---

## Cross-Platform Issues

### Windows: `pg_dump` not found

**Cause:** PostgreSQL tools not in PATH.

**Fix:**
```powershell
# Add PostgreSQL bin to PATH
$env:PATH += ";C:\Program Files\PostgreSQL\18\bin"

# Or install PostgreSQL with pg_dump included
# https://www.postgresql.org/download/windows/
```

### macOS: Socket path not detected

**Cause:** PostgreSQL installed via Homebrew uses different socket path.

**Fix:**
```bash
# Find socket path
psql -h /tmp -U postgres -c "SELECT 1;"

# Set correct path
gaet set GAET_LOCAL_DB_HOST=/tmp
```

---

## General Debugging

### Enable verbose logging
```bash
export GAET_DEBUG=1
gaet push --dry-run
```

### Check config
```bash
gaet get          # View all settings
gaet doctor       # Comprehensive health check
```

### View full logs
```bash
gaet log 200      # Last 200 lines
gaet log --follow # Real-time tailing
```

### Reinstall
```bash
gaet uninstall --purge
# Then reinstall from https://github.com/ghanirahmans/gaet
```
