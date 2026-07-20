# gaet — Database Backup & Sync

Backup database PostgreSQL lokal ke cloud (Supabase, Neon, RDS, VPS), dengan CLI cantik dan dashboard Next.js.

```bash
gaet check        # Verifikasi semua koneksi
gaet push         # Backup lokal → cloud
gaet status       # Cek status sinkronisasi
gaet serve        # Buka dashboard web
```

## Instalasi

```bash
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
bash install.sh
```

Atau langsung:

```bash
curl -fsSL https://raw.githubusercontent.com/ghanirahmans/gaet/main/install.sh | bash
```

## Quick Start

Butuh database PostgreSQL tujuan (cloud). Ga usah takut — cuma 3 langkah:

```bash
# 1. Install
git clone https://github.com/ghanirahmans/gaet.git
cd gaet
bash install.sh

# 2. Isi GAET_REMOTE_URL (satu-satunya yang wajib)
nano ~/.gaet/.env

# 3. Backup pertama!
gaet check        # Cek semua koneksi
gaet push         # Backup ke cloud
gaet serve        # Dashboard web (http://localhost:9191)
```

**Cuma butuh 1 hal:** connection string ke database PostgreSQL cloud-mu.
Bisa dari Supabase, Neon, atau VPS sendiri. Formatnya:

```
postgresql://user:password@host:5432/nama_database
```

Database lokal pake PostgreSQL yang udah jalan di mesinmu.
Default-nya konek ke `hindsight@127.0.0.1:5432/hindsight` — ganti di `~/.gaet/.env` kalo beda.

## Konfigurasi

Semua konfigurasi di satu file: `~/.gaet/.env`

```env
GAET_REMOTE_URL=postgresql://user:pass@host:5432/db
GAET_LOCAL_DB_HOST=127.0.0.1
GAET_RETENTION_DAYS=7
```

Lihat `.env.example` untuk semua opsi lengkap dengan dokumentasi tiap variable.

## Perintah

| Perintah | Keterangan |
|----------|------------|
| `gaet init` | Setup wizard interaktif |
| `gaet push` | Backup lokal → cloud |
| `gaet fetch` | Restore cloud → lokal |
| `gaet status` | Status sinkronisasi (dengan tabel) |
| `gaet status --json` | Status dalam format JSON |
| `gaet check` | Validasi konfigurasi & koneksi |
| `gaet log` | Lihat log backup |
| `gaet push --auto[=N]` | Auto-backup tiap N jam (default 6) |
| `gaet stop` | Hentikan auto-backup |
| `gaet serve` | Jalankan dashboard (systemd service) |

## Dashboard Web

Dashboard dibangun dengan **Next.js 15 + Tailwind CSS v4** dan jalan sebagai **production server** (bukan dev mode).

```bash
# Cukup sekali jalan:
gaet serve

# Dashboard langsung aktif di http://localhost:9191
# - Auto-build jika belum dibangun
# - Jalan sebagai systemd user service
# - Auto-restart jika crash
# - Linger enabled (tahan reboot)
```

### Fitur Dashboard
- Status real-time (auto-refresh tiap 8 detik)
- Tabel sinkronisasi per-database (9 tabel)
- Tombol push/fetch satu klik
- Indikator auto-backup + timer
- Dark theme premium
- API endpoint: `/api/status`, `/api/push`, `/api/fetch`, `/api/stop`

### Manajemen Dashboard

```bash
# Status service
systemctl --user status gaet-dashboard.service

# Lihat log real-time
journalctl --user -u gaet-dashboard.service -f

# Restart
systemctl --user restart gaet-dashboard.service

# Stop
systemctl --user stop gaet-dashboard.service
```

## Production Features

| Fitur | Keterangan |
|-------|------------|
| 🔒 **Concurrency lock** | Cegah bentrok backup berjalan bersamaan |
| ⏱️ **Timeout 120s** | Koneksi cloud tidak akan hang selamanya |
| ✅ **Integrity check** | Dump diverifikasi sebelum dikirim ke cloud |
| 🔄 **Auto-retry via systemd** | Service restart otomatis jika crash |
| 🛡️ **Password via env** | Credential tidak pernah tampil di CLI |
| 📦 **Compressed dump** | Format custom dengan kompresi level 9 |
| 🧹 **Retensi otomatis** | Backup lama dihapus otomatis (default 7 hari) |
| 🔌 **Multi-cloud** | Bisa pakai Supabase, Neon, RDS, VPS sendiri |

## Requirements

- Python 3
- PostgreSQL tools (`pg_dump`, `pg_restore`, `psql`)
- Node.js 18+ (untuk dashboard)
- systemd (untuk service management, opsional)
- PostgreSQL cloud target (Supabase, Neon, RDS, VPS, atau server sendiri)

## Struktur Project

```
~/Projects/gaet/
├── gaet                    # CLI utama (bash, ~800 lines)
├── install.sh              # Installer
├── .env.example            # Template konfigurasi lengkap
├── scripts/
│   └── status.py           # Modul status (Python)
├── dashboard/              # Next.js 15 app
│   ├── app/
│   │   ├── page.tsx        # Dashboard utama (280 lines)
│   │   ├── globals.css     # Dark theme premium
│   │   └── api/            # 4 API routes
│   ├── package.json
│   └── next.config.ts
└── systemd/                # Service files (auto-generated)
    ├── gaet-dashboard.service
    ├── gaet-backup.service
    └── gaet-backup.timer
```

## Lisensi

MIT
