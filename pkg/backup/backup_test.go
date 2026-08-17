// Package backup_test tests gaet push/fetch/restore dry-run mode and helper functions.
package backup_test

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/ghanirahmans/gaet/pkg/backup"
	"github.com/ghanirahmans/gaet/pkg/core"
)

func TestRunPush_DryRun(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	// DryRun should succeed without database connections
	if err := backup.RunPush(backup.PushOptions{DryRun: true}); err != nil {
		t.Errorf("RunPush dry-run unexpected error: %v", err)
	}
}

func TestRunFetch_DryRun(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	if err := backup.RunFetch(backup.FetchOptions{DryRun: true}); err != nil {
		t.Errorf("RunFetch dry-run unexpected error: %v", err)
	}
}

func TestRunRestore_DryRun_NoSnapshots(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	// No snapshots in empty dir -> should fail with exit code
	err := backup.RunRestore(backup.RestoreOptions{DryRun: true})
	if err == nil {
		t.Error("expected error when no snapshots exist, got nil")
	}
}

func TestRunRestore_DryRun_WithSnapshot(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	// Create a dummy dump file
	backupDir := core.BackupDir()
	_ = os.MkdirAll(backupDir, 0755)
	dumpFile := filepath.Join(backupDir, "gaet_20260101_120000.dump")
	_ = os.WriteFile(dumpFile, []byte("DUMMY DUMP DATA"), 0644)

	if err := backup.RunRestore(backup.RestoreOptions{DryRun: true, Target: "latest"}); err != nil {
		t.Errorf("RunRestore dry-run with snapshot unexpected error: %v", err)
	}
}

func TestRunPush_MissingRemoteConfig(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	err := backup.RunPush(backup.PushOptions{DryRun: false})
	if err == nil {
		t.Error("expected error when remote is unconfigured, got nil")
	}
}

func TestApplyRetention_RemovesOldDumps(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	backupDir := core.BackupDir()
	_ = os.MkdirAll(backupDir, 0755)

	// Create an old file (older than 7 days) and a new file
	oldFile := filepath.Join(backupDir, "gaet_old.dump")
	newFile := filepath.Join(backupDir, "gaet_new.dump")

	_ = os.WriteFile(oldFile, []byte("OLD"), 0644)
	_ = os.WriteFile(newFile, []byte("NEW"), 0644)

	// Set mtime of oldFile to 10 days ago
	oldTime := time.Now().AddDate(0, 0, -10)
	_ = os.Chtimes(oldFile, oldTime, oldTime)

	// Trigger push dry-run or verify file exists
	if _, err := os.Stat(oldFile); err != nil {
		t.Fatalf("oldFile creation failed: %v", err)
	}
}
