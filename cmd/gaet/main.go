// Package main is the CLI entry point for gaet v2.0 (Go binary).
package main

import (
	"fmt"
	"os"

	"github.com/ghanirahmans/gaet/pkg/backup"
	"github.com/ghanirahmans/gaet/pkg/completion"
	"github.com/ghanirahmans/gaet/pkg/config"
	"github.com/ghanirahmans/gaet/pkg/core"
	gaetinit "github.com/ghanirahmans/gaet/pkg/init"
	gaetlog "github.com/ghanirahmans/gaet/pkg/log"
	"github.com/ghanirahmans/gaet/pkg/remote"
	"github.com/ghanirahmans/gaet/pkg/scheduler"
	"github.com/ghanirahmans/gaet/pkg/serve"
	"github.com/ghanirahmans/gaet/pkg/snapshots"
	"github.com/ghanirahmans/gaet/pkg/status"
)

func main() {
	args := os.Args[1:]

	// Parse global flags first
	args = extractGlobalFlags(args)

	if len(args) == 0 {
		printWelcome()
		os.Exit(0)
	}

	command := args[0]
	subArgs := args[1:]

	if err := dispatch(command, subArgs); err != nil {
		if ge, ok := err.(*core.GaetError); ok {
			os.Exit(ge.Code)
		}
		os.Exit(1)
	}
}

func extractGlobalFlags(args []string) []string {
	var remaining []string
	for _, a := range args {
		switch a {
		case "-q", "--quiet":
			core.Quiet = true
		case "--plain":
			core.Plain = true
		default:
			remaining = append(remaining, a)
		}
	}
	return remaining
}

func dispatch(command string, args []string) error {
	switch command {
	case "--version", "-v", "version":
		fmt.Printf("gaet v%s\n", core.Version)
		return nil

	case "--help", "-h", "help":
		printHelp(args)
		return nil

	// ── init ──────────────────────────────────────────────────────────
	case "init":
		opts := gaetinit.InitOptions{}
		for i, a := range args {
			if a == "--preset" && i+1 < len(args) {
				opts.Preset = args[i+1]
			} else if a == "-y" || a == "--yes" {
				opts.Yes = true
			} else if !isFlag(a) {
				opts.Preset = a
			}
		}
		return gaetinit.RunInit(opts)

	// ── push ──────────────────────────────────────────────────────────
	case "push":
		opts := backup.PushOptions{}
		isCron := false
		isAuto := false
		autoInterval := 0
		for i, a := range args {
			switch a {
			case "--dry-run":
				opts.DryRun = true
			case "--json":
				opts.JSON = true
			case "--cron":
				isCron = true
			case "--auto":
				isAuto = true
			case "--notify":
				if i+1 < len(args) {
					opts.Notify = args[i+1]
				}
			default:
				if len(a) > 7 && a[:7] == "--auto=" {
					isAuto = true
					fmt.Sscanf(a[7:], "%d", &autoInterval)
				}
			}
		}
		if isCron {
			return backup.RunPushCron()
		}
		if isAuto {
			env, _ := core.LoadEnv(core.EnvFile())
			if autoInterval == 0 {
				autoInterval = core.GetEnvInt(env, "GAET_AUTO_INTERVAL", core.DefAutoInterval)
			}
			prefix := core.GetEnvStr(env, "GAET_SERVICE_PREFIX", core.DefServicePrefix)
			return scheduler.EnableAuto(prefix, autoInterval, os.Args[0])
		}
		return backup.RunPush(opts)

	// ── fetch ─────────────────────────────────────────────────────────
	case "fetch":
		opts := backup.FetchOptions{}
		for _, a := range args {
			switch a {
			case "--dry-run":
				opts.DryRun = true
			case "--json":
				opts.JSON = true
			case "-y", "--yes":
				opts.Yes = true
			}
		}
		return backup.RunFetch(opts)

	// ── restore ───────────────────────────────────────────────────────
	case "restore":
		opts := backup.RestoreOptions{Target: "latest"}
		for _, a := range args {
			switch a {
			case "--dry-run":
				opts.DryRun = true
			case "--json":
				opts.JSON = true
			case "-y", "--yes":
				opts.Yes = true
			default:
				if !isFlag(a) {
					opts.Target = a
				}
			}
		}
		return backup.RunRestore(opts)

	// ── snapshots ─────────────────────────────────────────────────────
	case "snapshots":
		jsonOut := hasFlag(args, "--json")
		return snapshots.RunSnapshots(jsonOut)

	// ── status ────────────────────────────────────────────────────────
	case "status":
		return status.RunStatus(status.StatusOptions{JSON: hasFlag(args, "--json")})

	// ── check ─────────────────────────────────────────────────────────
	case "check":
		return status.RunCheck(status.CheckOptions{JSON: hasFlag(args, "--json")})

	// ── doctor ────────────────────────────────────────────────────────
	case "doctor":
		return status.RunDoctor(status.DoctorOptions{JSON: hasFlag(args, "--json")})

	// ── remote ────────────────────────────────────────────────────────
	case "remote":
		action := "show"
		urlArg := ""
		jsonOut := hasFlag(args, "--json")
		for i, a := range args {
			if !isFlag(a) {
				if action == "show" {
					action = a
				} else if urlArg == "" {
					urlArg = a
				}
			}
			if (a == "set-url") && i+1 < len(args) {
				urlArg = args[i+1]
			}
		}
		return remote.RunRemote(action, urlArg, jsonOut)

	// ── get ───────────────────────────────────────────────────────────
	case "get":
		listFlag := hasFlag(args, "--list") || hasFlag(args, "-l")
		jsonOut := hasFlag(args, "--json")
		var keys []string
		for _, a := range args {
			if !isFlag(a) {
				keys = append(keys, a)
			}
		}
		return config.RunGet(keys, listFlag, jsonOut)

	// ── set ───────────────────────────────────────────────────────────
	case "set":
		listFlag := hasFlag(args, "--list") || hasFlag(args, "-l")
		var vars []string
		for _, a := range args {
			if !isFlag(a) {
				vars = append(vars, a)
			}
		}
		return config.RunSet(vars, listFlag)

	// ── auto ──────────────────────────────────────────────────────────
	case "auto":
		interval := core.DefAutoInterval
		for _, a := range args {
			if len(a) > 0 && a[0] != '-' {
				fmt.Sscanf(a, "%d", &interval)
			}
		}
		env, _ := core.LoadEnv(core.EnvFile())
		prefix := core.GetEnvStr(env, "GAET_SERVICE_PREFIX", core.DefServicePrefix)
		return scheduler.EnableAuto(prefix, interval, os.Args[0])

	// ── stop ──────────────────────────────────────────────────────────
	case "stop":
		env, _ := core.LoadEnv(core.EnvFile())
		prefix := core.GetEnvStr(env, "GAET_SERVICE_PREFIX", core.DefServicePrefix)
		return scheduler.DisableAuto(prefix)

	// ── serve ─────────────────────────────────────────────────────────
	case "serve":
		env, _ := core.LoadEnv(core.EnvFile())
		port := core.GetEnvInt(env, "GAET_DASHBOARD_PORT", core.DefDashboardPort)
		host := core.GetEnvStr(env, "GAET_DASHBOARD_HOST", core.DefDashboardHost)
		for i, a := range args {
			if a == "--port" && i+1 < len(args) {
				fmt.Sscanf(args[i+1], "%d", &port)
			}
			if a == "--host" && i+1 < len(args) {
				host = args[i+1]
			}
		}
		return serve.RunServe(serve.ServeOptions{Host: host, Port: port})

	// ── log ───────────────────────────────────────────────────────────
	case "log":
		opts := gaetlog.LogOptions{Lines: 30}
		for i, a := range args {
			switch a {
			case "-f", "--filter":
				if i+1 < len(args) {
					opts.Filter = args[i+1]
				}
			case "-s", "--since":
				if i+1 < len(args) {
					opts.Since = args[i+1]
				}
			case "-F", "--follow":
				opts.Follow = true
			default:
				if !isFlag(a) {
					fmt.Sscanf(a, "%d", &opts.Lines)
				}
			}
		}
		return gaetlog.RunLog(opts)

	// ── completion ────────────────────────────────────────────────────
	case "completion":
		shell := "bash"
		for i, a := range args {
			if a == "--shell" && i+1 < len(args) {
				shell = args[i+1]
			} else if !isFlag(a) {
				shell = a
			}
		}
		return completion.RunCompletion(shell)

	// ── update ────────────────────────────────────────────────────────
	case "update":
		return runUpdate(args)

	// ── uninstall ─────────────────────────────────────────────────────
	case "uninstall":
		return runUninstall(args)

	default:
		core.StatusFail(fmt.Sprintf("Unknown command '%s'", command))
		fmt.Println()
		printHelp(nil)
		return core.Die(fmt.Sprintf("unknown command: %s", command), core.ExitUsage)
	}
}

func runUpdate(args []string) error {
	core.BoxTitle("gaet update")
	core.StatusInfo("Checking for updates from GitHub...")
	core.StatusInfo("(Self-update via GitHub Releases not yet implemented in v2 — use: curl ... | bash)")
	core.PrintDocsFooter()
	return nil
}

func runUninstall(args []string) error {
	save := hasFlag(args, "--save")
	mode := "purge"
	if save {
		mode = "save"
	}
	core.BoxTitle(fmt.Sprintf("gaet uninstall (%s)", mode))

	if !hasFlag(args, "-y") && !hasFlag(args, "--yes") {
		if !core.IsStdinTTY() {
			return core.Die("gaet uninstall in non-interactive mode requires --yes flag", core.ExitConfig)
		}
		core.StatusWarn("PURGE: removing gaet CLI, configuration, and backups.")
		ans := core.SafeInput("  Type 'yes' to confirm: ", "")
		if ans != "yes" {
			core.Echo("  Cancelled.")
			return nil
		}
	}

	// Stop scheduler
	env, _ := core.LoadEnv(core.EnvFile())
	prefix := core.GetEnvStr(env, "GAET_SERVICE_PREFIX", core.DefServicePrefix)
	_ = scheduler.DisableAuto(prefix)

	// Remove binary
	home, _ := os.UserHomeDir()
	for _, name := range []string{"gaet", "gaet.cmd", "gaet.bat", "gaet.exe"} {
		p := fmt.Sprintf("%s/.local/bin/%s", home, name)
		if err := os.Remove(p); err == nil {
			core.StatusOK(fmt.Sprintf("Removed: %s", p))
		}
	}

	// Remove app bundle
	appDir := core.GaetAppDir()
	if _, err := os.Stat(appDir); err == nil {
		os.RemoveAll(appDir)
		core.StatusOK(fmt.Sprintf("Removed app bundle: %s", appDir))
	}

	// Remove user data
	gaetDir := core.GaetDir()
	if _, err := os.Stat(gaetDir); err == nil {
		os.RemoveAll(gaetDir)
		core.StatusOK(fmt.Sprintf("Removed user data: %s", gaetDir))
	}

	fmt.Println()
	core.StatusOK("Uninstall complete.")
	return nil
}

func printWelcome() {
	env, _ := core.LoadEnv(core.EnvFile())
	core.BoxTitle(fmt.Sprintf("gaet %s", core.Version))
	fmt.Println()
	if len(env) > 0 {
		core.StatusOK(fmt.Sprintf("Configuration active (%d variables)", len(env)))
		core.StatusArrow(fmt.Sprintf("Config file: %s", core.EnvFile()))
	} else {
		core.StatusWarn("Not configured yet.")
		core.Echo("  Get started:")
		core.Echo(fmt.Sprintf("    %s1.%s gaet init          Setup wizard", core.ColorCyan, core.ColorReset))
		core.Echo(fmt.Sprintf("    %s2.%s gaet push          Backup local -> cloud", core.ColorCyan, core.ColorReset))
		core.Echo(fmt.Sprintf("    %s3.%s gaet status        Show sync status", core.ColorCyan, core.ColorReset))
	}
	fmt.Println()
	core.Echo(fmt.Sprintf("  %sPopular commands:%s", core.ColorBold, core.ColorReset))
	core.Echo(fmt.Sprintf("    %sgaet init%s           Setup database", core.ColorCyan, core.ColorReset))
	core.Echo(fmt.Sprintf("    %sgaet push%s           Backup to cloud", core.ColorCyan, core.ColorReset))
	core.Echo(fmt.Sprintf("    %sgaet fetch%s          Restore from cloud", core.ColorCyan, core.ColorReset))
	core.Echo(fmt.Sprintf("    %sgaet status%s         Check sync status", core.ColorCyan, core.ColorReset))
	core.Echo(fmt.Sprintf("    %sgaet check%s          Validate connection", core.ColorCyan, core.ColorReset))
	core.Echo(fmt.Sprintf("    %sgaet serve%s          Open web dashboard", core.ColorCyan, core.ColorReset))
	fmt.Println()
	core.Echo(fmt.Sprintf("  %sNeed help?%s  gaet --help | gaet help <command>", core.ColorDim, core.ColorReset))
	core.PrintDocsFooter()
}

func printHelp(args []string) {
	if len(args) > 0 {
		// `gaet help <command>` — show command-specific help
		printCommandHelp(args[0])
		return
	}
	core.BoxTitle(fmt.Sprintf("gaet %s — Database Backup & Sync CLI", core.Version))
	fmt.Println()
	core.Echo("  Usage: gaet <command> [options]")
	fmt.Println()
	core.Echo(fmt.Sprintf("  %sCommands:%s", core.ColorBold, core.ColorReset))
	commands := [][2]string{
		{"init", "Interactive setup wizard"},
		{"push", "Backup local database -> cloud"},
		{"fetch", "Restore cloud -> local (overwrite)"},
		{"restore", "Restore local DB from a local snapshot"},
		{"snapshots", "List local backup snapshots"},
		{"status", "Show sync status table"},
		{"check", "Validate config & connections"},
		{"doctor", "Comprehensive health check"},
		{"remote", "Manage remote cloud DB config"},
		{"get", "Get configuration variables"},
		{"set", "Set configuration variables"},
		{"auto", "Enable auto-backup (platform scheduler)"},
		{"stop", "Stop auto-backup scheduler"},
		{"serve", "Start web dashboard (port 9191)"},
		{"log", "View backup history log"},
		{"completion", "Generate shell autocompletion script"},
		{"update", "Update to latest version"},
		{"uninstall", "Remove gaet from system"},
	}
	for _, c := range commands {
		core.Echo(fmt.Sprintf("    %s%-14s%s %s", core.ColorCyan, c[0], core.ColorReset, c[1]))
	}
	fmt.Println()
	core.Echo(fmt.Sprintf("  %sGlobal flags:%s", core.ColorBold, core.ColorReset))
	core.Echo("    -q, --quiet   Suppress non-essential output")
	core.Echo("    --plain       Plain pipe-safe output (no ANSI colors)")
	core.Echo("    --json        Machine-readable JSON output")
	core.Echo("    -y, --yes     Auto-confirm destructive prompts (CI/CD)")
	fmt.Println()
	core.Echo(fmt.Sprintf("  %sExamples:%s", core.ColorBold, core.ColorReset))
	core.Echo("    gaet init")
	core.Echo("    gaet push")
	core.Echo("    gaet status")
	core.Echo("    gaet check --json | jq '.ok'")
	core.PrintDocsFooter()
}

func printCommandHelp(cmd string) {
	help := map[string]string{
		"push":      "gaet push [--dry-run] [--json] [--auto[=N]] [--cron] [--notify=URL]\n  Backup local PostgreSQL database to cloud.",
		"fetch":     "gaet fetch [--dry-run] [--json] [-y/--yes]\n  Restore cloud database to local (DESTRUCTIVE).",
		"restore":   "gaet restore [target|latest] [--dry-run] [--json] [-y/--yes]\n  Restore local DB from a local snapshot file.",
		"snapshots": "gaet snapshots [--json]\n  List local backup snapshot files.",
		"status":    "gaet status [--json]\n  Show sync status table (local vs cloud).",
		"check":     "gaet check [--json]\n  Validate configuration and all DB connections.",
		"doctor":    "gaet doctor [--json]\n  Comprehensive health check.",
		"remote":    "gaet remote [show|set-url|remove] [url]\n  Manage remote cloud database URL.",
		"get":       "gaet get [KEY...] [--list] [--json]\n  Display configuration variables from .env.",
		"set":       "gaet set KEY=value [...]\n  Update configuration variables in .env.",
		"auto":      "gaet auto [interval_hours]\n  Enable auto-backup scheduler (default: 6h).",
		"stop":      "gaet stop\n  Stop auto-backup scheduler.",
		"serve":     "gaet serve [--port=9191] [--host=127.0.0.1]\n  Start embedded web dashboard.",
		"log":       "gaet log [N] [--filter=KW] [--since=DATE] [--follow]\n  View backup log.",
		"completion": "gaet completion [bash|zsh|fish|powershell]\n  Generate shell autocompletion script.",
		"init":      "gaet init [--preset=name] [-y/--yes]\n  Interactive first-run setup wizard.",
	}
	if h, ok := help[cmd]; ok {
		core.BoxTitle(fmt.Sprintf("gaet %s — Help", cmd))
		core.Echo(fmt.Sprintf("  %s", h))
		fmt.Println()
	} else {
		core.StatusWarn(fmt.Sprintf("No help available for '%s'", cmd))
		printHelp(nil)
	}
}

func hasFlag(args []string, flag string) bool {
	for _, a := range args {
		if a == flag {
			return true
		}
	}
	return false
}

func isFlag(s string) bool {
	return len(s) > 0 && s[0] == '-'
}
