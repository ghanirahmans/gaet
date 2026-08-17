// Package config_test tests gaet get / gaet set command logic.
package config_test

import (
	"os"
	"strings"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/config"
	"github.com/ghanirahmans/gaet/pkg/core"
)

func TestRunGet_ShowsList(t *testing.T) {
	// Should not error when --list is requested
	if err := config.RunGet(nil, true, false); err != nil {
		t.Errorf("RunGet --list: unexpected error: %v", err)
	}
}

func TestRunSet_RejectsInvalidFormat(t *testing.T) {
	err := config.RunSet([]string{"INVALID_NO_EQUALS"}, false)
	if err == nil {
		t.Error("expected error for format without '=', got nil")
	}
}

func TestRunSet_RejectsEmptyKey(t *testing.T) {
	err := config.RunSet([]string{"=value"}, false)
	if err == nil {
		t.Error("expected error for empty key, got nil")
	}
}

func TestRunSet_WritesConfig(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	if err := config.RunSet([]string{"GAET_RETENTION_DAYS=14"}, false); err != nil {
		t.Fatalf("RunSet error: %v", err)
	}

	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		t.Fatalf("LoadEnv: %v", err)
	}
	if env["GAET_RETENTION_DAYS"] != "14" {
		t.Errorf("GAET_RETENTION_DAYS not saved correctly: %v", env)
	}
}

func TestRunSet_ClearsLocalURLWhenIndividualVarsSet(t *testing.T) {
	tmp := t.TempDir()
	t.Setenv("GAET_DIR", tmp)

	envFile := core.EnvFile()
	_ = os.MkdirAll(core.GaetDir(), 0755)
	os.WriteFile(envFile, []byte("export GAET_LOCAL_URL=postgresql://u@h:5432/d\n"), 0600)

	if err := config.RunSet([]string{"GAET_LOCAL_DB_HOST=newhost"}, false); err != nil {
		t.Fatalf("RunSet error: %v", err)
	}

	data, _ := os.ReadFile(envFile)
	if strings.Contains(string(data), "GAET_LOCAL_URL=postgresql") {
		t.Error("GAET_LOCAL_URL should have been cleared when individual DB vars are set")
	}
}

func TestRunSet_ShowsSchemaOnEmptyVars(t *testing.T) {
	// Should not error (just shows schema)
	err := config.RunSet([]string{}, false)
	if err != nil {
		t.Errorf("RunSet with empty vars: unexpected error: %v", err)
	}
}
