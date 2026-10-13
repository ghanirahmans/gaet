//go:build e2e

package e2e

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// B1: Seeded local → push — all tables present on remote with exact row counts
func TestE2E_Push_Seeded(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	assertRowCounts(t, testRemoteURL)
}

// B2: Atomic dump publish — exactly one gaet_*.dump, no .tmp left, pg_restore --list exits 0
func TestE2E_Push_AtomicDump(t *testing.T) {
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
	tmpFiles, _ := filepath.Glob(filepath.Join(backupDir, "gaet_*.tmp"))
	if len(gaetDumps) != 1 {
		t.Errorf("expected exactly 1 gaet_*.dump, got %d", len(gaetDumps))
	}
	if len(tmpFiles) != 0 {
		t.Errorf("expected 0 .tmp files, got %d: %v", len(tmpFiles), tmpFiles)
	}

	cmd := exec.Command("pg_restore", "--list", gaetDumps[0])
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Errorf("pg_restore --list failed: %v\noutput: %s", err, out)
	}
}

// B3: Integrity failure — stub pg_restore fails during integrity check
func TestE2E_Push_IntegrityFailure(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := t.TempDir()
	writeEnvFile(t, gaetDir, baseEnvContent(testLocalURL, testRemoteURL))

	failRestore := toolShimScript(t, "pg_restore", "integrity check failed", 1)
	_, _, code := runGaet(t, gaetDir, map[string]string{
		"GAET_PG_RESTORE": failRestore,
	}, "push", "--yes")
	if code != core.ExitGeneral {
		t.Errorf("expected exit code %d (ExitGeneral), got %d", core.ExitGeneral, code)
	}

	backupDir := filepath.Join(gaetDir, "backups")
	gaetDumps, _ := filepath.Glob(filepath.Join(backupDir, "gaet_*.dump"))
	if len(gaetDumps) != 0 {
		t.Errorf("expected 0 published dumps after integrity failure, got %d", len(gaetDumps))
	}
}

// B4: Remote clean-then-restore semantics — remote tables dropped before restore
func TestE2E_Push_CleanRemoteThenRestore(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	dbExec(t, testRemoteURL, "CREATE TABLE remote_only_table (id int); INSERT INTO remote_only_table VALUES (1);")

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	if tableExists(t, testRemoteURL, "remote_only_table") {
		t.Error("remote_only_table should have been dropped by push")
	}
	assertRowCounts(t, testRemoteURL)
}

// B5: push --json
func TestE2E_Push_JSON(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	out, _, code := runGaet(t, gaetDir, nil, "push", "--yes", "--json")
	if code != 0 {
		t.Fatalf("push --json exit code %d", code)
	}

	// JSON output may have log lines before it; extract the last JSON object
	jsonStart := strings.LastIndex(out, "{")
	if jsonStart == -1 {
		t.Fatalf("no JSON object found in output: %s", out)
	}
	jsonStr := out[jsonStart:]
	var result map[string]any
	if err := json.Unmarshal([]byte(jsonStr), &result); err != nil {
		t.Fatalf("invalid JSON from push --json: %v\noutput: %s", err, out)
	}
	if result["ok"] != true {
		t.Errorf("expected ok=true, got %v", result["ok"])
	}
}

// B6: Drain/overwrite — push empty local over larger remote
func TestE2E_Push_OverwriteLargerRemote(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	// Seed remote with data, then clean local to be empty
	seedDB(t, testRemoteURL)
	cleanupDB(t, testLocalURL)

	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	tables := listTables(t, testRemoteURL)
	if len(tables) != 0 {
		t.Errorf("expected 0 tables after overwriting with empty local, got %d: %v", len(tables), tables)
	}
}

// B7: Retention on push — old dumps removed
func TestE2E_Push_Retention(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := t.TempDir()

	envContent := baseEnvContent(testLocalURL, testRemoteURL)
	envContent += "GAET_RETENTION_DAYS=7\n"
	writeEnvFile(t, gaetDir, envContent)

	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	oldDump := filepath.Join(backupDir, "gaet_old_20260101_000000.dump")
	_ = os.WriteFile(oldDump, []byte("OLD DATA"), 0644)
	oldTime := time.Now().AddDate(0, 0, -10)
	_ = os.Chtimes(oldDump, oldTime, oldTime)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	if _, err := os.Stat(oldDump); err == nil {
		t.Error("old dump should have been removed by retention")
	}

	newDumps, _ := filepath.Glob(filepath.Join(backupDir, "gaet_*.dump"))
	if len(newDumps) != 1 {
		t.Errorf("expected 1 new dump after push, got %d", len(newDumps))
	}
}

// B8: Parallel dump GAET_DUMP_JOBS=3
func TestE2E_Push_ParallelDump(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, map[string]string{"GAET_DUMP_JOBS": "3"}, "push", "--yes")
	if code != 0 {
		t.Fatalf("parallel push exit code %d", code)
	}

	backupDir := filepath.Join(gaetDir, "backups")
	gaetDumps, _ := filepath.Glob(filepath.Join(backupDir, "gaet_*.dump"))
	if len(gaetDumps) != 1 {
		t.Errorf("expected 1 dump, got %d", len(gaetDumps))
	}
	assertRowCounts(t, testRemoteURL)
}

// B9: push while lock held → ExitLocked
func TestE2E_Push_LockContention(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)
	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	// Write a lock with the current process's PID (not stale)
	lockPath := filepath.Join(backupDir, ".gaet.lock")
	_ = os.WriteFile(lockPath, []byte(fmt.Sprintf("%d", os.Getpid())), 0600)
	t.Cleanup(func() { os.Remove(lockPath) })

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != core.ExitLocked {
		t.Errorf("expected exit code %d (ExitLocked), got %d", core.ExitLocked, code)
	}
}

// B10: Remote unreachable (bad host) → ExitCloudDown
func TestE2E_Push_RemoteUnreachable(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := t.TempDir()
	badURL := "postgresql://gaet:testpass@127.0.0.1:99999/gaet_remote"
	writeEnvFile(t, gaetDir, baseEnvContent(testLocalURL, badURL))

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != core.ExitCloudDown {
		t.Errorf("expected exit code %d (ExitCloudDown), got %d", core.ExitCloudDown, code)
	}

	backupDir := filepath.Join(gaetDir, "backups")
	gaetDumps, _ := filepath.Glob(filepath.Join(backupDir, "gaet_*.dump"))
	if len(gaetDumps) == 0 {
		t.Error("expected local snapshot to be published before remote failure")
	}
}