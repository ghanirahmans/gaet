#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# gaet — Database Backup & Sync CLI
# ═══════════════════════════════════════════════════════════════════
# Backup PostgreSQL lokal ke remote database (Supabase, Neon, dll), dengan dashboard web.
#
#   gaet init        Setup wizard
#   gaet push        Local → cloud
#   gaet fetch       Cloud → local
#   gaet status      Tampilkan status
#   gaet check       Validasi konfigurasi
#   gaet log         Lihat log
#   gaet serve       Dashboard web
#   gaet stop        Hentikan auto-backup
# ═══════════════════════════════════════════════════════════════════

set -uo pipefail
GAET_VERSION="1.0.0"
GAET_NAME="gaet"

# ─── Config ──────────────────────────────────────────────────────
GAET_CONFIG_DIR="${GAET_CONFIG_DIR:-${HOME}/.gaet}"
GAET_BACKUP_DIR="${GAET_BACKUP_DIR:-${GAET_CONFIG_DIR}/backups}"
GAET_LOG_FILE="${GAET_LOG_FILE:-${GAET_BACKUP_DIR}/gaet.log}"
GAET_CRON_LOG="${GAET_CRON_LOG:-${GAET_BACKUP_DIR}/cron.log}"
GAET_RETENTION_DAYS="${GAET_RETENTION_DAYS:-7}"
GAET_DASHBOARD_PORT="${GAET_DASHBOARD_PORT:-9191}"
GAET_DASHBOARD_HOST="${GAET_DASHBOARD_HOST:-0.0.0.0}"
GAET_REMOTE_SSLMODE="${GAET_REMOTE_SSLMODE:-require}"
GAET_SERVICE_PREFIX="${GAET_SERVICE_PREFIX:-gaet}"

# ─── Colors ──────────────────────────────────────────────────────
if [ -t 1 ]; then
    R=$'\033[0;31m'    G=$'\033[0;32m'    Y=$'\033[1;33m'
    C=$'\033[0;36m'    B=$'\033[1m'       D=$'\033[2m'
    W=$'\033[1;37m'    NC=$'\033[0m'
    ICON_OK='✓'   ICON_FAIL='✗'   ICON_WARN='⚠'
    ICON_INFO='ℹ' ICON_ARROW='→'  ICON_STAR='✦'
else
    R=''; G=''; Y=''; C=''; B=''; D=''; W=''; NC=''
    ICON_OK='OK' ICON_FAIL='FAIL' ICON_WARN='WARN'
    ICON_INFO='i' ICON_ARROW='>' ICON_STAR='*'
fi

# ─── Script Path ─────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Locking ──────────────────────────────────────────────────
GAET_LOCK_FILE="${GAET_BACKUP_DIR}/.gaet.lock"
acquire_lock() {
    if ! mkdir "${GAET_LOCK_FILE}.dir" 2>/dev/null; then
        die "gaet sedang berjalan (lock: ${GAET_LOCK_FILE})"
    fi
    trap 'rm -rf "${GAET_LOCK_FILE}.dir"' EXIT
}
release_lock() {
    rm -rf "${GAET_LOCK_FILE}.dir"
    trap - EXIT
}
log()    { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$GAET_LOG_FILE"; }
cronlog(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$GAET_CRON_LOG"; }

# ─── Terminal UI ─────────────────────────────────────────────────
box_title() {
    local title="$1"
    local width=56
    local pad=$(( (width - ${#title} - 2) / 2 ))
    echo ""
    echo -e "  ${C}╭${NC}─${D}────────────────────────────────────────────────────${NC}─${C}╮${NC}"
    printf "  ${C}│${NC}%*s${B} %s ${NC}%*s${C}│${NC}\n" $pad "" "$title" $((pad + (width - ${#title} - 2) % 2)) ""
    echo -e "  ${C}╰${NC}─${D}────────────────────────────────────────────────────${NC}─${C}╯${NC}"
    echo ""
}

box_section() {
    local title="$1"
    echo -e "  ${C}─${NC} ${B}${title}${NC}"
}

status_ok()  { echo -e "  ${G}${ICON_OK}${NC}  $*"; }
status_fail(){ echo -e "  ${R}${ICON_FAIL}${NC}  $*"; }
status_warn(){ echo -e "  ${Y}${ICON_WARN}${NC}  $*"; }
status_info(){ echo -e "  ${C}${ICON_INFO}${NC}  $*"; }
status_arrow(){ echo -e "  ${D}${ICON_ARROW}${NC}  $*"; }

draw_table() {
    # Usage: <header1:header2:...> <rows> where rows is "col1|col2|..."
    local headers="$1"
    shift
    local IFS=':'
    local -a h=($headers)
    unset IFS
    local ncols=${#h[@]}
    local cols=("${h[@]}")

    # Calculate column widths from headers
    local -a widths=()
    for ((i=0; i<ncols; i++)); do
        widths[$i]=${#cols[$i]}
    done

    # Measure data rows
    local data_rows=()
    for row in "$@"; do
        data_rows+=("$row")
        IFS='|' read -ra vals <<< "$row"
        for ((i=0; i<${#vals[@]}; i++)); do
            [ ${#vals[$i]} -gt ${widths[$i]} ] && widths[$i]=${#vals[$i]}
        done
    done

    # Padding per column
    local -a pads=()
    for ((i=0; i<ncols; i++)); do
        pads[$i]=${widths[$i]}
    done

    # Build separator
    local sep="  ${D}├"
    for ((i=0; i<ncols; i++)); do
        sep+="─"
        for ((j=0; j<${pads[$i]}; j++)); do sep+="─"; done
        sep+="─"
        [ $i -lt $((ncols-1)) ] && sep+="┼" || sep+="┤${NC}"
    done

    # Top border
    local top="  ${D}╭"
    for ((i=0; i<ncols; i++)); do
        top+="─"
        for ((j=0; j<${pads[$i]}; j++)); do top+="─"; done
        top+="─"
        [ $i -lt $((ncols-1)) ] && top+="┬" || top+="╮${NC}"
    done
    echo -e "$top"

    # Header
    local hdr="  ${D}│${NC}"
    for ((i=0; i<ncols; i++)); do
        local val="${cols[$i]}"
        local pad=$((pads[$i] - ${#val}))
        printf "${D}│${NC}${B} %s${NC}%*s" "$val" $((pad + 1)) ""
    done
    echo -e " ${D}│${NC}"
    echo -e "$sep"

    # Data
    for row in "${data_rows[@]}"; do
        IFS='|' read -ra vals <<< "$row"
        echo -n "  ${D}│${NC}"
        for ((i=0; i<ncols; i++)); do
            local val="${vals[$i]:-}"
            local pad=$((pads[$i] - ${#val}))
            printf " %s%*s ${D}│${NC}" "$val" $pad ""
        done
        echo ""
    done

    # Bottom border
    local bot="  ${D}╰"
    for ((i=0; i<ncols; i++)); do
        bot+="─"
        for ((j=0; j<${pads[$i]}; j++)); do bot+="─"; done
        bot+="─"
        [ $i -lt $((ncols-1)) ] && bot+="┴" || bot+="╯${NC}"
    done
    echo -e "$bot"
}

# ─── PG Tools ───────────────────────────────────────────────────
GAET_PG_DUMP=""; GAET_PG_RESTORE=""; GAET_PSQL=""
PG_DUMP=""; PG_RESTORE=""; PSQL=""
find_pg_tools() {
    [ -n "${GAET_PG_DUMP}" ]    && PG_DUMP="$GAET_PG_DUMP"
    [ -n "${GAET_PG_RESTORE}" ] && PG_RESTORE="$GAET_PG_RESTORE"
    [ -n "${GAET_PSQL}" ]       && PSQL="$GAET_PSQL"

    # Auto-discover pg0 — find newest version
    local pg0_base="$HOME/.pg0/installation"
    if [ -d "$pg0_base" ]; then
        local pg0_ver
        pg0_ver=$(ls -1 "$pg0_base" 2>/dev/null | sort -V | tail -1)
        [ -n "$pg0_ver" ] && local pg0="$pg0_base/$pg0_ver/bin" || local pg0=""
        [ -n "$pg0_ver" ] && [ -z "$PG_DUMP" ]    && [ -x "$pg0/pg_dump" ]    && PG_DUMP="$pg0/pg_dump"
        [ -n "$pg0_ver" ] && [ -z "$PG_RESTORE" ] && [ -x "$pg0/pg_restore" ] && PG_RESTORE="$pg0/pg_restore"
        [ -n "$pg0_ver" ] && [ -z "$PSQL" ]       && [ -x "$pg0/psql" ]       && PSQL="$pg0/psql"
    fi

    [ -z "$PG_DUMP" ]    && PG_DUMP=$(command -v pg_dump 2>/dev/null || true)
    [ -z "$PG_RESTORE" ] && PG_RESTORE=$(command -v pg_restore 2>/dev/null || true)
    [ -z "$PSQL" ]       && PSQL=$(command -v psql 2>/dev/null || true)
}

# ─── Config Loading ─────────────────────────────────────────────
load_env() {
    local env_file="${GAET_CONFIG_DIR}/.env"
    [ -f "$env_file" ] && source "$env_file"
}

load_remote_url() {
    local url="${GAET_REMOTE_URL:-${GAET_SUPABASE_URL:-}}"
    [ -z "$url" ] && return 1
    # Parse postgresql://user:pass@host:port/db
    local stripped="${url#postgresql://}"
    [ "$stripped" = "$url" ] && stripped="${url#postgres://}"
    GAET_REMOTE_USER="${stripped%%:*}"
    local rest="${stripped#*:}"
    GAET_REMOTE_PASS="${rest%%@*}"
    rest="${rest#*@}"
    GAET_REMOTE_HOST="${rest%%:*}"
    rest="${rest#*:}"
    GAET_REMOTE_PORT="${rest%%/*}"
    GAET_REMOTE_DB="${rest#*/}"
    GAET_REMOTE_DB="${GAET_REMOTE_DB%%\?*}"
    return 0
}

# ─── Help & Version ────────────────────────────────────────────
usage() {
    echo ""
    echo -e "  ${W}${GAET_NAME} v${GAET_VERSION}${NC} ${D}— Database Backup & Sync${NC}"
    echo ""
    echo -e "  ${B}Usage:${NC}"
    echo -e "    ${C}gaet init${NC}          ${D}Setup wizard (config + test)${NC}"
    echo -e "    ${C}gaet push${NC}          ${D}Backup local → cloud${NC}"
    echo -e "    ${C}gaet fetch${NC}         ${D}Restore cloud → local${NC}"
    echo -e "    ${C}gaet status${NC}        ${D}Tampilkan status sinkronisasi${NC}"
    echo -e "    ${C}gaet status --json${NC}  ${D}Status dalam format JSON${NC}"
    echo -e "    ${C}gaet check${NC}         ${D}Validasi konfigurasi & koneksi${NC}"
    echo -e "    ${C}gaet log${NC}           ${D}Lihat log backup${NC}"
    echo -e "    ${C}gaet serve${NC}         ${D}Jalankan dashboard web${NC}"
    echo -e "    ${C}gaet push --auto${NC}   ${D}Aktifkan auto-backup${NC}"
    echo -e "    ${C}gaet stop${NC}          ${D}Hentikan auto-backup${NC}"
    echo -e "    ${C}gaet --version${NC}     ${D}Tampilkan versi${NC}"
    echo ""
    echo -e "  ${B}Config:${NC}  ${C}${GAET_CONFIG_DIR}/.env${NC}"
    echo ""
}

version() { echo "${GAET_NAME} v${GAET_VERSION}"; }

die() { echo -e "  ${R}${ICON_FAIL}${NC}  $*" >&2; exit 1; }

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# ─── Pre-flight ────────────────────────────────────────────────
check_tools() {
    find_pg_tools
    local ok=true
    [ -z "$PG_DUMP" ]    && status_fail "pg_dump tidak ditemukan"    && ok=false
    [ -z "$PG_RESTORE" ] && status_fail "pg_restore tidak ditemukan" && ok=false
    [ -z "$PSQL" ]       && status_fail "psql tidak ditemukan"       && ok=false
    $ok || die "Pasang PostgreSQL tools dulu, atau set GAET_PG_DUMP dll di .env"
}

check_local_db() {
    find_pg_tools
    export PGPASSWORD="${GAET_LOCAL_DB_PASS:-hindsight}"
    if ! "${PSQL}" -h "${GAET_LOCAL_DB_HOST:-127.0.0.1}" -p "${GAET_LOCAL_DB_PORT:-5432}" \
         -U "${GAET_LOCAL_DB_USER:-hindsight}" -d "${GAET_LOCAL_DB_NAME:-hindsight}" \
         -tAc "SELECT 1;" &>/dev/null; then
        die "Gak bisa konek ke database lokal (${GAET_LOCAL_DB_HOST:-127.0.0.1}:${GAET_LOCAL_DB_PORT:-5432}/${GAET_LOCAL_DB_NAME:-hindsight})
  Cek konfigurasi database di ${GAET_CONFIG_DIR}/.env, atau set GAET_LOCAL_DB_HOST, GAET_LOCAL_DB_USER, GAET_LOCAL_DB_PASS"
    fi
}

check_remote() {
    load_remote_url || die "GAET_REMOTE_URL belum diisi. Jalankan: gaet init"
    export PGPASSWORD="$GAET_REMOTE_PASS"
    if ! PGSSLMODE="$GAET_REMOTE_SSLMODE" "${PSQL}" -h "$GAET_REMOTE_HOST" -p "$GAET_REMOTE_PORT" \
         -U "$GAET_REMOTE_USER" -d "$GAET_REMOTE_DB" \
         -tAc "SELECT 1;" &>/dev/null; then
        die "Gak bisa konek ke cloud. Cek GAET_REMOTE_URL di ${GAET_CONFIG_DIR}/.env"
    fi
}

# ─── Commands ──────────────────────────────────────────────────

cmd_init() {
    box_title "${GAET_NAME} init"
    find_pg_tools

    box_section "PostgreSQL Tools"
    [ -n "$PG_DUMP" ]    && status_ok "pg_dump   ${D}"${PG_DUMP}"${NC}"    || status_fail "pg_dump tidak ditemukan"
    [ -n "$PG_RESTORE" ] && status_ok "pg_restore ${D}"${PG_RESTORE}"${NC}" || status_fail "pg_restore tidak ditemukan"
    [ -n "$PSQL" ]       && status_ok "psql      ${D}"${PSQL}"${NC}"       || status_fail "psql tidak ditemukan"

    mkdir -p "$GAET_CONFIG_DIR" "$GAET_BACKUP_DIR"
    local env_file="${GAET_CONFIG_DIR}/.env"

    if [ ! -f "$env_file" ]; then
        echo ""
        box_section "Konfigurasi Database Lokal"
        echo -e "  ${D}Default: hindsight@127.0.0.1:5432/hindsight${NC}"
        local h="${GAET_LOCAL_DB_HOST:-127.0.0.1}" p="${GAET_LOCAL_DB_PORT:-5432}"
        local u="${GAET_LOCAL_DB_USER:-hindsight}" n="${GAET_LOCAL_DB_NAME:-hindsight}"
        local w="${GAET_LOCAL_DB_PASS:-hindsight}"
        read -r -p "  Host [${h}]: "     inp; [ -n "$inp" ] && h=$inp
        read -r -p "  Port [${p}]: "     inp; [ -n "$inp" ] && p=$inp
        read -r -p "  User [${u}]: "     inp; [ -n "$inp" ] && u=$inp
        read -r -p "  Database [${n}]: " inp; [ -n "$inp" ] && n=$inp
        read -r -s -p "  Password [${w}]: " inp; echo ""; [ -n "$inp" ] && w=$inp

        echo ""
        box_section "Cloud / Remote Database"
        echo -e "  ${D}Masukkan connection string PostgreSQL tujuan-mu.${NC}"
        echo -e "  ${D}Bisa dari Supabase, Neon, RDS, atau VPS sendiri.${NC}"
        echo -e "  ${D}Format: postgresql://user:password@host:5432/db${NC}"
        read -r -p "  GAET_REMOTE_URL: " remote_url

        echo ""
        box_section "Backup"
        read -r -p "  Retensi (hari) [${GAET_RETENTION_DAYS}]: " ret
        ret="${ret:-$GAET_RETENTION_DAYS}"

        cat > "$env_file" << EOF
# ══════════════════════════════════════════════════════════════
# gaet — Konfigurasi
# ══════════════════════════════════════════════════════════════
# Dibuat: $(date '+%Y-%m-%d %H:%M:%S')
# ══════════════════════════════════════════════════════════════

# Database Lokal
GAET_LOCAL_DB_HOST=${h}
GAET_LOCAL_DB_PORT=${p}
GAET_LOCAL_DB_USER=${u}
GAET_LOCAL_DB_NAME=${n}
GAET_LOCAL_DB_PASS=${w}

# Remote Database (Cloud)
GAET_REMOTE_URL=${remote_url}

# Backup
GAET_RETENTION_DAYS=${ret}
EOF
        chmod 600 "$env_file"
        echo ""
        status_ok "Config tersimpan di ${env_file}"
    else
        status_info "Config sudah ada: ${env_file}"
        load_env
    fi

    echo ""
    box_section "Pre-flight Check"
    cmd_check
}

cmd_check() {
    load_env
    local all_ok=true

    box_title "${GAET_NAME} check"

    # Tools
    echo -n "  ${C}🔧${NC}  PostgreSQL tools... "
    find_pg_tools
    if [ -n "$PG_DUMP" ] && [ -n "$PG_RESTORE" ] && [ -n "$PSQL" ]; then
        echo -e "${G}OK${NC}"
        status_arrow "pg_dump   ${D}"${PG_DUMP}"${NC}"
        status_arrow "pg_restore ${D}"${PG_RESTORE}"${NC}"
        status_arrow "psql      ${D}"${PSQL}"${NC}"
    else
        echo -e "${R}FAIL${NC}"
        all_ok=false
    fi

    # Local DB
    local h="${GAET_LOCAL_DB_HOST:-127.0.0.1}"
    local p="${GAET_LOCAL_DB_PORT:-5432}"
    local u="${GAET_LOCAL_DB_USER:-hindsight}"
    local n="${GAET_LOCAL_DB_NAME:-hindsight}"
    local w="${GAET_LOCAL_DB_PASS:-hindsight}"
    echo -n "  ${C}💾${NC}  Database lokal (${h}:${p}/${n})... "
    if export PGPASSWORD="$w" && "${PSQL}" -h "$h" -p "$p" -U "$u" -d "$n" -tAc "SELECT 1;" &>/dev/null; then
        echo -e "${G}OK${NC}"
        local lsize
        lsize=$("${PSQL}" -h "$h" -p "$p" -U "$u" -d "$n" -tAc \
            "SELECT round(pg_database_size('${n}')/1024.0/1024.0,1) || ' MB';" 2>/dev/null || echo "?")
        status_arrow "Size: ${lsize}"
    else
        echo -e "${R}FAIL${NC}"; all_ok=false
    fi

    # Remote config
    echo -n "  ${C}☁️${NC}   Cloud config... "
    if load_remote_url 2>/dev/null; then
        echo -e "${G}OK${NC}"
        # Connection
        echo -n "  ${C}☁️${NC}   Koneksi cloud... "
        if export PGPASSWORD="$GAET_REMOTE_PASS" && \
           PGSSLMODE="$GAET_REMOTE_SSLMODE" "${PSQL}" -h "$GAET_REMOTE_HOST" -p "$GAET_REMOTE_PORT" \
           -U "$GAET_REMOTE_USER" -d "$GAET_REMOTE_DB" -tAc "SELECT 1;" &>/dev/null; then
            echo -e "${G}OK${NC}"
            local ssize
            ssize=$(PGSSLMODE="$GAET_REMOTE_SSLMODE" "${PSQL}" -h "$GAET_REMOTE_HOST" -p "$GAET_REMOTE_PORT" \
                -U "$GAET_REMOTE_USER" -d "$GAET_REMOTE_DB" -tAc \
                "SELECT round(pg_database_size('${GAET_REMOTE_DB}')/1024.0/1024.0,1) || ' MB';" 2>/dev/null || echo "?")
            status_arrow "Size: ${ssize}"
        else
            echo -e "${R}FAIL${NC}"; all_ok=false
        fi
    else
        echo -e "${Y}LEWAT${NC}"
        status_arrow "Set GAET_REMOTE_URL di ${GAET_CONFIG_DIR}/.env"
    fi

    # Backup dir
    echo -n "  ${C}📁${NC}  Direktori backup... "
    if [ -d "$GAET_BACKUP_DIR" ] && [ -w "$GAET_BACKUP_DIR" ]; then
        echo -e "${G}OK${NC} ${D}${GAET_BACKUP_DIR}${NC}"
        local count=$(find "$GAET_BACKUP_DIR" -name "*.dump" 2>/dev/null | wc -l)
        status_arrow "Backup tersimpan: ${count}"
    else
        mkdir -p "$GAET_BACKUP_DIR" 2>/dev/null && echo -e "${Y}DIBUAT${NC}" || { echo -e "${R}FAIL${NC}"; all_ok=false; }
    fi

    # Auto-backup
    echo -n "  ${C}⏰${NC}  Auto-backup timer... "
    if systemctl --user is-active "${GAET_SERVICE_PREFIX}-backup.timer" &>/dev/null 2>&1; then
        local next
        next=$(systemctl --user show "${GAET_SERVICE_PREFIX}-backup.timer" -p NextElapseUSecRealtime 2>/dev/null | cut -d= -f2-)
        echo -e "${G}AKTIF${NC}"
        status_arrow "Next: ${next}"
    else
        echo -e "${Y}tidak aktif${NC}"
        status_arrow "Aktifkan dengan: gaet push --auto"
    fi

    echo ""
    if $all_ok; then
        echo -e "  ${G}${ICON_OK}${NC}  ${B}Semua cek berhasil!${NC}"
    else
        echo -e "  ${Y}${ICON_WARN}${NC}  ${B}Ada yang gagal — perbaiki dulu sebelum backup.${NC}"
        return 1
    fi
}

cmd_status() {
    load_env
    local json_mode=false
    [ "${1:-}" = "--json" ] && json_mode=true

    if $json_mode; then
        python3 -c "
import sys, json, os
for p in ['${SCRIPT_DIR}/scripts', '${SCRIPT_DIR}', '${HOME}/.local/bin', '${HOME}/.gaet', '${HOME}/.hermes/scripts']:
    sys.path.insert(0, p)
try:
    from status import get_status
    print(json.dumps(get_status()))
except Exception as e:
    print(json.dumps({'error': str(e), 'memories': 0, 'synced': False}))
" 2>/dev/null || echo '{"error":"status module unavailable"}'
        return
    fi

    find_pg_tools
    export PGPASSWORD="${GAET_LOCAL_DB_PASS:-hindsight}"
    local h="${GAET_LOCAL_DB_HOST:-127.0.0.1}"
    local p="${GAET_LOCAL_DB_PORT:-5432}"
    local u="${GAET_LOCAL_DB_USER:-hindsight}"
    local n="${GAET_LOCAL_DB_NAME:-hindsight}"

    box_title "${GAET_NAME} status"

    # Last backup
    local latest=$(ls -t "$GAET_BACKUP_DIR"/*.dump 2>/dev/null | head -1)
    if [ -n "$latest" ]; then
        local size=$(du -h "$latest" | cut -f1)
        local bdate=$(date -r "$latest" '+%Y-%m-%d %H:%M:%S')
        status_ok "Backup terakhir: ${bdate} ${D}(${size})${NC}"
    else
        status_warn "Belum pernah backup"
    fi
    local count=$(find "$GAET_BACKUP_DIR" -name "*.dump" 2>/dev/null | wc -l)
    status_arrow "Total backup: ${count}"

    echo ""

    # Local
    box_section "Database Lokal"
    local loc_out
    loc_out=$("${PSQL}" -h "$h" -p "$p" -U "$u" -d "$n" -tAc "SELECT count(*) || ' memories' FROM memory_units;" 2>/dev/null)
    if [ -n "$loc_out" ]; then
        echo -e "    ${G}${ICON_OK}${NC}  ${loc_out}"
        local loc_size
        loc_size=$("${PSQL}" -h "$h" -p "$p" -U "$u" -d "$n" -tAc \
            "SELECT round(pg_database_size('${n}')/1024.0/1024.0,1) || ' MB';" 2>/dev/null || echo "?")
        status_arrow "Size: ${loc_size}"
    else
        echo -e "    ${Y}tidak tersedia${NC}"
    fi

    # Cloud
    if load_remote_url 2>/dev/null; then
        echo ""
        box_section "Cloud Database"
        export PGPASSWORD="$GAET_REMOTE_PASS"
        local cloud_out=$(PGSSLMODE="$GAET_REMOTE_SSLMODE" "${PSQL}" -h "$GAET_REMOTE_HOST" \
            -p "$GAET_REMOTE_PORT" -U "$GAET_REMOTE_USER" -d "$GAET_REMOTE_DB" \
            -tAc "SELECT count(*) || ' memories' FROM memory_units;" 2>/dev/null)
        if [ -n "$cloud_out" ]; then
            echo -e "  ${G}${ICON_OK}${NC}  ${cloud_out}"
        else
            echo -e "  ${Y}tidak terjangkau${NC}"
        fi
    fi

    # Cron
    echo ""
    if systemctl --user is-active "${GAET_SERVICE_PREFIX}-backup.timer" &>/dev/null 2>&1; then
        local next=$(systemctl --user show "${GAET_SERVICE_PREFIX}-backup.timer" \
            -p NextElapseUSecRealtime 2>/dev/null | cut -d= -f2-)
        status_ok "Auto-backup aktif • ${D}Next: ${next}${NC}"
    else
        status_warn "Auto-backup tidak aktif"
    fi
}

cmd_push() {
    acquire_lock
    check_tools
    check_local_db
    load_remote_url || die "GAET_REMOTE_URL belum diisi"

    log "🚀 Push: local → cloud"
    box_title "gaet push"

    # Step 1: Local dump
    echo -e "  ${C}📦${NC}  ${B}Dumping database lokal...${NC}"
    local backup_file="${GAET_BACKUP_DIR}/gaet_${TIMESTAMP}.dump"
    export PGPASSWORD="${GAET_LOCAL_DB_PASS:-hindsight}"
    if "${PG_DUMP}" -h "${GAET_LOCAL_DB_HOST:-127.0.0.1}" -p "${GAET_LOCAL_DB_PORT:-5432}" \
        -U "${GAET_LOCAL_DB_USER:-hindsight}" -d "${GAET_LOCAL_DB_NAME:-hindsight}" \
        --format=custom --compress=9 --file="$backup_file" 2>>"$GAET_LOG_FILE"; then
        local size=$(du -h "$backup_file" | cut -f1)
        echo -e "    ${G}${ICON_OK}${NC}  Dump tersimpan ${D}(${size})${NC}"
        # Verify dump integrity
        if ! "${PG_RESTORE}" --list "$backup_file" &>/dev/null; then
            rm -f "$backup_file"
            die "Dump korup — backup dibatalkan"
        fi
    else
        echo -e "    ${R}${ICON_FAIL}${NC}  Dump gagal!"
        rm -f "$backup_file"
        exit 2
    fi

    # Step 2: Restore to cloud with timeout
    echo -e "  ${C}☁️${NC}   ${B}Mensinkronkan ke cloud...${NC}"
    export PGPASSWORD="$GAET_REMOTE_PASS"
    if timeout 120 "${PG_RESTORE}" -h "$GAET_REMOTE_HOST" -p "$GAET_REMOTE_PORT" \
        -U "$GAET_REMOTE_USER" -d "$GAET_REMOTE_DB" \
        --clean --if-exists --no-owner --no-acl \
        "$backup_file" >>"$GAET_LOG_FILE" 2>&1; then
        echo -e "    ${G}${ICON_OK}${NC}  Sinkronisasi selesai!"
    else
        echo -e "    ${Y}${ICON_WARN}${NC}  Sinkronisasi selesai (dengan peringatan)"
    fi

    # Step 3: Retention
    find "$GAET_BACKUP_DIR" -name "gaet_*.dump" -type f -mtime +$GAET_RETENTION_DAYS -delete 2>/dev/null || true

    echo ""
    echo -e "  ${G}${ICON_OK}${NC}  ${B}Push selesai!${NC}"
    log "✅ Push complete"
}

cmd_fetch() {
    acquire_lock
    check_tools
    check_local_db
    load_remote_url || die "GAET_REMOTE_URL belum diisi"

    log "⬇️  Fetch: cloud → local"
    box_title "gaet fetch"

    # Step 1: Cloud dump
    echo -e "  ${C}☁️${NC}   ${B}Dumping database cloud...${NC}"
    export PGPASSWORD="$GAET_REMOTE_PASS"
    local fetch_file="${GAET_BACKUP_DIR}/cloud_${TIMESTAMP}.dump"
    if PGSSLMODE="$GAET_REMOTE_SSLMODE" "${PG_DUMP}" -h "$GAET_REMOTE_HOST" -p "$GAET_REMOTE_PORT" \
        -U "$GAET_REMOTE_USER" -d "$GAET_REMOTE_DB" \
        --format=custom --compress=9 --file="$fetch_file" 2>>"$GAET_LOG_FILE"; then
        local size=$(du -h "$fetch_file" | cut -f1)
        echo -e "    ${G}${ICON_OK}${NC}  Dump cloud tersimpan ${D}(${size})${NC}"
    else
        echo -e "    ${R}${ICON_FAIL}${NC}  Dump cloud gagal!"
        rm -f "$fetch_file"
        exit 2
    fi

    # Step 2: Restore to local
    echo -e "  ${C}💾${NC}  ${B}Merestore ke database lokal...${NC}"
    export PGPASSWORD="${GAET_LOCAL_DB_PASS:-hindsight}"
    "${PSQL}" -h "${GAET_LOCAL_DB_HOST:-127.0.0.1}" -p "${GAET_LOCAL_DB_PORT:-5432}" \
        -U "${GAET_LOCAL_DB_USER:-hindsight}" -d "${GAET_LOCAL_DB_NAME:-hindsight}" -tAc \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${GAET_LOCAL_DB_NAME:-hindsight}' AND pid <> pg_backend_pid();" \
        2>/dev/null || true

    "${PG_RESTORE}" -h "${GAET_LOCAL_DB_HOST:-127.0.0.1}" -p "${GAET_LOCAL_DB_PORT:-5432}" \
        -U "${GAET_LOCAL_DB_USER:-hindsight}" -d "${GAET_LOCAL_DB_NAME:-hindsight}" \
        --clean --if-exists "$fetch_file" >>"$GAET_LOG_FILE" 2>&1

    if [ $? -le 1 ]; then
        echo -e "    ${G}${ICON_OK}${NC}  Restore lokal selesai!"
    else
        echo -e "    ${Y}${ICON_WARN}${NC}  Restore selesai (dengan peringatan)"
    fi

    rm -f "$fetch_file"
    echo ""
    echo -e "  ${G}${ICON_OK}${NC}  ${B}Fetch selesai!${NC}"
    log "⬇️  Fetch complete"
}

cmd_push_cron() {
    load_env
    load_remote_url || { cronlog "❌ GAET_REMOTE_URL tidak dikonfigurasi"; exit 1; }
    find_pg_tools

    cronlog "📦 [cron] Mulai auto-backup..."
    local cron_file="${GAET_BACKUP_DIR}/cron_${TIMESTAMP}.dump"
    export PGPASSWORD="${GAET_LOCAL_DB_PASS:-hindsight}"

    if "${PG_DUMP}" -h "${GAET_LOCAL_DB_HOST:-127.0.0.1}" -p "${GAET_LOCAL_DB_PORT:-5432}" \
        -U "${GAET_LOCAL_DB_USER:-hindsight}" -d "${GAET_LOCAL_DB_NAME:-hindsight}" \
        --format=custom --compress=9 --file="$cron_file" 2>>"$GAET_CRON_LOG"; then
        export PGPASSWORD="$GAET_REMOTE_PASS"
        if PGSSLMODE="$GAET_REMOTE_SSLMODE" "${PG_RESTORE}" -h "$GAET_REMOTE_HOST" \
            -p "$GAET_REMOTE_PORT" -U "$GAET_REMOTE_USER" -d "$GAET_REMOTE_DB" \
            --clean --if-exists --no-owner --no-acl \
            "$cron_file" 2>>"$GAET_CRON_LOG"; then
            local size=$(du -h "$cron_file" | cut -f1)
            cronlog "✅ [cron] Backup sukses (${size})"
        else
            cronlog "⚠️ [cron] Restore bermasalah"
        fi
    else
        cronlog "❌ [cron] Dump lokal gagal!"
    fi
    rm -f "$cron_file"
    find "$GAET_BACKUP_DIR" -name "cron_*.dump" -type f -delete 2>/dev/null || true
}

cmd_auto_on() {
    local interval="${1:-${GAET_AUTO_INTERVAL:-6}}"
    if ! [[ "$interval" =~ ^[1-9]$|^1[0-9]$|^2[0-3]$ ]]; then
        die "Interval harus 1-23 jam."
    fi

    box_title "Auto-backup"
    status_info "Mengaktifkan auto-backup setiap ${interval} jam..."

    mkdir -p "$HOME/.config/systemd/user"

    cat > "$HOME/.config/systemd/user/${GAET_SERVICE_PREFIX}-backup.service" << EOF
[Unit]
Description=${GAET_NAME} backup to remote database
After=network.target

[Service]
Type=oneshot
ExecStart=%h/.local/bin/${GAET_NAME} push --cron
StandardOutput=append:%h/${GAET_BACKUP_DIR##$HOME/}/cron.log
StandardError=append:%h/${GAET_BACKUP_DIR##$HOME/}/cron.log
EOF

    cat > "$HOME/.config/systemd/user/${GAET_SERVICE_PREFIX}-backup.timer" << EOF
[Unit]
Description=${GAET_NAME} periodic backup (every ${interval}h)
Requires=${GAET_SERVICE_PREFIX}-backup.service

[Timer]
OnCalendar=*-*-* 00/0${interval}:00:00
Persistent=true
RandomizedDelaySec=30

[Install]
WantedBy=timers.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable --now "${GAET_SERVICE_PREFIX}-backup.timer" 2>/dev/null || \
        warn "Gagal enable timer (systemd user session berjalan?)"

    if systemctl --user is-active "${GAET_SERVICE_PREFIX}-backup.timer" &>/dev/null 2>&1; then
        local next=$(systemctl --user show "${GAET_SERVICE_PREFIX}-backup.timer" \
            -p NextElapseUSecRealtime 2>/dev/null | cut -d= -f2-)
        echo -e "    ${G}${ICON_OK}${NC}  Auto-backup aktif!"
        echo -e "    ${D}${ICON_ARROW}${NC}  Next: ${next}"
    fi
}

cmd_stop_auto() {
    status_info "Menghentikan auto-backup..."
    systemctl --user disable --now "${GAET_SERVICE_PREFIX}-backup.timer" 2>/dev/null || true
    systemctl --user disable --now "${GAET_SERVICE_PREFIX}-backup.service" 2>/dev/null || true
    status_ok "Auto-backup dihentikan"
}

cmd_log() {
    local lines="${1:-30}"
    [[ "$lines" =~ ^[0-9]+$ ]] || lines=30
    if [ ! -f "$GAET_LOG_FILE" ]; then
        echo -e "  ${Y}Belum ada log. Jalankan 'gaet push' dulu.${NC}"
        return
    fi
    local total=$(wc -l < "$GAET_LOG_FILE")
    local start=$((total - lines))
    [ "$start" -lt 1 ] && start=1
    box_title "${GAET_NAME} log"
    echo -e "  ${D}${total} baris terakhir (menampilkan ${lines})${NC}"
    echo ""
    sed -n "${start},${total}p" "$GAET_LOG_FILE" | while IFS= read -r line; do
        echo -e "  ${D}│${NC} $line"
    done
}

cmd_serve() {
    # Cari dashboard di beberapa lokasi
    local dashboard_dir=""
    for cand in         "${SCRIPT_DIR}/dashboard"         "${HOME}/Projects/gaet/dashboard"         "${GAET_CONFIG_DIR}/dashboard"         "${HOME}/.local/share/gaet/dashboard"; do
        if [ -d "$cand" ] && [ -f "${cand}/package.json" ]; then
            dashboard_dir="$cand"
            break
        fi
    done

    if [ -z "$dashboard_dir" ]; then
        die "Dashboard tidak ditemukan. Pastikan kamu menjalankan gaet dari folder proyek."
    fi

    local dist_dir="${dashboard_dir}/.next"
    local port="${GAET_DASHBOARD_PORT:-9191}"
    local host="${GAET_DASHBOARD_HOST:-0.0.0.0}"

    box_title "${GAET_NAME} serve"

    # Build if not built
    if [ ! -d "$dist_dir" ]; then
        echo -e "  ${C}📦${NC}  ${B}Membangun dashboard...${NC}"
        cd "$dashboard_dir"
        if [ ! -d "node_modules" ]; then
            npm install --silent 2>&1 | tail -1
        fi
        if npm run build 2>&1; then
            echo -e "    ${G}${ICON_OK}${NC}  Build selesai!"
        else
            die "Build dashboard gagal. Coba manual: cd ${dashboard_dir} && npm install && npm run build"
        fi
    fi

    # Setup systemd service
    local service_file="$HOME/.config/systemd/user/${GAET_SERVICE_PREFIX}-dashboard.service"
    mkdir -p "$HOME/.config/systemd/user"

    cat > "$service_file" << EOF
[Unit]
Description=${GAET_NAME} Dashboard (Next.js)
After=network.target

[Service]
Type=simple
Environment=PORT=${port}
Environment=HOST=${host}
ExecStart=$(which node) ${dashboard_dir}/node_modules/.bin/next start ${dashboard_dir} --port ${port}
Restart=on-failure
RestartSec=3
WorkingDirectory=${dashboard_dir}

[Install]
WantedBy=default.target
EOF

    # Enable linger (user session survives reboot)
    if command -v loginctl &>/dev/null; then
        loginctl enable-linger 2>/dev/null || true
    fi

    systemctl --user daemon-reload
    systemctl --user enable --now "${GAET_SERVICE_PREFIX}-dashboard.service" 2>&1

    echo ""
    if systemctl --user is-active "${GAET_SERVICE_PREFIX}-dashboard.service" &>/dev/null; then
        echo -e "  ${G}${ICON_OK}${NC}  ${B}Dashboard aktif!${NC}"
        echo -e "  ${D}${ICON_ARROW}${NC}  http://localhost:${port}"
        echo -e "  ${D}${ICON_ARROW}${NC}  systemctl --user status ${GAET_SERVICE_PREFIX}-dashboard.service"
        echo -e "  ${D}${ICON_ARROW}${NC}  journalctl --user -u ${GAET_SERVICE_PREFIX}-dashboard.service -f"
    else
        status_fail "Gagal memulai dashboard"
        journalctl --user -u "${GAET_SERVICE_PREFIX}-dashboard.service" --no-pager -n 20 2>&1
    fi
}

# ─── MAIN ──────────────────────────────────────────────────────
load_env

case "${1:-}" in
    --version|-v) version; exit 0 ;;
    --help|-h)    usage; exit 0 ;;
esac

mkdir -p "$GAET_BACKUP_DIR"

case "${1:-status}" in
    init)
        cmd_init
        ;;
    push)
        shift
        case "${1:-}" in
            --cron)     cmd_push_cron ;;
            --auto)     cmd_auto_on "${2:-6}" ;;
            --auto=*)   cmd_auto_on "${1#--auto=}" ;;
            *)          cmd_push ;;
        esac
        ;;
    fetch)
        cmd_fetch
        ;;
    status)
        shift
        cmd_status "$@"
        ;;
    check)
        cmd_check
        ;;
    log)
        shift
        cmd_log "${1:-30}"
        ;;
    serve)
        cmd_serve
        ;;
    stop)
        cmd_stop_auto
        ;;
    *)
        echo -e "  ${Y}gaet: perintah tidak dikenal '${1:-}'${NC}"
        echo -e "  ${D}Coba 'gaet --help' untuk daftar perintah.${NC}"
        exit 1
        ;;
esac
