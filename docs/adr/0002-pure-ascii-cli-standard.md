# ADR-0002: Pure ASCII CLI Output Standard

## Status
Accepted

## Context
Initial iterations of Gaet used Unicode emojis (e.g. `✓`, `⚠`, `✗`, `💾`, `☁️`, `⚙️`, `💡`, `📖`) in CLI print statements. While visually appealing in modern UTF-8 Linux terminals, emojis caused critical UX regressions:
1. Encoding errors (`UnicodeEncodeError`) on legacy Windows Command Prompt, Git Bash, or minimal Docker containers with `C` or ASCII locales.
2. Inconsistent rendering width across terminal emulators, leading to misaligned tables and boxes.
3. Pipe and CI/CD parsing difficulties when raw UTF-8 glyphs were captured in build logs.

## Decision
We decided to enforce a **Pure ASCII CLI Standard** across all CLI output and installer scripts:

1. **Standardized ASCII Status Tags**:
   - `[ OK ]` — Successful operation
   - `[FAIL]` — Fatal failure or error
   - `[WARN]` — Warning or missing optional dependency
   - `[INFO]` — Informational status message
   - `[NOTE]` — Parameter or execution detail

2. **Clean Text Headers**: Replace all category emojis with clear text (e.g. `Local Database`, `Cloud Remote`, `Backup & Options`).

3. **Color ANSI Styling**: Retain standard ANSI color codes (`\033[0;32m` for Green, `\033[0;31m` for Red, etc.) for visual hierarchy, which auto-disable when stdout is piped or `--plain` is specified.

## Consequences
- **Positive**: 100% cross-platform compatibility across Windows CMD, PowerShell, Linux, macOS, SSH sessions, and CI/CD pipelines.
- **Positive**: Clean, predictable column alignment in tables and ASCII box headers.
- **Negative**: CLI output relies on ANSI colors and standard tags rather than rich graphical emojis.
