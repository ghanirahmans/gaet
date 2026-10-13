package tests

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/scheduler"
)

// TestRemoveFiles_Systemd verifies that RemoveFiles deletes leftover systemd
// unit files (which `systemctl disable` leaves on disk).
func TestRemoveFiles_Systemd(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("systemd unit files are linux-only")
	}

	home := t.TempDir()
	t.Setenv("HOME", home)

	unitDir := filepath.Join(home, ".config", "systemd", "user")
	if err := os.MkdirAll(unitDir, 0o755); err != nil {
		t.Fatal(err)
	}
	prefix := "gaet-ut"
	files := []string{prefix + "-backup.service", prefix + "-backup.timer", prefix + "-serve.service"}
	for _, f := range files {
		if err := os.WriteFile(filepath.Join(unitDir, f), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}

	scheduler.RemoveFiles(prefix)

	for _, f := range files {
		if _, err := os.Stat(filepath.Join(unitDir, f)); !os.IsNotExist(err) {
			t.Errorf("unit file %s should have been removed", f)
		}
	}
}
