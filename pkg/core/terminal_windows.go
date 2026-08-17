//go:build windows

package core

import (
	"os"
	"syscall"
	"unsafe"
)

// isTerminal returns true when the file is a terminal (Console).
func isTerminal(f *os.File) bool {
	var mode uint32
	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	getConsoleMode := kernel32.NewProc("GetConsoleMode")
	r, _, _ := getConsoleMode.Call(f.Fd(), uintptr(unsafe.Pointer(&mode)))
	return r != 0
}

// IsStdinTTY returns true when stdin is a terminal.
func IsStdinTTY() bool {
	return isTerminal(os.Stdin)
}
