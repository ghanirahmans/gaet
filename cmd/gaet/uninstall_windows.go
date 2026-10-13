//go:build windows

package main

import (
	"fmt"
	"os/exec"
	"strings"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// removeUserPathEntry removes dir from the current user's PATH environment
// variable (HKCU\Environment\Path), which install.ps1 appends to. Returns true
// if the PATH was rewritten. Uses PowerShell (stdlib-only project; no registry
// bindings) and single-quotes the path so backslashes are taken literally.
func removeUserPathEntry(dir string) bool {
	quoted := "'" + strings.ReplaceAll(dir, "'", "''") + "'"
	script := fmt.Sprintf(`
$d = %s
$p = [Environment]::GetEnvironmentVariable('Path','User')
if ($p) {
  $kept = @($p -split ';' | Where-Object { $_ -ne '' -and $_.TrimEnd('\') -ne $d.TrimEnd('\') })
  [Environment]::SetEnvironmentVariable('Path', ($kept -join ';'), 'User')
  Write-Output 'GAET_PATH_UPDATED'
}`, quoted)
	out, _, rc := core.RunCmdSimple("powershell", []string{"-NoProfile", "-NonInteractive", "-Command", script}, nil, 15e9)
	return rc == 0 && strings.Contains(out, "GAET_PATH_UPDATED")
}

// scheduleSelfDelete removes a running gaet.exe after this process exits.
// Windows locks the image of a running executable, so it cannot be deleted
// while gaet is still running; a detached cmd child waits briefly and deletes
// it once the handle is released.
func scheduleSelfDelete(exe string) {
	c := exec.Command("cmd", "/c", `ping 127.0.0.1 -n 2 >nul & del /f /q "`+exe+`"`)
	_ = c.Start() // detached; do not Wait — it must outlive this process
}
