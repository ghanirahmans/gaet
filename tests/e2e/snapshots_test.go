//go:build e2e

package e2e

import (
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// F1: snapshots --json lists all *.dump
func TestE2E_Snapshots_JSON(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)
	for _, name := range []string{"gaet_20260101_120000.dump", "gaet_20260102_130000.dump", "gaet_20260103_140000.dump"} {
		_ = os.WriteFile(filepath.Join(backupDir, name), []byte("FAKE"), 0644)
	}

	out, _, code := runGaet(t, gaetDir, nil, "snapshots", "--json")
	if code != 0 {
		t.Fatalf("snapshots --json exit code %d", code)
	}

	var result map[string]any
	if err := json.Unmarshal([]byte(out), &result); err != nil {
		t.Fatalf("invalid JSON: %v\noutput: %s", err, out)
	}
	count, ok := result["count"].(float64)
	if !ok {
		t.Fatalf("expected count field, got: %v", result)
	}
	if count != 3 {
		t.Errorf("expected 3 snapshots, got %f", count)
	}
}

// F2: REST GET /api/snapshots — JSON list matches
func TestE2E_REST_SnapshotsList(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)
	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)
	_ = os.WriteFile(filepath.Join(backupDir, "gaet_test.dump"), []byte("FAKE"), 0644)

	baseURL := startServe(t, gaetDir)

	resp, err := http.Get(baseURL + "/api/snapshots")
	if err != nil {
		t.Fatalf("GET /api/snapshots: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if _, ok := data["snapshots"]; !ok {
		t.Error("response missing 'snapshots'")
	}
	if _, ok := data["count"]; !ok {
		t.Error("response missing 'count'")
	}
}

// F3: REST DELETE /api/snapshots/delete — file removed; 404 for unknown
func TestE2E_REST_SnapshotDelete(t *testing.T) {
	ensureDBAvailable(t)
	gaetDir := setupTestEnv(t)
	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	dumpName := "gaet_test_delete.dump"
	dumpPath := filepath.Join(backupDir, dumpName)
	_ = os.WriteFile(dumpPath, []byte("DELETE ME"), 0644)

	baseURL := startServe(t, gaetDir)

	body := `{"file":"` + dumpName + `"}`
	resp, err := http.Post(baseURL+"/api/snapshots/delete", "application/json", strings.NewReader(body))
	if err != nil {
		t.Fatalf("POST /api/snapshots/delete: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	if _, err := os.Stat(dumpPath); err == nil {
		t.Error("dump file should have been deleted")
	}

	resp2, err := http.Post(baseURL+"/api/snapshots/delete?file=nonexistent.dump", "application/json", nil)
	if err != nil {
		t.Fatalf("POST unknown: %v", err)
	}
	defer resp2.Body.Close()
	if resp2.StatusCode != http.StatusNotFound {
		t.Errorf("expected 404 for unknown snapshot, got %d", resp2.StatusCode)
	}
}

// F4: REST GET /api/snapshots/download — 200 + body bytes == file; 404 for unknown
func TestE2E_REST_SnapshotDownload(t *testing.T) {
	ensureDBAvailable(t)
	gaetDir := setupTestEnv(t)
	backupDir := filepath.Join(gaetDir, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	dumpName := "gaet_download_test.dump"
	dumpData := []byte("DOWNLOAD ME PLEASE")
	dumpPath := filepath.Join(backupDir, dumpName)
	_ = os.WriteFile(dumpPath, dumpData, 0644)

	baseURL := startServe(t, gaetDir)

	resp, err := http.Get(baseURL + "/api/snapshots/download?file=" + dumpName)
	if err != nil {
		t.Fatalf("GET /api/snapshots/download: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	body, _ := io.ReadAll(resp.Body)
	if string(body) != string(dumpData) {
		t.Errorf("downloaded content mismatch: got %q, want %q", string(body), string(dumpData))
	}

	resp2, err := http.Get(baseURL + "/api/snapshots/download?file=nonexistent.dump")
	if err != nil {
		t.Fatalf("GET unknown: %v", err)
	}
	resp2.Body.Close()
	if resp2.StatusCode != http.StatusNotFound {
		t.Errorf("expected 404 for unknown snapshot, got %d", resp2.StatusCode)
	}
}

// F5: Empty backup dir — no error, empty list
func TestE2E_REST_SnapshotsEmptyDir(t *testing.T) {
	gaetDir := setupTestEnv(t)
	baseURL := startServe(t, gaetDir)

	resp, err := http.Get(baseURL + "/api/snapshots")
	if err != nil {
		t.Fatalf("GET /api/snapshots: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	count, ok := data["count"].(float64)
	if !ok {
		t.Fatalf("expected count field, got: %v", data)
	}
	if count != 0 {
		t.Errorf("expected 0 snapshots in empty dir, got %f", count)
	}
}

// I4: Path traversal in snapshot name — rejected
func TestE2E_REST_SnapshotDownloadPathTraversal(t *testing.T) {
	gaetDir := setupTestEnv(t)
	_ = os.MkdirAll(filepath.Join(gaetDir, "backups"), 0755)
	baseURL := startServe(t, gaetDir)

	resp, err := http.Get(baseURL + "/api/snapshots/download?file=../../../etc/passwd")
	if err != nil {
		t.Fatalf("GET: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		t.Error("path traversal should not return 200")
	}
}