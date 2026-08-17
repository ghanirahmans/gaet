// Package core provides low-level primitives: paths, output, env, exec, lock.
package core

import (
	"fmt"
	"os"
)

// Color control — enabled when stdout is a TTY unless NO_COLOR is set.
var (
	useColor bool

	ColorReset  string
	ColorRed    string
	ColorBRed   string
	ColorGreen  string
	ColorBGreen string
	ColorYellow string
	ColorCyan   string
	ColorBCyan  string
	ColorMagenta string
	ColorDim    string
	ColorBold   string
)

func init() {
	noColor := os.Getenv("NO_COLOR") != ""
	forceColor := os.Getenv("CLICOLOR_FORCE") == "1"
	isTTY := isTerminal(os.Stdout)
	useColor = (isTTY || forceColor) && !noColor

	if useColor {
		ColorReset   = "\033[0m"
		ColorRed     = "\033[0;31m"
		ColorBRed    = "\033[1;31m"
		ColorGreen   = "\033[0;32m"
		ColorBGreen  = "\033[1;32m"
		ColorYellow  = "\033[1;33m"
		ColorCyan    = "\033[0;36m"
		ColorBCyan   = "\033[1;36m"
		ColorMagenta = "\033[0;35m"
		ColorDim     = "\033[2m"
		ColorBold    = "\033[1m"
	}
}

// Global output mode flags
var (
	Quiet bool
	Plain bool
)

// IsPlain returns true when --plain is active OR stdout is not a TTY.
func IsPlain() bool {
	return Plain || !isTerminal(os.Stdout)
}

// Echo prints a message to stdout unless Quiet is set.
func Echo(msg string) {
	if Quiet {
		return
	}
	fmt.Println(msg)
}

// Echof prints a formatted message unless Quiet is set.
func Echof(format string, args ...any) {
	if Quiet {
		return
	}
	fmt.Printf(format+"\n", args...)
}

// StatusOK prints a green [ OK ] status line.
func StatusOK(msg string) {
	fmt.Printf("  %s[ OK ]%s  %s\n", ColorBGreen, ColorReset, msg)
}

// StatusFail prints a red [FAIL] status line to stderr.
func StatusFail(msg string) {
	fmt.Fprintf(os.Stderr, "  %s[FAIL]%s  %s\n", ColorBRed, ColorReset, msg)
}

// StatusWarn prints a yellow [WARN] status line.
func StatusWarn(msg string) {
	fmt.Printf("  %s[WARN]%s  %s\n", ColorYellow, ColorReset, msg)
}

// StatusInfo prints a cyan [INFO] status line.
func StatusInfo(msg string) {
	fmt.Printf("  %s[INFO]%s  %s\n", ColorBCyan, ColorReset, msg)
}

// StatusArrow prints a dim [NOTE] / arrow status line.
func StatusArrow(msg string) {
	fmt.Printf("  %s[NOTE]%s  %s\n", ColorDim, ColorReset, msg)
}

// Die prints an error to stderr and returns a GaetError for the caller to exit.
// The caller in cmd/gaet/main.go calls os.Exit with the error code.
func Die(msg string, code int) *GaetError {
	fmt.Fprintf(os.Stderr, "  %s[FAIL]%s  %s\n", ColorBRed, ColorReset, msg)
	if !IsPlain() && !Quiet {
		fmt.Fprintf(os.Stderr, "  %sTroubleshooting: %shttps://github.com/ghanirahmans/gaet/blob/main/TROUBLESHOOTING.md%s\n",
			ColorDim, ColorCyan, ColorReset)
	}
	return &GaetError{Code: code, Message: msg}
}

// BoxTitle prints a main section title header.
func BoxTitle(title string) {
	if Quiet {
		return
	}
	if IsPlain() {
		fmt.Printf("\n  ==> %s\n\n", title)
		return
	}
	fmt.Printf("\n  %s▌%s  %s%s%s\n\n",
		ColorBCyan, ColorReset,
		ColorBold, title, ColorReset)
}

// BoxSection prints a sub-section header.
func BoxSection(title string) {
	if Quiet {
		return
	}
	if IsPlain() {
		fmt.Printf("\n  ── %s ──\n", title)
		return
	}
	fmt.Printf("\n  %s▌%s  %s%s%s\n",
		ColorCyan, ColorReset,
		ColorDim, title, ColorReset)
}

// PrintDocsFooter prints the documentation URL footer.
func PrintDocsFooter() {
	if IsPlain() || Quiet {
		return
	}
	fmt.Printf("\n  %sDocumentation:%s %shttps://github.com/ghanirahmans/gaet%s\n",
		ColorDim, ColorReset, ColorCyan, ColorReset)
}
