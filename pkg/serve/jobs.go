package serve

import (
	"fmt"
	"sync"
	"time"
)

// jobState is the status of an asynchronously-running long operation.
type jobState struct {
	ID         string    `json:"id"`
	Name       string    `json:"name"`
	Status     string    `json:"status"` // running | success | failed
	Message    string    `json:"msg"`
	StartedAt  time.Time `json:"started_at"`
	FinishedAt time.Time `json:"finished_at,omitempty"`
}

var (
	jobsMu    sync.Mutex
	jobsByID  = map[string]*jobState{}
	jobsOrder []string
	jobsSeq   uint64
)

// jobsKeep bounds how many finished jobs are retained in memory.
const jobsKeep = 50

// startJob runs fn asynchronously and returns a job id. Long operations
// (push/fetch/restore) may outlive the HTTP request, so callers that opt in via
// ?async=1 get a job id to poll at /api/jobs/{id} instead of a held-open request.
func startJob(name string, fn func() error) string {
	jobsMu.Lock()
	jobsSeq++
	id := fmt.Sprintf("%s-%d-%d", name, time.Now().Unix(), jobsSeq)
	st := &jobState{ID: id, Name: name, Status: "running", StartedAt: time.Now()}
	jobsByID[id] = st
	jobsOrder = append(jobsOrder, id)
	for len(jobsOrder) > jobsKeep {
		delete(jobsByID, jobsOrder[0])
		jobsOrder = jobsOrder[1:]
	}
	jobsMu.Unlock()

	go func() {
		err := fn()
		jobsMu.Lock()
		defer jobsMu.Unlock()
		st.FinishedAt = time.Now()
		if err != nil {
			st.Status = "failed"
			st.Message = err.Error()
		} else {
			st.Status = "success"
			st.Message = "completed"
		}
	}()
	return id
}

func getJob(id string) (jobState, bool) {
	jobsMu.Lock()
	defer jobsMu.Unlock()
	if st, ok := jobsByID[id]; ok {
		return *st, true
	}
	return jobState{}, false
}

func listJobs() []jobState {
	jobsMu.Lock()
	defer jobsMu.Unlock()
	out := make([]jobState, 0, len(jobsOrder))
	for _, id := range jobsOrder {
		if st, ok := jobsByID[id]; ok {
			out = append(out, *st)
		}
	}
	return out
}
