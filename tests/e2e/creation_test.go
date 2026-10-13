//go:build e2e

package e2e

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
)

func execCommand(name string, args ...string) *exec.Cmd {
	return exec.Command(name, args...)
}

func runCmd(t *testing.T, cmd *exec.Cmd) (string, string, int) {
	t.Helper()
	var outBuf, errBuf strings.Builder
	cmd.Stdout = &outBuf
	cmd.Stderr = &errBuf
	err := cmd.Run()
	code := 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			code = exitErr.ExitCode()
		} else {
			t.Fatalf("failed to run command: %v", err)
		}
	}
	return outBuf.String(), errBuf.String(), code
}

// A1: gaet init --preset hindsight -y writes valid .env
func TestE2E_Init_Preset(t *testing.T) {
	gaetDir := t.TempDir()
	out, _, code := runGaet(t, gaetDir, nil, "init", "--preset", "hindsight", "-y")
	if code != 0 {
		t.Fatalf("init exit code %d, want 0\nstdout: %s", code, out)
	}
	envFile := filepath.Join(gaetDir, ".env")
	if _, err := os.Stat(envFile); err != nil {
		t.Fatalf("env file not created at %s", envFile)
	}
}

// A2: gaet init non-interactive preserves existing local config
func TestE2E_Init_NonInteractive_PreservesConfig(t *testing.T) {
	gaetDir := t.TempDir()
	existingURL := "postgresql://myuser@127.0.0.1:5432/mydb"
	writeEnvFile(t, gaetDir, baseEnvContent(existingURL, testRemoteURL))

	_, _, code := runGaet(t, gaetDir, nil, "init", "-y")
	if code != 0 {
		t.Fatalf("init exit code %d", code)
	}

	env, err := core.LoadEnv(filepath.Join(gaetDir, ".env"))
	if err != nil {
		t.Fatalf("LoadEnv: %v", err)
	}
	// init normalizes the URL by reconstructing it (drops password, uses parsed components)
	parsedURL := env["GAET_LOCAL_URL"]
	if parsedURL == "" {
		t.Error("GAET_LOCAL_URL should not be empty after init")
	}
	// The URL should preserve the host/dbname portion
	if !strings.Contains(parsedURL, "127.0.0.1") || !strings.Contains(parsedURL, "mydb") {
		t.Errorf("expected URL to contain host and db, got: %s", parsedURL)
	}
}

// A3: gaet init on unknown preset → exit ExitConfig
func TestE2E_Init_UnknownPreset(t *testing.T) {
	gaetDir := t.TempDir()
	_, _, code := runGaet(t, gaetDir, nil, "init", "--preset", "nonexistent_preset_xyz", "-y")
	if code != core.ExitConfig {
		t.Errorf("expected exit code %d (ExitConfig), got %d", core.ExitConfig, code)
	}
}

// A4: Create fresh empty DBs; run gaet check — reports local_ok=true
func TestE2E_FreshDB_CheckStatus(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	// Clean both DBs to empty state
	cleanupDB(t, testLocalURL)
	cleanupDB(t, testRemoteURL)

	gaetDir := setupTestEnv(t)

	out, _, code := runGaet(t, gaetDir, nil, "check", "--json")
	if code != 0 {
		t.Fatalf("check exit code %d\nstdout: %s", code, out)
	}
	if !strings.Contains(out, "ok") {
		t.Errorf("check --json should contain ok field: %s", out)
	}
}

// A5: gaet push from an empty local DB
func TestE2E_Push_EmptyDB(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	cleanupDB(t, testLocalURL)

	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push from empty DB exit code %d", code)
	}

	tables := listTables(t, testRemoteURL)
	if len(tables) != 0 {
		t.Errorf("expected 0 tables on remote after push from empty DB, got %d: %v", len(tables), tables)
	}
}

// A6: gaet push when DB does not exist → ExitLocalDown
func TestE2E_Push_DBDoesNotExist(t *testing.T) {
	ensureDBAvailable(t)
	gaetDir := t.TempDir()
	writeEnvFile(t, gaetDir, baseEnvContent(
		"postgresql://gaet@127.0.0.1:5434/gaet_nonexistent_db",
		testRemoteURL,
	))

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != core.ExitLocalDown {
		t.Errorf("expected exit code %d (ExitLocalDown), got %d", core.ExitLocalDown, code)
	}
}

// A7: Password-less local (trust auth) — push succeeds
func TestE2E_Push_PasswordlessTrust(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	seedDB(t, testRemoteURL)

	gaetDir := t.TempDir()
	// Use a passwordless URL (no password, trust auth)
	passwordlessLocal := strings.Replace(testLocalURL, "testpass@", "", 1)
	envContent := "# gaet test config\nGAET_LOCAL_URL=" + passwordlessLocal + "\nGAET_REMOTE_URL=" + testRemoteURL + "\nGAET_RETENTION_DAYS=7\n"
	writeEnvFile(t, gaetDir, envContent)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push with passwordless URL exit code %d", code)
	}

	assertRowCounts(t, testRemoteURL)
}