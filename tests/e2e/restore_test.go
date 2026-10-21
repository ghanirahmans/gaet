//go:build e2e

package e2e

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// E1: restore latest --yes after mutating local — local matches snapshot
func TestE2E_Restore_LatestAfterMutation(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	dbExec(t, testLocalURL, "DELETE FROM order_items WHERE id > 3000;")
	dbExec(t, testLocalURL, "DELETE FROM audit_log WHERE id > 1000;")

	mutatedItems := getTableRowCount(t, testLocalURL, "order_items")
	if mutatedItems >= 6000 {
		t.Fatalf("expected local order_items < 6000 after mutation, got %d", mutatedItems)
	}

	_, _, code = runGaet(t, gaetDir, nil, "restore", "latest", "--yes")
	if code != 0 {
		t.Fatalf("restore exit code %d", code)
	}

	assertRowCounts(t, testLocalURL)
}

// E2: restore <name> partial-match resolves correctly
func TestE2E_Restore_PartialMatch(t *testing.T) {
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

	dumpName := filepath.Base(gaetDumps[0])
	parts := strings.Split(dumpName, "_")
	if len(parts) < 2 {
		t.Fatalf("unexpected dump name format: %s", dumpName)
	}
	partial := "gaet_" + parts[1]

	// Mutate local - delete from child tables first to avoid FK violations
	dbExec(t, testLocalURL, "DELETE FROM order_items WHERE order_id > 2000;")
	dbExec(t, testLocalURL, "DELETE FROM payments WHERE order_id > 2000;")
	dbExec(t, testLocalURL, "DELETE FROM orders WHERE id > 2000;")

	_, _, code = runGaet(t, gaetDir, nil, "restore", partial, "--yes")
	if code != 0 {
		t.Fatalf("restore with partial match exit code %d", code)
	}

	assertRowCounts(t, testLocalURL)
}

// E3: restore <nonexistent> → ExitGeneral
func TestE2E_Restore_Nonexistent(t *testing.T) {
	gaetDir := t.TempDir()
	writeEnvFile(t, gaetDir, baseEnvContent(testLocalURL, testRemoteURL))
	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	_, stderr, code := runGaet(t, gaetDir, nil, "restore", "nonexistent_snapshot.dump", "--yes")
	if code != core.ExitGeneral {
		t.Errorf("expected exit code %d (ExitGeneral), got %d", core.ExitGeneral, code)
	}
	if !strings.Contains(stderr, "No snapshots") && !strings.Contains(stderr, "not found") {
		t.Errorf("error should mention snapshots not found: %s", stderr)
	}
}

// E4: Corrupt snapshot — integrity check fails, DB not reset
func TestE2E_Restore_CorruptSnapshot(t *testing.T) {
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
	if err := os.WriteFile(dumpPath, []byte("CORRUPTED DATA NOT A VALID DUMP"), 0644); err != nil {
		t.Fatal(err)
	}

	beforeTables := len(listTables(t, testLocalURL))

	_, _, code = runGaet(t, gaetDir, nil, "restore", "latest", "--yes")
	if code != core.ExitConfig {
		t.Errorf("expected exit code %d (ExitConfig) for corrupt snapshot, got %d", core.ExitConfig, code)
	}

	afterTables := len(listTables(t, testLocalURL))
	if afterTables != beforeTables {
		t.Errorf("DB should not be reset on corrupt snapshot: before=%d, after=%d", beforeTables, afterTables)
	}
}

// E5: Safety snapshot on restore
func TestE2E_Restore_SafetySnapshot(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	// Mutate local - delete from child tables first to avoid FK violations
	// order_items and payments reference orders, so delete those for any order
	// that references a user > 500 OR has id > 2000
	dbExec(t, testLocalURL, "DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE id > 2000 OR user_id > 500);")
	dbExec(t, testLocalURL, "DELETE FROM payments WHERE order_id IN (SELECT id FROM orders WHERE id > 2000 OR user_id > 500);")
	dbExec(t, testLocalURL, "DELETE FROM orders WHERE id > 2000 OR user_id > 500;")
	dbExec(t, testLocalURL, "DELETE FROM audit_log WHERE order_id > 2000 OR user_id > 500;")
	dbExec(t, testLocalURL, "DELETE FROM users WHERE id > 500;")

	_, _, code = runGaet(t, gaetDir, nil, "restore", "latest", "--yes")
	if code != 0 {
		t.Fatalf("restore exit code %d", code)
	}

	backupDir := filepath.Join(gaetDir, "backups")
	safetyDumps, _ := filepath.Glob(filepath.Join(backupDir, "safety_restore_*.dump"))
	if len(safetyDumps) == 0 {
		t.Error("expected safety_restore_*.dump to exist after restore")
	}

	if len(safetyDumps) > 0 {
		if err := verifyDump(safetyDumps[0]); err != nil {
			t.Errorf("safety snapshot is corrupt: %v", err)
		}
	}
}

// E6: No snapshots at all → ExitGeneral
func TestE2E_Restore_NoSnapshots(t *testing.T) {
	gaetDir := t.TempDir()
	writeEnvFile(t, gaetDir, baseEnvContent(testLocalURL, testRemoteURL))
	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	_, _, code := runGaet(t, gaetDir, nil, "restore", "latest", "--yes")
	if code != core.ExitGeneral {
		t.Errorf("expected exit code %d (ExitGeneral), got %d", core.ExitGeneral, code)
	}
}

// E7: restore picks newest via globDumps modtime sort
func TestE2E_Restore_PicksNewestMtime(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)
	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	for i, name := range []string{"gaet_older.dump", "gaet_middle.dump", "gaet_newest.dump"} {
		f := filepath.Join(backupDir, name)
		_ = os.WriteFile(f, []byte("FAKE"), 0644)
		mtime := time.Now().Add(-time.Duration(3-i) * time.Hour)
		_ = os.Chtimes(f, mtime, mtime)
	}

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	_, _, code = runGaet(t, gaetDir, nil, "restore", "latest", "--yes")
	if code != 0 {
		t.Fatalf("restore exit code %d", code)
	}

	assertRowCounts(t, testLocalURL)
}

// E8: restore without --yes non-TTY → ExitConfig
func TestE2E_Restore_NoYesNonTTY(t *testing.T) {
	gaetDir := t.TempDir()
	writeEnvFile(t, gaetDir, baseEnvContent(testLocalURL, testRemoteURL))
	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)
	dumpFile := filepath.Join(backupDir, "gaet_20260101_000000.dump")
	_ = os.WriteFile(dumpFile, []byte("DUMMY"), 0644)

	_, _, code := runGaet(t, gaetDir, nil, "restore", "latest")
	if code != core.ExitConfig {
		t.Errorf("expected exit code %d (ExitConfig), got %d", core.ExitConfig, code)
	}
}