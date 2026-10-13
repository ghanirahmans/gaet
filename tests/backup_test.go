// Package backup_test tests gaet push/fetch/restore dry-run mode and helper functions.
package tests

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/backup"
	"github.com/ghanirahmans/gaet/pkg/core"
)

func TestRunPush_DryRun(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

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

	err := backup.RunRestore(backup.RestoreOptions{DryRun: true})
	if err == nil {
		t.Fatal("expected error when no snapshots exist, got nil")
	}
	ge, ok := err.(*core.GaetError)
	if !ok {
		t.Fatal("expected *GaetError")
	}
	if ge.Code != core.ExitGeneral {
		t.Errorf("expected ExitGeneral (%d), got %d", core.ExitGeneral, ge.Code)
	}
}

func TestRunRestore_DryRun_WithSnapshot(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

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
		t.Fatal("expected error when remote is unconfigured, got nil")
	}
	ge, ok := err.(*core.GaetError)
	if !ok {
		t.Fatal("expected *GaetError")
	}
	if ge.Code != core.ExitConfig {
		t.Errorf("expected ExitConfig (%d), got %d", core.ExitConfig, ge.Code)
	}
}

func TestRunFetch_MissingRemoteConfig(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	err := backup.RunFetch(backup.FetchOptions{DryRun: false})
	if err == nil {
		t.Fatal("expected error when remote is unconfigured, got nil")
	}
	ge, ok := err.(*core.GaetError)
	if !ok {
		t.Fatal("expected *GaetError")
	}
	if ge.Code != core.ExitConfig {
		t.Errorf("expected ExitConfig (%d), got %d", core.ExitConfig, ge.Code)
	}
}

func TestRunRestore_NoYesNonTTY(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)
	t.Setenv("CI", "true")

	backupDir := core.BackupDir()
	_ = os.MkdirAll(backupDir, 0755)
	dumpFile := filepath.Join(backupDir, "gaet_20260101_120000.dump")
	_ = os.WriteFile(dumpFile, []byte("DUMMY DUMP DATA"), 0644)

	// Without --yes and non-TTY stdin, should fail with ExitConfig
	err := backup.RunRestore(backup.RestoreOptions{Target: "latest", Yes: false})
	if err == nil {
		t.Fatal("expected error when --yes is not passed in non-TTY")
	}
	ge, ok := err.(*core.GaetError)
	if !ok {
		t.Fatal("expected *GaetError")
	}
	if ge.Code != core.ExitConfig {
		t.Errorf("expected ExitConfig (%d), got %d", core.ExitConfig, ge.Code)
	}
}

// NOTE: applyRetention unit tests live in pkg/backup/backup_test.go (white-box)
// where the unexported function is accessible.
