# gaet Sandbox — E2E Testing Environment

A local testing harness untuk gaet CLI yang mensimulasikan sistem transaksional industry-like (e-commerce/order/payment system).

## Prerequisites

### PostgreSQL Instances

| Role    | Host            | Port | User      | DB          | Auth   |
|---------|-----------------|------|-----------|-------------|--------|
| Local   | 127.0.0.1       | 5432 | ghaniyrahmans | postgres | peer   |
| Remote  | 127.0.0.1       | 5433 | postgres  | cloud_test  | trust  |

**Verify connectivity:**
```bash
psql -h 127.0.0.1 -p 5432 -U ghaniyrahmans -d postgres -c "SELECT 1;"
psql -h 127.0.0.1 -p 5433 -U postgres  -d cloud_test -c "SELECT 1;"
```

### gaet Binary

Binary harus terbuild dan accessible. Default path: `./gaet` di project root.

```bash
cd /path/to/gaet
go build -ldflags="-s -w" -o gaet ./cmd/gaet
```

---

## Quick Start

### Full E2E Test
```bash
cd /path/to/gaet/sandbox
./run-all-tests.sh
```

### Individual Phase
```bash
# 1. Seed local DB
psql -h 127.0.0.1 -p 5432 -U ghaniyrahmans -d postgres -f seed-data.sql

# 2. Push to remote
export GAET_DIR=/tmp/gaet-test
export GAET_LOCAL_URL=postgresql://ghaniyrahmans@127.0.0.1:5432/postgres
export GAET_REMOTE_URL=postgresql://postgres@127.0.0.1:5433/cloud_test
./gaet push

# 3. Fetch (overwrite local)
./gaet fetch --yes

# 4. Verify
./verify-data.sh local fresh_copy
./verify-data.sh remote fresh_copy

# 5. Cleanup
psql -h 127.0.0.1 -p 5432 -U ghaniyrahmans -d postgres -f cleanup-schema.sql
psql -h 127.0.0.1 -p 5433 -U postgres -d cloud_test -f cleanup-schema.sql
```

---

## Test Scenarios Covered

| Phase | Scenario              | Command                        |
|-------|----------------------|--------------------------------|
| 0     | Pre-flight check     | `gaet check --json`            |
| 1     | Seed data            | `psql -f seed-data.sql`        |
| 3     | Push (local→remote)  | `gaet push`                    |
| 4     | Fetch (remote→local) | `gaet fetch`                   |
| 5     | Local restore        | `gaet restore <snapshot>`      |
| 6     | Conflict scenario    | push modified + full sync      |
| 7     | Retention cleanup    | `gaet push` (old file removed) |
| 8     | Log inspection       | `gaet log`                     |

---

## Schema Overview

```
system_config(5 rows)
users(1,000 rows)
products(500 rows)
orders(3,000 rows)
payments(3,000 rows)
order_items(6,000 rows)
audit_log(2,000 rows)
```

Total ~12,500 baris — cukup untuk testing sync, retention, dan restore.

---

## Cleanup

Script `run-all-tests.sh` otomatis cleanup pada exit via trap handler.

Manual cleanup:
```bash
psql -h 127.0.0.1 -p 5432 -U ghaniyrahmans -d postgres -f cleanup-schema.sql
psql -h 127.0.0.1 -p 5433 -U postgres -d cloud_test -f cleanup-schema.sql
```
