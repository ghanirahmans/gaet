package core

import (
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// managedUnixPrefixes are directories owned by the OS, a package manager, or a
// system-wide install. A gaet binary running from one of these was installed via
// a native package (.deb/.rpm/.apk/.pkg.tar.zst/.pkg) or placed system-wide, and
// must not be "updated" into the user-local launcher dir (~/.local/bin), which
// would create a shadowing second copy.
var managedUnixPrefixes = []string{
	"/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin",
	"/opt", "/snap", "/nix/store",
}

// IsManagedInstall reports whether exePath looks like a system / package-manager
// install rather than the user-local launcher dir written by install.sh /
// install.ps1 (~/.local/bin). Symlinks are resolved when possible; the check is
// prefix-based with path-boundary awareness.
func IsManagedInstall(exePath string) bool {
	if strings.TrimSpace(exePath) == "" {
		return false
	}

	p := exePath
	if resolved, err := filepath.EvalSymlinks(p); err == nil && resolved != "" {
		p = resolved
	}
	if abs, err := filepath.Abs(p); err == nil {
		p = abs
	}
	p = filepath.Clean(p)

	if runtime.GOOS == "windows" {
		lp := strings.ToLower(p)
		for _, env := range []string{"ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "SystemRoot"} {
			base := os.Getenv(env)
			if base == "" {
				continue
			}
			base = strings.ToLower(filepath.Clean(base))
			if lp == base || strings.HasPrefix(lp, base+string(os.PathSeparator)) {
				return true
			}
		}
		return false
	}

	for _, prefix := range managedUnixPrefixes {
		if p == prefix || strings.HasPrefix(p, prefix+string(os.PathSeparator)) {
			return true
		}
	}
	return false
}
