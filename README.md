# gaet

**Database Backup & Sync CLI** — Backup PostgreSQL lokal ke cloud (Supabase, Neon, RDS, atau VPS sendiri).

```bash
gaet check          # Verifikasi semua koneksi
gaet push           # Backup lokal → cloud
gaet status         # Status sinkronisasi
gaet serve          # Dashboard web
```

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey)

---

## Features

| Feature | Description |
|---------|-------------|
| 🔒 Concurrency lock | Cegah backup berjalan bersamaan |
| ⏱️ 120s timeout | Koneksi cloud tidak hang selamanya |
| ✅ Integrity check | Dump diverifikasi sebelum upload |
| 📦 Compressed dumps | Format custom, kompresi level 9 |
| 🧹 Auto-retention | Backup lama dihapus otomatis (default 7 hari) |
| 🔄 Auto-backup | Periodik via systemd / launchd / Task Scheduler |
| 🚀 Web dashboard | Next.js 15 — real-time status, satu klik push/fetch |
| 🔌 Multi-cloud | Supabase, Neon, RDS, atau PostgreSQL VPS sendiri |
| 🌓 Light/Dark mode | Dashboard mendukung tema terang dan gelap |
| 📊 Sync visualization | Tabel sinkronisasi dengan progress bar |

---

## Platform Support

| Platform | CLI | Auto-backup | Dashboard Service |
|----------|-----|-------------|-------------------|
| 🐧 Linux | ✅ Full | systemd user timer | systemd user service |
| 🍎 macOS | ✅ Full | launchd timer | launchd agent |
| 🪟 Windows | ✅ Full | Task Scheduler | Background PID |

**gaet murni Python** — zero dependency pip. Cuma butuh PostgreSQL tools.

---

## Requirements

| Dependency | Required? | Catatan |
|------------|-----------|---------|
| Python 3.8+ | ✅ Required | CLI utama |
| PostgreSQL tools | ✅ Required | `pg_dump`, `pg_restore`, `psql` |
| Node.js 18+ | ⚠️ Dashboard only | Untuk web dashboard |
| Cloud PostgreSQL | ✅ Required | Target backup (Supabase/Neon/RDS/VPS) |

---

## Quick Start

### 1. Install

```bash
# Clone dan install
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
bash install.sh

# Atau auto-pilot
bash install.sh --yes
```

### 2. Konfigurasi

```bash
# Jalankan wizard
gaet init

# Atau edit manual
nano ~/.gaet/.env
```

**Minimal config** — cuma 2 baris yang wajib diisi:

```env
# Database lokal (default: hindsight@127.0.0.1:5432/hindsight)
GAET_LOCAL_URL=postgresql://user:pass@127.0.0.1:5432/db

# Database cloud (WAJIB)
GAET_REMOTE_URL=postgresql://user:pass@host:5432/db
```

### 3. Backup Pertama

```bash
gaet check        # Verifikasi koneksi
gaet push         # Backup lokal → cloud
gaet status       # Cek status
gaet serve        # Buka dashboard
```

---

## Commands

| Command | Deskripsi |
|---------|-----------|
| `gaet init` | Setup wizard interaktif |
| `gaet init hindsight` | Setup dengan preset Hindsight |
| `gaet push` | Backup lokal → cloud |
| `gaet fetch` | Restore cloud → lokal |
| `gaet status` | Tabel sinkronisasi |
| `gaet status --json` | Status JSON untuk scripting |
| `gaet check` | Validasi konfigurasi & koneksi |
| `gaet log [N]` | Lihat N baris log terakhir |
| `gaet push --auto[=N]` | Auto-backup tiap N jam (default 6) |
| `gaet stop` | Hentikan auto-backup & dashboard |
| `gaet stop --scheduler` | Hentikan auto-backup saja |
| `gaet stop --dashboard` | Hentikan dashboard saja |
| `gaet serve` | Jalankan dashboard web |
| `gaet update` | Update ke versi terbaru dari GitHub |
| `gaet update --force` | Force update (skip perubahan lokal) |
| `gaet --version` | Tampilkan versi |
| `gaet --help` | Tampilkan bantuan |

---

## How Push/Fetch Works

```
┌─────────────┐    pg_dump     ┌──────────────┐    pg_restore    ┌──────────────┐
│  Local DB   │ ──────────────→│  .dump file   │ ──────────────→ │  Cloud DB    │
│  (source)   │  (compressed)  │  (temp file)  │  (auto-create)  │  (target)    │
└─────────────┘                └──────────────┘                 └──────────────┘
```

**Step 1:** `pg_dump` — Ambil semua dari database lokal
**Step 2:** Integrity check — Validasi dump sebelum upload
**Step 3:** `pg_restore` — Restore ke cloud dengan cleanup flags
**Step 4:** Retention — Hapus backup lama (default 7 hari)

**Yang di-auto-detect:**
- ✅ Semua tabel (schema)
- ✅ Semua data
- ✅ Indexes & sequences
- ✅ Foreign keys & constraints
- ✅ Extensions (pgvector, dll)

---

## Presets

gaet works dengan **PostgreSQL database manapun**. Untuk database populer, presets auto-configure:

| Preset | Deskripsi | Usage |
|--------|-----------|-------|
| `hindsight` | Hindsight AI memory database | `gaet init hindsight` |

```bash
# Generic (database apapun)
gaet init

# Dengan preset
gaet init hindsight
```

**Custom presets:** Edit dict `PRESETS` di `gaet.py`.

---

## Auto-Backup

```bash
# Aktifkan auto-backup (default: tiap 6 jam)
gaet push --auto

# Tiap 3 jam
gaet push --auto=3

# Hentikan
gaet stop
```

**Platform-specific commands:**

| Platform | Cek Status | Hapus |
|----------|------------|-------|
| 🐧 Linux | `systemctl --user list-timers` | `gaet stop --scheduler` |
| 🍎 macOS | `launchctl list \| grep gaet` | `gaet stop --scheduler` |
| 🪟 Windows | `schtasks /Query /TN "gaet-backup"` | `gaet stop --scheduler` |

---

## Dashboard Web

Dashboard Next.js 15 dengan Tailwind CSS v4. Running di background via systemd/launchd.

```bash
# Start
gaet serve

# Buka di browser
http://localhost:9191
```

### Fitur Dashboard
- Real-time sync status (auto-refresh 8 detik)
- Tabel sinkronisasi per-database
- Tombol push/fetch satu klik
- Indikator auto-backup
- Light/Dark mode toggle
- Responsive design (mobile-first)

### Manage Service

```bash
# Status
gaet status --json

# Log
journalctl --user -u gaet-dashboard.service -f

# Restart
gaet stop --dashboard
gaet serve
```

---

## Configuration

Semua config di `~/.gaet/.env`:

| Variable | Default | Deskripsi |
|----------|---------|-----------|
| `GAET_REMOTE_URL` | — | PostgreSQL URL cloud (WAJIB) |
| `GAET_LOCAL_URL` | `postgresql://postgres:@127.0.0.1:5432/postgres` | Database lokal |
| `GAET_TABLES` | *(auto-discover)* | Comma-separated table list |
| `GAET_RETENTION_DAYS` | `7` | Hari penyimpanan backup |
| `GAET_DASHBOARD_PORT` | `9191` | Port dashboard web |
| `GAET_DASHBOARD_HOST` | `0.0.0.0` | Dashboard bind address |
| `GAET_AUTO_INTERVAL` | `6` | Interval auto-backup (jam) |
| `GAET_SERVICE_PREFIX` | `gaet` | Prefix nama service |
| `GAET_PG_DUMP` | *(auto-detect)* | Path ke pg_dump |
| `GAET_PG_RESTORE` | *(auto-detect)* | Path ke pg_restore |
| `GAET_PSQL` | *(auto-detect)* | Path ke psql |
| `GAET_REMOTE_SSLMODE` | `require` | SSL mode untuk cloud |
| `GAET_PROJECT_DIR` | — | Override project root |

---

## Project Structure

```
gaet/
├── gaet.py                  # CLI utama (Python, ~2000 baris)
├── install.sh               # Universal installer
├── .env.example             # Template konfigurasi
├── README.md                # Dokumentasi ini
├── dashboard/               # Next.js 15 app
│   ├── app/
│   │   ├── page.tsx         # Dashboard utama
│   │   ├── globals.css      # Dark/Light theme
│   │   ├── layout.tsx       # Layout & fonts
│   │   └── api/             # API routes
│   ├── public/              # Static assets (logo)
│   ├── package.json
│   └── next.config.ts
└── scripts/
    ├── __init__.py
    ├── status.py            # Status module
    ├── scheduler.py         # Systemd/launchd/Task Scheduler
    ├── service_manager.py   # Dashboard service
    └── installer.py         # Universal installer
```

---

## Development

```bash
# Jalankan dari source
python gaet.py --help

# Test tanpa PostgreSQL
python gaet.py status --json

# Build dashboard
cd dashboard
npm install
npm run build

# Run dashboard foreground (debug)
python gaet.py serve
```

### Testing

| Platform | Status |
|----------|--------|
| 🐧 Linux | ✅ systemd --user |
| 🍎 macOS | ✅ launchd (code ready) |
| 🪟 Windows | ✅ Task Scheduler + PID file |

---

## Dependencies

**Python: 0 external packages** — stdlib only, no `pip install` needed.

**External tools:**
- `pg_dump`, `pg_restore`, `psql` — PostgreSQL (auto-detect)
- `node`, `npm` — Node.js (dashboard only)
- `systemctl` / `launchctl` / `schtasks` — Auto-detected

---

## Troubleshooting

### `gaet check` gagal
- Pastikan PostgreSQL tools terinstall: `which pg_dump pg_restore psql`
- Cek config: `cat ~/.gaet/.env`
- Test koneksi: `gaet check`

### Dashboard tidak bisa diakses
- Cek service: `gaet stop --dashboard && gaet serve`
- Cek log: `journalctl --user -u gaet-dashboard.service -f`
- Pastikan port 9191 belum dipakai: `lsof -i :9191`

### Auto-backup tidak jalan
- Cek timer: `systemctl --user list-timers | grep gaet`
- Restart: `gaet stop --scheduler && gaet push --auto`

### `gaet update` tidak bisa jalan
- Cek perubahan lokal: `git status`
- Force update: `gaet update --force`

---

## FAQ

**Q: gaet support database selain PostgreSQL?**
A: Belum. gaet dirancang khusus untuk PostgreSQL ecosystem.

**Q: Bisa backup ke S3/GCS langsung?**
A: Ga. gaet backup ke PostgreSQL cloud (Supabase, Neon, RDS). Kalau butuh object storage, pertimbangkan tool lain.

**Q: Berapa lama backup disimpan?**
A: Default 7 hari. Atur dengan `GAET_RETENTION_DAYS`.

**Q: Apakah aman?**
A: Ya. gaet tidak simpan password di logs. Semua credential hanya di `~/.gaet/.env` dengan permission 600.

---

## License

MIT License

---

## Links

- **GitHub**: [github.com/ghanirahmans/gaet](https://github.com/ghanirahmans/gaet)
- **Issues**: [github.com/ghanirahmans/gaet/issues](https://github.com/ghanirahmans/gaet/issues)

---

*gaet v1.0.0 — dirancang sebagai safety net untuk database-mu.*
