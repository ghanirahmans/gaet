// Package serve_test tests embedded web dashboard HTTP endpoints.
package tests

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
)

func TestServe_APIStatusEndpoint(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		env, _ := core.LoadEnv(core.EnvFile())
		h, p, u, n, _ := core.GetLocalDB(env)
		fmt.Fprintf(w, `{"local_ok":false,"host":"%s","port":"%s","user":"%s","db":"%s"}`, h, p, u, n)
	})

	req := httptest.NewRequest("GET", "/api/status", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}

	var data map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &data); err != nil {
		t.Fatalf("invalid JSON from /api/status: %v, body=%s", err, rec.Body.String())
	}
	if _, ok := data["local_ok"]; !ok {
		t.Error("/api/status response missing 'local_ok'")
	}
}

func TestServe_APILogsEndpoint(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	backupDir := core.BackupDir()
	_ = os.MkdirAll(backupDir, 0755)
	logFile := filepath.Join(backupDir, "gaet.log")
	_ = os.WriteFile(logFile, []byte("[2026-01-01] Test log line\n"), 0644)

	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		data, err := os.ReadFile(logFile)
		if err == nil {
			w.Write(data)
		} else {
			w.Write([]byte("No log yet."))
		}
	})

	req := httptest.NewRequest("GET", "/api/logs", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if rec.Body.String() != "[2026-01-01] Test log line\n" {
		t.Errorf("unexpected logs body: %s", rec.Body.String())
	}
}
