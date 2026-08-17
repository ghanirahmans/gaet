// Package status_test tests gaet status, check, and doctor without a real database.
package tests

import (
	"os"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/status"
)

func TestRunCheck_NoConfig(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	// Should not panic; check handles missing env gracefully
	_ = status.RunCheck(status.CheckOptions{JSON: true})
}

func TestRunDoctor_NoConfig(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	if err := status.RunDoctor(status.DoctorOptions{JSON: false}); err != nil {
		t.Errorf("RunDoctor: unexpected error: %v", err)
	}
}

func TestRunDoctor_JSONMode(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	if err := status.RunDoctor(status.DoctorOptions{JSON: true}); err != nil {
		t.Errorf("RunDoctor --json: unexpected error: %v", err)
	}
}

func TestRunStatus_NoConfig(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	if err := status.RunStatus(status.StatusOptions{JSON: false}); err != nil {
		t.Errorf("RunStatus: unexpected error: %v", err)
	}
}

func TestRunStatus_JSONMode(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)
	// Suppress output noise in JSON mode
	old := os.Stdout
	_, w, _ := os.Pipe()
	os.Stdout = w
	defer func() {
		w.Close()
		os.Stdout = old
	}()

	if err := status.RunStatus(status.StatusOptions{JSON: true}); err != nil {
		t.Errorf("RunStatus --json: unexpected error: %v", err)
	}
}
