#!/usr/bin/env bash
# ============================================================================
# gaet v1.1.0 LTS — PostgreSQL Database Backup & Cloud Sync CLI
# Usage: curl -sSL https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1/install.sh | bash
# ============================================================================
set -eo pipefail

GAET_BIN_DIR="$HOME/.local/bin"
GAET_CONFIG="$HOME/.gaet"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  gaet v1.1.0 LTS - Database Backup & Cloud Sync CLI  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── 0. Check prerequisites ─────────────────────────────────────────────────
if ! command -v curl &>/dev/null; then
    echo "  [FAIL]  curl is required. Install it first."
    echo "          Ubuntu/Debian: sudo apt install curl"
    echo "          macOS:         brew install curl"
    exit 1
fi
echo "  [ OK ]  curl"

# ── 1. Check PostgreSQL tools ─────────────────────────────────────────────
if command -v pg_dump &>/dev/null; then
    echo "  [ OK ]  pg_dump"
else
    echo "  [WARN]  PostgreSQL tools (pg_dump) not found."
    echo "          Ubuntu/Debian: sudo apt install postgresql-client"
    echo "          macOS:         brew install postgresql"
fi

# ── 2. Create directories ─────────────────────────────────────────────────
mkdir -p "$GAET_BIN_DIR"
mkdir -p "$GAET_CONFIG"

# Clean up legacy Python application bundle if present
rm -rf "$HOME/.local/share/gaet" 2>/dev/null || true

# ── 3. Install binary ──────────────────────────────────────────────────────
rm -f "$GAET_BIN_DIR/gaet" 2>/dev/null || true
# If running in local repository or go toolchain is available, build directly
if [ -f "go.mod" ] && command -v go &>/dev/null; then
    echo "  [INFO]  Building gaet binary from source..."
    go build -ldflags="-s -w" -o "$GAET_BIN_DIR/gaet" ./cmd/gaet
    echo "  [ OK ]  Built gaet binary -> $GAET_BIN_DIR/gaet"
elif command -v go &>/dev/null; then
    echo "  [INFO]  Installing gaet via go install..."
    GOBIN="$GAET_BIN_DIR" go install github.com/ghanirahmans/gaet/cmd/gaet@latest
    echo "  [ OK ]  Installed gaet binary -> $GAET_BIN_DIR/gaet"
else
    # Fallback to downloading GitHub Release binary asset
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64) ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
    esac
    BIN_URL="https://github.com/ghanirahmans/gaet/releases/latest/download/gaet-${OS}-${ARCH}"
    echo "  [INFO]  Downloading gaet binary (${OS}/${ARCH})..."
    if curl -fsSL "$BIN_URL" -o "$GAET_BIN_DIR/gaet"; then
        chmod +x "$GAET_BIN_DIR/gaet"
        echo "  [ OK ]  Downloaded gaet -> $GAET_BIN_DIR/gaet"
    else
        echo "  [WARN]  Could not download pre-compiled binary. Building locally if Go is available..."
        if command -v go &>/dev/null; then
            GOBIN="$GAET_BIN_DIR" go install github.com/ghanirahmans/gaet/cmd/gaet@latest
        else
            echo "  [FAIL]  Installation failed. Please install Go or check GitHub release assets."
            exit 1
        fi
    fi
fi

chmod +x "$GAET_BIN_DIR/gaet" 2>/dev/null || true

# ── 4. Create config if not exists ────────────────────────────────────────
if [ ! -f "$GAET_CONFIG/.env" ]; then
    cat > "$GAET_CONFIG/.env" << 'EOF'
# gaet configuration
# Docs: https://github.com/ghanirahmans/gaet#configuration

# Local database
GAET_LOCAL_URL=postgresql://postgres@127.0.0.1:5432/postgres

# Remote database (Cloud)
GAET_REMOTE_URL=

# Retention (days)
GAET_RETENTION_DAYS=7
EOF
    echo "  [ OK ]  Config created -> $GAET_CONFIG/.env"
else
    echo "  [ OK ]  Config exists -> $GAET_CONFIG/.env"
fi

# ── 5. Check PATH ─────────────────────────────────────────────────────────
if echo "$PATH" | tr ':' '\n' | grep -qF "$GAET_BIN_DIR"; then
    echo "  [ OK ]  PATH -> $GAET_BIN_DIR is in PATH"
else
    echo "  [WARN]  Add $GAET_BIN_DIR to your PATH:"
    echo "          export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "          Add to ~/.bashrc or ~/.zshrc for persistence."
fi

# ── 6. Done ───────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     Installation complete!                           ║"
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
