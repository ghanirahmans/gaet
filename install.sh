#!/usr/bin/env bash
# ============================================================================
# gaet — One-liner installer
# Usage: curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/master/install.sh | bash
# ============================================================================
set -eo pipefail

GAET_DIR="$HOME/.local/bin"
GAET_CONFIG="$HOME/.gaet"
API_BASE="https://api.github.com/repos/ghanirahmans/gaet/contents"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  gaet — Database Backup & Sync CLI                  ║"
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

# ── 3. Create directories ─────────────────────────────────────────────────
mkdir -p "$GAET_DIR"
mkdir -p "$GAET_CONFIG"

# ── 4. Download gaet CLI ──────────────────────────────────────────────────
echo -n "  Downloading gaet..."
# Use GitHub API to bypass raw CDN cache
api_json=$(curl -sSL "$API_BASE/gaet.py?ref=master")
# Validate API response
if echo "$api_json" | "$PYTHON" -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if 'content' in d else 1)" 2>/dev/null; then
    echo "$api_json" | "$PYTHON" -c "import json,sys,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode(),end='')" > "$GAET_DIR/gaet"
    chmod +x "$GAET_DIR/gaet"
    echo " OK"
else
    err_msg=$(echo "$api_json" | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin).get('message','API error'))" 2>/dev/null || echo "unknown error")
    echo " FAILED"
    echo "  ✗ GitHub API: $err_msg"
    exit 1
fi

# ── 5. Download scripts ───────────────────────────────────────────────────
mkdir -p "$GAET_DIR/scripts"
for f in status.py scheduler.py service_manager.py installer.py __init__.py; do
    api_json=$(curl -sSL "$API_BASE/scripts/$f?ref=master")
    if echo "$api_json" | "$PYTHON" -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if 'content' in d else 1)" 2>/dev/null; then
        echo "$api_json" | "$PYTHON" -c "import json,sys,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode(),end='')" > "$GAET_DIR/scripts/$f"
    else
        err_msg=$(echo "$api_json" | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin).get('message','API error'))" 2>/dev/null || echo "unknown error")
        echo "  ⚠  Gagal mendownload scripts/$f: $err_msg"
    fi
done
echo "  Scripts downloaded"

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
        # Windows: PATH uses ;
        if echo "$PATH" | tr ';' '\n' | grep -qF "$GAET_DIR"; then
            echo "  ✓ ~/.local/bin is in PATH"
        else
            echo "  ⚠  Add ~/.local/bin to your PATH"
            echo "     Add this to your shell profile:"
            echo '     export PATH="$HOME/.local/bin:$PATH"'
        fi
        # Windows: add .exe for better compatibility
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
