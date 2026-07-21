# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅ Active |

## Reporting a Vulnerability

If you discover a security vulnerability in gaet, please report it privately.

**Do not** submit a public GitHub issue. Instead, email the maintainer directly or open a draft security advisory at:

- GitHub: [github.com/ghanirahmans/gaet/security/advisories](https://github.com/ghanirahmans/gaet/security/advisories)

You should receive a response within 48 hours. If not, follow up to ensure receipt.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

We take all reports seriously and will:
1. Confirm receipt within 48 hours
2. Assess severity and impact
3. Develop and test a fix
4. Release a patch with attribution (if desired)

## Security Architecture

### Credential Storage

| Credential | Storage Method | Security |
|------------|---------------|----------|
| `GAET_LOCAL_DB_PASS` | `~/.gaet/.env` with `0o600` perms | Separate from URL, never logged |
| `GAET_REMOTE_URL` | `~/.gaet/.env` with `0o600` perms | Contains password (cloud provider format) |
| PGPASSFILE temp | Temp file with `0o600` perms | Auto-deleted after each command |

### Data in Transit
- Cloud connections use `PGSSLMODE=require` by default
- All PostgreSQL traffic is encrypted via TLS

### Data at Rest
- Backup dumps are unencrypted PostgreSQL custom format
- Stored in `~/.gaet/backups/` with user-default permissions
- Retention policy auto-deletes old backups

### Process Isolation
- No network daemon (dashboard runs on demand)
- No root/sudo required — runs entirely as user
- No background processes (except optional dashboard & scheduler)

## Security Checklist

### Before Production Use
- [ ] `.env` file permissions verified (`chmod 600 ~/.gaet/.env`)
- [ ] `GAET_LOCAL_DB_PASS` used instead of password in URL
- [ ] `GAET_REMOTE_SSLMODE=require` (default, verify)
- [ ] Dashboard CORS origin configured if remote access needed
- [ ] `GAET_PATH` environment set if gaet not in standard PATH
- [ ] Regular backup testing: `gaet push --dry-run` in CI
- [ ] Retention policy configured: `GAET_RETENTION_DAYS`

## Known Security Considerations

1. **Remote URL passwords**: Cloud providers (Supabase, Neon) generate URLs with embedded passwords. Consider using environment variable injection (`export GAET_REMOTE_URL=...`) instead of `.env` for these.

2. **Backup file access**: Dump files in `~/.gaet/backups/` contain all database data. Ensure filesystem permissions are restricted.

3. **Dashboard network exposure**: Dashboard binds to `0.0.0.0:9191` by default. For production, use `GAET_DASHBOARD_HOST=127.0.0.1` or a reverse proxy with authentication.

4. **Scheduler credentials**: Auto-backup via systemd/launchd runs as your user. Credentials in `.env` are accessible to any process running as your user.
