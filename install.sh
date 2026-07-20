#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# gaet — Database Backup & Sync  Installer
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail
VERSION="1.0.0"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

HBLUE='\033[0;34m'; HGREEN='\033[0;32m'; HYELLOW='\033[1;33m'; HNC='\033[0m'
info()  { echo -e "${HBLUE}ℹ${HNC}  $*"; }
ok()    { echo -e "${HGREEN}✅${HNC} $*"; }
warn()  { echo -e "${HYELLOW}⚠${HNC} $*"; }

echo ""
echo -e "${HBLUE}  gaet v${VERSION} — Database Backup & Sync${HNC}"
echo ""

# Prerequisites
info "Memeriksa prerequisites..."
for cmd in python3 pg_dump pg_restore psql; do
    command -v $cmd &>/dev/null && ok "$cmd ditemukan" || warn "$cmd tidak ditemukan"
done

# Install CLI
mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "${SCRIPT_DIR}/gaet" "${INSTALL_DIR}/gaet"
chmod +x "${INSTALL_DIR}/gaet"
ok "gaet → ${INSTALL_DIR}/gaet"

# Install Python module
cp "${SCRIPT_DIR}/scripts/status.py" "${INSTALL_DIR}/status.py"
ok "status.py → ${INSTALL_DIR}/"

# Config
mkdir -p "$HOME/.gaet/backups"
if [ ! -f "$HOME/.gaet/.env" ]; then
    cp "${SCRIPT_DIR}/.env.example" "$HOME/.gaet/.env"
    chmod 600 "$HOME/.gaet/.env"
    ok "Config template → ~/.gaet/.env"
    warn "Edit ~/.gaet/.env dan isi GAET_REMOTE_URL"
else
    ok "Config sudah ada: ~/.gaet/.env"
fi

# PATH check
if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
    warn "${INSTALL_DIR} tidak ada di PATH!"
    echo "  Tambahkan ke ~/.bashrc: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo -e "${HGREEN}  ✅ gaet v${VERSION} terinstall!${HNC}"
echo ""
echo "  Langkah selanjutnya:"
echo "    1. nano ~/.gaet/.env           # Isi GAET_REMOTE_URL"
echo "    2. gaet check                  # Verifikasi config"
echo "    3. gaet push                   # Backup pertama"
echo "    4. gaet push --auto            # Aktifkan auto-backup"
echo "    5. gaet serve                   # Dashboard web (http://localhost:9191)"
echo ""
