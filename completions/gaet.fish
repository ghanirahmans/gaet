# fish completion for gaet

function __gaet_no_subcommand
    set -l cmd (commandline -opc)
    test (count $cmd) -eq 1
end

function __gaet_using_command
    set -l cmd (commandline -opc)
    test (count $cmd) -ge 2; and test "$cmd[2]" = "$argv[1]"
end

# Global flags
complete -c gaet -l help -s h -d 'Show help'
complete -c gaet -l version -s v -d 'Show version'
complete -c gaet -l quiet -s q -d 'Suppress non-essential output'
complete -c gaet -l plain -d 'Plain, decoration-free output'
complete -c gaet -l json -d 'Output JSON'
complete -c gaet -l dry-run -d 'Simulate without executing'
complete -c gaet -l yes -s y -d 'Skip confirmation'

# Subcommands
complete -c gaet -n __gaet_no_subcommand -a init -d 'Interactive setup wizard'
complete -c gaet -n __gaet_no_subcommand -a check -d 'Validate config & connections'
complete -c gaet -n __gaet_no_subcommand -a status -d 'Show sync status'
complete -c gaet -n __gaet_no_subcommand -a push -d 'Backup local to cloud'
complete -c gaet -n __gaet_no_subcommand -a fetch -d 'Restore cloud to local'
complete -c gaet -n __gaet_no_subcommand -a stop -d 'Stop auto-backup & dashboard'
complete -c gaet -n __gaet_no_subcommand -a log -d 'View backup log'
complete -c gaet -n __gaet_no_subcommand -a serve -d 'Start web dashboard'
complete -c gaet -n __gaet_no_subcommand -a get -d 'Get environment variables'
complete -c gaet -n __gaet_no_subcommand -a set -d 'Set environment variables'
complete -c gaet -n __gaet_no_subcommand -a install -d 'Setup dependencies & config'
complete -c gaet -n __gaet_no_subcommand -a update -d 'Update to latest version'
complete -c gaet -n __gaet_no_subcommand -a uninstall -d 'Remove gaet'
complete -c gaet -n __gaet_no_subcommand -a help -d 'Show help for a command'
