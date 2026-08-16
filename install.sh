#!/usr/bin/env bash
# ============================================================================
# gaet — One-liner installer
# Usage:        curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
# Reinstall:    curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
# ============================================================================
set -eo pipefail

GAET_DIR="$HOME/.local/bin"
GAET_CONFIG="$HOME/.gaet"
# Raw content URLs (NOT api.github.com — avoids the 60 req/h API rate limit for
# anonymous users). Files are fetched directly from the repo's default branch.
RAW_BASE="https://raw.githubusercontent.com/ghanirahmans/gaet/master"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  gaet — Database Backup & Sync CLI                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 0. Check prerequisites ─────────────────────────────────────────────────
echo -n "  Checking curl... "
if ! command -v curl &>/dev/null; then
    echo "NOT FOUND"
    echo "  ✗ curl is required. Install it first."
    echo "     Ubuntu/Debian: sudo apt install curl"
    echo "     macOS:         brew install curl"
    exit 1
fi
echo "OK"

# ── 1. Check Python ───────────────────────────────────────────────────────
echo -n "  Checking Python... "
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done
if [ -n "$PYTHON" ]; then
    PYTHON_VER=$($PYTHON --version 2>&1 | awk '{print $2}')
    echo "OK ($PYTHON_VER)"
else
    echo "NOT FOUND"
    echo "  ✗ Python 3.8+ is required. Install it first."
    exit 1
fi

# ── 2. Check PostgreSQL tools ─────────────────────────────────────────────
echo -n "  Checking pg_dump... "
if command -v pg_dump &>/dev/null; then
    echo "OK"
else
    echo "NOT FOUND"
    echo "  ⚠  PostgreSQL tools not found. Install postgresql-client."
    echo "     Ubuntu/Debian: sudo apt install postgresql-client"
    echo "     macOS:         brew install postgresql"
    echo "     Windows:       https://www.postgresql.org/download/"
fi

# ── Helper: download one file with 2 retries ───────────────────────────────
# Uses raw.githubusercontent.com (no API rate limit). Retries twice on failure
# to smooth over transient CDN flakes.
dl() {
    local url="$1"; local dst="$2"
    local i
    for i in 1 2 3; do
        if curl -fsSL "$url" -o "$dst" 2>/dev/null; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# ── 3. Create directories ─────────────────────────────────────────────────
mkdir -p "$GAET_DIR"
mkdir -p "$GAET_CONFIG"

# ── 4. Download gaet CLI ──────────────────────────────────────────────────
echo -n "  Downloading gaet..."
# Shim (entry point)
if dl "$RAW_BASE/gaet.py" "$GAET_DIR/gaet"; then
    chmod +x "$GAET_DIR/gaet"
else
    echo " FAILED"
    echo "  ✗ Could not download shim: $RAW_BASE/gaet.py"
    exit 1
fi
# v3 src-layout: package lives in src/gaet. Download into gaet_pkg/gaet/ —
# a dir named gaet/ next to the gaet binary is impossible on disk (file/dir
# name clash), so the package dir is nested under gaet_pkg/.
PKG_FILES="__init__.py __main__.py registry.py cli.py core.py detect.py init.py config.py status.py backup.py scheduler.py log.py serve.py export.py update.py remote.py snapshots.py"
PKG_OK=0
mkdir -p "$GAET_DIR/gaet_pkg/gaet"
for f in $PKG_FILES; do
    if dl "$RAW_BASE/src/gaet/$f" "$GAET_DIR/gaet_pkg/gaet/$f"; then
        PKG_OK=$((PKG_OK + 1))
    fi
done
echo " OK (cli + $PKG_OK package files)"

# ── 5. Download scripts ───────────────────────────────────────────────────
mkdir -p "$GAET_DIR/scripts"
SCRIPTS_OK=0
for f in status.py scheduler.py service_manager.py installer.py __init__.py; do
    if dl "$RAW_BASE/scripts/$f" "$GAET_DIR/scripts/$f"; then
        SCRIPTS_OK=$((SCRIPTS_OK + 1))
    fi
done
echo "  Scripts downloaded ($SCRIPTS_OK/5)"

# ── 5a. Download shell completions ────────────────────────────────────────
echo -n "  Downloading completions..."
COMP_DIR="$GAET_DIR/completions"
mkdir -p "$COMP_DIR"
COMP_OK=0
for f in gaet.bash gaet.zsh gaet.fish gaet.ps1; do
    if dl "$RAW_BASE/completions/$f" "$COMP_DIR/$f"; then
        COMP_OK=$((COMP_OK + 1))
    fi
done
echo " OK ($COMP_OK files)"

# ── 5b. Download dashboard ────────────────────────────────────────────────
# gaet serve imports `dashboard.server`, which must live in the install dir
# (~/.local/bin/dashboard/) so it is importable from the gaet entry script
# (sys.path[0] = ~/.local/bin).
echo -n "  Downloading dashboard..."
DASH_DIR="$GAET_DIR/dashboard"
DASH_OK=0
mkdir -p "$DASH_DIR/static" "$DASH_DIR/public"
# Pure Python HTTP server — no Node.js/npm build step required (v2.0.1+).
# Only files that exist in the repo are downloaded (index.html is
# self-contained: <style> + <script> inline, no external CSS/JS).
for f in server.py static/index.html public/gaet-logo.png; do
    if dl "$RAW_BASE/dashboard/$f" "$DASH_DIR/$f"; then
        DASH_OK=$((DASH_OK + 1))
    fi
done
if [ "$DASH_OK" -gt 0 ]; then
    echo " OK ($DASH_OK files)"
else
    echo " SKIPPED (dashboard needs 'gaet update')"
fi

# ── 6. Create config if not exists ────────────────────────────────────────
if [ ! -f "$GAET_CONFIG/.env" ]; then
    cat > "$GAET_CONFIG/.env" << 'EOF'
# gaet configuration
# Docs: https://github.com/ghanirahmans/gaet#configuration
#
# MINIMUM required: GAET_REMOTE_URL
# Everything else has sensible defaults.

# Cloud database (REQUIRED)
# GAET_REMOTE_URL=postgresql://user:pass@host:5432/db

# Local database (default: postgres@127.0.0.1:5432/postgres)
# GAET_LOCAL_URL=postgresql://postgres:@127.0.0.1:5432/postgres

# Retention (days)
# GAET_RETENTION_DAYS=7

# Tables to backup (comma-separated, auto-discovered if empty)
# GAET_TABLES=

# Dashboard port
# GAET_DASHBOARD_PORT=9191
EOF
    echo "  Config created: $GAET_CONFIG/.env"
else
    echo "  Config exists: $GAET_CONFIG/.env"
fi

# ── 7. Check PATH ─────────────────────────────────────────────────────────
echo ""
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
        if echo "$PATH" | tr ';' '\n' | grep -qF "$GAET_DIR"; then
            echo "  ✓ ~/.local/bin is in PATH"
        else
            echo "  ⚠  Add ~/.local/bin to your PATH"
            echo "     Add this to your shell profile:"
            echo '     export PATH="$HOME/.local/bin:$PATH"'
        fi
        if [ ! -f "$GAET_DIR/gaet.exe" ]; then
            cp "$GAET_DIR/gaet" "$GAET_DIR/gaet.exe" 2>/dev/null || true
        fi
        ;;
    *)
        if echo "$PATH" | tr ':' '\n' | grep -qF "$GAET_DIR"; then
            echo "  ✓ ~/.local/bin is in PATH"
        else
            echo "  ⚠  Add ~/.local/bin to your PATH:"
            echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo ""
            echo "     Add to ~/.bashrc or ~/.zshrc for persistence."
        fi
        ;;
esac

# ── 8. Done ───────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✓ Installation complete!                           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Next steps:"
echo "    1. Configure:  gaet init"
echo "    2. Check:      gaet check"
echo "    3. Backup:     gaet push"
echo "    4. Dashboard:  gaet serve"
echo ""
echo "  Docs: https://github.com/ghanirahmans/gaet"
echo ""
