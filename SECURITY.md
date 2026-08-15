# Security — gaet

Security considerations and policies for gaet.

---

## Design Principles

1. **Least privilege** — gaet runs as your user, not root
2. **Minimal attack surface** — no external dependencies, no network requests
3. **Secure defaults** — passwords never logged, files have restrictive permissions
4. **Defense in depth** — multiple validation layers for dump integrity

---

## Data Handling

### Passwords

- Stored in `~/.gaet/.env` (plain text, but file permissions are `0600`)
- Never passed as command-line arguments (prevents `ps aux` exposure)
- Masked in all output: `postgresql://user:***@host:5432/db`
- Never logged to `gaet.log` or `cron.log`

### Backup Files

- Stored in `~/.gaet/backups/gaet_*.dump`
- PostgreSQL custom format (`pg_dump --format=custom`) — encrypted at rest if filesystem is encrypted
- Delete automatically after `GAET_RETENTION_DAYS`

### Network Connections

- Uses standard PostgreSQL wire protocol
- SSL/TLS controlled by `GAET_REMOTE_SSLMODE`:
  - `disable` — no encryption (local testing only)
  - `prefer` — try SSL, fall back to plain (default)
  - `require` — enforce SSL (breaks non-SSL servers)
  - `verify-ca` / `verify-full` — verify certificate (advanced)

---

## File Permissions

| Path | Permissions | Purpose |
|------|-------------|---------|
| `~/.gaet/.env` | `0600` (-rw-------) | Config with passwords |
| `~/.gaet/backups/*.dump` | `0600` | Backup data |
| `~/.gaet/backups/.gaet.lock` | `0644` (-rw-r--r--) | Lock file (no secrets) |
| `gaet.log` | `0644` | Log file (no passwords) |
| `cron.log` | `0644` | Cron log (no passwords) |

If permissions are wrong, fix them:
```bash
chmod 600 ~/.gaet/.env
chmod 600 ~/.gaet/backups/*.dump
```

---

## Input Validation

### SQL Injection Prevention

- All SQL queries use parameterized statements where possible
- Table names validated against regex `^[a-zA-Z_][a-zA-Z0-9_]*$`
- Subprocess calls use argument arrays, not shell strings:
  ```python
  subprocess.run(["pg_dump", "-Fc", dbname], ...)  # Safe
  subprocess.run(f"pg_dump {dbname}", shell=True)  # DANGEROUS
  ```

### Command Injection Prevention

- User input never interpolated into shell commands
- Paths validated to prevent directory traversal
- URLs parsed with `urllib.parse` before use

---

## Third-Party Dependencies

gaet has **zero external dependencies**. Only requires:
- Python 3.8+ stdlib
- PostgreSQL client tools (`pg_dump`, `pg_restore`, `psql`)

No pip packages, no npm packages, no system libraries beyond POSIX standards.

---

## Security Checklist

Before using in production:

- [ ] Change default PostgreSQL passwords
- [ ] Enable SSL for cloud connections (`GAET_REMOTE_SSLMODE=require`)
- [ ] Use firewall to restrict database access
- [ ] Rotate credentials periodically
- [ ] Audit `~/.gaet/.env` permissions regularly
- [ ] Monitor backup logs for anomalies
- [ ] Keep gaet updated (`gaet update`)

---

## Reporting Vulnerabilities

If you find a security vulnerability:

1. **Do NOT open a public issue**
2. Email: [REDACTED_SK_KEY]
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (optional)

We will acknowledge receipt within 48 hours and provide a timeline for fix.

---

## Known Security Notes

### Password in `.env` file

**Risk:** Low (file permissions `0600`, local access required)

**Mitigation:**
- Store `.env` on encrypted filesystem
- Use different password per environment
- Consider using `PGPASSWORD` environment variable instead of file

### Unencrypted network connections

**Risk:** Medium (credentials and data transmitted in plaintext)

**Mitigation:**
- Use `GAET_REMOTE_SSLMODE=require` for production
- Use VPN or SSH tunnel for untrusted networks
- Prefer managed PostgreSQL services with SSL enforced

### Local file locks

**Risk:** Low (local attacker could read lock state)

**Mitigation:**
- Lock file contains no sensitive data
- PID-based stale detection prevents brute force
- File permissions `0644` are sufficient

---

## Compliance

gaet is designed to work with:
- **GDPR** — data never leaves your control (you manage the infrastructure)
- **SOC 2** — backup integrity verified via `pg_restore --list`
- **HIPAA** — encryption at rest via filesystem encryption, encryption in transit via SSL

Note: gaet itself does not provide encryption at rest. Use your OS/filesystem encryption (LUKS, FileVault, BitLocker) for that layer.
