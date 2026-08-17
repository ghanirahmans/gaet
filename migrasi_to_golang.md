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
7. [Strategi Pengujian (Go Native Testing & Mocking)](#7-strategi-pengujian-go-native-testing--mocking)
8. [Perencanaan Rilis, Build Pipeline & GitHub Actions](#8-perencanaan-rilis-build-pipeline--github-actions)
9. [Prosedur Rollback & Pemeliharaan LTS](#9-prosedur-rollback--pemeliharaan-lts)

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

Untuk menjamin kejelasan alur data, berikut adalah tipe data domain utama yang akan digunakan di seluruh paket Go:

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
	Name    string    `json:"name"`
	Path    string    `json:"path"`
	SizeBytes int64   `json:"size_bytes"`
	SizeMB   float64   `json:"size_mb"`
	ModTime  time.Time `json:"mod_time"`
	IsLatest bool      `json:"is_latest"`
}

// Global execution options passed from CLI flags
type GlobalOptions struct {
	JSONOutput bool
	PlainOutput bool
	Quiet      bool
	Yes        bool
	Debug      bool
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
	"os"
)

// Standardized ANSI color codes (disabled automatically if --plain or non-TTY)
var (
	ColorReset  = "\033[0m"
	ColorRed    = "\033[31m"
	ColorGreen  = "\033[32m"
	ColorYellow = "\033[33m"
	ColorCyan   = "\033[36m"
	ColorDim    = "\033[2m"
	ColorBold   = "\033[1m"
)

// Print standard ASCII status OK tag
func StatusOK(msg string) {
	fmt.Printf("  %s[ OK ]%s  %s\n", ColorGreen, ColorReset, msg)
}

// Print standard ASCII status FAIL tag
func StatusFail(msg string) {
	fmt.Printf("  %s[FAIL]%s  %s\n", ColorRed, ColorReset, msg)
}

// Print standard ASCII status WARN tag
func StatusWarn(msg string) {
	fmt.Printf("  %s[WARN]%s  %s\n", ColorYellow, ColorReset, msg)
}

// Print standard ASCII status INFO tag
func StatusInfo(msg string) {
	fmt.Printf("  %s[INFO]%s  %s\n", ColorCyan, ColorReset, msg)
}

// Print standard ASCII status NOTE tag
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

// LoadEnv reads a .env file and parses key-value pairs into a map
func LoadEnv(filePath string) (map[string]string, error) {
	envMap := make(map[string]string)

	file, err := os.Open(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return envMap, nil // Return empty map if file doesn't exist yet
		}
		return nil, fmt.Errorf("failed to open env file: %w", err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue // Skip comments and empty lines
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			val := strings.TrimSpace(parts[1])
			// Strip quotes if present
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

// RunCmd executes an external command with timeout and environment variable injection
func RunCmd(ctx context.Context, name string, args []string, env map[string]string, timeout time.Duration) (*ExecResult, error) {
	timeoutCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	cmd := exec.CommandContext(timeoutCtx, name, args...)
	
	// Inject custom environment variables (e.g. PGPASSWORD)
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

// Go embed directive wrapping all frontend assets in dashboard/static
//
//go:embed static/*
var embeddedAssets embed.FS

// GetFileSystem returns an http.FileSystem backed by the embedded static assets
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

## 7. Strategi Pengujian (Go Native Testing & Mocking)

Semua unit test di Go akan memanfaatkan paket standar `testing`:

```go
package core_test

import (
	"testing"
	"github.com/ghanirahmans/gaet/pkg/core"
)

func TestLoadEnv(t *testing.T) {
	// Test parsing .env functionality
	envMap, err := core.LoadEnv("testdata/.env.test")
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if envMap["GAET_LOCAL_DB_PORT"] != "5432" {
		t.Errorf("Expected port 5432, got %s", envMap["GAET_LOCAL_DB_PORT"])
	}
}
```

### Protocol Kepatuhan Test:
- Setiap perintah di `pkg/` harus memiliki pengujian unit terisolasi.
- Running `go test -v ./...` wajib menghasilkan **100% PASS** tanpa error sebelum merge ke branch utama.

---

## 8. Perencanaan Rilis, Build Pipeline & GitHub Actions

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

## 9. Prosedur Rollback & Pemeliharaan LTS

* **Branch `lts/v1.0`**: Tetap dipertahankan sebagai versi **Python 3.8+ LTS** untuk pengguna lama yang memerlukan script Python murni.
* **Branch `feat/golang-migration`**: Menjadi lokasi aktif untuk pengembangan versi Go hingga siap dirilis sebagai **Gaet V2.0**.
* **Keamanan Data**: File data pengguna di `~/.gaet` (`.env` dan `backups/*.dump`) **100% kompatibel** antara versi Python (V1) dan versi Go (V2).

---

*Dokumentasi spesifikasi ini resmi disetujui sebagai acuan utama eksekusi proyek migrasi Gaet V2.0.*
