package core

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// SafeInput reads a line from stdin with a fallback to defaultVal on EOF.
// In non-interactive mode (non-TTY) it still attempts to read from stdin.
func SafeInput(prompt, defaultVal string) string {
	if IsStdinTTY() {
		fmt.Print(prompt)
	}
	reader := bufio.NewReader(os.Stdin)
	line, err := reader.ReadString('\n')
	if err != nil {
		return defaultVal
	}
	return strings.TrimRight(line, "\r\n")
}

// SafeGetPass reads a password from stdin without echoing when on a TTY.
// Falls back to SafeInput when stdin is not a TTY.
func SafeGetPass(prompt string) string {
	if !IsStdinTTY() {
		return strings.TrimRight(SafeInput(prompt, ""), "\r\n")
	}
	// Use terminal raw mode to suppress echo
	old, err := tcGetAttr(os.Stdin)
	if err != nil {
		return SafeInput(prompt, "")
	}
	fmt.Print(prompt)
	noEcho := disableEcho(old)
	if err := tcSetAttr(os.Stdin, noEcho); err != nil {
		return SafeInput(prompt, "")
	}
	reader := bufio.NewReader(os.Stdin)
	line, _ := reader.ReadString('\n')
	_ = tcSetAttr(os.Stdin, old)
	fmt.Println() // newline after hidden input
	return strings.TrimRight(line, "\r\n")
}
