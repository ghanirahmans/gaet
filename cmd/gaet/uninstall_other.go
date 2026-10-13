//go:build !windows

package main

// removeUserPathEntry is a no-op outside Windows: the Unix installer
// (install.sh) never modifies PATH.
func removeUserPathEntry(string) bool { return false }

// scheduleSelfDelete is a no-op outside Windows: Unix allows unlinking a
// running executable directly.
func scheduleSelfDelete(string) {}
