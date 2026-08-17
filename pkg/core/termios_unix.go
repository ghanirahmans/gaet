//go:build !windows

package core

import (
	"os"
	"syscall"
	"unsafe"
)

func tcGetAttr(f *os.File) (syscall.Termios, error) {
	var t syscall.Termios
	_, _, errno := syscall.Syscall(
		syscall.SYS_IOCTL,
		f.Fd(),
		0x5401, // TCGETS
		uintptr(unsafe.Pointer(&t)),
	)
	if errno != 0 {
		return t, errno
	}
	return t, nil
}

func tcSetAttr(f *os.File, t syscall.Termios) error {
	_, _, errno := syscall.Syscall(
		syscall.SYS_IOCTL,
		f.Fd(),
		0x5402, // TCSETS
		uintptr(unsafe.Pointer(&t)),
	)
	if errno != 0 {
		return errno
	}
	return nil
}

func disableEcho(t syscall.Termios) syscall.Termios {
	t.Lflag &^= syscall.ECHO | syscall.ECHOE | syscall.ECHOK | syscall.ECHONL
	return t
}
