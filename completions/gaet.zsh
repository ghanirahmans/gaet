#compdef gaet

_gaet() {
    local -a commands
    commands=(
        'init:Interactive setup wizard'
        'check:Validate config & connections'
        'status:Show sync status'
        'push:Backup local to cloud'
        'fetch:Restore cloud to local'
        'stop:Stop auto-backup & dashboard'
        'log:View backup log'
        'serve:Start web dashboard'
        'get:Get environment variables'
        'set:Set environment variables'
        'install:Setup dependencies & config'
        'update:Update to latest version'
        'uninstall:Remove gaet'
        'help:Show help for a command'
    )
    
    _arguments -C \
        '(- *)'{-h,--help}'[Show help]' \
        '(-v,--version)'{-v,--version}'[Show version]' \
        '(-q,--quiet)'{-q,--quiet}'[Suppress non-essential output]' \
        '--plain[Plain, decoration-free output]' \
        '--json[Output JSON]' \
        '--dry-run[Simulate without executing]' \
        '(-y,--yes)'{-y,--yes}'[Skip confirmation]' \
        '1:command:->commands' \
        '*::arg:->args'
    
    case $state in
        commands)
            _describe 'command' commands
            ;;
        args)
            case $words[1] in
                push)
                    _arguments \
                        '--auto[Enable auto-backup (hours)]:interval' \
                        '--cron[Run from scheduler]' \
                        '--dry-run[Simulate]' \
                        '--json[Output JSON]' \
                        '--quiet[Suppress output]' \
                        '--plain[Plain output]'
                    ;;
                fetch)
                    _arguments \
                        '--dry-run[Simulate]' \
                        '--yes[Skip confirmation]' \
                        '--json[Output JSON]' \
                        '--quiet[Suppress output]' \
                        '--plain[Plain output]'
                    ;;
                status)
                    _arguments \
                        '--json[Output JSON]' \
                        '--quiet[Suppress output]' \
                        '--plain[Plain output]'
                    ;;
                log)
                    _arguments \
                        '--filter[Filter by keyword]:keyword' \
                        '--since[Filter since date]:date' \
                        '(-q,--quiet)'{-q,--quiet}'[Suppress output]' \
                        '--plain[Plain output]' \
                        '1:lines'
                    ;;
                serve)
                    _arguments \
                        '--port[Custom port]:port' \
                        '--no-browser[Don\'t open browser]' \
                        '--quiet[Suppress output]' \
                        '--plain[Plain output]'
                    ;;
                get)
                    _arguments \
                        '1:key:*' \
                        '--quiet[Suppress output]' \
                        '--plain[Plain output]'
                    ;;
                set)
                    _arguments \
                        '1:variable:*' \
                        '--quiet[Suppress output]' \
                        '--plain[Plain output]'
                    ;;
                check)
                    _arguments \
                        '--json[Output JSON]' \
                        '--quiet[Suppress output]' \
                        '--plain[Plain output]'
                    ;;
                help)
                    _arguments \
                        '1:topic:->topics' \
                        '--json[Output JSON]'
                    ;;
                install)
                    _arguments \
                        '--yes[Auto-approve]' \
                        '--skip-deps[Skip dependencies]' \
                        '--skip-build[Skip dashboard build]' \
                        '--skip-config[Skip config wizard]' \
                        '--skip-service[Skip service setup]' \
                        '--interval[Auto-backup interval (hours)]:interval'
                    ;;
                update)
                    _arguments \
                        '--force[Force update]' \
                        '--skip-build[Skip dashboard build]'
                    ;;
                uninstall)
                    _arguments \
                        '--purge[Remove everything]'
                    ;;
                *)
                    _arguments \
                        '--quiet[Suppress output]' \
                        '--plain[Plain output]'
                    ;;
            esac
            ;;
    esac
}

_gaet "$@"
