#!/usr/bin/env bash
# ============================================================================
# gaet — One-liner installer
# Usage:        curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
# Reinstall:    curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
# ============================================================================
set -eo pipefail

GAET_DIR="$HOME/.local/bin"
GAET_CONFIG="$HOME/.gaet"
GAET_BRANCH="${GAET_BRANCH:-lts/v1.0}"
# Resolve commit SHA dynamically to bypass GitHub raw CDN 5-minute cache
COMMIT_SHA=$(curl -fsSL https://api.github.com/repos/ghanirahmans/gaet/commits/$GAET_BRANCH 2>/dev/null | grep '"sha"' | head -n1 | cut -d'"' -f4 || true)
if [ -z "$COMMIT_SHA" ]; then
    COMMIT_SHA="$GAET_BRANCH"
fi
RAW_BASE="https://raw.githubusercontent.com/ghanirahmans/gaet/$COMMIT_SHA"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  gaet - Database Backup & Sync CLI                   ║"
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

GAET_APP_DIR="$HOME/.local/share/gaet"

# Clean up legacy un-isolated folders if present
rm -rf "$GAET_DIR/gaet_pkg" "$GAET_DIR/scripts" "$GAET_DIR/dashboard" "$GAET_DIR/completions" "$GAET_CONFIG/app" 2>/dev/null || true

# ── 3. Create directories ─────────────────────────────────────────────────
mkdir -p "$GAET_DIR"
mkdir -p "$GAET_CONFIG"
mkdir -p "$GAET_APP_DIR"
mkdir -p "$GAET_APP_DIR/src/gaet"
mkdir -p "$GAET_APP_DIR/scripts"
mkdir -p "$GAET_APP_DIR/completions"
mkdir -p "$GAET_APP_DIR/dashboard/static" "$GAET_APP_DIR/dashboard/public"

# ── 4. Download gaet bundle ───────────────────────────────────────────────
echo "  Downloading gaet bundle..."
if dl "$RAW_BASE/gaet.py" "$GAET_APP_DIR/gaet.py"; then
    chmod +x "$GAET_APP_DIR/gaet.py"
    echo "  [ OK ]  gaet.py -> $GAET_APP_DIR/gaet.py"
else
    echo "  [FAIL]  Could not download gaet.py from: $RAW_BASE/gaet.py"
    exit 1
fi

PKG_FILES="__init__.py __main__.py registry.py cli.py core.py detect.py init.py config.py status.py backup.py scheduler.py log.py serve.py export.py update.py remote.py snapshots.py"
for f in $PKG_FILES; do
    dl "$RAW_BASE/src/gaet/$f" "$GAET_APP_DIR/src/gaet/$f"
done
echo "  [ OK ]  src/gaet -> $GAET_APP_DIR/src/gaet/"

for f in status.py scheduler.py service_manager.py installer.py __init__.py; do
    dl "$RAW_BASE/scripts/$f" "$GAET_APP_DIR/scripts/$f"
done
echo "  [ OK ]  scripts -> $GAET_APP_DIR/scripts/"

for f in gaet.bash gaet.zsh gaet.fish gaet.ps1; do
    dl "$RAW_BASE/completions/$f" "$GAET_APP_DIR/completions/$f"
done
echo "  [ OK ]  completions -> $GAET_APP_DIR/completions/"

for f in server.py static/index.html public/gaet-logo.png; do
    dl "$RAW_BASE/dashboard/$f" "$GAET_APP_DIR/dashboard/$f"
done
echo "  [ OK ]  dashboard -> $GAET_APP_DIR/dashboard/"

# ── 5. Create launcher wrapper script in ~/.local/bin/gaet ───────────────
cat > "$GAET_DIR/gaet" << 'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/.local/share/gaet/gaet.py" "$@"
EOF
chmod +x "$GAET_DIR/gaet"
echo "  [ OK ]  CLI Launcher -> $GAET_DIR/gaet"

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
