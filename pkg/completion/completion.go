// Package completion implements `gaet completion` shell autocompletion generator.
package completion

import (
	"fmt"
	"strings"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// RunCompletion generates shell autocompletion scripts.
func RunCompletion(shell string) error {
	switch strings.ToLower(shell) {
	case "bash":
		fmt.Print(bashScript)
	case "zsh":
		fmt.Print(zshScript)
	case "fish":
		fmt.Print(fishScript)
	case "powershell", "ps1":
		fmt.Print(psScript)
	default:
		return core.Die(fmt.Sprintf("Unknown shell '%s'. Supported: bash, zsh, fish, powershell", shell), core.ExitUsage)
	}
	return nil
}

const bashScript = `# gaet bash completion
_gaet_complete() {
    local cur prev cmds
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    cmds="init push fetch restore snapshots status check doctor remote get set auto stop serve log completion update uninstall help"
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${cmds}" -- "${cur}") )
    fi
}
complete -F _gaet_complete gaet
`

const zshScript = `#compdef gaet
_gaet() {
    local -a subcmds
    subcmds=(init push fetch restore snapshots status check doctor remote get set auto stop serve log completion update uninstall help)
    _describe 'command' subcmds
}
compdef _gaet gaet
`

const fishScript = `# gaet fish completion
set -l cmds init push fetch restore snapshots status check doctor remote get set auto stop serve log completion update uninstall help
complete -c gaet -f -a "$cmds"
`

const psScript = `# gaet PowerShell completion
Register-ArgumentCompleter -Native -CommandName gaet -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $cmds = @('init','push','fetch','restore','snapshots','status','check','doctor','remote','get','set','auto','stop','serve','log','completion','update','uninstall','help')
    $cmds | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }
}
`
