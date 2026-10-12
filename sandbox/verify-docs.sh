#!/usr/bin/env bash
# verify-docs.sh — Docs/Code drift detector for the gaet repository.
#
# Verifies that documentation stays aligned with the actual Go source code.
# Run locally:  bash sandbox/verify-docs.sh
# Run in CI:    see .github/workflows/ci.yml (docs-consistency job)
#
# Checks:
#   1. Every `gaet <command>` referenced in README.md exists as a case in cmd/gaet/main.go
#   2. Every GAET_* / env key in .env.example is a known config key (pkg/config/config.go) or referenced in pkg/
#   3. The Go version in go.mod is consistent with the version cited in AGENTS.md
#
# Exit non-zero if any drift is found. Output is plain-text for CI friendliness.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0

# ── helpers ───────────────────────────────────────────────────────────────────
check() { # <label> <ok_bool> <detail>
  local label="$1" ok="$2" detail="${3:-}"
  if [[ "$ok" == "pass" ]]; then
    printf "  [ OK ]  %s\n" "$label"
    PASS=$((PASS+1))
  else
    printf "  [FAIL]  %s\n" "$label"
    [[ -n "$detail" ]] && printf "         %s\n" "$detail"
    FAIL=$((FAIL+1))
  fi
}

echo "gaet — Docs / Code consistency check"
echo "======================================"
echo ""

# ── Check 1: README commands vs main.go dispatch ──────────────────────────────
echo ":: Check 1 — README command references vs cmd/gaet/main.go dispatch"
# Extract real subcommand cases from main.go: lines like `	case "name":`
mapfile -t MAIN_CASES < <(
  grep -E '^[[:space:]]+case "[a-z][a-z0-9_-]+"' cmd/gaet/main.go \
    | sed -E 's/^[[:space:]]+case "([a-z][a-z0-9_-]+)".*/\1/' \
    | sort -u
)
MAIN_CASES_STR="$(printf '|%s|' "${MAIN_CASES[@]}")"

# Extract `gaet <word>` command tokens from README usage / command table
mapfile -t README_CMDS < <(
  grep -oE 'gaet [a-z][a-z0-9_-]+' README.md \
    | sed 's/^gaet //' \
    | sort -u
)

phantom_found=0
for cmd in "${README_CMDS[@]}"; do
  # 'help'/'version' are main.go aliases handled outside the switch
  if [[ "$cmd" == "help" || "$cmd" == "version" ]]; then continue; fi
  if [[ "$MAIN_CASES_STR" == *"|$cmd|"* ]]; then
    : # resolves correctly
  else
    check "README references 'gaet $cmd' with NO case in main.go dispatch" fail \
      "'$cmd' is documented but not dispatched — phantom command (remove from README or add a switch case)"
    phantom_found=1
  fi
done
if [[ "$phantom_found" -eq 0 ]]; then
  check "All README command references resolve to a main.go dispatch case" pass
fi
echo ""

# ── Check 2: .env.example keys vs config.go allKeys + pkg/ refs ────────────────
echo ":: Check 2 — .env.example keys vs pkg/config/config.go allKeys"
# Match env-key tokens of the form KEY= or KEY = (optional spaces). The required
# '=' excludes section-header words such as COMPLETE / FORMAT / MINIMAL.
mapfile -t ENV_KEYS < <(
  grep -oE '[A-Z][A-Z0-9_]*[[:space:]]*=' .env.example \
    | sed -E 's/[[:space:]]*=$//' \
    | sort -u
)
# Authoritative config keys: the first quoted field of each entry in the
# allKeys block (NOT all all-caps string literals in config.go).
mapfile -t CONFIG_KEYS < <(
  awk '/^var allKeys/{f=1;next} f&&/^}/{exit} f' pkg/config/config.go \
    | awk -F'"' '{print $2}' \
    | sort -u
)
# Keys referenced anywhere in pkg/ or cmd/ (covers GAET_* core/env keys).
PKG_REF_STR="$(grep -rhoE '\bGAET_[A-Z][A-Z0-9_]*\b' pkg/ cmd/ 2>/dev/null | sort -u)"

unknown_found=0
for key in "${ENV_KEYS[@]}"; do
  if echo "$PKG_REF_STR" | grep -qx "$key"; then continue; fi
  if printf '|%s' "${CONFIG_KEYS[@]}" | grep -q "|${key}|"; then continue; fi
  # allow documented dashboard/port keys even if optional
  if [[ "$key" == "GAET_DASHBOARD_PORT" || "$key" == "GAET_DASHBOARD_HOST" ]]; then continue; fi
  check ".env.example lists '$key' with no source reference" fail \
    "'$key' is not in config.go allKeys nor referenced in pkg/ or cmd/ — remove or implement"
  unknown_found=1
done
if [[ "$unknown_found" -eq 0 ]]; then
  check "All .env.example keys are backed by source code" pass
fi
echo ""

# ── Check 3: Go version consistency (go.mod vs AGENTS.md) ─────────────────────
echo ":: Check 3 — go.mod Go version vs AGENTS.md"
GOMOD_GO_VERSION="$(grep -E '^go [0-9]+\.[0-9]+$' go.mod | awk '{print $2}')"
AGENTS_GO_VERSION="$(grep -oE 'Golang 1\.[0-9]+\+' AGENTS.md | grep -oE '1\.[0-9]+' || true)"
if [[ -n "$GOMOD_GO_VERSION" && -n "$AGENTS_GO_VERSION" ]]; then
  if [[ "$GOMOD_GO_VERSION" == "$AGENTS_GO_VERSION" ]]; then
    check "Go version aligned (go.mod=$GOMOD_GO_VERSION, AGENTS.md=$AGENTS_GO_VERSION)" pass
  else
    check "Go version mismatch: go.mod='$GOMOD_GO_VERSION' but AGENTS.md='$AGENTS_GO_VERSION'" fail \
      "Update AGENTS.md to 'Golang $GOMOD_GO_VERSION+' to match go.mod"
  fi
fi
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────
echo "======================================"
echo "Results: $PASS passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
  echo "EXIT: 1 (doc/code drift detected)"
  exit 1
fi
echo "EXIT: 0 (all docs align with code)"
exit 0
