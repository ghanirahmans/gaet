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
#   4. Every relative Markdown link in tracked docs resolves to an existing file;
#      #anchors on same-repo links match a real heading slug.
#   5. Every live docs/*.md file is listed in docs/README.md (index completeness).
#   6. Stale-token denylist: live (non-historical) docs must not reference the
#      retired Python engine or other superseded facts.
#
# Files listed in sandbox/historical-docs.txt are exempt from checks 4 (anchor
# part), 5 and 6 — they intentionally describe the past.
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

# Slugify a heading the way GitHub does (close enough for anchor checks):
# lowercase, drop punctuation except '-'/'_', spaces -> '-'. Emits one slug per
# line (trailing newline matters: callers use `grep -qx` for exact matching).
slugify() {
  printf '%s\n' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[`*_]//g; s/[^a-z0-9 _-]//g; s/ /-/g'
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

# ── shared: tracked doc list + historical manifest ────────────────────────────
# Tracked Markdown at the repo root, docs/ (incl. docs/adr/), sdk and sandbox.
mapfile -t DOC_FILES < <(
  git ls-files '*.md' 2>/dev/null | grep -vE '^(\.kilo|node_modules|sdk/node_modules)/'
)
if [[ "${#DOC_FILES[@]}" -eq 0 ]]; then
  # Fallback when git is unavailable (e.g. a source tarball).
  mapfile -t DOC_FILES < <(find . -name '*.md' \
    -not -path './.git/*' -not -path './.kilo/*' \
    -not -path './node_modules/*' -not -path './sdk/node_modules/*' \
    | sed 's|^\./||' | sort)
fi

# Historical/archived docs (exempt from live-doc checks).
HISTORICAL=()
if [[ -f sandbox/historical-docs.txt ]]; then
  mapfile -t HISTORICAL < <(grep -vE '^[[:space:]]*(#|$)' sandbox/historical-docs.txt)
fi
is_historical() { # <path>
  local p="$1" h
  for h in "${HISTORICAL[@]}"; do [[ "$p" == "$h" ]] && return 0; done
  return 1
}

# Build the set of heading slugs defined by a Markdown file.
headings_of() { # <file>
  grep -E '^#{1,6}[[:space:]]' "$1" 2>/dev/null | sed -E 's/^#{1,6}[[:space:]]+//' | while IFS= read -r h; do
    slugify "$h"
  done | sort -u
}

# ── Check 4: relative Markdown links + anchors resolve ────────────────────────
echo ":: Check 4 — relative Markdown links resolve (file + #anchor)"
link_errors=0
for doc in "${DOC_FILES[@]}"; do
  [[ -f "$doc" ]] || continue
  docdir="$(dirname "$doc")"
  # Extract link targets from [text](target) — ignore images, http(s), mailto.
  while IFS= read -r raw; do
    [[ -z "$raw" ]] && continue
    target="$raw"
    # Trim surrounding angle brackets if present.
    [[ "$target" == \<* ]] && target="${target#<}" && target="${target%>}"
    # Split off the anchor.
    anchor=""
    if [[ "$target" == *#* ]]; then
      anchor="${target#*#}"
      target="${target%%#*}"
    fi
    # Skip absolute/external links.
    case "$target" in
      http://*|https://*|mailto:*|ftp://*|tel:*|"") ;; # no file part to check
      *)
        # Resolve relative to the doc's directory.
        resolved="$(
          cd "$docdir" 2>/dev/null && realpath -m "$target" 2>/dev/null
        )"
        rel="${resolved#"$ROOT"/}"
        if [[ ! -e "$rel" ]]; then
          check "broken link in $doc -> '$raw'" fail "target '$rel' does not exist"
          link_errors=1
          continue
        fi
        # Anchor check: only for Markdown targets inside the repo.
        if [[ -n "$anchor" && "$rel" == *.md ]]; then
          if ! headings_of "$rel" | grep -qx "$anchor"; then
            check "broken anchor in $doc -> '$raw'" fail "no heading slug '#$anchor' in $rel"
            link_errors=1
          fi
        fi
        ;;
    esac
  done < <(grep -oE '\]\([^)]+\)' "$doc" 2>/dev/null | sed -E 's/^\]\(//; s/\)$//')
done
if [[ "$link_errors" -eq 0 ]]; then
  check "All relative Markdown links and anchors resolve" pass
fi
echo ""

# ── Check 5: docs index completeness (docs/README.md) ─────────────────────────
echo ":: Check 5 — docs index completeness (docs/README.md)"
INDEX="docs/README.md"
index_errors=0
if [[ -f "$INDEX" ]]; then
  # Every live docs/*.md (top level only, not the index itself, not historical)
  # must be linked from the index.
  while IFS= read -r f; do
    [[ "$f" == "$INDEX" ]] && continue
    is_historical "$f" && continue
    base="$(basename "$f")"
    if ! grep -qF "($base)" "$INDEX"; then
      check "docs index missing link to $f" fail "add a link to '$base' in $INDEX"
      index_errors=1
    fi
  done < <(find docs -maxdepth 1 -name '*.md' | sed 's|^\./||' | sort)
else
  check "docs/README.md index is missing" fail "create docs/README.md"
  index_errors=1
fi
if [[ "$index_errors" -eq 0 ]]; then
  check "Every live docs/*.md is listed in docs/README.md" pass
fi
echo ""

# ── Check 6: stale-token denylist (live docs only) ────────────────────────────
echo ":: Check 6 — stale-token denylist in live docs"
# Patterns that must not be presented as CURRENT behavior in a live doc. A match
# is only stale when the line affirms it; lines that explicitly frame the token
# as legacy/removed/rejected are fine (e.g. "the legacy Python implementation
# used src/gaet/...", "Not Adopted: pip install gaet", "no .pgpass written").
DELIST_PATTERNS=(
  'gaet\.py'
  'src/gaet'
  'pip install gaet'
  '\.pgpass'
  '9191'
)
# Framing markers that mark a token as historical/negated rather than current.
NEGATION_RE='legacy|deprecat|archiv|supersed|replaced|formerly|no longer|removed|obsolet|not adopted|never|instead of|no temp|does not|doesn.t|without|rather than|previously|migrat|histor'
stale_found=0
for doc in "${DOC_FILES[@]}"; do
  [[ -f "$doc" ]] || continue
  is_historical "$doc" && continue
  for pat in "${DELIST_PATTERNS[@]}"; do
    while IFS= read -r hit; do
      [[ -z "$hit" ]] && continue
      ln="${hit%%:*}"
      text="${hit#*:}"
      # Skip lines that frame the token as legacy/negated (case-insensitive).
      if printf '%s' "$text" | grep -qiE "$NEGATION_RE"; then continue; fi
      check "stale token in $doc:$ln (matches /$pat/)" fail "$hit"
      stale_found=1
    done < <(grep -nE "$pat" "$doc" 2>/dev/null || true)
  done
done
if [[ "$stale_found" -eq 0 ]]; then
  check "No stale Python-engine tokens presented as current in live docs" pass
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
