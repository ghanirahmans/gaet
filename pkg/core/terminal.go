package core

import (
	"os"
	"syscall"
	"unsafe"
)

// isTerminal returns true when the file is a terminal (TTY).
// Uses pure stdlib syscall.SYS_IOCTL — no external dependencies.
func isTerminal(f *os.File) bool {
	var termios syscall.Termios
	_, _, err := syscall.Syscall(
		syscall.SYS_IOCTL,
		f.Fd(),
		// TCGETS = 0x5401 on Linux; on other platforms this may need build tags
		0x5401,
		uintptr(unsafe.Pointer(&termios)),
	)
	return err == 0
}

// IsStdinTTY returns true when stdin is a terminal.
func IsStdinTTY() bool {
	return isTerminal(os.Stdin)
}
