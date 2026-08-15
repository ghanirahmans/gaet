# PowerShell completions for gaet
# Install: Copy this file to $HOME/.ps1int or use: Register-ArgumentCompleter -Native -CommandName gaet -ScriptBlock $completer

$gaetCommands = @(
    'init',
    'check',
    'status',
    'push',
    'fetch',
    'stop',
    'log',
    'serve',
    'get',
    'set',
    'install',
    'update',
    'uninstall',
    'help',
    'diff',
    'export',
    'completion',
    'doctor'
)

$gaetFlags = @(
    '--help', '-h',
    '--version', '-v',
    '--quiet', '-q',
    '--plain',
    '--json',
    '--dry-run',
    '--yes', '-y',
    '--follow', '-F',
    '--notify',
    '--tables',
    '--watch',
    '--auto',
    '--cron',
    '--since',
    '--port',
    '--no-browser',
    '--force',
    '--purge',
    '--skip-deps',
    '--skip-build',
    '--skip-config',
    '--skip-service',
    '--interval'
)

$completer = {
    param($commandName, $parameterName, $wordToComplete, $commandAst, $fakeBoundParameters)
    
    $completion = @()
    
    # Complete commands
    if (-not $WordToComplete -or $WordToComplete -notmatch '^-') {
        foreach ($cmd in $gaetCommands) {
            if ($cmd -like "$WordToComplete*") {
                $completion += [System.Management.Automation.CompletionResult]::new($cmd, $cmd, 'ParameterValue', $cmd)
            }
        }
    }
    
    # Complete flags
    if ($WordToComplete -match '^-') {
        foreach ($flag in $gaetFlags) {
            if ($flag -like "$WordToComplete*") {
                $completion += [System.Management.Automation.CompletionResult]::new($flag, $flag, 'ParameterValue', $flag)
            }
        }
    }
    
    return $completion
}

# Register for current session
Register-ArgumentCompleter -Native -CommandName gaet -ScriptBlock $completer
