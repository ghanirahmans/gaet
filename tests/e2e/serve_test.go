//go:build e2e

package e2e

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/serve"
)

// H1: Serve Handler() works directly with httptest
func TestE2E_Serve_HandlerDirect(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)

	handler := serve.Handler()
	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/api/status")
	if err != nil {
		t.Fatalf("GET /api/status: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}
}

// H2: GET /api/snapshots via Handler
func TestE2E_Serve_SnapshotsViaHandler(t *testing.T) {
	ensureDBAvailable(t)
	gaetDir := setupTestEnv(t)
	os.Setenv("GAET_DIR", gaetDir)
	t.Cleanup(func() { os.Unsetenv("GAET_DIR") })

	handler := serve.Handler()
	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/api/snapshots")
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

	if _, ok := data["count"]; !ok {
		t.Error("expected 'count' field")
	}
}

// H3: GET /api/jobs via Handler
func TestE2E_Serve_JobsViaHandler(t *testing.T) {
	setupTestEnv(t)

	handler := serve.Handler()
	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/api/jobs")
	if err != nil {
		t.Fatalf("GET /api/jobs: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}

	if _, ok := data["jobs"]; !ok {
		t.Error("expected 'jobs' field")
	}
}

// H4: Static index.html served at /
func TestE2E_Serve_StaticAssets(t *testing.T) {
	handler := serve.Handler()
	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/")
	if err != nil {
		t.Fatalf("GET /: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 for index, got %d", resp.StatusCode)
	}

	body, _ := io.ReadAll(resp.Body)
	if !strings.Contains(string(body), "<html") && !strings.Contains(string(body), "<!DOCTYPE") {
		t.Error("index should contain HTML")
	}
}

// H5: POST /api/push?async=1 returns 202
func TestE2E_Serve_PushAsync(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)
	os.Setenv("GAET_DIR", gaetDir)
	t.Cleanup(func() { os.Unsetenv("GAET_DIR") })

	handler := serve.Handler()
	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Post(ts.URL+"/api/push?async=1", "application/json", nil)
	if err != nil {
		t.Fatalf("POST /api/push?async=1: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusAccepted {
		t.Fatalf("expected 202, got %d", resp.StatusCode)
	}
}

// H6: GET /api/status detailed health check
func TestE2E_Serve_StatusDetail(t *testing.T) {
	ensureDBAvailable(t)
	gaetDir := setupTestEnv(t)
	os.Setenv("GAET_DIR", gaetDir)
	t.Cleanup(func() { os.Unsetenv("GAET_DIR") })

	handler := serve.Handler()
	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/api/status")
	if err != nil {
		t.Fatalf("GET /api/status: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}

	expectedFields := []string{"local_ok", "remote_configured", "host", "port", "user"}
	for _, field := range expectedFields {
		if _, ok := data[field]; !ok {
			t.Errorf("expected '%s' field in status response", field)
		}
	}
}

// H7: POST /api/restore with body
func TestE2E_Serve_RestoreWithBody(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)
	os.Setenv("GAET_DIR", gaetDir)
	t.Cleanup(func() { os.Unsetenv("GAET_DIR") })

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	handler := serve.Handler()
	ts := httptest.NewServer(handler)
	defer ts.Close()

	body := `{"filename":"latest","yes":true}`
	resp, err := http.Post(ts.URL+"/api/restore", "application/json", strings.NewReader(body))
	if err != nil {
		t.Fatalf("POST /api/restore: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		t.Fatalf("expected 200 or 202, got %d", resp.StatusCode)
	}
}

// H8: Unknown route returns 404
func TestE2E_Serve_UnknownRoute(t *testing.T) {
	handler := serve.Handler()
	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/api/unknown-route")
	if err != nil {
		t.Fatalf("GET /api/unknown: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusNotFound {
		t.Errorf("expected 404 for unknown route, got %d", resp.StatusCode)
	}
}

// H9: GET /api/snapshots/download returns dump file
func TestE2E_Serve_SnapshotDownload(t *testing.T) {
	gaetDir := setupTestEnv(t)
	os.Setenv("GAET_DIR", gaetDir)
	t.Cleanup(func() { os.Unsetenv("GAET_DIR") })

	backupDir := filepath.Join(gaetDir, "backups")
	if err := os.MkdirAll(backupDir, 0755); err != nil {
		t.Fatal(err)
	}
	dumpData := []byte("test dump content")
	dumpPath := filepath.Join(backupDir, "test_download.dump")
	if err := os.WriteFile(dumpPath, dumpData, 0644); err != nil {
		t.Fatal(err)
	}

	handler := serve.Handler()
	ts := httptest.NewServer(handler)
	defer ts.Close()

	resp, err := http.Get(ts.URL + "/api/snapshots/download?file=test_download.dump")
	if err != nil {
		t.Fatalf("GET /api/snapshots/download: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	body, _ := io.ReadAll(resp.Body)
	if string(body) != string(dumpData) {
		t.Errorf("content mismatch: got %q, want %q", string(body), string(dumpData))
	}
}
