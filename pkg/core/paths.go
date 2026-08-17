package core

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
)

const (
	AppName        = "gaet"
	Version        = "1.1.2"
	DocsURL        = "https://github.com/ghanirahmans/gaet"
	TroubleshootURL = "https://github.com/ghanirahmans/gaet/blob/main/docs/troubleshooting.md"
	GitHubAPI      = "https://api.github.com/repos/ghanirahmans/gaet/releases/latest"
	GitHubRaw      = "https://raw.githubusercontent.com/ghanirahmans/gaet/lts/v1.1"

	DefLocalHost     = "127.0.0.1"
	DefLocalPort     = "5432"
	DefLocalUser     = "postgres"
	DefLocalDB       = "postgres"
	DefLocalPass     = ""
	DefRetentionDays = 7
	DefAutoInterval  = 6
	DefDashboardPort = 6161
	DefDashboardHost = "127.0.0.1"
	DefRemoteSSLMode = "prefer"
	DefTimeout        = 900
	DefTimeoutPerGB   = 300
	DefServicePrefix  = "gaet"
)

// GaetDir returns the user data directory (~/.gaet or $GAET_DIR).
func GaetDir() string {
	if d := os.Getenv("GAET_DIR"); d != "" {
		return d
	}
	return filepath.Join(homeDir(), ".gaet")
}

// GaetAppDir returns the application bundle directory.
func GaetAppDir() string {
	if d := os.Getenv("GAET_APP_DIR"); d != "" {
		return d
	}
	if runtime.GOOS == "windows" {
		local := os.Getenv("LOCALAPPDATA")
		if local == "" {
			local = filepath.Join(homeDir(), "AppData", "Local")
		}
		return filepath.Join(local, AppName)
	}
	return filepath.Join(homeDir(), ".local", "share", AppName)
}

// BackupDir returns the backups subdirectory under GaetDir.
func BackupDir() string {
	return filepath.Join(GaetDir(), "backups")
}

// EnvFile returns the path to ~/.gaet/.env.
func EnvFile() string {
	return filepath.Join(GaetDir(), ".env")
}

// LogFile returns the main log file path.
func LogFile() string {
	return filepath.Join(BackupDir(), "gaet.log")
}

// CronLogFile returns the cron/auto-backup log file path.
func CronLogFile() string {
	return filepath.Join(BackupDir(), "cron.log")
}

// LockPath returns the lockfile path.
func LockPath() string {
	return filepath.Join(BackupDir(), ".gaet.lock")
}

// LauncherDir returns the directory where the gaet binary launcher is placed.
func LauncherDir() string {
	if runtime.GOOS == "windows" {
		return filepath.Join(homeDir(), ".local", "bin")
	}
	return filepath.Join(homeDir(), ".local", "bin")
}

// EnsureDir creates a directory (and parents) if it doesn't exist.
func EnsureDir(path string) error {
	if err := os.MkdirAll(path, 0755); err != nil {
		return fmt.Errorf("mkdir %q: %w", path, err)
	}
	return nil
}

// IsWindows returns true on Windows.
func IsWindows() bool { return runtime.GOOS == "windows" }

// IsLinux returns true on Linux.
func IsLinux() bool { return runtime.GOOS == "linux" }

// IsMacOS returns true on macOS.
func IsMacOS() bool { return runtime.GOOS == "darwin" }

func homeDir() string {
	h, err := os.UserHomeDir()
	if err != nil {
		h = "."
	}
	return h
}
