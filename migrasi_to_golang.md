# Blueprint & Spec Teknikal Komprehensif: Migrasi Gaet Python ➔ Go (Golang) V2.0

Dokumen ini adalah **Spesifikasi Teknikal & Panduan Eksekusi Komprehensif** untuk memigrasikan seluruh arsitektur **Gaet** dari **Python 3.8+** ke **Go (Golang)** pada branch `feat/golang-migration`.

---

## 📑 Daftar Isi

1. [Visi Arsitektur & Prinsip Utama](#1-visi-arsitektur--prinsip-utama)
2. [Peta Struktur Direktori & Modul](#2-peta-struktur-direktori--modul)
3. [Spesifikasi Tipe Data & Struct Utama (Go Domain Models)](#3-spesifikasi-tipe-data--struct-utama-go-domain-models)
4. [Matriks Detail Subcommand & Pemetaan Fungsi Kode](#4-matriks-detail-subcommand--pemetaan-fungsi-kode)
5. [Arsitektur Core Sub-System (Go Implementation Specs)](#5-arsitektur-core-sub-system-go-implementation-specs)
   - [5.1 Core Output & Pure ASCII Standard (`pkg/core/output.go`)](#51-core-output--pure-ascii-standard-pkgcoreoutputgo)
   - [5.2 Zero-Dependency `.env` Parser (`pkg/core/env.go`)](#52-zero-dependency-env-parser-pkgcoreenvgo)
   - [5.3 Cross-Platform Subprocess & Timeout Runner (`pkg/core/exec.go`)](#53-cross-platform-subprocess--timeout-runner-pkgcoreexecgo)
   - [5.4 Embedded Dashboard Engine (`pkg/serve/embed.go`)](#54-embedded-dashboard-engine-pkgserveembedgo)
6. [Manajemen Layanan Background (Systemd, Launchd, Task Scheduler)](#6-manajemen-layanan-background-systemd-launchd-task-scheduler)
7. [Mekanisme Concurrency File Locking & Log Rotation (`pkg/core/lock.go`)](#7-mekanisme-concurrency-file-locking--log-rotation-pkgcorelockgo)
8. [Keamanan, Masking Password & Sanitasi Terminal](#8-keamanan-masking-password--sanitasi-terminal)
9. [Generator Autocompletion Shell Native (`pkg/completion`)](#9-generator-autocompletion-shell-native-pkgcompletion)
10. [Strategi Pengujian & Benchmarking Kinerja (Python vs Go)](#10-strategi-pengujian--benchmarking-kinerja-python-vs-go)
11. [Perencanaan Rilis, Build Pipeline & GitHub Actions](#11-perencanaan-rilis-build-pipeline--github-actions)
12. [Prosedur Rollback & Pemeliharaan LTS](#12-prosedur-rollback--pemeliharaan-lts)
13. [Checklist Task Eksekusi Pengembang (Developer Implementation Roadmap)](#13-checklist-task-eksekusi-pengembang-developer-implementation-roadmap)

---

## 1. Visi Arsitektur & Prinsip Utama

Migrasi ini bertujuan untuk mentransformasi Gaet dari skrip Python yang bergantung pada runtime OS target menjadi **1 Standalone Native Binary Executable** berkinerja tinggi.

### 🌟 5 Pilar Arsitektur Go Gaet:
1. **Zero External Dependencies**:
   - Seluruh runtime CLI & Web Dashboard hanya bergantung pada **Go Standard Library** (target versi: **Go 1.21+**).
   - Menghasilkan binary tunggal tanpa `pip`, `virtualenv`, atau interpreter `python3`.
2. **Embedded Web Assets (`//go:embed`)**:
   - Seluruh file frontend di `dashboard/static/` dibungkus ke dalam binary `gaet`.
   - `gaet serve` dapat dijalankan di mana saja tanpa memerlukan ketersediaan folder aset eksternal.
3. **100% Pure ASCII UI Compliance**:
   - Mempertahankan standar UI tanpa emoji sesuai aturan `AGENTS.md` dan `ADR-0002`:
     - `  [ OK ]  <Pesan Sukses>`
     - `  [FAIL]  <Pesan Gagal>`
     - `  [WARN]  <Pesan Peringatan>`
     - `  [INFO]  <Pesan Informasi>`
     - `  [NOTE]  <Pesan Catatan Parameter>`
4. **Dual-Personality API Architecture**:
   - Fungsi bisnis melempar tipe error terstruktur (`GaetError`), bukan langsung memanggil `os.Exit()`.
   - Memungkinkan Gaet di-import sebagai modul Go library (`import "github.com/ghanirahmans/gaet/pkg/client"`).
5. **Cross-Platform Path & Process Invariance**:
   - Mematuhi standar **XDG Base Directory** di Linux/macOS dan **AppData** di Windows menggunakan `path/filepath`.

---

## 2. Peta Struktur Direktori & Modul

```text
gaet/ (Branch: feat/golang-migration)
├── go.mod                       # Modul Go (module github.com/ghanirahmans/gaet)
├── main.go                      # Shim Entry Point (mengarahkan eksekusi ke cmd/gaet)
├── cmd/
│   └── gaet/
│       ├── main.go              # CLI main entry point
│       └── root.go              # Argument Router, Flag Parsing & Signal Trap (SIGINT/SIGTERM)
├── pkg/
│   ├── core/                    # Low-level core engine
│   │   ├── paths.go             # XDG & Windows AppData path constants
│   │   ├── output.go            # ASCII status formatters, ANSI color definitions, Box printers
│   │   ├── env.go               # .env file reader, writer, and variable parser
│   │   ├── exec.go              # Subprocess exec runner with timeout & env injection
│   │   ├── lock.go              # Cross-platform file lock (GAET_DIR/gaet.lock)
│   │   ├── logger.go            # Structured log writer & auto-rotation (log/slog)
│   │   ├── errors.go            # Typed error definitions (GaetError, ConfigError, DBError)
│   │   └── core_test.go         # Core package unit tests
│   ├── registry/                # Command registration & dispatch engine
│   │   ├── router.go            # Declarative @command router interface
│   │   └── flags.go             # Global flag handler (--json, --plain, --quiet, --yes)
│   ├── detect/                  # Database auto-discovery engine
│   │   ├── socket.go            # Unix domain socket scanner (/tmp, /run/postgresql)
│   │   ├── tcp.go               # TCP port & instance ping checker
│   │   └── detect_test.go       # Auto-detect unit tests
│   ├── init/                    # Setup wizard
│   │   └── wizard.go            # Interactive TTY wizard & Non-interactive preset handler
│   ├── config/                  # Configuration management
│   │   └── config.go            # Subcommands: gaet get, gaet set
│   ├── backup/                  # Backup engine
│   │   ├── push.go              # Subcommand: gaet push (pg_dump wrapper)
│   │   └── fetch.go             # Subcommand: gaet fetch (remote sync)
│   ├── restore/                 # Restoration engine
│   │   └── restore.go           # Subcommand: gaet restore (pg_restore / psql safety guards)
│   ├── snapshots/               # Local snapshot manager
│   │   └── snapshots.go         # Subcommand: gaet snapshots (retention & table view)
│   ├── remote/                  # Remote cloud DB engine
│   │   └── remote.go            # Subcommand: gaet remote (set-url, remove, test)
│   ├── status/                  # Health & Sync Doctor
│   │   ├── status.go            # Subcommands: gaet status, gaet check
│   │   └── doctor.go            # Subcommand: gaet doctor (tool verification)
│   ├── scheduler/               # Platform background timer manager
│   │   ├── systemd.go           # Linux Systemd unit manager
│   │   ├── launchd.go           # macOS Launchd plist manager
│   │   └── windows.go           # Windows Task Scheduler manager
│   ├── serve/                   # Embedded Web Dashboard Server
│   │   ├── server.go            # net/http server & API endpoints (/api/status, /api/snapshots)
│   │   └── embed.go             # //go:embed static assets
│   ├── completion/              # Shell Autocompletion Generator
│   │   └── completion.go        # Subcommand: gaet completion (bash, zsh, fish, powershell)
│   ├── log/                     # Log history viewer
│   │   └── log.go               # Subcommand: gaet log
│   └── update/                  # Self-updater & Purge engine
│       └── update.go            # Subcommands: gaet update, gaet uninstall
├── dashboard/                   # Web UI Assets
│   └── static/                  # HTML, CSS, JS, SVG assets
├── scripts/                     # Service templates (systemd.service, plist)
├── tests/                       # E2E integration tests
└── migrasi_to_golang.md         # Blueprint & Spesifikasi Dokumentasi Ini
```

---

## 3. Spesifikasi Tipe Data & Struct Utama (Go Domain Models)

```go
package domain

import "time"

// Configuration model representing parsed .env settings
type Config struct {
	LocalHost      string
	LocalPort      string
	LocalUser      string
	LocalDB        string
	LocalPass      string
	LocalURL       string
	RemoteURL      string
	RetentionDays  int
	PgDumpPath     string
	PgRestorePath  string
	PsqlPath       string
}

// PostgreSQL detected local instance
type PGInstance struct {
	Host      string   `json:"host"`
	Port      int      `json:"port"`
	User      string   `json:"user"`
	Databases []string `json:"databases"`
	IsSocket  bool     `json:"is_socket"`
}

// Snapshot metadata model for local dumps
type SnapshotFile struct {
	Name      string    `json:"name"`
	Path      string    `json:"path"`
	SizeBytes int64     `json:"size_bytes"`
	SizeMB    float64   `json:"size_mb"`
	ModTime   time.Time `json:"mod_time"`
	IsLatest  bool      `json:"is_latest"`
}

// Global execution options passed from CLI flags
type GlobalOptions struct {
	JSONOutput  bool
	PlainOutput bool
	Quiet       bool
	Yes         bool
	Debug       bool
}
```

---

## 4. Matriks Detail Subcommand & Pemetaan Fungsi Kode

| Command CLI | Modul Python Asal | Package Go Target | Fungsi & Penanganan Teknis Utama |
| :--- | :--- | :--- | :--- |
| `gaet init` | `src/gaet/init.py` | `pkg/init` | TTY interactive prompt dengan `bufio.Scanner`, auto-detect PG, pembuatan `.env`. |
| `gaet push` | `src/gaet/backup.py` | `pkg/backup` | Subprocess `pg_dump -F c -b -v`, penamaan timestamp `gaet_YYYYMMDD_HHMMSS.dump`. |
| `gaet fetch` | `src/gaet/backup.py` | `pkg/backup` | Penarikan dump dari cloud remote PostgreSQL (`pg_dump` remote connection). |
| `gaet restore` | `src/gaet/restore.py` | `pkg/restore` | Subprocess `pg_restore` / `psql` + Konfirmasi TTY / `-y` flag check. |
| `gaet snapshots`| `src/gaet/snapshots.py`| `pkg/snapshots` | Pemindaian folder `GAET_DIR/backups`, kalkulasi ukuran, tabel ASCII snapshot. |
| `gaet status` | `src/gaet/status.py` | `pkg/status` | Tabel komparasi sync lokal vs cloud (`SELECT count(*) FROM table`). |
| `gaet check` | `src/gaet/status.py` | `pkg/status` | Pengecekan koneksi cepat lokal & remote DB. |
| `gaet doctor` | `src/gaet/status.py` | `pkg/status` | Diagnostik lengkap (PATH `pg_dump`, izin folder `~/.gaet`, ketersediaan port). |
| `gaet remote` | `src/gaet/remote.py` | `pkg/remote` | Subcommands: `remote set-url`, `remote remove`, `remote test`. |
| `gaet get` | `src/gaet/config.py` | `pkg/config` | Membaca variabel tunggal dari `.env`. |
| `gaet set` | `src/gaet/config.py` | `pkg/config` | Memperbarui variabel kunci pada `.env`. |
| `gaet auto` | `src/gaet/scheduler.py` | `pkg/scheduler` | Aktivasi/Deaktivasi Systemd Timer, Launchd Plist, atau Windows Task Scheduler. |
| `gaet serve` | `src/gaet/serve.py` | `pkg/serve` | Menjalankan HTTP Web Server port 8080 dengan aset frontend embedded (`//go:embed`). |
| `gaet completion`| `src/gaet/status.py`| `pkg/completion` | Membangkitkan skrip autokomplit terminal (.bash, .zsh, .fish, .ps1). |
| `gaet log` | `src/gaet/log.py` | `pkg/log` | Membaca & menampilkan isi file log riwayat eksekusi (`GAET_DIR/gaet.log`). |
| `gaet export` | `src/gaet/export.py` | `pkg/export` | Ekspor data atau konfigurasi dalam format JSON/YAML. |
| `gaet update` | `src/gaet/update.py` | `pkg/update` | Memeriksa GitHub Releases, mendownload binary baru, dan mengganti binary berjalan. |
| `gaet uninstall`| `src/gaet/update.py` | `pkg/update` | Penghapusan binary launcher & pembersihan opsional `--purge`. |

---

## 5. Arsitektur Core Sub-System (Go Implementation Specs)

### 5.1 Core Output & Pure ASCII Standard (`pkg/core/output.go`)

```go
package core

import (
	"fmt"
)

var (
	ColorReset  = "\033[0m"
	ColorRed    = "\033[31m"
	ColorGreen  = "\033[32m"
	ColorYellow = "\033[33m"
	ColorCyan   = "\033[36m"
	ColorDim    = "\033[2m"
	ColorBold   = "\033[1m"
)

func StatusOK(msg string) {
	fmt.Printf("  %s[ OK ]%s  %s\n", ColorGreen, ColorReset, msg)
}

func StatusFail(msg string) {
	fmt.Printf("  %s[FAIL]%s  %s\n", ColorRed, ColorReset, msg)
}

func StatusWarn(msg string) {
	fmt.Printf("  %s[WARN]%s  %s\n", ColorYellow, ColorReset, msg)
}

func StatusInfo(msg string) {
	fmt.Printf("  %s[INFO]%s  %s\n", ColorCyan, ColorReset, msg)
}

func StatusNote(label, value string) {
	fmt.Printf("  %s[NOTE]%s  %-15s %s\n", ColorDim, ColorReset, label+":", value)
}
```

---

### 5.2 Zero-Dependency `.env` Parser (`pkg/core/env.go`)

```go
package core

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

func LoadEnv(filePath string) (map[string]string, error) {
	envMap := make(map[string]string)

	file, err := os.Open(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return envMap, nil
		}
		return nil, fmt.Errorf("failed to open env file: %w", err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			val := strings.TrimSpace(parts[1])
			val = strings.Trim(val, `"'`)
			envMap[key] = val
		}
	}

	return envMap, scanner.Err()
}
```

---

### 5.3 Cross-Platform Subprocess & Timeout Runner (`pkg/core/exec.go`)

```go
package core

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"time"
)

type ExecResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

func RunCmd(ctx context.Context, name string, args []string, env map[string]string, timeout time.Duration) (*ExecResult, error) {
	timeoutCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	cmd := exec.CommandContext(timeoutCtx, name, args...)
	
	if len(env) > 0 {
		cmd.Env = exec.Command(name).Environ()
		for k, v := range env {
			cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
		}
	}

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err := cmd.Run()
	exitCode := 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			exitCode = -1
		}
	}

	return &ExecResult{
		Stdout:   stdoutBuf.String(),
		Stderr:   stderrBuf.String(),
		ExitCode: exitCode,
	}, nil
}
```

---

### 5.4 Embedded Dashboard Engine (`pkg/serve/embed.go`)

```go
package serve

import (
	"embed"
	"io/fs"
	"net/http"
)

//go:embed static/*
var embeddedAssets embed.FS

func GetFileSystem() (http.FileSystem, error) {
	subFS, err := fs.Sub(embeddedAssets, "static")
	if err != nil {
		return nil, err
	}
	return http.FS(subFS), nil
}
```

---

## 6. Manajemen Layanan Background (Systemd, Launchd, Task Scheduler)

Porting `pkg/scheduler` akan menangani integrasi background timer secara native berdasarkan platform pengguna:

1. **Linux (Systemd User Unit)**:
   - Membuat file `~/.config/systemd/user/gaet-backup.service` dan `gaet-backup.timer`.
   - Menggunakan subprocess `systemctl --user daemon-reload` dan `systemctl --user enable --now gaet-backup.timer`.
2. **macOS (Launchd Plist)**:
   - Membuat file `~/Library/LaunchAgents/com.gaet.backup.plist`.
   - Menggunakan subprocess `launchctl load ~/Library/LaunchAgents/com.gaet.backup.plist`.
3. **Windows (Task Scheduler)**:
   - Menggunakan subprocess `schtasks /Create /TN "gaet-backup" /TR "gaet push" /SC DAILY /ST 02:00 /F`.

---

## 7. Mekanisme Concurrency File Locking & Log Rotation (`pkg/core/lock.go`)

Untuk mencegah dua proses `gaet push` atau `gaet restore` berjalan bersamaan (misalnya dipicu bersamaan oleh Systemd Timer dan manual user):

### 7.1 Cross-Platform Lockfile (`GAET_DIR/gaet.lock`)
```go
package core

import (
	"fmt"
	"os"
	"path/filepath"
)

type FileLock struct {
	file *os.File
}

// AcquireLock attempts to obtain an exclusive file lock on gaet.lock
func AcquireLock() (*FileLock, error) {
	lockPath := filepath.Join(GetGaetDir(), "gaet.lock")
	file, err := os.OpenFile(lockPath, os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
	if err != nil {
		if os.IsExist(err) {
			return nil, fmt.Errorf("another gaet process is currently running (lockfile present: %s)", lockPath)
		}
		return nil, err
	}
	return &FileLock{file: file}, nil
}

func (l *FileLock) Release() {
	if l.file != nil {
		l.file.Close()
		os.Remove(l.file.Name())
	}
}
```

### 7.2 Automatic Log Rotation (Limit 5 MB)
Sistem pencatatan log pada `pkg/core/logger.go` menggunakan standard library `log/slog` dan secara otomatis memutar file log (`gaet.log` ➔ `gaet.log.old`) saat ukuran melebihi 5 MB.

---

## 8. Keamanan, Masking Password & Sanitasi Terminal

1. **URL Password Masking**:
   - Seluruh cetakan URL koneksi database yang berisi password (seperti `postgresql://user:pass@host:5432/db`) wajib disanitasi menggunakan helper `MaskURLPassword(url)` menjadi `postgresql://user:***@host:5432/db`.
2. **Memory Password Zeroing**:
   - Karakter password yang dibaca via `term.ReadPassword()` disimpan dalam slice byte `[]byte` dan segera di-zero (`b[i] = 0`) setelah koneksi database selesai dibuka.

---

## 9. Generator Autocompletion Shell Native (`pkg/completion`)

Subcommand `gaet completion` membangkitkan skrip autokomplit secara native tanpa ketergantungan luar:
* `gaet completion --shell bash` ➔ Menghasilkan skrip bash completion.
* `gaet completion --shell zsh` ➔ Menghasilkan skrip zsh completion.
* `gaet completion --shell fish` ➔ Menghasilkan skrip fish completion.
* `gaet completion --shell powershell` ➔ Menghasilkan skrip PowerShell completion.

---

## 10. Strategi Pengujian & Benchmarking Kinerja (Python vs Go)

### 10.1 Benchmark Suite (`go test -bench=.`)
Kinerja versi Go akan diukur menggunakan Go Benchmark suite untuk memastikan peningkatan kecepatan startup & efisiensi RAM:

```go
func BenchmarkStartupTime(b *testing.B) {
	for i := 0; i < b.N; i++ {
		core.LoadEnv(filepath.Join(b.TempDir(), ".env"))
	}
}
```

### 10.2 Parity Validation Matrix (Validasi Byte-for-Byte Output CLI)
Setiap subcommand CLI versi Go diuji agar menghasilkan output byte-for-byte yang identik dengan versi Python (termasuk tag status ASCII `[ OK ]`, `[FAIL]`, `[WARN]`, `[INFO]`, `[NOTE]`).

---

## 11. Perencanaan Rilis, Build Pipeline & GitHub Actions

Workflow GitHub Actions `.github/workflows/release.yml` akan secara otomatis melakukan kompilasi silang (*cross-compilation*) saat tag rilis `v2.x` di-push:

```yaml
name: Release Go Binaries

on:
  push:
    tags:
      - 'v2.*'

jobs:
  build:
    name: Build Multi-Platform Binaries
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-go@v4
        with:
          go-version: '1.21'
      
      - name: Build Binaries
        run: |
          mkdir -p dist
          GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o dist/gaet-linux-amd64 .
          GOOS=linux GOARCH=arm64 go build -ldflags="-s -w" -o dist/gaet-linux-arm64 .
          GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" -o dist/gaet-darwin-amd64 .
          GOOS=darwin GOARCH=arm64 go build -ldflags="-s -w" -o dist/gaet-darwin-arm64 .
          GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o dist/gaet-windows-amd64.exe .

      - name: Upload Release Assets
        uses: softprops/action-gh-release@v1
        with:
          files: dist/*
```

---

## 12. Prosedur Rollback & Pemeliharaan LTS

* **Strategi Rilis LTS v1.1.0 (Golang Stable)**:
  - Branch `feat/golang-migration` (Versi Go) akan dikembangkan dan diuji hingga 100% stabil.
  - Setelah versi Go ini lulus seluruh test parity dan dinyatakan stabil di lingkungan produksi, versi ini akan **dipromosikan secara langsung sebagai rilis LTS Baru: `lts/v1.1.0`** (serta merge ke `main`).
* **Branch `lts/v1.0` (Python Standard Baseline)**:
  - Tetap dipertahankan sebagai versi **Python 3.8+ LTS Baseline** legasi.
* **Keamanan Data**:
  - File data pengguna di `~/.gaet` (`.env` dan `backups/*.dump`) **100% kompatibel** antara versi Python (v1.0) dan versi Go (LTS v1.1.0).

---

## 13. Checklist Task Eksekusi Pengembang (Developer Implementation Roadmap)

Berikut adalah panduan bertahap (task-by-task checklist) yang akan dicentang oleh pengembang selama proses penulisan kode Go:

### 🟩 Phase 1: Core Engine & Modul Inisialisasi (`pkg/core`)
- [ ] Inisialisasi `go.mod` (module `github.com/ghanirahmans/gaet`, Go 1.21+).
- [ ] Implementasi `pkg/core/paths.go` (XDG Base Dir & AppData Windows).
- [ ] Implementasi `pkg/core/output.go` (Status tags ASCII `[ OK ]`, `[FAIL]`, ANSI colors, Box printers).
- [ ] Implementasi `pkg/core/env.go` (Parser file `.env` zero-dependency).
- [ ] Implementasi `pkg/core/exec.go` (Subprocess runner `exec.CommandContext` dengan timeout).
- [ ] Implementasi `pkg/core/lock.go` (Lockfile `gaet.lock` cross-platform).
- [ ] Implementasi `pkg/core/logger.go` (Structured logging `slog` & auto-rotation 5MB).
- [ ] Unit Test `pkg/core/*_test.go` (Target: 100% Pass).

### 🟩 Phase 2: Command Router & Handler Konfigurasi (`pkg/registry`, `pkg/config`)
- [ ] Implementasi `pkg/registry/router.go` (Interface `Command` & dispatcher).
- [ ] Implementasi `pkg/registry/flags.go` (Global flags `--json`, `--plain`, `--quiet`, `--yes`).
- [ ] Implementasi `pkg/config/config.go` (Perintah `gaet get` dan `gaet set`).
- [ ] Unit Test `pkg/registry` & `pkg/config`.

### 🟩 Phase 3: Auto-Discovery & Wizard Setup (`pkg/detect`, `pkg/init`)
- [ ] Implementasi `pkg/detect/socket.go` (Scanner Unix Domain Socket `/run/postgresql`).
- [ ] Implementasi `pkg/detect/tcp.go` (Ping check port 5432 TCP).
- [ ] Implementasi `pkg/init/wizard.go` (Interactive TTY setup & preset non-interactive).
- [ ] Unit Test `pkg/detect` & `pkg/init`.

### 🟩 Phase 4: Backup, Restore & Snapshots Engine (`pkg/backup`, `pkg/restore`, `pkg/snapshots`)
- [ ] Implementasi `pkg/backup/push.go` (Subprocess `pg_dump -F c`).
- [ ] Implementasi `pkg/backup/fetch.go` (Remote cloud sync).
- [ ] Implementasi `pkg/restore/restore.go` (`pg_restore`/`psql` + konfirmasi TTY `--yes`).
- [ ] Implementasi `pkg/snapshots/snapshots.go` (Tabel snapshot ASCII & auto-retention).
- [ ] Unit Test `pkg/backup`, `pkg/restore`, `pkg/snapshots`.

### 🟩 Phase 5: Health Check, Doctor & Remote (`pkg/status`, `pkg/remote`)
- [ ] Implementasi `pkg/status/status.go` (Perintah `gaet status` & `gaet check`).
- [ ] Implementasi `pkg/status/doctor.go` (Diagnostik sistem & ketersediaan tool `pg_dump`).
- [ ] Implementasi `pkg/remote/remote.go` (Perintah `gaet remote`).
- [ ] Unit Test `pkg/status` & `pkg/remote`.

### 🟩 Phase 6: Service Scheduler & Shell Completion (`pkg/scheduler`, `pkg/completion`)
- [ ] Implementasi `pkg/scheduler/systemd.go` (Systemd timer/service manager).
- [ ] Implementasi `pkg/scheduler/launchd.go` (macOS Launchd plist manager).
- [ ] Implementasi `pkg/scheduler/windows.go` (Windows Task Scheduler manager).
- [ ] Implementasi `pkg/completion/completion.go` (Perintah `gaet completion`).

### 🟩 Phase 7: Embedded Dashboard Engine (`pkg/serve`)
- [ ] Pembungkusan aset `dashboard/static/` via `//go:embed` pada `pkg/serve/embed.go`.
- [ ] Implementasi HTTP REST API `/api/status`, `/api/snapshots`, `/api/logs` pada `pkg/serve/server.go`.

### 🟩 Phase 8: Final Binary Build & Single File Installer
- [ ] Membuat Makefile / build script kompilasi silang.
- [ ] Meng-update `install.sh` & `install.ps1` untuk download single binary.
- [ ] Verifikasi E2E full suite.

---

*Dokumentasi spesifikasi ini resmi disetujui sebagai acuan utama eksekusi proyek migrasi Gaet V2.0.*
