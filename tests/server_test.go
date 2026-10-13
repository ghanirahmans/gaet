// Package serve_test tests the embedded web dashboard HTTP endpoints
// against the real serve.Handler() mux, not inline mocks.
package tests

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
	"github.com/ghanirahmans/gaet/pkg/serve"
)

// newTestServer creates an httptest.Server backed by the real serve.Handler().
// It sets GAET_DIR so the handlers resolve a temp backup dir.
func newTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)
	_ = os.MkdirAll(core.BackupDir(), 0755)
	srv := httptest.NewServer(serve.Handler())
	t.Cleanup(srv.Close)
	return srv
}

func TestServe_APIStatusEndpoint(t *testing.T) {
	srv := newTestServer(t)
	resp, err := http.Get(srv.URL + "/api/status")
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
	if _, ok := data["local_ok"]; !ok {
		t.Error("response missing 'local_ok'")
	}
	if _, ok := data["tables"]; !ok {
		t.Error("response missing 'tables'")
	}
}

func TestServe_APILogsEndpoint(t *testing.T) {
	srv := newTestServer(t)

	backupDir := core.BackupDir()
	logFile := filepath.Join(backupDir, "gaet.log")
	_ = os.WriteFile(logFile, []byte("[2026-01-01] Test log line\n"), 0644)

	resp, err := http.Get(srv.URL + "/api/logs")
	if err != nil {
		t.Fatalf("GET /api/logs: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	logs, ok := data["logs"].([]any)
	if !ok {
		t.Fatalf("response missing 'logs' array: %v", data)
	}
	if len(logs) == 0 {
		t.Error("expected at least one log line")
	}
}

func TestServe_APISnapshotsEndpoint(t *testing.T) {
	srv := newTestServer(t)
	resp, err := http.Get(srv.URL + "/api/snapshots")
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

func TestServe_StaticRootServesEmbeddedAssets(t *testing.T) {
	srv := newTestServer(t)
	resp, err := http.Get(srv.URL + "/")
	if err != nil {
		t.Fatalf("GET /: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 for static root, got %d", resp.StatusCode)
	}
}

func TestServe_APICheckEndpoint(t *testing.T) {
	srv := newTestServer(t)
	resp, err := http.Get(srv.URL + "/api/check")
	if err != nil {
		t.Fatalf("GET /api/check: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if _, ok := data["ok"]; !ok {
		t.Error("response missing 'ok'")
	}
	if _, ok := data["checks"]; !ok {
		t.Error("response missing 'checks'")
	}
}

func TestServe_APIJobsUnknownID(t *testing.T) {
	srv := newTestServer(t)
	// Must set URL.Path for go 1.21 ServeMux prefix matching on /api/jobs/{id}
	resp, err := http.Get(srv.URL + "/api/jobs/nonexistent-job-id")
	if err != nil {
		t.Fatalf("GET /api/jobs/nonexistent: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404 for unknown job, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if data["ok"] != false {
		t.Error("expected ok=false for unknown job")
	}
}

func TestServe_APIJobsList(t *testing.T) {
	srv := newTestServer(t)
	resp, err := http.Get(srv.URL + "/api/jobs")
	if err != nil {
		t.Fatalf("GET /api/jobs: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	body, _ := io.ReadAll(resp.Body)
	var data map[string]any
	if err := json.Unmarshal(body, &data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}
	if _, ok := data["ok"]; !ok {
		t.Error("response missing 'ok'")
	}
	if _, ok := data["jobs"]; !ok {
		t.Error("response missing 'jobs'")
	}
}

func TestServe_APISnapshotsDownloadUnknown(t *testing.T) {
	srv := newTestServer(t)
	resp, err := http.Get(srv.URL + "/api/snapshots/download?file=nonexistent.dump")
	if err != nil {
		t.Fatalf("GET /api/snapshots/download: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404 for unknown snapshot, got %d", resp.StatusCode)
	}
}

func TestServe_APISnapshotsDeleteUnknown(t *testing.T) {
	srv := newTestServer(t)
	resp, err := http.Post(srv.URL+"/api/snapshots/delete?file=nonexistent.dump", "application/json", nil)
	if err != nil {
		t.Fatalf("POST /api/snapshots/delete: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404 for unknown snapshot delete, got %d", resp.StatusCode)
	}
}

func TestServe_CORS(t *testing.T) {
	srv := newTestServer(t)
	resp, err := http.Get(srv.URL + "/api/status")
	if err != nil {
		t.Fatalf("GET: %v", err)
	}
	defer resp.Body.Close()

	if origin := resp.Header.Get("Access-Control-Allow-Origin"); origin != "*" {
		t.Errorf("expected CORS origin '*', got %q", origin)
	}
}
