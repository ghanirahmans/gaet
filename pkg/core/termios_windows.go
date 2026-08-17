//go:build windows

package core

import (
	"os"
	"syscall"
	"unsafe"
)

type termios = uint32

func tcGetAttr(f *os.File) (uint32, error) {
	// Windows uses GetConsoleMode
	var mode uint32
	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	getConsoleMode := kernel32.NewProc("GetConsoleMode")
	r, _, err := getConsoleMode.Call(f.Fd(), uintptr(unsafe.Pointer(&mode)))
	if r == 0 {
		return 0, err
	}
	return mode, nil
}

func tcSetAttr(f *os.File, mode uint32) error {
	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	setConsoleMode := kernel32.NewProc("SetConsoleMode")
	r, _, err := setConsoleMode.Call(f.Fd(), uintptr(mode))
	if r == 0 {
		return err
	}
	return nil
}

func disableEcho(mode uint32) uint32 {
	const ENABLE_ECHO_INPUT = 0x0004
	return mode &^ ENABLE_ECHO_INPUT
}
