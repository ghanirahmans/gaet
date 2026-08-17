package core

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"time"
)

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
