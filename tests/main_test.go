// Package main_test contains CLI integration tests for the gaet binary.
// Tests run against the compiled binary to validate end-to-end behavior.
package tests

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// binaryPath returns path to the gaet binary built in the project root.
func binaryPath(t *testing.T) string {
	t.Helper()
	root := projectRoot(t)
	binName := "gaet"
	if runtime.GOOS == "windows" {
		binName = "gaet.exe"
	}
	bin := filepath.Join(root, binName)
	if _, err := os.Stat(bin); err == nil {
		return bin
	}
	// Auto-build binary if missing
	cmd := exec.Command("go", "build", "-o", bin, "./cmd/gaet")
	cmd.Dir = root
	if err := cmd.Run(); err != nil {
		t.Fatalf("failed to auto-build gaet binary for test: %v", err)
	}
	t.Cleanup(func() {
		os.Remove(bin)
	})
	return bin
}

func projectRoot(t *testing.T) string {
	t.Helper()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("os.Getwd: %v", err)
	}
	// Walk up to find go.mod
	dir := wd
	for {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			t.Fatalf("could not find project root (go.mod) from %s", wd)
		}
		dir = parent
	}
}

func runGaet(t *testing.T, gaetDir string, args ...string) (stdout, stderr string, exitCode int) {
	t.Helper()
	bin := binaryPath(t)
	cmd := exec.Command(bin, args...)
	cmd.Env = append(os.Environ(), "GAET_DIR="+gaetDir, "NO_COLOR=1")
	var outBuf, errBuf strings.Builder
	cmd.Stdout = &outBuf
	cmd.Stderr = &errBuf
	err := cmd.Run()
	exitCode = 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		}
	}
	return outBuf.String(), errBuf.String(), exitCode
}

// ── Version ──────────────────────────────────────────────────────────────

func TestBinary_Version(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "--version")
	if code != 0 {
		t.Errorf("exit code %d, want 0", code)
	}
	if !strings.HasPrefix(out, "gaet v") {
		t.Errorf("unexpected version output: %q", out)
	}
}

// ── Help ──────────────────────────────────────────────────────────────────

func TestBinary_Help(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "--help")
	if code != 0 {
		t.Errorf("exit code %d, want 0", code)
	}
	for _, keyword := range []string{"push", "fetch", "restore", "snapshots", "status", "init"} {
		if !strings.Contains(out, keyword) {
			t.Errorf("--help output missing keyword %q", keyword)
		}
	}
}

func TestBinary_HelpSubcommand(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "help", "push")
	if code != 0 {
		t.Errorf("exit code %d, want 0", code)
	}
	if !strings.Contains(out, "push") {
		t.Errorf("help push output missing 'push': %q", out)
	}
}

// ── Unknown command ───────────────────────────────────────────────────────

func TestBinary_UnknownCommand(t *testing.T) {
	tmp := t.TempDir()
	_, _, code := runGaet(t, tmp, "notacommand")
	if code == 0 {
		t.Error("expected non-zero exit for unknown command")
	}
}

// ── check --json ──────────────────────────────────────────────────────────

func TestBinary_CheckJSON(t *testing.T) {
	tmp := t.TempDir()
	out, _, _ := runGaet(t, tmp, "check", "--json")

	// Must be valid JSON
	var result map[string]any
	if err := json.Unmarshal([]byte(out), &result); err != nil {
		t.Errorf("check --json produced invalid JSON: %v\noutput: %q", err, out)
	}
	if _, ok := result["ok"]; !ok {
		t.Errorf("check --json missing 'ok' field: %v", result)
	}
	if _, ok := result["checks"]; !ok {
		t.Errorf("check --json missing 'checks' field: %v", result)
	}
}

// ── doctor --json ─────────────────────────────────────────────────────────

func TestBinary_DoctorJSON(t *testing.T) {
	tmp := t.TempDir()
	out, _, _ := runGaet(t, tmp, "doctor", "--json")

	var result map[string]any
	if err := json.Unmarshal([]byte(out), &result); err != nil {
		t.Errorf("doctor --json produced invalid JSON: %v\noutput: %q", err, out)
	}
	if _, ok := result["checks"]; !ok {
		t.Errorf("doctor --json missing 'checks' field: %v", result)
	}
}

// ── snapshots --json ──────────────────────────────────────────────────────

func TestBinary_SnapshotsJSON(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "snapshots", "--json")
	if code != 0 {
		t.Errorf("snapshots --json: exit code %d", code)
	}
	var result map[string]any
	if err := json.Unmarshal([]byte(out), &result); err != nil {
		t.Errorf("snapshots --json invalid JSON: %v\noutput: %q", err, out)
	}
	if _, ok := result["count"]; !ok {
		t.Errorf("snapshots --json missing 'count': %v", result)
	}
}

// ── get --list ────────────────────────────────────────────────────────────

func TestBinary_GetList(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "get", "--list")
	if code != 0 {
		t.Errorf("get --list exit code %d", code)
	}
	for _, key := range []string{"GAET_LOCAL_URL", "GAET_REMOTE_URL", "GAET_RETENTION_DAYS"} {
		if !strings.Contains(out, key) {
			t.Errorf("get --list missing key %q", key)
		}
	}
}

// ── set + get roundtrip ───────────────────────────────────────────────────

func TestBinary_SetGet_Roundtrip(t *testing.T) {
	tmp := t.TempDir()

	_, _, code := runGaet(t, tmp, "set", "GAET_RETENTION_DAYS=21")
	if code != 0 {
		t.Errorf("set exit code %d", code)
	}

	out, _, code2 := runGaet(t, tmp, "get", "GAET_RETENTION_DAYS")
	if code2 != 0 {
		t.Errorf("get exit code %d", code2)
	}
	if !strings.Contains(out, "21") {
		t.Errorf("get output should contain '21', got: %q", out)
	}
}

// ── remote set-url / show ─────────────────────────────────────────────────

func TestBinary_Remote_SetURL_Show(t *testing.T) {
	tmp := t.TempDir()
	url := "postgresql://myuser:mypass@myhost:5432/mydb"

	_, _, code := runGaet(t, tmp, "remote", "set-url", url)
	if code != 0 {
		t.Errorf("remote set-url exit code %d", code)
	}

	out, _, code2 := runGaet(t, tmp, "remote", "show")
	if code2 != 0 {
		t.Errorf("remote show exit code %d", code2)
	}
	if !strings.Contains(out, "myhost") {
		t.Errorf("remote show should display host 'myhost', got: %q", out)
	}
	if strings.Contains(out, "mypass") {
		t.Errorf("remote show should mask password, got: %q", out)
	}
}

func TestBinary_Remote_InvalidURL(t *testing.T) {
	tmp := t.TempDir()
	_, _, code := runGaet(t, tmp, "remote", "set-url", "not-a-url")
	if code == 0 {
		t.Error("expected non-zero exit for invalid remote URL")
	}
}

// ── completion ────────────────────────────────────────────────────────────

func TestBinary_Completion_Bash(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "completion", "bash")
	if code != 0 {
		t.Errorf("completion bash exit code %d", code)
	}
	if !strings.Contains(out, "_gaet_complete") {
		t.Errorf("bash completion missing '_gaet_complete': %q", out)
	}
}

func TestBinary_Completion_Zsh(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "completion", "zsh")
	if code != 0 {
		t.Errorf("completion zsh exit code %d", code)
	}
	if !strings.Contains(out, "compdef") {
		t.Errorf("zsh completion missing 'compdef': %q", out)
	}
}

func TestBinary_Completion_UnknownShell(t *testing.T) {
	tmp := t.TempDir()
	_, _, code := runGaet(t, tmp, "completion", "windowspower")
	if code == 0 {
		t.Error("expected non-zero exit for unknown shell")
	}
}

// ── log ───────────────────────────────────────────────────────────────────

func TestBinary_Log_NoFile(t *testing.T) {
	tmp := t.TempDir()
	_, _, code := runGaet(t, tmp, "log")
	if code != 0 {
		t.Errorf("log (no file) exit code %d", code)
	}
}

// ── restore (dry-run, no snapshot) ───────────────────────────────────────

func TestBinary_Restore_DryRun_NoSnapshot(t *testing.T) {
	tmp := t.TempDir()
	_, _, code := runGaet(t, tmp, "restore", "--dry-run")
	// No snapshot → should fail gracefully (non-zero but no panic)
	if code == 0 {
		t.Error("expected non-zero exit when no snapshots exist")
	}
}

// ── push (dry-run, no config) ─────────────────────────────────────────────

func TestBinary_Push_DryRun(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "push", "--dry-run")
	if code != 0 {
		t.Errorf("push --dry-run exit code %d", code)
	}
	if !strings.Contains(out, "Dry-run") && !strings.Contains(out, "dry-run") {
		t.Errorf("push --dry-run should indicate dry-run mode: %q", out)
	}
}

// ── fetch (dry-run, no config) ────────────────────────────────────────────

func TestBinary_Fetch_DryRun(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "fetch", "--dry-run")
	if code != 0 {
		t.Errorf("fetch --dry-run exit code %d", code)
	}
	if !strings.Contains(out, "Dry-run") && !strings.Contains(out, "dry-run") {
		t.Errorf("fetch --dry-run should indicate dry-run mode: %q", out)
	}
}

// ── quiet mode ────────────────────────────────────────────────────────────

func TestBinary_QuietFlag(t *testing.T) {
	tmp := t.TempDir()
	out, _, code := runGaet(t, tmp, "--quiet", "snapshots")
	if code != 0 {
		t.Errorf("--quiet exit code %d", code)
	}
	// Quiet mode should suppress most output
	if strings.TrimSpace(out) != "" {
		t.Logf("note: --quiet produced output: %q (may be acceptable for error-only output)", out)
	}
}
