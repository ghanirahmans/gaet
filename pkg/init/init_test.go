// Package gaetinit_test tests gaet init wizard non-interactive mode and presets.
package gaetinit_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
	gaetinit "github.com/ghanirahmans/gaet/pkg/init"
)

func TestRunInit_NonInteractive_Default(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)
	t.Setenv("CI", "true") // forces non-interactive mode

	err := gaetinit.RunInit(gaetinit.InitOptions{})
	if err != nil {
		t.Fatalf("RunInit non-interactive error: %v", err)
	}

	envFile := filepath.Join(tmp, ".env")
	if _, statErr := os.Stat(envFile); statErr != nil {
		t.Fatalf("env file was not created at %s", envFile)
	}

	env, loadErr := core.LoadEnv(envFile)
	if loadErr != nil {
		t.Fatalf("LoadEnv error: %v", loadErr)
	}
	if env["GAET_RETENTION_DAYS"] == "" {
		t.Error("GAET_RETENTION_DAYS should be set in default config")
	}
}

func TestRunInit_NonInteractive_Preset(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)
	t.Setenv("CI", "true")

	err := gaetinit.RunInit(gaetinit.InitOptions{Preset: "hindsight"})
	if err != nil {
		t.Fatalf("RunInit preset hindsight error: %v", err)
	}

	envFile := filepath.Join(tmp, ".env")
	data, _ := os.ReadFile(envFile)
	if !strings.Contains(string(data), "GAET_TABLES=") && !strings.Contains(string(data), "memory_units") {
		t.Errorf("Preset tables not written to config: %s", string(data))
	}
}

func TestRunInit_InvalidPreset(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)
	t.Setenv("CI", "true")

	err := gaetinit.RunInit(gaetinit.InitOptions{Preset: "nonexistent_preset_xyz"})
	if err == nil {
		t.Error("expected error for non-existent preset, got nil")
	}
}
