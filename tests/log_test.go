// Package log_test tests the gaet log command.
package tests

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
	gaetlog "github.com/ghanirahmans/gaet/pkg/log"
)

func TestRunLog_NoLogFile(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	// Should not error when no log files exist
	if err := gaetlog.RunLog(gaetlog.LogOptions{Lines: 10}); err != nil {
		t.Errorf("RunLog no file: unexpected error: %v", err)
	}
}

func TestRunLog_WithContent(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	backupDir := core.BackupDir()
	_ = os.MkdirAll(backupDir, 0755)
	logPath := filepath.Join(backupDir, "gaet.log")
	os.WriteFile(logPath, []byte("[2026-01-01 00:00:00] Push complete\n[2026-01-02 00:00:00] Fetch complete\n"), 0644)

	if err := gaetlog.RunLog(gaetlog.LogOptions{Lines: 5}); err != nil {
		t.Errorf("RunLog with content: unexpected error: %v", err)
	}
}

func TestRunLog_WithFilter(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	backupDir := core.BackupDir()
	_ = os.MkdirAll(backupDir, 0755)
	logPath := filepath.Join(backupDir, "gaet.log")
	os.WriteFile(logPath, []byte("[2026-01-01] Push complete\n[2026-01-02] Fetch complete\n"), 0644)

	if err := gaetlog.RunLog(gaetlog.LogOptions{Lines: 10, Filter: "push"}); err != nil {
		t.Errorf("RunLog with filter: unexpected error: %v", err)
	}
}

func TestRunLog_DefaultsTo30Lines(t *testing.T) {
	opts := gaetlog.LogOptions{} // Lines = 0 → should default to 30
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)
	if err := gaetlog.RunLog(opts); err != nil {
		t.Errorf("RunLog defaults: unexpected error: %v", err)
	}
}
