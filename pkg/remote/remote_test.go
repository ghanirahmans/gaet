// Package remote_test tests the gaet remote command.
package remote_test

import (
	"os"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
	"github.com/ghanirahmans/gaet/pkg/remote"
)

func TestRunRemote_ShowUnconfigured(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	// Should not error when no remote is configured
	if err := remote.RunRemote("show", "", false); err != nil {
		t.Errorf("RunRemote show: unexpected error: %v", err)
	}
}

func TestRunRemote_SetURL_Valid(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)
	_ = os.MkdirAll(core.GaetDir(), 0755)

	url := "postgresql://user:pass@host:5432/db"
	if err := remote.RunRemote("set-url", url, false); err != nil {
		t.Fatalf("RunRemote set-url: unexpected error: %v", err)
	}

	env, _ := core.LoadEnv(core.EnvFile())
	if env["GAET_REMOTE_URL"] != url {
		t.Errorf("GAET_REMOTE_URL not saved: %v", env)
	}
}

func TestRunRemote_SetURL_Invalid(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	err := remote.RunRemote("set-url", "not-a-url", false)
	if err == nil {
		t.Error("expected error for invalid URL, got nil")
	}
}

func TestRunRemote_SetURL_MissingURL(t *testing.T) {
	err := remote.RunRemote("set-url", "", false)
	if err == nil {
		t.Error("expected error when URL arg is empty for set-url, got nil")
	}
}

func TestRunRemote_Remove(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)
	_ = os.MkdirAll(core.GaetDir(), 0755)

	// First set, then remove
	url := "postgresql://user:pass@host:5432/db"
	_ = remote.RunRemote("set-url", url, false)

	if err := remote.RunRemote("remove", "", false); err != nil {
		t.Fatalf("RunRemote remove: unexpected error: %v", err)
	}

	env, _ := core.LoadEnv(core.EnvFile())
	if env["GAET_REMOTE_URL"] != "" {
		t.Errorf("GAET_REMOTE_URL should be empty after remove, got: %s", env["GAET_REMOTE_URL"])
	}
}

func TestRunRemote_JSONOutput_Unconfigured(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	if err := remote.RunRemote("show", "", true); err != nil {
		t.Errorf("RunRemote --json unconfigured: unexpected error: %v", err)
	}
}
