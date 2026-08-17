// Package completion_test tests the completion command output.
package completion_test

import (
	"strings"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/completion"
)

func TestRunCompletion_Bash(t *testing.T) {
	// Capture stdout — we just test it doesn't error
	if err := completion.RunCompletion("bash"); err != nil {
		t.Errorf("completion bash: %v", err)
	}
}

func TestRunCompletion_Zsh(t *testing.T) {
	if err := completion.RunCompletion("zsh"); err != nil {
		t.Errorf("completion zsh: %v", err)
	}
}

func TestRunCompletion_Fish(t *testing.T) {
	if err := completion.RunCompletion("fish"); err != nil {
		t.Errorf("completion fish: %v", err)
	}
}

func TestRunCompletion_PowerShell(t *testing.T) {
	if err := completion.RunCompletion("powershell"); err != nil {
		t.Errorf("completion powershell: %v", err)
	}
}

func TestRunCompletion_UnknownShell(t *testing.T) {
	err := completion.RunCompletion("unknownshell")
	if err == nil {
		t.Error("expected error for unknown shell, got nil")
	}
	if !strings.Contains(err.Error(), "unknownshell") {
		t.Errorf("error should mention shell name, got: %v", err)
	}
}
