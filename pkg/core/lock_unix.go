//go:build !windows

package core

import (
	"os"
	"syscall"
)

// processExists checks if a process with the given PID is alive on Unix.
func processExists(pid int) bool {
	p, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	// Signal 0 checks existence without sending an actual signal
	err = p.Signal(syscall.Signal(0))
	return err == nil
}
