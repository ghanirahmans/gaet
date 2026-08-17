package core

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"time"
)

// OpenBrowser opens a URL in the user's default web browser.
func OpenBrowser(url string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "linux":
		cmd = exec.Command("xdg-open", url)
	case "darwin":
		cmd = exec.Command("open", url)
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	default:
		return fmt.Errorf("unsupported platform")
	}
	return cmd.Start()
}

// ExecResult holds the stdout, stderr, and exit code of a subprocess.
type ExecResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

// RunCmd runs an external command with a timeout and optional extra env vars.
// Extra env is merged on top of the current process environment.
func RunCmd(ctx context.Context, name string, args []string, env map[string]string, timeout time.Duration) (*ExecResult, error) {
	tCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	cmd := exec.CommandContext(tCtx, name, args...)

	// Merge env
	if len(env) > 0 {
		base := os.Environ()
		for k, v := range env {
			base = append(base, fmt.Sprintf("%s=%s", k, v))
		}
		cmd.Env = base
	}

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	code := 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			code = exitErr.ExitCode()
		} else {
			code = -1
		}
	}

	return &ExecResult{
		Stdout:   stdout.String(),
		Stderr:   stderr.String(),
		ExitCode: code,
	}, nil
}

// RunCmdSimple runs a command with default 30s timeout. Returns stdout, stderr, exitCode.
func RunCmdSimple(name string, args []string, env map[string]string, timeout time.Duration) (string, string, int) {
	r, err := RunCmd(context.Background(), name, args, env, timeout)
	if err != nil && r == nil {
		return "", err.Error(), -1
	}
	return r.Stdout, r.Stderr, r.ExitCode
}

// PGEnv builds a PGPASSWORD env map for pg_* tools.
func PGEnv(user, password, sslMode string) map[string]string {
	env := map[string]string{}
	if password != "" {
		env["PGPASSWORD"] = password
	}
	if sslMode != "" {
		env["PGSSLMODE"] = sslMode
	}
	return env
}

// GetDynamicTimeout calculates dynamic timeout budget based on base timeout + timeout budget per 1 GB of data.
// Supports GAET_TIMEOUT (legacy fallback GAET_PG_TIMEOUT) and GAET_TIMEOUT_PER_GB (legacy fallback GAET_PG_TIMEOUT_PER_GB).
func GetDynamicTimeout(env map[string]string, sizeBytes int64) time.Duration {
	baseTimeout := GetEnvInt(env, "GAET_TIMEOUT", 0)
	if baseTimeout == 0 {
		baseTimeout = GetEnvInt(env, "GAET_PG_TIMEOUT", DefTimeout)
	}

	perGBBudget := GetEnvInt(env, "GAET_TIMEOUT_PER_GB", 0)
	if perGBBudget == 0 {
		perGBBudget = GetEnvInt(env, "GAET_PG_TIMEOUT_PER_GB", DefTimeoutPerGB)
	}

	sizeGB := float64(sizeBytes) / (1024 * 1024 * 1024)
	extraSeconds := int(sizeGB * float64(perGBBudget))
	totalSeconds := baseTimeout + extraSeconds
	return time.Duration(totalSeconds) * time.Second
}
