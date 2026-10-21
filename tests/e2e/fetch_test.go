//go:build e2e

package e2e

import (
	"path/filepath"
	"strings"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// D1: Diverge local, then fetch --yes — local row counts == remote's
func TestE2E_Fetch_SyncsLocalFromRemote(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	seedDB(t, testRemoteURL)
	gaetDir := setupTestEnv(t)

	dbExec(t, testLocalURL, "DELETE FROM order_items WHERE id > 3000;")
	dbExec(t, testLocalURL, "DELETE FROM audit_log WHERE id > 1000;")

	localItems := getTableRowCount(t, testLocalURL, "order_items")
	if localItems >= 6000 {
		t.Fatalf("expected local order_items < 6000 after delete, got %d", localItems)
	}

	_, _, code := runGaet(t, gaetDir, nil, "fetch", "--yes")
	if code != 0 {
		t.Fatalf("fetch exit code %d", code)
	}

	assertRowCounts(t, testLocalURL)
}

// D2: Safety snapshot created on fetch
func TestE2E_Fetch_SafetySnapshot(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	seedDB(t, testRemoteURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "fetch", "--yes")
	if code != 0 {
		t.Fatalf("fetch exit code %d", code)
	}

	backupDir := filepath.Join(gaetDir, "backups")
	safetyDumps, _ := filepath.Glob(filepath.Join(backupDir, "safety_fetch_*.dump"))
	if len(safetyDumps) == 0 {
		t.Error("expected safety_fetch_*.dump to exist after fetch")
	}

	if len(safetyDumps) > 0 {
		if err := verifyDump(safetyDumps[0]); err != nil {
			t.Errorf("safety snapshot is corrupt: %v", err)
		}
	}
}

// D3: Forced local reset failure via failing psql stub
func TestE2E_Fetch_ResetFailure(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	seedDB(t, testRemoteURL)
	gaetDir := setupTestEnv(t)

	failPsql := toolShimScript(t, "psql", "reset failed", 1)
	_, stderr, code := runGaet(t, gaetDir, map[string]string{
		"GAET_PSQL": failPsql,
	}, "fetch", "--yes")
	if code != core.ExitGeneral {
		t.Errorf("expected exit code %d (ExitGeneral), got %d", core.ExitGeneral, code)
	}

	if !strings.Contains(stderr, "safety") && !strings.Contains(stderr, "snapshot") {
		t.Errorf("error should mention safety snapshot: %s", stderr)
	}
}

// D4: Fetch without --yes in non-TTY → ExitConfig
func TestE2E_Fetch_NoYesNonTTY(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	seedDB(t, testRemoteURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "fetch")
	if code != core.ExitConfig {
		t.Errorf("expected exit code %d (ExitConfig), got %d", core.ExitConfig, code)
	}
}

// D5: Fetch when remote empty — local emptied
func TestE2E_Fetch_EmptyRemote(t *testing.T) {
	ensureDBAvailable(t)
	resetDBsClean(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "fetch", "--yes")
	if code != 0 {
		t.Fatalf("fetch from empty remote exit code %d", code)
	}

	tables := listTables(t, testLocalURL)
	if len(tables) != 0 {
		t.Errorf("expected 0 tables on local after fetch from empty remote, got %d: %v", len(tables), tables)
	}
}

// D6: fetch --json
func TestE2E_Fetch_JSON(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	seedDB(t, testRemoteURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "fetch", "--yes", "--json")
	if code != 0 {
		t.Fatalf("fetch --json exit code %d", code)
	}
}
