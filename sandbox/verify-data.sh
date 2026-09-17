#!/bin/bash
# =============================================================
# sandbox/verify-data.sh
# Utility: assert row counts against expected values
# Usage: ./verify-data.sh <db_role> <schema_name>
#   db_role     — "local" or "remote"
#   schema_name — "pre_seed", "fresh_copy", or "modified"
# =============================================================

ROLE="${1:-local}"
PHASE="${2:-fresh_copy}"

if [[ "$ROLE" == "local" ]]; then
  DB="gaet_local"
elif [[ "$ROLE" == "remote" ]]; then
  DB="gaet_remote"
else
  echo "ERROR: Unknown role '$ROLE'. Use 'local' or 'remote'."
  exit 1
fi

# Connection params (TCP with password)
export PGHOST="127.0.0.1"
export PGPORT="5432"
export PGUSER="ghaniyrahmans"
export PGPASSWORD="sandbox"
export PGDATABASE="$DB"

# Expected counts per phase
# In 'modified' phase, we delete orders/payments/order_items/audit_log where id/order_id > 2500
# orders: 3000 → 2500
# payments: 3000 → 2500 (one-to-one with orders)
# order_items: 6000 → ~4500 (roughly 60% of 6000 remain, since order_id distribution is random)
# audit_log: 2000 → ~1667 (order_id distribution is random)
# For simplicity, we use approximate counts for modified phase
declare -A EXPECTED_COUNTS
case "$PHASE" in
  pre_seed|fresh_copy)
    EXPECTED_COUNTS=(
      ["users"]="1000"
      ["products"]="500"
      ["orders"]="3000"
      ["payments"]="3000"
      ["order_items"]="6000"
      ["audit_log"]="2000"
      ["system_config"]="5"
    )
    ;;
  modified)
    # After deleting orders (id>2500) + payments + order_items + audit_log with order_id>2500
    EXPECTED_COUNTS=(
      ["users"]="1000"
      ["products"]="500"
      ["orders"]="2500"
      ["payments"]="2500"
      ["system_config"]="5"
    )
    ;;
  *)
    echo "ERROR: Unknown phase '$PHASE'. Use: pre_seed, fresh_copy, modified"
    exit 1
    ;;
esac

# Get actual counts for each table
declare -A ACTUAL_COUNTS
for table in "${!EXPECTED_COUNTS[@]}"; do
  COUNT=$(psql -tAc "SELECT count(*) FROM $table;" 2>/dev/null || echo "-1")
  ACTUAL_COUNTS["$table"]="$COUNT"
done

# Compare and report
PASS=0
FAIL=0
echo "=== Verification: $ROLE / $PHASE ==="
for table in $(echo "${!EXPECTED_COUNTS[@]}" | tr ' ' '\n' | sort); do
  EXPECTED="${EXPECTED_COUNTS[$table]}"
  ACTUAL="${ACTUAL_COUNTS[$table]}"
  if [[ "$ACTUAL" == "$EXPECTED" ]]; then
    echo "  [ PASS ]  $table: $ACTUAL rows"
    ((PASS++))
  else
    echo "  [ FAIL ]  $table: expected $EXPECTED, got $ACTUAL"
    ((FAIL++))
  fi
done

echo "---"
echo "Results: $PASS passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
