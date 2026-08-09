# bash completion for gaet
_gaet_completions() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="init check status push fetch stop log serve get set install update uninstall help"
    
    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "--help --version --quiet --plain --json --dry-run --yes" -- ${cur}) )
    elif [[ ${cur} == * && ${prev} != "gaet" ]]; then
        COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
    fi
}
complete -F _gaet_completions gaet
