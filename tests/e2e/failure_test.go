//go:build e2e

package e2e

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// I1: Failing pg_dump tool stub — push fails with ExitGeneral
func TestE2E_Failure_DumpFailure(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	failDump := toolShimScript(t, "pg_dump", "dump failed intentionally", 1)
	_, stderr, code := runGaet(t, gaetDir, map[string]string{
		"GAET_PG_DUMP": failDump,
	}, "push", "--yes")
	if code != core.ExitLocalDown {
		t.Errorf("expected exit code %d (ExitLocalDown), got %d", core.ExitLocalDown, code)
	}
	if !strings.Contains(stderr, "dump") && !strings.Contains(stderr, "failed") {
		t.Errorf("error should mention dump failure: %s", stderr)
	}
}

// I2: Corrupt dump file — integrity check fails
func TestE2E_Failure_CorruptDump(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	backupDir := filepath.Join(gaetDir, "backups")
	gaetDumps, _ := filepath.Glob(filepath.Join(backupDir, "gaet_*.dump"))
	if len(gaetDumps) == 0 {
		t.Fatal("expected at least one snapshot")
	}

	dumpPath := gaetDumps[0]
	if err := os.WriteFile(dumpPath, []byte("CORRUPT"), 0644); err != nil {
		t.Fatal(err)
	}

	if err := verifyDump(dumpPath); err == nil {
		t.Error("corrupt dump should fail verification")
	}
}

// I3: pg_restore failure stub — restore fails
func TestE2E_Failure_RestoreToolFailure(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	failRestore := toolShimScript(t, "pg_restore", "restore failed", 1)
	_, stderr, code := runGaet(t, gaetDir, map[string]string{
		"GAET_PG_RESTORE": failRestore,
	}, "restore", "latest", "--yes")
	if code != core.ExitConfig {
		t.Errorf("expected exit code %d (ExitConfig), got %d", core.ExitConfig, code)
	}
	if !strings.Contains(strings.ToLower(stderr), "corrupt") && !strings.Contains(strings.ToLower(stderr), "restore") {
		t.Errorf("error should mention restore/corrupt failure: %s", stderr)
	}
}

// I4: Lock contention — stale lock file causes ExitLocked
func TestE2E_Failure_LockContention(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	lockPath := filepath.Join(gaetDir, "backups", ".gaet.lock")
	_ = os.MkdirAll(filepath.Dir(lockPath), 0755)
	if err := os.WriteFile(lockPath, []byte("stale lock"), 0644); err != nil {
		t.Fatal(err)
	}

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != core.ExitLocked {
		t.Errorf("expected exit code %d (ExitLocked), got %d", core.ExitLocked, code)
	}
}

// I5: Remote unreachable — push fails with ExitCloudDown
func TestE2E_Failure_RemoteUnreachable(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)

	gaetDir := t.TempDir()
	unreachableURL := "postgres://user:pass@127.0.0.1:1/invalid"
	writeEnvFile(t, gaetDir, baseEnvContent(testLocalURL, unreachableURL))

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != core.ExitCloudDown {
		t.Errorf("expected exit code %d (ExitCloudDown), got %d", core.ExitCloudDown, code)
	}
}

// I6: Local DB unreachable — push fails with ExitLocalDown
func TestE2E_Failure_LocalDown(t *testing.T) {
	gaetDir := t.TempDir()

	unreachableLocal := "postgres://user:pass@127.0.0.1:1/local"
	dummyRemote := "postgres://user:pass@127.0.0.1:2/remote"
	writeEnvFile(t, gaetDir, baseEnvContent(unreachableLocal, dummyRemote))

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != core.ExitLocalDown {
		t.Errorf("expected exit code %d (ExitLocalDown), got %d", core.ExitLocalDown, code)
	}
}

// I7: psql tool missing — push fails
func TestE2E_Failure_PSQLMissing(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, stderr, code := runGaet(t, gaetDir, map[string]string{
		"GAET_PSQL": "/nonexistent/psql/should/not/exist",
	}, "push", "--yes")
	if code != core.ExitCloudDown {
		t.Errorf("expected exit code %d (ExitCloudDown for psql failure), got %d", core.ExitCloudDown, code)
	}
	if !strings.Contains(stderr, "cloud") && !strings.Contains(stderr, "Cloud") && !strings.Contains(stderr, "clean") && !strings.Contains(stderr, "reset") {
		t.Errorf("error should mention cloud failure: %s", stderr)
	}
}

// I8: Empty local DB — push creates snapshot with no tables
func TestE2E_Failure_EmptyLocalDB(t *testing.T) {
	ensureDBAvailable(t)
	resetDBsClean(t)
	gaetDir := setupTestEnv(t)

	_, stderr, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push from empty DB exit code %d: %s", code, stderr)
	}

	tables := listTables(t, testRemoteURL)
	if len(tables) != 0 {
		t.Errorf("expected 0 tables on remote after push, got %d: %v", len(tables), tables)
	}
}