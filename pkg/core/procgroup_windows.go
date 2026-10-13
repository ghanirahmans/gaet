//go:build windows

package core

import (
	"os/exec"
	"strconv"
)

// applyProcessGroup is a no-op on Windows (no process groups via Setpgid).
func applyProcessGroup(cmd *exec.Cmd) {}

// killProcessGroup terminates cmd's process tree via taskkill (best effort),
// so child processes are not left running after a cancel/timeout.
func killProcessGroup(cmd *exec.Cmd) {
	if cmd.Process == nil {
		return
	}
	_ = exec.Command("taskkill", "/T", "/F", "/PID", strconv.Itoa(cmd.Process.Pid)).Run()
}
