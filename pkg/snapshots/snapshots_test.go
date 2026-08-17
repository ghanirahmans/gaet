// Package snapshots_test tests the gaet snapshots command.
package snapshots_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
	"github.com/ghanirahmans/gaet/pkg/snapshots"
)

func TestRunSnapshots_EmptyDir(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	// Should not error on empty backup dir
	if err := snapshots.RunSnapshots(false); err != nil {
		t.Errorf("RunSnapshots empty dir: unexpected error: %v", err)
	}
}

func TestRunSnapshots_JSONOutput(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	// Create a fake dump file
	backupDir := core.BackupDir()
	_ = os.MkdirAll(backupDir, 0755)
	fakeDump := filepath.Join(backupDir, "gaet_20260101_000000.dump")
	os.WriteFile(fakeDump, []byte("FAKE DUMP DATA"), 0644)

	if err := snapshots.RunSnapshots(true); err != nil {
		t.Errorf("RunSnapshots --json: unexpected error: %v", err)
	}
}

func TestRunSnapshots_ListsFiles(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	backupDir := core.BackupDir()
	_ = os.MkdirAll(backupDir, 0755)

	// Create multiple dump files
	for _, name := range []string{"gaet_20260101_120000.dump", "gaet_20260102_130000.dump"} {
		os.WriteFile(filepath.Join(backupDir, name), []byte("FAKE"), 0644)
	}

	// Should succeed without error
	if err := snapshots.RunSnapshots(false); err != nil {
		t.Errorf("RunSnapshots: unexpected error: %v", err)
	}
}
