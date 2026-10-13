//go:build !windows

package core

import (
	"os/exec"
	"syscall"
)

// applyProcessGroup places cmd in its own process group so that cancelling the
// context can terminate the whole tree (pg_dump/psql children included) rather
// than just the immediate parent.
func applyProcessGroup(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}

// killProcessGroup terminates cmd's process group (best effort).
func killProcessGroup(cmd *exec.Cmd) {
	if cmd.Process == nil {
		return
	}
	if pgid, err := syscall.Getpgid(cmd.Process.Pid); err == nil && pgid > 0 {
		_ = syscall.Kill(-pgid, syscall.SIGTERM)
		return
	}
	_ = cmd.Process.Kill()
}
