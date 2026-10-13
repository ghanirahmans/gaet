package serve

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// waitForJob polls a job until it transitions out of "running" or times out.
func waitForJob(t *testing.T, id string) jobState {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		st, ok := getJob(id)
		if !ok {
			t.Fatal("job disappeared")
		}
		if st.Status != "running" {
			return st
		}
		time.Sleep(10 * time.Millisecond)
	}
	st, _ := getJob(id)
	t.Fatalf("job did not finish within 5s: status=%s", st.Status)
	return st
}

func TestWantAsync_TruthTable(t *testing.T) {
	cases := []struct {
		query  string
		expect bool
	}{
		{"1", true},
		{"true", true},
		{"yes", true},
		{"True", true},
		{"YES", true},
		{"0", false},
		{"", false},
		{"no", false},
		{"other", false},
		{"2", false},
	}
	for _, tc := range cases {
		req := httptest.NewRequest(http.MethodPost, "/api/push?async="+tc.query, nil)
		if got := wantAsync(req); got != tc.expect {
			t.Errorf("wantAsync(async=%q) = %v, want %v", tc.query, got, tc.expect)
		}
	}
}

func TestWantAsync_NoQueryParam(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/api/push", nil)
	if wantAsync(req) {
		t.Error("wantAsync without query param should be false")
	}
}

func TestJobsStore_StartsRunning(t *testing.T) {
	id := startJob("test", func() error { return nil })
	if id == "" {
		t.Fatal("startJob returned empty id")
	}
	st, ok := getJob(id)
	if !ok {
		t.Fatal("getJob returned false for existing job")
	}
	if st.Status != "running" {
		t.Errorf("expected running, got %s", st.Status)
	}
	if st.Name != "test" {
		t.Errorf("expected name 'test', got %s", st.Name)
	}
	if !st.FinishedAt.IsZero() {
		t.Error("FinishedAt should be zero at start")
	}
}

func TestJobsStore_TransitionsToSuccess(t *testing.T) {
	id := startJob("test", func() error { return nil })
	st, _ := getJob(id)
	if st.Status != "running" {
		t.Fatalf("expected running initially, got %s", st.Status)
	}
	st = waitForJob(t, id)
	if st.Status != "success" {
		t.Errorf("expected success, got %s", st.Status)
	}
	if st.Message != "completed" {
		t.Errorf("expected message 'completed', got %s", st.Message)
	}
	if st.FinishedAt.IsZero() {
		t.Error("FinishedAt should be set on success")
	}
}

func TestJobsStore_TransitionsToFailed(t *testing.T) {
	id := startJob("test", func() error { return errors.New("boom") })
	st := waitForJob(t, id)
	if st.Status != "failed" {
		t.Errorf("expected failed, got %s", st.Status)
	}
	if st.Message == "" {
		t.Error("expected non-empty message on failure")
	}
}

func TestJobsStore_GetUnknownID(t *testing.T) {
	_, ok := getJob("does-not-exist-12345")
	if ok {
		t.Error("getJob should return false for unknown id")
	}
}

func TestJobsStore_ListJobs(t *testing.T) {
	id1 := startJob("test1", func() error { return nil })
	id2 := startJob("test2", func() error { return nil })
	jobs := listJobs()
	if len(jobs) < 2 {
		t.Fatalf("expected at least 2 jobs, got %d", len(jobs))
	}
	found1, found2 := false, false
	for _, j := range jobs {
		if j.ID == id1 {
			found1 = true
		}
		if j.ID == id2 {
			found2 = true
		}
	}
	if !found1 || !found2 {
		t.Error("listJobs should contain both started jobs")
	}
}

func TestJobsStore_CapsAt50(t *testing.T) {
	jobsMu.Lock()
	jobsByID = map[string]*jobState{}
	jobsOrder = []string{}
	jobsSeq = 0
	jobsMu.Unlock()

	for i := 0; i < 60; i++ {
		startJob("cap", func() error { return nil })
	}
	jobs := listJobs()
	if len(jobs) > 50 {
		t.Errorf("expected at most 50 jobs, got %d", len(jobs))
	}
	if len(jobs) != 50 {
		t.Errorf("expected exactly 50 jobs, got %d", len(jobs))
	}
}

func TestJobsStore_EvictsOldest(t *testing.T) {
	jobsMu.Lock()
	jobsByID = map[string]*jobState{}
	jobsOrder = []string{}
	jobsSeq = 0
	jobsMu.Unlock()

	id1 := startJob("evict", func() error { return nil })
	id2 := startJob("evict", func() error { return nil })

	for i := 0; i < 50; i++ {
		startJob("fill", func() error { return nil })
	}

	jobs := listJobs()
	if len(jobs) > 50 {
		t.Fatalf("expected at most 50, got %d", len(jobs))
	}
	for _, j := range jobs {
		if j.ID == id1 || j.ID == id2 {
			t.Errorf("oldest jobs should have been evicted: found %s", j.ID)
		}
	}
}
