package tests

import (
	"path/filepath"
	"runtime"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
)

func TestIsManagedInstall_SystemPaths(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("unix path prefixes")
	}
	managed := []string{
		"/usr/bin/gaet",
		"/bin/gaet",
		"/usr/sbin/gaet",
		"/sbin/gaet",
		"/usr/local/bin/gaet",
		"/opt/gaet/gaet",
		"/nix/store/abc123-gaet-1.2.3/bin/gaet",
	}
	for _, p := range managed {
		if !core.IsManagedInstall(p) {
			t.Errorf("IsManagedInstall(%q) = false, want true", p)
		}
	}
}

func TestIsManagedInstall_UserLocalPaths(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("unix path prefixes")
	}
	home := t.TempDir()
	userLocal := []string{
		filepath.Join(home, ".local", "bin", "gaet"),
		filepath.Join(home, "go", "bin", "gaet"),
		"/tmp/gaet",
		"",
	}
	for _, p := range userLocal {
		if core.IsManagedInstall(p) {
			t.Errorf("IsManagedInstall(%q) = true, want false", p)
		}
	}
}

func TestIsManagedInstall_Boundary(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("unix path prefixes")
	}
	// A sibling directory sharing a textual prefix must not match.
	if core.IsManagedInstall("/usr/binfoo/gaet") {
		t.Errorf("IsManagedInstall(/usr/binfoo/gaet) = true, want false")
	}
	// The managed directory itself counts.
	if !core.IsManagedInstall("/usr/bin") {
		t.Errorf("IsManagedInstall(/usr/bin) = false, want true")
	}
}
