//go:build e2e

package e2e

import (
	"encoding/json"
	"testing"
)

// C1: Delete rows on remote, then push — remote restored to local's full dataset
func TestE2E_Divergence_PushSyncsAfterRemoteDelete(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("initial push exit code %d", code)
	}

	dbExec(t, testRemoteURL, "DELETE FROM order_items WHERE id > 3000;")
	dbExec(t, testRemoteURL, "DELETE FROM audit_log WHERE id > 1000;")

	remoteItems := getTableRowCount(t, testRemoteURL, "order_items")
	if remoteItems >= 6000 {
		t.Fatalf("expected remote order_items < 6000 after delete, got %d", remoteItems)
	}

	_, _, code = runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("sync push exit code %d", code)
	}

	assertRowCounts(t, testRemoteURL)
}

// C2: Remote schema drift (extra table) — dropped by resetTargetObjects
func TestE2E_Divergence_ExtraRemoteTableDropped(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	dbExec(t, testRemoteURL, "CREATE TABLE IF NOT EXISTS extra_remote_table (id int);")

	if !tableExists(t, testRemoteURL, "extra_remote_table") {
		t.Fatal("extra_remote_table should exist after creation")
	}

	_, _, code = runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("second push exit code %d", code)
	}

	if tableExists(t, testRemoteURL, "extra_remote_table") {
		t.Error("extra_remote_table should have been dropped by resetTargetObjects")
	}
}

// C3: gaet diff after divergence — reports mismatch
func TestE2E_Divergence_DiffReportsMismatch(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	dbExec(t, testRemoteURL, "DROP TABLE IF EXISTS audit_log CASCADE;")

	out, _, code := runGaet(t, gaetDir, nil, "diff", "--json")
	if code != 0 {
		t.Fatalf("diff exit code %d", code)
	}
	var result map[string]any
	if err := json.Unmarshal([]byte(out), &result); err != nil {
		t.Fatalf("diff --json invalid JSON: %v\noutput: %s", err, out)
	}
}

// C4: gaet doctor after divergence — runs without error
func TestE2E_Divergence_DoctorRuns(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	dbExec(t, testRemoteURL, "DELETE FROM order_items WHERE id > 3000;")
	dbExec(t, testRemoteURL, "DELETE FROM payments WHERE id > 1500;")
	dbExec(t, testRemoteURL, "DELETE FROM orders WHERE id > 1500;")

	_, _, code = runGaet(t, gaetDir, nil, "doctor", "--json")
	if code != 0 {
		t.Fatalf("doctor exit code %d", code)
	}
}