# gaet — Security & Code Quality Audit Report

---

## Document Control

| Field | Value |
|-------|-------|
| **Project** | gaet — PostgreSQL Backup & Sync CLI |
| **Version audited** | 2.0.0 (commit `7481d56`, branch `master`) |
| **Audit date** | 2026-08-08 |
| **Auditor** | Hermes Agent (automated static analysis) |
| **Audit type** | Static source code review (SAST), no dynamic testing |
| **Standards referenced** | OWASP Top 10 (2021), CWE v4.14, CVSS v3.1 |
| **Overall risk rating** | **High** — 2 Critical, 4 High, 8 Medium, 12 Low |

---

## 1. Executive Summary

gaet is a zero-dependency, cross-platform CLI tool for PostgreSQL backup and cloud synchronization. The codebase demonstrates solid architectural foundations — atomic locking, integrity verification, cross-platform scheduler abstraction, and credential hygiene patterns that exceed expectations for a tool of this scope.

However, the audit identified **26 findings** across security, reliability, code quality, and supply chain domains. The most severe issues are:

1. **Unauthenticated network-accessible API** (Critical) — the dashboard binds to `0.0.0.0:9191` by default with no authentication and a bypassable CORS check. Any host on the network can trigger destructive operations (`fetch` overwrites the local database).

2. **SQL Injection via table-name interpolation** (High) — `gaet.py` interpolates table names directly into SQL queries without validation, despite a validation function existing in `scripts/status.py`.

3. **Installer/CLI configuration incompatibility** (High) — `scripts/installer.py` writes environment variables (`GAET_DB_*`) that the CLI does not read (`GAET_LOCAL_*`), rendering `gaet install` output non-functional.

4. **Windows installer targets wrong Git branch** (High) — `install.ps1` fetches from branch `main`; the repository uses `master`. Windows installation will fail with HTTP 404.

The full findings are detailed below with CWE identifiers, CVSS scores, and specific remediation guidance.

---

## 2. Audit Scope & Methodology

### 2.1 Scope

| In Scope | Out of Scope |
|----------|-------------|
| `gaet.py` (2,745 lines) | Runtime/dynamic testing |
| `scripts/*.py` (scheduler, installer, status, service_manager) | Penetration testing |
| `dashboard/` (Next.js 15 app — all routes, components, config) | Dependency vulnerability scanning (npm/pip) |
| `install.sh`, `install.ps1`, `install.py` | Infrastructure/deployment hardening |
| `tests/`, documentation files | |

### 2.2 Methodology

- **Manual static analysis** of all source files (full read, line-by-line)
- **Cross-referencing** between modules to detect contract mismatches
- **Pattern matching** for known vulnerability classes (injection, credential handling, access control)
- **Standards mapping** to CWE, OWASP Top 10, and CVSS v3.1

### 2.3 Severity Definitions

| Severity | CVSS Range | Definition |
|----------|------------|------------|
| **Critical** | 9.0 – 10.0 | Immediately exploitable; severe impact on confidentiality, integrity, or availability |
| **High** | 7.0 – 8.9 | Exploitable under specific conditions; significant impact |
| **Medium** | 4.0 – 6.9 | Requires preconditions; moderate impact |
| **Low** | 0.1 – 3.9 | Minimal risk; defense-in-depth or code quality concern |

---

## 3. Findings Summary

| ID | Title | Severity | CWE | OWASP |
|----|-------|----------|-----|-------|
| **GAET-SEC-001** | SQL Injection via table-name interpolation | High (7.6) | CWE-89 | A03:2021 |
| **GAET-SEC-002** | Unauthenticated API with bypassable CORS | Critical (9.0) | CWE-306, CWE-942 | A01:2021, A05:2021 |
| **GAET-SEC-003** | SQL Injection via database name in `pg_terminate_backend` | Medium (5.6) | CWE-89 | A03:2021 |
| **GAET-SEC-004** | Inconsistent credential protection (`PGPASSWORD` in process env) | Medium (4.7) | CWE-522 | A02:2021 |
| **GAET-SEC-005** | File permission regression in `cmd_set` | Medium (4.6) | CWE-732 | A01:2021 |
| **GAET-SEC-006** | Insufficient password masking in `cmd_get` | Low (2.7) | CWE-200 | A02:2021 |
| **GAET-BUG-001** | Installer writes incompatible env var names | High | — | — |
| **GAET-BUG-002** | Windows installer targets wrong Git branch | High | — | — |
| **GAET-BUG-003** | `--auto` without value fails instead of using default | Medium | — | — |
| **GAET-BUG-004** | `pg_restore` exit code conflates warnings with errors | Medium | CWE-754 | — |
| **GAET-BUG-005** | Version mismatch across three components | Medium | — | — |
| **GAET-BUG-006** | Dead code — unreachable `die()` after prior `die()` | Low | — | — |
| **GAET-BUG-007** | Port-scan blocking in `detect_local_pg` | Low | — | — |
| **GAET-QUAL-001** | Three divergent `.env` parser implementations | Medium | CWE-1042 | — |
| **GAET-QUAL-002** | Two divergent URL parser implementations | Medium | — | — |
| **GAET-QUAL-003** | Duplicate scheduler implementations (inline vs module) | Low | — | — |
| **GAET-QUAL-004** | Duplicate dashboard directory discovery logic | Low | — | — |
| **GAET-QUAL-005** | No `pyproject.toml` / `setup.py` — `pip install -e .` fails | Medium | — | — |
| **GAET-QUAL-006** | Blocking `execFileSync` in all dashboard API routes | Medium | — | — |
| **GAET-QUAL-007** | Monolithic `gaet.py` at 2,745 lines | Low | — | — |
| **GAET-QUAL-008** | Minimal test coverage — no pipeline/integration tests | Low | — | — |
| **GAET-SCM-001** | No integrity verification on downloaded files | Medium (5.3) | CWE-494 | A08:2021 |
| **GAET-SCM-002** | `curl | bash` install pattern | Low (2.4) | CWE-829 | A08:2021 |
| **GAET-DOC-001** | No `LICENSE` file despite MIT badge in README | Low | — | — |
| **GAET-DOC-002** | CONTRIBUTING.md references non-existent test files | Low | — | — |
| **GAET-DOC-003** | `DASHBOARD_ORIGIN` env var naming inconsistency | Low | — | — |

---

## 4. Detailed Findings

---

### GAET-SEC-001 — SQL Injection via Table-Name Interpolation

| Field | Value |
|-------|-------|
| **Severity** | High |
| **CVSS v3.1** | 7.6 (`AV:L/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H`) |
| **CWE** | CWE-89: Improper Neutralization of Special Elements used in an SQL Command |
| **OWASP** | A03:2021 — Injection |

**Affected locations:**
- `gaet.py:1332` (`cmd_status`)
- `gaet.py:1425` (`get_status_inline`)

**Description:**

Table names from the `GAET_TABLES` configuration variable (or auto-discovered from `information_schema.tables`) are interpolated directly into SQL queries using Python f-strings, without any validation or escaping:

```python
union = " UNION ALL ".join(
    f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}"
    for t in tables_def
)
```

A validation function `_validate_table_name()` exists in `scripts/status.py` (regex `^[a-zA-Z_][a-zA-Z0-9_]*$`), but `gaet.py` does not import or call it.

**Attack vectors:**

1. **Config injection** — If an attacker can write to `~/.gaet/.env` (e.g., shared system, compromised process running as the same user), they can set `GAET_TABLES=users; DROP TABLE audit_log--`. The next `gaet status` or `gaet push` will execute the injected SQL.

2. **Auto-discovery injection** — PostgreSQL permits quoted identifiers containing arbitrary characters (e.g., `CREATE TABLE "foo; DROP TABLE bar--" (...)`). An attacker with `CREATE` privilege on the `public` schema can create a maliciously named table. `gaet` will auto-discover it via `information_schema.tables` and interpolate the name into the count query, triggering SQL injection.

**Impact:** Full database compromise — data exfiltration, modification, or destruction of all tables in the database.

**Remediation:**

```python
_TABLE_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def _validate_table_name(name: str) -> bool:
    return bool(_TABLE_NAME_RE.match(name))

# In cmd_status and get_status_inline:
safe_tables = [t for t in tables_def if _validate_table_name(t)]
union = " UNION ALL ".join(
    f"SELECT '{t}'::text as tbl, count(*)::int as cnt FROM public.{t}"
    for t in safe_tables
)
```

Additionally, consider using `quote_ident()` via psql or parameterized queries via `psycopg2` (if a dependency is acceptable).

---

### GAET-SEC-002 — Unauthenticated API with Bypassable CORS Check

| Field | Value |
|-------|-------|
| **Severity** | Critical |
| **CVSS v3.1** | 9.0 (`AV:A/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H`) |
| **CWE** | CWE-306: Missing Authentication for Critical Function; CWE-942: Permissive Cross-domain Policy with Untrusted Domains |
| **OWASP** | A01:2021 — Broken Access Control; A05:2021 — Security Misconfiguration |

**Affected locations:**
- `dashboard/app/api/status/route.ts:9`
- `dashboard/app/api/push/route.ts:9`
- `dashboard/app/api/fetch/route.ts:9`
- `dashboard/app/api/stop/route.ts:9`
- `gaet.py:74` (`DEF_DASHBOARD_HOST = "0.0.0.0"`)

**Description:**

All four dashboard API routes implement CORS validation with the following pattern:

```typescript
const origin = req.headers.get("origin");
const allowedOrigin = process.env.DASHBOARD_ORIGIN || "http://localhost:9191";
if (origin && origin !== allowedOrigin) {
  return NextResponse.json({ ok: false, msg: "Forbidden" }, { status: 403 });
}
```

The check is **conditional on the presence of the `Origin` header**. Requests without an `Origin` header (curl, server-to-server calls, non-browser HTTP clients) bypass the check entirely. Furthermore, no authentication mechanism exists — no token, session, API key, or rate limiting is implemented on any route.

The dashboard binds to `0.0.0.0:9191` by default (`DEF_DASHBOARD_HOST = "0.0.0.0"` in `gaet.py:74`), making it accessible from any host on the local network.

**Impact:**

An attacker on the same network can:
- `GET /api/status` — read database table names, row counts, and sizes (information disclosure)
- `POST /api/push` — trigger a backup, overwriting cloud database data
- `POST /api/fetch` — trigger a restore, **overwriting the local database** (data destruction)
- `POST /api/stop` — stop auto-backup services (availability disruption)

**Remediation:**

1. **Change default bind address** to `127.0.0.1`:
   ```python
   DEF_DASHBOARD_HOST = "127.0.0.1"
   ```

2. **Implement token-based authentication**:
   - Generate a random token at `gaet serve` startup, write to `~/.gaet/.env` as `GAET_DASHBOARD_TOKEN`
   - Pass token via `Authorization: Bearer <token>` header on all API routes
   - Verify on every request before processing

3. **Fix CORS logic** to reject requests without a valid Origin:
   ```typescript
   const origin = req.headers.get("origin");
   if (!origin || origin !== allowedOrigin) {
     return NextResponse.json({ ok: false, msg: "Forbidden" }, { status: 403 });
   }
   ```

4. **Add rate limiting** (e.g., `next-rate-limiter` or middleware-based).

---

### GAET-SEC-003 — SQL Injection via Database Name in `pg_terminate_backend`

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **CVSS v3.1** | 5.6 (`AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:H`) |
| **CWE** | CWE-89: SQL Injection |
| **OWASP** | A03:2021 — Injection |

**Affected location:**
- `gaet.py:1738–1740` (`cmd_fetch`)

**Description:**

The database name `n` is interpolated directly into a SQL string with single-quote delimiters:

```python
run_cmd([psql, ..., "-tAc",
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
    f"WHERE datname='{n}' AND pid <> pg_backend_pid();"], ...)
```

If the database name contains a single quote (e.g., `my'db`), this breaks the SQL syntax. A maliciously crafted name could inject arbitrary SQL.

**Additional issue:** `pg_terminate_backend()` requires superuser privileges or membership in `pg_signal_backend`. When run as a regular user, the query silently fails — connections are not terminated, and the subsequent `pg_restore` may encounter lock contention or fail.

**Remediation:**

Use parameterized queries or `psql` variable substitution with proper escaping:

```python
# Use psql variable binding (-v) which handles quoting
run_cmd([psql, ..., "-v", f"dbname={n}", "-tAc",
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
    "WHERE datname = :'dbname' AND pid <> pg_backend_pid();"], ...)
```

For the privilege issue, document that `fetch` requires superuser or `pg_signal_backend` role membership, or implement a fallback that uses `pg_terminate_backend` only when available.

---

### GAET-SEC-004 — Inconsistent Credential Protection (`PGPASSWORD` in Process Environment)

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **CVSS v3.1** | 4.7 (`AV:L/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N`) |
| **CWE** | CWE-522: Insufficiently Protected Credentials |
| **OWASP** | A02:2021 — Cryptographic Failures |

**Affected locations:**
- `gaet.py:979` (`cmd_init` — connection test)
- `gaet.py:1126, 1134, 1157, 1166` (`cmd_check_inner`)
- `gaet.py:1269, 1280, 1300, 1312, 1337` (`cmd_status`)
- `gaet.py:1430, 1460, 1511, 1523` (`get_status_inline`)
- `gaet.py:1605, 1631` (`cmd_push`)
- `gaet.py:1742, 1748` (`cmd_fetch`)

**Description:**

The function `pg_env()` (defined at `gaet.py:629`) correctly implements a `PGPASSFILE`-based approach to avoid exposing passwords via the `PGPASSWORD` environment variable, which is readable via `/proc/<pid>/environ` on Linux. This is documented in `SECURITY.md` and `README.md` as a security feature.

However, `pg_env()` is only called in `check_local_db()`. All other call sites use `env={"PGPASSWORD": w}` directly:

```python
out, _, rc = run_cmd(
    [psql, "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"],
    env={"PGPASSWORD": w},   # ← password in process environment
    timeout=5,
)
```

**Impact:** Database passwords are exposed in the process environment table (`/proc/<pid>/environ`) for the duration of each `psql`/`pg_dump`/`pg_restore` subprocess. Any local user (or compromised process) can read these.

**Remediation:**

Replace all `env={"PGPASSWORD": w}` call sites with the `pg_env()` + `cleanup_pg_env()` pattern:

```python
env_dict = pg_env(u, w)
try:
    out, _, rc = run_cmd([psql, ..., "-tAc", "SELECT 1;"], env=env_dict, timeout=5)
finally:
    cleanup_pg_env(env_dict)
```

---

### GAET-SEC-005 — File Permission Regression in `cmd_set`

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **CVSS v3.1** | 4.6 (`AV:L/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N`) |
| **CWE** | CWE-732: Incorrect Permission Assignment for Critical Resource |
| **OWASP** | A01:2021 — Broken Access Control |

**Affected location:**
- `gaet.py:2050`

**Description:**

`cmd_init` correctly creates `~/.gaet/.env` with `0o600` permissions using `os.open()`:

```python
fd = os.open(str(ENV_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
```

However, `cmd_set` writes the file using standard `open()`, which uses the process umask (typically `0o022`, resulting in `0o644` — world-readable):

```python
with open(str(ENV_FILE), "w", encoding="utf-8") as f:
    f.writelines(lines)
```

After `gaet set GAET_LOCAL_DB_PASS=secret`, the `.env` file may become readable by all local users.

**Remediation:**

```python
# After writing, ensure permissions are correct
with open(str(ENV_FILE), "w", encoding="utf-8") as f:
    f.writelines(lines)
os.chmod(str(ENV_FILE), 0o600)
```

Or use `os.open()` with explicit mode (same pattern as `cmd_init`).

---

### GAET-SEC-006 — Insufficient Password Masking in `cmd_get`

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **CVSS v3.1** | 2.7 (`AV:L/AC:L/PR:L/UI:N/S:U/C:L/I:N/A:N`) |
| **CWE** | CWE-200: Exposure of Sensitive Information to an Unauthorized Actor |
| **OWASP** | A02:2021 — Cryptographic Failures |

**Affected location:**
- `gaet.py:1966–1970`

**Description:**

The masking logic in `cmd_get` (and duplicated in `cmd_set:2058–2062`) only masks values when `len(value) > 20`:

```python
if len(value) > 20:
    display_value = value[:10] + "***" + value[-5:]
else:
    display_value = "***"
```

For values longer than 20 characters (typical for PostgreSQL connection URLs containing embedded passwords), the first 10 and last 5 characters are displayed in cleartext. Cloud provider connection strings (e.g., Supabase pooler URLs) often contain the password in the middle of the URL — but the username and host prefix are exposed.

**Remediation:**

For URL-type values, parse and mask the password component specifically (reuse `mask_url_password()`). For password-type values, always display `"****"` regardless of length.

---

### GAET-BUG-001 — Installer Writes Incompatible Environment Variable Names

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Category** | Reliability / Functional Defect |

**Affected location:**
- `scripts/installer.py:setup_config()` (writes `GAET_DB_HOST`, `GAET_DB_PORT`, `GAET_DB_NAME`, `GAET_DB_USER`, `GAET_DB_PASSWORD`)
- `gaet.py:get_local_db()` (reads `GAET_LOCAL_DB_HOST`, `GAET_LOCAL_URL`, `GAET_LOCAL_DB_PASS`)

**Description:**

The interactive installer (`gaet install` → `scripts/installer.py:setup_config()`) writes database configuration using a different naming convention than what the CLI reads:

| Installer writes | CLI reads |
|------------------|----------|
| `GAET_DB_HOST` | `GAET_LOCAL_DB_HOST` |
| `GAET_DB_PORT` | `GAET_LOCAL_DB_PORT` |
| `GAET_DB_NAME` | `GAET_LOCAL_DB_NAME` |
| `GAET_DB_USER` | `GAET_LOCAL_DB_USER` |
| `GAET_DB_PASSWORD` | `GAET_LOCAL_DB_PASS` |

The only shared variable is `GAET_REMOTE_URL`. All local database configuration written by the installer is invisible to `gaet push`, `gaet status`, `gaet check`, and `gaet fetch`.

**Impact:** After `gaet install`, the tool appears configured but uses fallback defaults (`postgres@127.0.0.1:5432/postgres`) for local DB. Backups will fail or target the wrong database.

**Remediation:**

Align `installer.py` with the CLI's variable names, or better: have `installer.py` delegate to `gaet init` for configuration rather than maintaining a separate wizard.

---

### GAET-BUG-002 — Windows Installer Targets Wrong Git Branch

| Field | Value |
|-------|-------|
| **Severity** | High |
| **Category** | Reliability / Distribution Defect |

**Affected location:**
- `install.ps1:8`

**Description:**

```powershell
$GITHUB_RAW = "https://raw.githubusercontent.com/ghanirahmans/gaet/main"
```

The repository uses `master` as its default branch (confirmed via `git branch` and all `install.sh` references). The PowerShell installer fetches from `main`, which does not exist. All download requests will return HTTP 404.

**Remediation:**

```powershell
$GITHUB_RAW = "https://raw.githubusercontent.com/ghanirahmans/gaet/master"
```

---

### GAET-BUG-003 — `--auto` Without Value Fails Instead of Using Default Interval

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Logic Error |

**Affected locations:**
- `gaet.py:2705–2710` (main routing)
- `gaet.py:1836` (`cmd_auto_on`)
- `gaet.py:1839` (validation)

**Description:**

The argparse configuration defines `--auto` as:

```python
push_parser.add_argument("--auto", nargs="?", const=0, type=int, ...)
```

When `--auto` is given without a value, `args.auto` is `0`. The routing logic:

```python
if args.auto is not None:
    if args.auto == 0:
        pass  # ← intended to use default, but does nothing
    cmd_auto_on(args)
```

`cmd_auto_on` then reads `args.auto` (still `0`) and hits:

```python
if interval is None or interval <= 0:
    die("Interval must be a positive number")
```

The intended behavior (per help text: "default 6") is never achieved. `--auto` without a value always exits with an error.

**Remediation:**

```python
if args.auto is not None:
    if args.auto == 0:
        args.auto = get_env_int(load_env(), "GAET_AUTO_INTERVAL", DEF_AUTO_INTERVAL)
    cmd_auto_on(args)
    return
```

---

### GAET-BUG-004 — `pg_restore` Exit Code Conflates Warnings with Errors

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Reliability |
| **CWE** | CWE-754: Improper Check for Unusual or Exceptional Conditions |

**Affected locations:**
- `gaet.py:1634–1637` (`cmd_push`)
- `gaet.py:1751–1754` (`cmd_fetch`)
- `gaet.py:1821–1825` (`cmd_push_cron`)

**Description:**

`pg_restore` returns a non-zero exit code for both benign warnings (e.g., "relation does not exist, skipping" when using `--clean --if-exists`) and actual errors (e.g., connection failure, permission denied). The code treats any non-zero code as success-with-warning:

```python
if rc3 == 0:
    echo("...selesai!")
else:
    echo("...selesai (dengan peringatan)")
```

This means a backup that partially failed (e.g., some tables not restored) is reported as successful, and the cron log records it as "bermasalah" (problematic) without distinguishing severity.

**Impact:** Users may believe backups are complete when they are not. Failed table restores go unnoticed.

**Remediation:**

Parse `pg_restore` stderr output to distinguish:
- `ERROR:` lines indicate actual failures
- `WARNING:` / `NOTICE:` lines indicate benign warnings

At minimum, log the full stderr to the log file for post-hoc analysis and set a higher exit threshold (e.g., `rc > 1` indicates failure).

---

### GAET-BUG-005 — Version Mismatch Across Components

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Configuration Management |

**Affected locations:**
- `gaet.py:47` — `VERSION = "2.0.0"`
- `dashboard/package.json:3` — `"version": "1.0.0"`
- `dashboard/app/page.tsx` (footer) — `"gaet v1.0.0"`
- `SECURITY.md` — `"1.0.x | Active"`

**Description:**

Four components report different version numbers. The CLI declares 2.0.0, the dashboard declares 1.0.0, the dashboard footer hardcodes v1.0.0, and `SECURITY.md` states only 1.0.x is supported. This creates confusion for users reporting issues and for security researchers verifying supported versions.

**Remediation:**

Establish a single source of truth for the version (e.g., `VERSION` in `gaet.py`). Have the dashboard read it at build time via an API route or environment variable. Update `SECURITY.md` to reflect 2.0.x as the supported version.

---

### GAET-BUG-006 — Dead Code: Unreachable `die()` Call

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Code Quality |

**Affected location:**
- `gaet.py:2508–2520`

**Description:**

```python
if not dashboard_dir:
    die("Dashboard tidak ditemukan...")  # exits here
...
if not dashboard_dir:                    # unreachable
    die("Dashboard tidak ditemukan")
```

The second check can never execute because `die()` calls `sys.exit()`.

---

### GAET-BUG-007 — Blocking Port Scan in `detect_local_pg`

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Performance / UX |

**Affected location:**
- `gaet.py:260–303`

**Description:**

`detect_local_pg()` sequentially attempts connections to 5 ports (`5432`–`5436`) × 2 users (`postgres`, `root`) = 10 connection attempts, each with a 3-second timeout. If no PostgreSQL is running, `gaet init` blocks for up to 30 seconds.

**Remediation:**

Use concurrent connection attempts (e.g., `concurrent.futures.ThreadPoolExecutor`) or reduce the scan set. Alternatively, check `/proc/net/tcp` or `ss -tlnp` first to identify which ports are actually listening.

---

### GAET-QUAL-001 — Three Divergent `.env` Parser Implementations

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **CWE** | CWE-1042: Operator Precedence / Inconsistent Implementations |

**Affected locations:**
- `gaet.py:174` (`load_env`) — handles `export KEY="val"` and bare `KEY=val`, strips quotes
- `scripts/status.py:38` (`load_env`) — different regex, different quote handling
- `scripts/installer.py:_read_existing_config:660` — simple `line.split("=", 1)`, no quote stripping, no `export` handling

**Description:**

Three independent `.env` parsers with subtly different behavior. The installer's `_read_existing_config` cannot handle `export` prefixes or quoted values, while `gaet.py`'s `load_env` handles both. If `cmd_set` writes `export KEY=value` (which it does at line 2037), the installer's parser will include `export ` in the key name.

**Remediation:**

Consolidate into a single shared parser. Either:
1. Move `load_env()` to a shared utility module imported by all scripts, or
2. Have `installer.py` call `gaet.py`'s `load_env()` directly.

---

### GAET-QUAL-002 — Two Divergent URL Parser Implementations

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Code Consistency |

**Affected locations:**
- `gaet.py:215` (`parse_remote_url`) → returns `Dict[str, str]`, handles URLs without passwords
- `scripts/status.py:165` (`parse_url`) → returns `Tuple[str, ...]`, does NOT handle URLs without passwords

**Description:**

`status.py`'s `parse_url` requires a password in the URL (regex `([^:]+):([^@]+)` — the `:` and password are mandatory). A valid local URL like `postgresql://postgres@127.0.0.1:5432/mydb` (which `gaet.py` handles correctly via `parse_remote_url`) will fail to parse in `status.py`, causing `get_status()` to skip remote/local DB operations silently.

**Remediation:**

Have `scripts/status.py` import `parse_remote_url` from `gaet.py`, or consolidate into a single shared function.

---

### GAET-QUAL-003 — Duplicate Scheduler Implementations

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Code Duplication |

**Affected locations:**
- `gaet.py:715–798` (inline fallback scheduler)
- `scripts/scheduler.py` (full implementation with docstrings, validation)

**Description:**

`gaet.py` contains an inline fallback scheduler implementation used when `scripts.scheduler` cannot be imported. The inline version lacks the prefix validation (`re.match(r'^[a-zA-Z0-9_-]+$', prefix)`) present in the module version. If `GAET_SERVICE_PREFIX` contains shell metacharacters, the inline version will inject them into systemd unit files or launchd plists without escaping.

**Remediation:**

If the inline fallback must remain, add the same prefix validation. Ideally, bundle `scripts/scheduler.py` with the CLI to eliminate the fallback need.

---

### GAET-QUAL-004 — Duplicate Dashboard Directory Discovery Logic

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Code Duplication |

**Affected locations:**
- `gaet.py:2491–2506` (`cmd_serve`)
- `scripts/service_manager.py:413–425` (`_find_dashboard_dir`)

**Description:**

Both functions search for the dashboard directory using different candidate lists and ordering. `cmd_serve` checks 4 locations in one order; `_find_dashboard_dir` checks 4 locations in a different order. Under certain conditions, `gaet serve` and `service_manager.start()` may resolve to different dashboard directories.

---

### GAET-QUAL-005 — No `pyproject.toml` / `setup.py`

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Packaging / Build System |

**Description:**

`README.md:134` instructs users to run `pip install -e .`, and `CONTRIBUTING.md` repeats this instruction. However, no `pyproject.toml`, `setup.py`, or `setup.cfg` exists in the repository. `pip install -e .` will fail with `ERROR: Directory '.' is not a package`.

**Remediation:**

Add a minimal `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=64"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "gaet"
version = "2.0.0"
description = "Zero-Config PostgreSQL Backup & Sync CLI"
requires-python = ">=3.8"
license = {text = "MIT"}

[project.scripts]
gaet = "gaet:main"
```

---

### GAET-QUAL-006 — Blocking `execFileSync` in Dashboard API Routes

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **Category** | Performance / Scalability |

**Affected locations:**
- `dashboard/app/api/status/route.ts:14`
- `dashboard/app/api/push/route.ts:20`
- `dashboard/app/api/fetch/route.ts:14`
- `dashboard/app/api/stop/route.ts:14`

**Description:**

All API routes use `execFileSync(gaet, args, { timeout: 180000 })`, which blocks the Node.js event loop for the duration of the command. A `gaet push` that takes 30+ seconds will freeze the entire dashboard — including status polling, other API calls, and page rendering.

**Remediation:**

Use `child_process.spawn` (async) or `execFile` (callback-based) instead of `execFileSync`. Return a job ID and poll for completion, or use Server-Sent Events (SSE) for progress streaming.

---

### GAET-QUAL-007 — Monolithic `gaet.py` at 2,745 Lines

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Maintainability |

**Description:**

`gaet.py` contains the entire CLI — argument parsing, all 13 commands, UI helpers, config loading, subprocess execution, scheduler fallback, service management, and update logic — in a single 2,745-line file. This is likely by design (zero-config, single-file philosophy) but impacts maintainability and testability.

**Remediation:** Low priority. If the project grows, consider splitting into modules: `cli.py`, `config.py`, `backup.py`, `ui.py`.

---

### GAET-QUAL-008 — Minimal Test Coverage

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Testing / QA |

**Description:**

`tests/test_gaet.py` (123 lines) tests only 4 utility functions: `parse_remote_url`, `mask_url_password`, `get_env_str`, `get_env_int`. No tests exist for:
- Core pipelines: `cmd_push`, `cmd_fetch`, `cmd_push_cron`
- Config: `cmd_init`, `cmd_set`, `cmd_get`
- Status: `cmd_status`, `get_status_inline`
- Scheduler: enable/disable lifecycle
- Locking: `acquire_lock`/`release_lock`
- Retention policy

`CONTRIBUTING.md` references `test_backup.py`, `test_restore.py`, and `test_security.py` — these files do not exist in the repository.

**Remediation:**

Add integration tests for the push/fetch pipeline (using a test PostgreSQL instance or mocks), unit tests for `cmd_set`/`cmd_get`, and tests for the scheduler lifecycle.

---

### GAET-SCM-001 — No Integrity Verification on Downloaded Files

| Field | Value |
|-------|-------|
| **Severity** | Medium |
| **CVSS v3.1** | 5.3 (`AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N`) |
| **CWE** | CWE-494: Download of Code Without Integrity Verification |
| **OWASP** | A08:2021 — Software and Data Integrity Failures |

**Affected locations:**
- `install.sh:43–49` (GitHub API download, no checksum)
- `install.ps1:42–44` (raw download, no checksum)
- `gaet.py:2259–2265` (`_gh_download`, no checksum)
- `gaet.py:2268–2331` (`_update_download`, no checksum)

**Description:**

All download paths fetch code from GitHub (API or raw) without verifying SHA-256 checksums, GPG signatures, or commit SHAs. A compromised CDN, MITM attack, or GitHub account breach would allow an attacker to inject malicious code into the installation.

**Remediation:**

1. Pin downloads to a specific commit SHA rather than `master` branch ref
2. Verify a SHA-256 checksum file after download
3. For `install.sh`, consider providing a detached `.sha256` signature file

---

### GAET-SCM-002 — `curl | bash` Install Pattern

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **CVSS v3.1** | 2.4 (`AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N`) |
| **CWE** | CWE-829: Inclusion of Functionality from Untrusted Control Sphere |
| **OWASP** | A08:2021 — Software and Data Integrity Failures |

**Affected location:**
- `README.md:36` (`curl -sSL https://... | bash`)

**Description:**

The recommended install method pipes a remote script directly into `bash`, executing arbitrary code without inspection. While common for developer tools, this pattern has no recovery path if the URL is compromised.

**Remediation:** Document the risk. Recommend `curl -sSL <url> -o install.sh && inspect && bash install.sh` as an alternative.

---

### GAET-DOC-001 — No `LICENSE` File Despite MIT Badge

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Legal / Compliance |

**Description:**

`README.md:22` displays an MIT license badge, but no `LICENSE` file exists in the repository. Without the actual license text, the project is technically "all rights reserved" by default, which may deter contributors and users.

**Remediation:** Add a `LICENSE` file containing the full MIT license text.

---

### GAET-DOC-002 — CONTRIBUTING.md References Non-Existent Test Files

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Documentation Accuracy |

**Description:**

`CONTRIBUTING.md` references `test_backup.py`, `test_restore.py`, and `test_security.py` in the project structure section. These files do not exist. The only test file is `tests/test_gaet.py`.

---

### GAET-DOC-003 — `DASHBOARD_ORIGIN` Env Var Naming Inconsistency

| Field | Value |
|-------|-------|
| **Severity** | Low |
| **Category** | Configuration Consistency |

**Affected locations:**
- `dashboard/next.config.ts:3` — reads `process.env.DASHBOARD_ORIGIN`
- `dashboard/app/api/*/route.ts` — reads `process.env.DASHBOARD_ORIGIN`
- `gaet.py` and `.env.example` — use `GAET_DASHBOARD_*` prefix for all other dashboard vars

**Description:**

All gaet environment variables use the `GAET_` prefix, except `DASHBOARD_ORIGIN`, which omits it. Users following the `GAET_` convention will not find this variable, and it will not be loaded from `~/.gaet/.env` (which is not automatically sourced into the dashboard process environment).

---

## 5. Positive Observations

The following security controls and design patterns were found to be correctly implemented:

| Control | Location | Assessment |
|---------|----------|------------|
| **Atomic file locking** | `gaet.py:156–169` | Directory-creation based lock, cross-platform atomic, proper `finally` cleanup |
| **Backup integrity verification** | `gaet.py:1612–1618`, `gaet.py:1805–1812` | `pg_restore --list` validates dump before upload; corrupt dumps are deleted |
| **Retention policy** | `gaet.py:1640–1647` | Correct mtime-based deletion, configurable retention window |
| **`.env` creation permissions** | `gaet.py:1030` | `os.open()` with `0o600` mode in `cmd_init` |
| **PGPASSFILE mechanism** | `gaet.py:629–656` | Correct implementation in `pg_env()`/`cleanup_pg_env()` — temp file, `0o600`, auto-delete |
| **HTTP security headers** | `dashboard/next.config.ts:6–13` | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` |
| **Dry-run mode** | `gaet.py:1548–1573`, `gaet.py:1662–1677` | Both push and fetch support simulation without data modification |
| **Cross-platform scheduler** | `scripts/scheduler.py` | Clean abstraction across systemd, launchd, and Task Scheduler with prefix validation |
| **Error boundary** | `dashboard/app/error.tsx` | Next.js error boundary with reset functionality |
| **Anti-flash theme script** | `dashboard/app/layout.tsx:21–28` | Inline script in `<head>` prevents FOUC for dark/light theme |
| **`.gitignore` hygiene** | `.gitignore` | `.env`, audit files, `node_modules`, `.next` properly ignored |
| **Confirmation prompts** | `gaet.py:1706–1709`, `gaet.py:2113–2116` | `fetch` and `uninstall --purge` require explicit `yes` confirmation |

---

## 6. Remediation Roadmap

### Phase 1 — Critical & High (Immediate, ≤1 week)

| Priority | Finding | Effort | Action |
|----------|---------|--------|--------|
| P0 | GAET-SEC-002 | Medium | Change default bind to `127.0.0.1`; fix CORS to reject missing Origin; add token auth |
| P0 | GAET-BUG-001 | Low | Align installer env var names with CLI (`GAET_LOCAL_*`) |
| P0 | GAET-BUG-002 | Trivial | Change `install.ps1` branch from `main` to `master` |
| P1 | GAET-SEC-001 | Low | Add `_validate_table_name()` calls in `cmd_status` and `get_status_inline` |
| P1 | GAET-SEC-003 | Low | Use psql variable binding for database name in `pg_terminate_backend` query |
| P1 | GAET-SCM-001 | Medium | Pin download URLs to commit SHA; add SHA-256 verification |

### Phase 2 — Medium (Short-term, ≤1 month)

| Priority | Finding | Effort | Action |
|----------|---------|--------|--------|
| P2 | GAET-SEC-004 | Medium | Replace all `PGPASSWORD` call sites with `pg_env()`/`cleanup_pg_env()` |
| P2 | GAET-SEC-005 | Trivial | Add `os.chmod(ENV_FILE, 0o600)` after write in `cmd_set` |
| P2 | GAET-BUG-003 | Low | Fix `--auto=0` default logic in `main()` |
| P2 | GAET-BUG-004 | Medium | Parse `pg_restore` stderr to distinguish warnings from errors |
| P2 | GAET-BUG-005 | Low | Unify version string across all components |
| P2 | GAET-QUAL-001 | Medium | Consolidate three `.env` parsers into one shared function |
| P2 | GAET-QUAL-002 | Low | Have `status.py` import `parse_remote_url` from `gaet.py` |
| P2 | GAET-QUAL-005 | Low | Add `pyproject.toml` |
| P2 | GAET-QUAL-006 | Medium | Replace `execFileSync` with async `spawn` in API routes |

### Phase 3 — Low (Backlog)

| Priority | Finding | Effort | Action |
|----------|---------|--------|--------|
| P3 | GAET-SEC-006 | Low | Improve password masking in `cmd_get` |
| P3 | GAET-BUG-006 | Trivial | Remove dead `die()` call |
| P3 | GAET-BUG-007 | Low | Parallelize port scan in `detect_local_pg` |
| P3 | GAET-QUAL-003 | Low | Add prefix validation to inline scheduler fallback |
| P3 | GAET-QUAL-004 | Low | Consolidate dashboard dir discovery |
| P3 | GAET-QUAL-007 | — | Split `gaet.py` into modules (optional, by-design trade-off) |
| P3 | GAET-QUAL-008 | Medium | Add integration tests for push/fetch pipeline |
| P3 | GAET-SCM-002 | Trivial | Document `curl | bash` risk in README |
| P3 | GAET-DOC-001 | Trivial | Add `LICENSE` file |
| P3 | GAET-DOC-002 | Trivial | Fix CONTRIBUTING.md test file references |
| P3 | GAET-DOC-003 | Trivial | Rename `DASHBOARD_ORIGIN` to `GAET_DASHBOARD_ORIGIN` |

---

## 7. References

| Standard | URL |
|----------|-----|
| OWASP Top 10 (2021) | https://owasp.org/Top10/ |
| CWE (Common Weakness Enumeration) v4.14 | https://cwe.mitre.org/ |
| CVSS v3.1 Calculator | https://www.first.org/cvss/calculator/3.1 |
| PostgreSQL Security Documentation | https://www.postgresql.org/docs/current/security.html |
| OWASP Cheat Sheet — SQL Injection Prevention | https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html |
| OWASP Cheat Sheet — CORS | https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html |

---

*End of report.*
