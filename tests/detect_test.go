// Package detect_test tests local PostgreSQL instance detection routines.
package tests

import (
	"testing"

	"github.com/ghanirahmans/gaet/pkg/detect"
)

func TestDetectLocalPG_EmptyPsqlPath(t *testing.T) {
	// Should return nil gracefully if psqlPath is empty
	res := detect.DetectLocalPG("")
	if res != nil {
		t.Errorf("expected nil for empty psqlPath, got: %v", res)
	}
}

func TestDetectLocalPG_NonExistentPsql(t *testing.T) {
	// Should return empty slice if psql path does not exist
	res := detect.DetectLocalPG("/nonexistent/path/psql")
	if len(res) != 0 {
		t.Errorf("expected empty slice for fake psql path, got: %v", res)
	}
}
