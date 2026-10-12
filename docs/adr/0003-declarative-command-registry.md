# ADR-0003: Command Dispatch Pattern

## Status
Accepted (applies to Golang engine v1.1.0+ on `main`)

## Context
As Gaet grew in subcommands (`init`, `push`, `fetch`, `restore`, `snapshots`, `status`, `check`, `doctor`, `diff`, `export`, `remote`, `get`, `set`, `auto`, `stop`, `serve`, `log`, `completion`, `update`, `uninstall`), each command needed an isolated, testable implementation. The legacy Python implementation used a `@command` decorator registry (`src/gaet/registry.py`) with dynamic discovery. For the Golang engine, we evaluated whether to adopt a third-party CLI framework (e.g., cobra/spf13) or a registry-based approach.

## Decision
We implemented command dispatch via an **explicit `switch` statement** in `cmd/gaet/main.go`, with each subcommand as an **isolated `pkg/` package** that exposes a single exported `Run*()` entry point.

```go
switch command {
case "init":
    return gaetinit.RunInit(opts)
case "push":
    return backup.RunPush(opts)
case "fetch":
    return backup.RunFetch(opts)
// ... (20 total cases)
default:
    core.StatusFail(fmt.Sprintf("Unknown command '%s'", command))
    return core.Die("", core.ExitUsage)
}
```

1. **Explicit Dispatch (no magic)**: `main.go` imports all subcommand packages and dispatches via a hand-written `switch`. No decorators, no dynamic reflection, no framework registration side-effects.
2. **Single Responsibility per Package**: Each package under `pkg/` (e.g., `pkg/backup`, `pkg/config`, `pkg/status`) contains one exported `Run*()` function — the sole entry point callable from both the CLI dispatch and the HTTP handlers in `pkg/serve`.
3. **Shared Foundation**: All subcommand packages depend **only** on `pkg/core` (the shared utility layer). No inter-subcommand dependencies exist, except `pkg/serve` which intentionally wraps `pkg/backup`, `pkg/detect`, and `pkg/scheduler` for REST API exposure.
4. **Zero Third-Party Dependencies**: No CLI framework (cobra, spf13, kingpin) is used, keeping the dependency graph at zero (verified: `go.mod` has no `require` directives).

## Consequences
- **Positive**: Adding a subcommand is a 3-line change in `main.go` (one `case`, one import, one struct). No registry side-effects to debug.
- **Positive**: Full control over flag parsing, error codes, and global output modes (`--json`, `--plain`, `--quiet`).
- **Positive**: Shared business logic between CLI and REST API — `pkg/serve/server.go` calls `backup.RunPush()`, `backup.RunFetch()`, `backup.RunRestore()` directly.
- **Negative**: Flag parsing is manual (per-case `for i, a := range args` loops) rather than declarative schema-driven. Acceptable trade-off given the < 25 commands and zero-dependency constraint.

## Reference Implementation
- `cmd/gaet/main.go`: the `dispatch()` function (the switch statement).
- `pkg/core/errors.go`: the typed `*GaetError` returned by each `Run*()` function.
- `pkg/serve/server.go`: demonstrates `pkg/serve` wrapping `pkg/backup` `Run*()` functions for HTTP handlers.
