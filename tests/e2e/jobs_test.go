//go:build e2e

package e2e

import (
	"encoding/json"
	"net/http"
	"strings"
	"testing"
)

// G1: POST /api/push?async=1 starts a job, returns jobID, polls to success
func TestE2E_Job_AsyncPush(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)
	baseURL := startServe(t, gaetDir)

	resp, err := http.Post(baseURL+"/api/push?async=1", "application/json", nil)
	if err != nil {
		t.Fatalf("POST /api/push?async=1: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusAccepted {
		t.Fatalf("expected 202, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}

	jobID, ok := data["job_id"].(string)
	if !ok {
		t.Fatalf("expected job_id in response: %v", data)
	}

	result := pollJob(t, baseURL, jobID)
	job, ok := result["job"].(map[string]any)
	if !ok {
		t.Fatalf("expected job field: %v", result)
	}

	status, ok := job["status"].(string)
	if !ok {
		t.Fatalf("expected status field: %v", job)
	}

	if status != "success" {
		t.Errorf("expected status 'success', got '%s'", status)
	}

	assertRowCounts(t, testRemoteURL)
}

// G2: POST /api/fetch?async=1 starts a job, polls to success
func TestE2E_Job_AsyncFetch(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	seedDB(t, testRemoteURL)
	gaetDir := setupTestEnv(t)
	baseURL := startServe(t, gaetDir)

	resp, err := http.Post(baseURL+"/api/fetch?async=1", "application/json", nil)
	if err != nil {
		t.Fatalf("POST /api/fetch?async=1: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusAccepted {
		t.Fatalf("expected 202, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}

	jobID, ok := data["job_id"].(string)
	if !ok {
		t.Fatalf("expected job_id in response: %v", data)
	}

	result := pollJob(t, baseURL, jobID)
	job, ok := result["job"].(map[string]any)
	if !ok {
		t.Fatalf("expected job field: %v", result)
	}

	status, ok := job["status"].(string)
	if !ok {
		t.Fatalf("expected status field: %v", job)
	}

	if status != "success" {
		t.Errorf("expected status 'success', got '%s'", status)
	}
}

// G3: GET /api/jobs — lists active and completed jobs
func TestE2E_Job_ListJobs(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)
	baseURL := startServe(t, gaetDir)

	resp, err := http.Get(baseURL + "/api/jobs")
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
		t.Error("expected 'jobs' field in response")
	}
}

// G4: GET /api/jobs/{id} — returns 404 for unknown job
func TestE2E_Job_GetUnknown(t *testing.T) {
	ensureDBAvailable(t)
	gaetDir := setupTestEnv(t)
	baseURL := startServe(t, gaetDir)

	resp, err := http.Get(baseURL + "/api/jobs/nonexistent-job-id")
	if err != nil {
		t.Fatalf("GET /api/jobs/unknown: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusNotFound {
		t.Errorf("expected 404, got %d", resp.StatusCode)
	}
}

// G5: Job eviction after 50+ jobs
func TestE2E_Job_Eviction(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)
	baseURL := startServe(t, gaetDir)

	maxJobs := 55
	var jobIDs []string

	for i := 0; i < maxJobs; i++ {
		resp, err := http.Post(baseURL+"/api/push?async=1", "application/json", nil)
		if err != nil {
			t.Logf("job %d start: %v", i, err)
			continue
		}
		var data map[string]any
		if err := json.NewDecoder(resp.Body).Decode(&data); err == nil {
			if id, ok := data["job_id"].(string); ok {
				jobIDs = append(jobIDs, id)
			}
		}
		resp.Body.Close()
	}

	for _, id := range jobIDs {
		pollJob(t, baseURL, id)
	}

	resp, err := http.Get(baseURL + "/api/jobs")
	if err != nil {
		t.Fatalf("GET /api/jobs: %v", err)
	}
	defer resp.Body.Close()

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}

	jobs, ok := data["jobs"].([]any)
	if !ok {
		t.Fatalf("expected jobs array: %v", data)
	}

	if len(jobs) > 50 {
		t.Errorf("expected at most 50 jobs (eviction), got %d", len(jobs))
	}
}

// G6: POST /api/restore with async — starts job, restores from snapshot
func TestE2E_Job_AsyncRestore(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	seedDB(t, testLocalURL)
	gaetDir := setupTestEnv(t)

	_, _, code := runGaet(t, gaetDir, nil, "push", "--yes")
	if code != 0 {
		t.Fatalf("push exit code %d", code)
	}

	dbExec(t, testLocalURL, "DELETE FROM users WHERE id > 500;")

	baseURL := startServe(t, gaetDir)

	body := `{"filename":"latest","yes":true}`
	resp, err := http.Post(baseURL+"/api/restore?async=1", "application/json", strings.NewReader(body))
	if err != nil {
		t.Fatalf("POST /api/restore?async=1: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusAccepted {
		t.Fatalf("expected 202, got %d", resp.StatusCode)
	}

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		t.Fatalf("invalid JSON: %v", err)
	}

	jobID, ok := data["job_id"].(string)
	if !ok {
		t.Fatalf("expected job_id in response: %v", data)
	}

	result := pollJob(t, baseURL, jobID)
	job, ok := result["job"].(map[string]any)
	if !ok {
		t.Fatalf("expected job field: %v", result)
	}

	status, ok := job["status"].(string)
	if !ok {
		t.Fatalf("expected status field: %v", job)
	}

	if status != "success" {
		t.Errorf("expected status 'success', got '%s'", status)
	}

	assertRowCounts(t, testLocalURL)
}

// G7: GET /api/status — returns 200 with DB status
func TestE2E_Job_StatusEndpoint(t *testing.T) {
	ensureDBAvailable(t)
	gaetDir := setupTestEnv(t)
	baseURL := startServe(t, gaetDir)

	resp, err := http.Get(baseURL + "/api/status")
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

	if _, ok := data["status"]; !ok {
		t.Error("expected 'status' field in response")
	}
}
