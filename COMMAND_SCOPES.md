# Gaet CLI — Architecture & Comprehensive Command Scope Specification

Dokumen ini mendefinisikan secara ketat batasan (*scope*), tanggung jawab (*responsibility*), dan perilaku input/output dari **seluruh 18 perintah CLI `gaet` (v3.0.x)** untuk menjamin transparansi, keandalan, dan konsistensi standar *Git-style*.

---

## 📐 4 Pilar Utama Arsitektur Command Gaet

1. **Single Responsibility Principle (SRP)**: Setiap perintah hanya menangani 1 tugas spesifik. `check` tidak boleh menjalankan wizard `init`, `push` tidak boleh meminta input setup, dst.
2. **Zero Surprises (Git Parity)**: Perintah *read-only* (`status`, `check`, `diff`, `doctor`, `log`, `get`, `export`) **DILARANG HARAM** meminta input interaktif, mengubah file `.env`, atau menggantung terminal.
3. **Graceful Failures**: Jika terjadi kegagalan (seperti koneksi DB mati atau password salah), CLI harus langsung *exit* seketika (< 0.1 detik) dengan kode kesalahan yang tepat dan pesan manusiawi.
4. **Safety Guards**: Perintah destruktif yang mengubah data (`fetch` menimpa DB lokal, `uninstall` menghapus file) **WAJIB** meminta konfirmasi manual atau menuntut flag `--yes` jika dijalankan non-interaktif.

---

## 📋 Matriks Spesifikasi Scope Lengkap (18 Perintah)

### 🚀 Kategori 1: Setup & Lifecycle (Inisialisasi & Pengelolaan Aplikasi)

| Command | Scope & Tanggung Jawab | Sifat Perintah | Input Interaktif? | Ekspektasi Saat Gagal / Exit Code | Batasan Ketat (*Strict Boundaries*) |
|---|---|---|---|---|---|
| **`gaet init`** | Setup wizard interaktif, inisialisasi `.env`, dan pembentukan workspace git (`~/.gaet` atau `GAET_DIR`). | Setup / Wizard | **YA** (Flat Numbered Menu 1-2-U-M-D-Q) | Non-zero jika dibatalkan (Ctrl+C) / Error IO | **Satu-satunya** perintah yang berhak menjalankan setup wizard interaktif dan membuat file `.env` baru. |
| **`gaet install`** | Memasang executable `gaet` dan symlink ke PATH sistem (`/usr/local/bin`). | System Install | **TIDAK** (Kecuali butuh `sudo`) | Non-zero jika izin ditolak | Tidak pernah menyentuh koneksi database. Hanya mengurus binary/PATH. |
| **`gaet update`** | Memperbarui kode sumber/paket `gaet` ke versi terbaru dari git/PyPI. | System Update | **TIDAK** | Non-zero jika jaringan/git gagal | Hanya memperbarui paket CLI `gaet`, tidak mengubah isi file `.env`. |
| **`gaet uninstall`** | Menghapus binary `gaet`, symlink, timer auto-backup, dan direktori konfigurasi. | Destructive System | **YA** (Konfirmasi `y/N`) / `--yes` flag | Non-zero jika dibatalkan | Meminta konfirmasi tegas sebelum menghapus file/konfigurasi sistem. |

---

### 🔄 Kategori 2: Data Synchronization (Sinkronisasi Database)

| Command | Scope & Tanggung Jawab | Sifat Perintah | Input Interaktif? | Ekspektasi Saat Gagal / Exit Code | Batasan Ketat (*Strict Boundaries*) |
|---|---|---|---|---|---|
| **`gaet push`** | Melakukan `pg_dump` DB lokal dan merestore ke Remote Cloud DB. | Data Sync (Mutate Remote) | **TIDAK** (Kecuali opsi `--auto`) | `EXIT_LOCAL_DOWN` (81) / `EXIT_CLOUD_DOWN` (82) | Abort seketika jika DB lokal/cloud tidak terhubung. **Tidak pernah** memicu wizard `init`. |
| **`gaet fetch`** | Melakukan `pg_dump` Remote Cloud DB dan merestore ke DB Lokal (overwrite). | Data Sync (Mutate Local) | **YA** (Ketik `yes`) / `--yes` flag di CI | `EXIT_LOCAL_DOWN` (81) / `EXIT_CLOUD_DOWN` (82) | **Destruktif ke DB lokal**. Wajib ketik `yes` di TTY. Menolak eksekusi di non-TTY tanpa `--yes`. |
| **`gaet restore`** | Memulihkan DB lokal dari snapshot file `.dump` lokal tertentu (default: latest). | Local Snapshot Restore | **YA** (Ketik `yes`) / `--yes` flag di CI | `EXIT_LOCAL_DOWN` (81) / `EXIT_CONFIG` (80) | **Destruktif ke DB lokal**. Rollback instan dari snapshot lokal tanpa perlu jaringan cloud. Wajib konfirmasi di TTY. |

---

### 📊 Kategori 3: Status, Diagnostics & History (Read-Only)

| Command | Scope & Tanggung Jawab | Sifat Perintah | Input Interaktif? | Ekspektasi Saat Gagal / Exit Code | Batasan Ketat (*Strict Boundaries*) |
|---|---|---|---|---|---|
| **`gaet status`** | Menampilkan ringkasan status sinkronisasi, jumlah tabel, ukuran DB, dan auto-backup. | Read-Only Summary | **TIDAK** (100% Non-interaktif) | `0` (atau `EXIT_CONFIG` jika tanpa `.env`) | 100% read-only. Tidak pernah minta password/input. |
| **`gaet check`** | Validasi instan ketersediaan tools PostgreSQL, `.env`, koneksi DB, dan folder backup. | Read-Only Diagnostic | **TIDAK** (100% Non-interaktif) | Non-zero jika ada check FAIL | Menggunakan flag `-w` (`--no-password`). Hanya memberi saran `gaet init` tanpa panggil wizard. |
| **`gaet diff`** | Perbandingan jumlah baris (*row count*) per tabel antara DB Lokal dan Cloud DB. | Read-Only Comparison | **TIDAK** (100% Non-interaktif) | Non-zero jika koneksi gagal | Membandingkan statistik tabel secara aman tanpa mengubah data. |
| **`gaet doctor`** | Pengecekan kesehatan sistem mendalam (OS, izin folder, koneksi, dependensi). | Read-Only Diagnostic | **TIDAK** (100% Non-interaktif) | Mengembalikan jumlah isu | Memberikan laporan teknis komprehensif untuk penyelesaian masalah. |
| **`gaet log`** | Menampilkan daftar dan histori file `.dump` yang tersimpan di direktori backup. | Read-Only History | **TIDAK** (100% Non-interaktif) | `0` | Menampilkan daftar file backup di folder `backups/`. |

---

### ⚙️ Kategori 4: Configuration & Utilities (Manajemen Konfigurasi & Shell)

| Command | Scope & Tanggung Jawab | Sifat Perintah | Input Interaktif? | Ekspektasi Saat Gagal / Exit Code | Batasan Ketat (*Strict Boundaries*) |
|---|---|---|---|---|---|
| **`gaet get`** | Membaca dan mencetak nilai variabel spesifik atau seluruh isi `.env`. | Config Read | **TIDAK** (100% Non-interaktif) | `0` (atau `1` jika key tak ada) | 100% read-only ke file `.env`. |
| **`gaet set`** | Mengubah atau menambah nilai variabel `KEY=VALUE` spesifik di file `.env`. | Config Write | **TIDAK** (100% Non-interaktif) | `0` / `1` (Format salah) | Mengubah key spesifik secara presisi tanpa panggil wizard `init`. |
| **`gaet export`** | Mengekspor konfigurasi `.env` dalam format variabel shell (`export GAET_...`). | Config Export | **TIDAK** (100% Non-interaktif) | `0` | Memudahkan penggunaan konfigurasi di script bash/zsh. |
| **`gaet completion`**| Menghasilkan kode auto-completion untuk shell (bash, zsh, fish). | Shell Tool | **TIDAK** (100% Non-interaktif) | `0` | Hanya mencetak script penyelesaian otomatis terminal. |
| **`gaet help`** | Menampilkan panduan bantuan teknis untuk perintah spesifik. | Information | **TIDAK** (100% Non-interaktif) | `0` | Mencetak manual penggunaan perintah. |

---

### 🌐 Kategori 5: Background Services & Dashboard (Layanan Background)

| Command | Scope & Tanggung Jawab | Sifat Perintah | Input Interaktif? | Ekspektasi Saat Gagal / Exit Code | Batasan Ketat (*Strict Boundaries*) |
|---|---|---|---|---|---|
| **`gaet serve`** | Menjalankan web dashboard lokal (HTTP server) untuk monitoring visual. | Service Run | **TIDAK** (Blocking process / Ctrl+C) | Non-zero jika port terpakai | Hanya menjalankan HTTP server dashboard monitoring. |
| **`gaet stop`** | Menghentikan daemon auto-backup (cron/systemd) atau server dashboard `serve`. | Service Control | **TIDAK** (100% Non-interaktif) | `0` / Non-zero jika service tak ada | Mematikan timer/server latar belakang secara aman. |

---

## 🔒 Aturan Emas Implementasi Kode (*Code Enforcement Guidelines*)

1. **Gunakan `pg_env()` dan `-w`**: Semua panggilan `psql`, `pg_dump`, `pg_restore` wajib menyertakan flag `-w` (`--no-password`) dan environment `PGPASSFILE` via `pg_env()`.
2. **Path Konfigurasi Dinamis**: Selalu manfaatkan konstanta `ENV_FILE` (yang mendukung `GAET_DIR`), jangan pernah hardcode `~/.gaet/.env` di pesan output.
3. **Penanganan Non-Interactive Mode**: Jika `sys.stdin.isatty()` bernilai `False`, perintah interaktif seperti `fetch` **wajib** meminta flag `--yes` atau langsung abort dengan `die()`.
