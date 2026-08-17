// Package scheduler_test tests auto-backup status detection.
package scheduler_test

import (
	"testing"

	"github.com/ghanirahmans/gaet/pkg/scheduler"
)

func TestIsActive_NonExistentService(t *testing.T) {
	// A non-existent service name should report false
	active := scheduler.IsActive("gaet-test-nonexistent-12345")
	if active {
		t.Error("IsActive should return false for fake service prefix")
	}
}

func TestDisableAuto_NonExistentService(t *testing.T) {
	// Disabling an uninstalled service should not panic or error fatally
	_ = scheduler.DisableAuto("gaet-test-nonexistent-12345")
}
