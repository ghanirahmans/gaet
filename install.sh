#!/bin/bash
# ============================================================================
# gaet — One-liner installer
# Usage: curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/main/install.sh | bash
# ============================================================================
set -e

GAET_DIR="$HOME/.local/bin"
GAET_CONFIG="$HOME/.gaet"
GITHUB_RAW="https://raw.githubusercontent.com/ghanirahmans/gaet/master"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  gaet — Database Backup & Sync CLI                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 1. Check Python ───────────────────────────────────────────────────────
echo -n "  Checking Python... "
if command -v python3 &>/dev/null; then
    PYTHON_VER=$(python3 --version 2>&1 | awk '{print $2}')
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
curl -sSL "$GITHUB_RAW/gaet" -o "$GAET_DIR/gaet"
chmod +x "$GAET_DIR/gaet"
echo " OK"

# ── 5. Download scripts ───────────────────────────────────────────────────
mkdir -p "$GAET_DIR/scripts"
for f in status.py scheduler.py service_manager.py installer.py __init__.py; do
    curl -sSL "$GITHUB_RAW/scripts/$f" -o "$GAET_DIR/scripts/$f"
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

# Dashboard port
# GAET_DASHBOARD_PORT=9191
EOF
    echo "  Config created: $GAET_CONFIG/.env"
else
    echo "  Config exists: $GAET_CONFIG/.env"
fi

# ── 7. Check PATH ─────────────────────────────────────────────────────────
echo ""
if echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"; then
    echo "  ✓ ~/.local/bin is in PATH"
else
    echo "  ⚠  Add ~/.local/bin to your PATH:"
    echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "     Add to ~/.bashrc or ~/.zshrc for persistence."
fi

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
