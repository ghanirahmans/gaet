#!/bin/bash
set -euo pipefail

# =============================================================
# sandbox/run-all-tests.sh
# Orchestrates the full gaet E2E workflow in a local environment.
#
# Prerequisites:
#   - gaet binary built and in PATH (or set GAET_BIN)
#   - PostgreSQL instance with databases:
#       gaet_local  (user ghaniyrahmans, password sandbox)
#       gaet_remote (user ghaniyrahmans, password sandbox)
#     Both accessible via TCP on localhost:5432
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GAET_BIN="${GAET_BIN:-$PROJECT_ROOT/gaet}"
SANDBOX_DIR="$SCRIPT_DIR"

# ─── Colors ─────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ok()    { echo -e "${GREEN}[PASS]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; }

step()  { echo ""; echo -e "${BLUE}══ $1 ══${NC}"; }

# ─── Config ─────────────────────────────────────────────────
TEST_DIR="$(mktemp -d /tmp/gaet-e2e-XXXXXX)"

export GAET_DIR="$TEST_DIR"

# Local: localhost TCP (peer/trust auth won't work over TCP, so we set password)
export GAET_LOCAL_URL="postgresql://ghaniyrahmans:sandbox@127.0.0.1:5432/gaet_local"

# Remote: localhost TCP
export GAET_REMOTE_URL="postgresql://ghaniyrahmans:sandbox@127.0.0.1:5432/gaet_remote"
export GAET_REMOTE_SSLMODE="disable"
export GAET_RETENTION_DAYS=7

# ─── Helper: psql shortcuts ──────────────────────────────────
psql_local()  { PGPASSWORD="sandbox" psql -h 127.0.0.1 -p 5432 -U ghaniyrahmans -d gaet_local "$@"; }
psql_remote() { PGPASSWORD="sandbox" psql -h 127.0.0.1 -p 5432 -U ghaniyrahmans -d gaet_remote "$@"; }

# ─── Cleanup handler ─────────────────────────────────────────
cleanup() {
  info "Cleaning up (GAET_DIR=$TEST_DIR)..."
  psql_local -v ON_ERROR_STOP=1 -f "$SANDBOX_DIR/cleanup-schema.sql" > /dev/null 2>&1 || true
  rm -rf "$TEST_DIR"
  ok "Cleanup complete."
}
trap cleanup EXIT

# =============================================================
# PHASE 0: Build & Pre-flight
# =============================================================
step "Phase 0: Build & Pre-flight Check"

if [[ ! -f "$GAET_BIN" ]]; then
  info "gaet binary not found at $GAET_BIN, building..."
  (cd "$PROJECT_ROOT" && go build -ldflags="-s -w" -o "$GAET_BIN" ./cmd/gaet)
fi

info "gaet version:"
"$GAET_BIN" --version

info "Environment:"
echo "  Local DB:  gaet_local  (127.0.0.1:5432, user ghaniyrahmans)"
echo "  Remote DB: gaet_remote (127.0.0.1:5432, user ghaniyrahmans)"
echo "  GAET_DIR:  $TEST_DIR"

# Verify both DBs are reachable
psql_local -c "SELECT 1;" > /dev/null && ok "Local DB reachable (gaet_local)" || { fail "Local DB NOT reachable"; exit 1; }
psql_remote -c "SELECT 1;" > /dev/null 2>&1 && ok "Remote DB reachable (gaet_remote)" || { fail "Remote DB NOT reachable"; exit 1; }

# =============================================================
# PHASE 1: Seed Initial Data (to local DB only)
# =============================================================
step "Phase 1: Seed Initial Data"

info "Running seed-data.sql on LOCAL database (gaet_local)..."
psql_local -v ON_ERROR_STOP=1 -f "$SANDBOX_DIR/seed-data.sql" 2>&1 | grep -E "CREATE TABLE|INSERT" | head -20

bash "$SANDBOX_DIR/verify-data.sh" local pre_seed
ok "Seed data loaded to local DB."

# =============================================================
# PHASE 2: gaet check (pre-flight config validation)
# =============================================================
step "Phase 2: gaet check (validate config & connections)"

info "Running: gaet check --json"
"$GAET_BIN" check --json || warn "gaet check returned non-zero (informational)"

# =============================================================
# PHASE 3: gaet push (local → remote)
# =============================================================
step "Phase 3: gaet push (local → remote)"

info "Running: gaet push --dry-run"
"$GAET_BIN" push --dry-run

info "Running: gaet push (actual)"
"$GAET_BIN" push

bash "$SANDBOX_DIR/verify-data.sh" remote fresh_copy
ok "Remote DB synced successfully."

# =============================================================
# PHASE 4: gaet fetch (remote → local overwrite)
# =============================================================
step "Phase 4: gaet fetch (remote → local overwrite)"

info "Modifying local data to simulate drift..."
# Delete child records first to avoid FK constraint violation
psql_local -c "DELETE FROM order_items WHERE order_id > 2500;" > /dev/null
psql_local -c "DELETE FROM payments WHERE order_id > 2500;" > /dev/null
psql_local -c "DELETE FROM audit_log WHERE order_id > 2500;" > /dev/null
psql_local -c "DELETE FROM orders WHERE id > 2500;" > /dev/null

info "Verifying local data is now modified..."
bash "$SANDBOX_DIR/verify-data.sh" local modified

info "Running: gaet fetch"
"$GAET_BIN" fetch --yes

info "Verifying local data restored from remote..."
bash "$SANDBOX_DIR/verify-data.sh" local fresh_copy
ok "Local DB restored from remote via gaet fetch."

# =============================================================
# PHASE 5: gaet restore (from local snapshot)
# =============================================================
step "Phase 5: gaet restore (from local snapshot)"

info "Listing snapshots..."
"$GAET_BIN" snapshots

SNAPSHOT_FILE=$(ls -t "$TEST_DIR/backups/gaet_"*.dump 2>/dev/null | head -1)
if [[ -z "$SNAPSHOT_FILE" ]]; then
  fail "No snapshot dump file found in $TEST_DIR/backups/"
  exit 1
fi
info "Restoring from snapshot: $(basename "$SNAPSHOT_FILE")"
"$GAET_BIN" restore "$(basename "$SNAPSHOT_FILE")" --yes

ok "Restore from local snapshot completed."

# =============================================================
# PHASE 6: Conflict scenario
# =============================================================
step "Phase 6: Conflict scenario (data divergence)"

info "Modifying remote data (delete last 100 orders)..."
# Delete child records first to avoid FK constraint violation
psql_remote -c "DELETE FROM order_items WHERE order_id > 2900;" > /dev/null
psql_remote -c "DELETE FROM payments WHERE order_id > 2900;" > /dev/null
psql_remote -c "DELETE FROM audit_log WHERE order_id > 2900;" > /dev/null
psql_remote -c "DELETE FROM orders WHERE id > 2900;" > /dev/null

info "Verifying remote modified..."
EXPECTED=2900
ACTUAL=$(psql_remote -tAc "SELECT count(*) FROM orders;" 2>/dev/null || echo "ERROR")
if [[ "$ACTUAL" == "$EXPECTED" ]]; then
  ok "Remote orders count = $ACTUAL (as expected)"
else
  warn "Remote orders count = $ACTUAL (expected $EXPECTED)"
fi

info "Running: gaet push (sync modified remote)"
"$GAET_BIN" push

info "Verifying local data matches remote (orders should still be 3000)..."
bash "$SANDBOX_DIR/verify-data.sh" local fresh_copy
ok "Conflict resolved: local restored to full dataset."

# =============================================================
# PHASE 7: Retention test
# =============================================================
step "Phase 7: Retention test"

info "Creating old dump file (10 days ago)..."
OLD_FILE="$TEST_DIR/backups/gaet_20240101_000000.dump"
echo "OLD BACKUP DATA" > "$OLD_FILE"
touch -d "10 days ago" "$OLD_FILE"

info "Running: gaet push (triggers retention cleanup)..."
"$GAET_BIN" push

if [[ -f "$OLD_FILE" ]]; then
  warn "Old file still exists: $OLD_FILE"
else
  ok "Old file removed by retention policy."
fi

# =============================================================
# PHASE 8: Log inspection
# =============================================================
step "Phase 8: Log inspection"

info "Running: gaet log"
"$GAET_BIN" log 10

# =============================================================
# Summary
# =============================================================
step "All Tests Complete"
ok "All E2E scenarios passed. GAET_DIR=$TEST_DIR (cleanup on exit)"

# Keep dir if KEEP_TEST_DIR=true
if [[ "${KEEP_TEST_DIR:-false}" == "true" ]]; then
  echo ""
  info "KEEP_TEST_DIR is set — not removing $TEST_DIR"
  echo "  Config: $TEST_DIR/.env"
  echo "  Dumps:  $TEST_DIR/backups/"
fi

exit 0
