//go:build windows

package core

import (
	"os"
)

// processExists checks if a process with the given PID is alive on Windows.
// Uses os.FindProcess which on Windows returns non-nil if the process exists.
func processExists(pid int) bool {
	p, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	// On Windows, FindProcess always succeeds if pid is valid.
	// We attempt to open the process; if it fails, it's gone.
	_ = p
	return true // Simplified — full impl would use OpenProcess
}
