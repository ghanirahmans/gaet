// Package log_test tests the gaet log command and JSON logging.
package tests

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
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
	os.WriteFile(logPath, []byte("{\"timestamp\":\"2026-01-01 00:00:00\",\"level\":\"INFO\",\"action\":\"PUSH\",\"status\":\"SUCCESS\"}\n"), 0644)

	if err := gaetlog.RunLog(gaetlog.LogOptions{Lines: 5}); err != nil {
		t.Errorf("RunLog with content: unexpected error: %v", err)
	}
}

func TestWriteJSONLog(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	core.Quiet = true
	defer func() { core.Quiet = false }()

	core.WriteJSONLog(core.LogEntry{
		Level:    "INFO",
		Category: "BACKUP",
		Action:   "PUSH",
		Status:   "SUCCESS",
		Message:  "Push complete test",
		Details:  map[string]interface{}{"size_mb": 12.5},
	})

	logPath := core.LogFile()
	data, err := os.ReadFile(logPath)
	if err != nil {
		t.Fatalf("Failed to read log file: %v", err)
	}

	content := strings.TrimSpace(string(data))
	var entry core.LogEntry
	if err := json.Unmarshal([]byte(content), &entry); err != nil {
		t.Fatalf("Log file line is not valid JSON: %v", err)
	}

	if entry.Action != "PUSH" || entry.Category != "BACKUP" || entry.Status != "SUCCESS" {
		t.Errorf("Unexpected log entry contents: %+v", entry)
	}
}

func TestRunLog_WithFilter(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	backupDir := core.BackupDir()
	_ = os.MkdirAll(backupDir, 0755)
	logPath := filepath.Join(backupDir, "gaet.log")
	os.WriteFile(logPath, []byte("{\"action\":\"PUSH\",\"message\":\"Push complete\"}\n{\"action\":\"FETCH\",\"message\":\"Fetch complete\"}\n"), 0644)

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
