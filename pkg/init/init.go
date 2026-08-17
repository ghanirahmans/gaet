// Package gaetinit implements `gaet init` — the interactive first-run setup wizard.
package gaetinit

import (
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
	"github.com/ghanirahmans/gaet/pkg/detect"
)

// Preset is a pre-configured database profile.
type Preset struct {
	LocalUser string
	LocalDB   string
	LocalPass string
	Tables    string
	Desc      string
}

var presets = map[string]Preset{
	"hindsight": {
		LocalUser: "hindsight", LocalDB: "hindsight", LocalPass: "hindsight",
		Tables: "memory_units,banks,chunks,entities,documents,async_operations,audit_log,file_storage,memory_links",
		Desc:   "Hindsight AI memory database",
	},
	"hindsight-hermes": {
		LocalUser: "hindsight", LocalDB: "hindsight", LocalPass: "hindsight",
		Tables: "memory_units,banks,chunks,entities,documents,memory_links,unit_entities,entity_cooccurrences,observation_history,mental_models,directives,async_operations,webhooks,file_storage,audit_log,llm_requests,graph_maintenance_queue",
		Desc:   "Hindsight memory database for Hermes Agent",
	},
}

// InitOptions holds flags for `gaet init`.
type InitOptions struct {
	Preset string
	Yes    bool
}

// RunInit implements `gaet init`.
func RunInit(opts InitOptions) error {
	env, _ := core.LoadEnv(core.EnvFile())
	core.BoxTitle("gaet init")

	// Non-interactive detection
	isCI := os.Getenv("CI") == "true" || os.Getenv("CONTAINER") == "1"
	isHermes := false
	for _, k := range os.Environ() {
		if strings.HasPrefix(k, "HERMES_") {
			isHermes = true
			break
		}
	}
	isInteractive := core.IsStdinTTY() && !isHermes && !isCI

	if !isInteractive {
		return runNonInteractive(env, opts)
	}

	// Check tools
	tools := core.FindDBTools(env)
	core.BoxSection("Database Client Tools Check")
	for _, name := range []string{"pg_dump", "pg_restore", "psql"} {
		var path string
		switch name {
		case "pg_dump":
			path = tools.PgDump
		case "pg_restore":
			path = tools.PgRestore
		case "psql":
			path = tools.Psql
		}
		if path != "" {
			core.StatusOK(fmt.Sprintf("%-12s %s", name, path))
		} else {
			core.StatusFail(fmt.Sprintf("%-12s not found in PATH", name))
		}
	}

	_ = core.EnsureDir(core.GaetDir())
	_ = core.EnsureDir(core.BackupDir())

	// Backup existing config
	envFile := core.EnvFile()
	if _, err := os.Stat(envFile); err == nil {
		backupPath := fmt.Sprintf("%s/.env.backup.%s", core.GaetDir(), time.Now().Format("20060102_150405"))
		if data, err := os.ReadFile(envFile); err == nil {
			os.WriteFile(backupPath, data, 0600)
			core.StatusInfo(fmt.Sprintf("Existing config backed up to: %s", backupPath))
		}
	}

	// Apply preset if specified
	var h, p, u, n, w string
	if opts.Preset != "" {
		pr, ok := presets[strings.ToLower(opts.Preset)]
		if !ok {
			return core.Die(fmt.Sprintf("Preset '%s' not found. Available: %s", opts.Preset, availablePresets()), core.ExitConfig)
		}
		core.StatusInfo(fmt.Sprintf("Preset: %s", pr.Desc))
		u, n, w = pr.LocalUser, pr.LocalDB, pr.LocalPass
		h, p = "127.0.0.1", "5432"
		// Let user pick instance if detected
		if tools.Psql != "" {
			instances := detect.DetectLocalPG(tools.Psql)
			if len(instances) > 0 {
				h = instances[0].Host
				p = instances[0].Port
			}
		}
	} else {
		// Interactive local DB setup
		var instances []detect.PGInstance
		if tools.Psql != "" {
			core.StatusInfo("Scanning local PostgreSQL instances...")
			instances = detect.DetectLocalPG(tools.Psql)
		}
		curH, curP, curU, curN, curW := core.GetLocalDB(env)
		h, p, u, n, w = localDBMenu(instances, curH, curP, curU, curN, curW)
	}

	// Test connection
	fmt.Println()
	if tools.Psql != "" && h != "" {
		fmt.Printf("  %s[INFO]%s  Testing %s@%s:%s/%s... ",
			core.ColorBCyan, core.ColorReset, u, h, p, n)
		envDB := core.PGEnv(u, w, "")
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"},
			envDB, 5*time.Second)
		if rc == 0 && strings.TrimSpace(out) == "1" {
			fmt.Printf("%sOK%s\n", core.ColorBGreen, core.ColorReset)
		} else {
			fmt.Printf("%sFAIL%s\n", core.ColorBRed, core.ColorReset)
			core.StatusWarn("Connection failed — config will be saved anyway. Fix with 'gaet set' or 'gaet init'.")
		}
	}

	// Step 2: Remote URL
	fmt.Println()
	core.BoxSection("Step 2/3: Cloud / Remote Database (Optional)")
	oldRemote := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if oldRemote == "" {
		oldRemote = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	prompt := "empty"
	if oldRemote != "" {
		prompt = "already set"
	}
	remoteURL := core.SafeInput(fmt.Sprintf("  GAET_REMOTE_URL [%s]: ", prompt), "")
	remoteURL = strings.TrimSpace(remoteURL)
	if remoteURL == "" {
		remoteURL = oldRemote
	}

	// Step 3: Retention
	fmt.Println()
	core.BoxSection("Step 3/3: Backup & Retention")
	oldRet := core.GetEnvStr(env, "GAET_RETENTION_DAYS", fmt.Sprintf("%d", core.DefRetentionDays))
	retInput := core.SafeInput(fmt.Sprintf("  Backup Retention Period (days) [%s]: ", oldRet), "")
	retInput = strings.TrimSpace(retInput)
	if retInput == "" {
		retInput = oldRet
	}

	// Build and write .env
	tablesLine := ""
	if opts.Preset != "" {
		if pr, ok := presets[strings.ToLower(opts.Preset)]; ok && pr.Tables != "" {
			tablesLine = "GAET_TABLES=" + pr.Tables
		}
	}
	content := buildEnvContent(h, p, u, n, w, remoteURL, retInput, tablesLine)
	if err := core.WriteEnvContent(envFile, content); err != nil {
		return err
	}

	fmt.Println()
	core.StatusOK(fmt.Sprintf("Configuration saved to: %s", envFile))
	fmt.Println()
	core.BoxSection("Initialization Summary")
	core.StatusArrow(fmt.Sprintf("Local DB: %s@%s:%s/%s", u, h, p, n))
	if remoteURL != "" {
		core.StatusArrow(fmt.Sprintf("Remote:   %s", core.MaskURLPassword(remoteURL)))
	}
	core.StatusArrow(fmt.Sprintf("Retention: %s days", retInput))
	fmt.Println()
	core.StatusOK("Gaet init complete! Run 'gaet status' to check synchronization.")
	core.PrintDocsFooter()
	return nil
}

func runNonInteractive(env map[string]string, opts InitOptions) error {
	core.StatusInfo("Non-interactive mode — applying configuration.")
	fmt.Println()

	var h, p, u, n, w string
	tablesLine := ""
	if opts.Preset != "" {
		pr, ok := presets[strings.ToLower(opts.Preset)]
		if !ok {
			return core.Die(fmt.Sprintf("Preset '%s' not found. Available: %s", opts.Preset, availablePresets()), core.ExitConfig)
		}
		u, n, w = pr.LocalUser, pr.LocalDB, pr.LocalPass
		h, p = "127.0.0.1", "5432"
		if pr.Tables != "" {
			tablesLine = "GAET_TABLES=" + pr.Tables
		}
	} else {
		h, p, u, n, w = core.GetLocalDB(env)
		if h == "" {
			h, p, u, n, w = "127.0.0.1", "5432", "postgres", "postgres", ""
			tools := core.FindPGTools(env)
			if tools.Psql != "" {
				instances := detect.DetectLocalPG(tools.Psql)
				if len(instances) > 0 {
					h = instances[0].Host
					p = instances[0].Port
					u = instances[0].User
					n = instances[0].DefaultDB
				}
			}
		} else {
			core.StatusOK(fmt.Sprintf("Preserved existing local DB config: %s@%s:%s/%s", u, h, p, n))
		}
	}

	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	retDays := core.GetEnvStr(env, "GAET_RETENTION_DAYS", fmt.Sprintf("%d", core.DefRetentionDays))

	envFile := core.EnvFile()
	_ = core.EnsureDir(core.GaetDir())
	content := buildEnvContent(h, p, u, n, w, remoteURL, retDays, tablesLine)
	if err := core.WriteEnvContent(envFile, content); err != nil {
		return err
	}
	core.StatusOK(fmt.Sprintf("Config initialized at %s", envFile))
	return nil
}

func localDBMenu(instances []detect.PGInstance, curH, curP, curU, curN, curW string) (h, p, u, n, w string) {
	for {
		fmt.Println()
		core.BoxSection("Step 1/3: Local Database Setup")

		if len(instances) > 0 {
			core.Echo(fmt.Sprintf("  %sDetected PostgreSQL instances:%s", core.ColorBold, core.ColorReset))
			for i, inst := range instances {
				host := inst.Host
				if strings.HasPrefix(host, "/") {
					host = "socket:" + host
				}
				core.Echo(fmt.Sprintf("  %s[%d]%s  %s@%s:%s", core.ColorCyan, i+1, core.ColorReset, inst.User, host, inst.Port))
				core.Echo(fmt.Sprintf("       %sDatabases: %s%s", core.ColorDim, strings.Join(inst.Databases, ", "), core.ColorReset))
			}
			fmt.Println()
		}

		if curH != "" {
			core.Echo(fmt.Sprintf("  %s[E]%s  Use current (%s@%s:%s/%s)", core.ColorCyan, core.ColorReset, curU, curH, curP, curN))
		}
		core.Echo(fmt.Sprintf("  %s[U]%s  Paste connection URL", core.ColorCyan, core.ColorReset))
		core.Echo(fmt.Sprintf("  %s[M]%s  Manual input", core.ColorCyan, core.ColorReset))
		core.Echo(fmt.Sprintf("  %s[D]%s  Default (127.0.0.1:5432/postgres)", core.ColorCyan, core.ColorReset))
		core.Echo(fmt.Sprintf("  %s[Q]%s  Quit", core.ColorCyan, core.ColorReset))
		fmt.Println()

		defChoice := "D"
		if len(instances) > 0 {
			defChoice = "1"
		} else if curH != "" {
			defChoice = "E"
		}
		choice := strings.ToUpper(strings.TrimSpace(core.SafeInput(fmt.Sprintf("  Select option [%s]: ", defChoice), "")))
		if choice == "" {
			choice = defChoice
		}

		// Numeric — select detected instance
		if len(choice) == 1 && choice[0] >= '1' && int(choice[0]-'0') <= len(instances) {
			idx := int(choice[0]-'0') - 1
			inst := instances[idx]
			h = inst.Host
			p = inst.Port
			u = inst.User
			w = ""
			n = inst.DefaultDB
			if len(inst.Databases) > 1 {
				n = selectDB(inst)
			}
			core.StatusOK(fmt.Sprintf("Selected: %s@%s:%s/%s", u, h, p, n))
			return
		}

		switch choice {
		case "Q":
			os.Exit(0)
		case "E":
			if curH != "" {
				return curH, curP, curU, curN, curW
			}
		case "U":
			urlIn := strings.TrimSpace(core.SafeInput("  URL: ", ""))
			if parsed, err := core.ParseRemoteURL(urlIn); err == nil {
				return parsed.Host, parsed.Port, parsed.User, parsed.DB, parsed.Password
			}
			core.StatusWarn("Could not parse URL — falling back to manual input.")
			fallthrough
		case "M":
			hh := strings.TrimSpace(core.SafeInput("    Host [127.0.0.1]: ", ""))
			if hh == "" {
				hh = "127.0.0.1"
			}
			pp := strings.TrimSpace(core.SafeInput("    Port [5432]: ", ""))
			if pp == "" {
				pp = "5432"
			}
			uu := strings.TrimSpace(core.SafeInput("    User [postgres]: ", ""))
			if uu == "" {
				uu = "postgres"
			}
			nn := strings.TrimSpace(core.SafeInput("    Database [postgres]: ", ""))
			if nn == "" {
				nn = "postgres"
			}
			ww := strings.TrimSpace(core.SafeGetPass("    Password []: "))
			return hh, pp, uu, nn, ww
		case "D":
			return "127.0.0.1", "5432", "postgres", "postgres", ""
		default:
			core.StatusWarn(fmt.Sprintf("Invalid option '%s'.", choice))
		}
	}
}

func selectDB(inst detect.PGInstance) string {
	if len(inst.Databases) == 0 {
		return inst.DefaultDB
	}
	core.Echo(fmt.Sprintf("  %sSelect database:%s", core.ColorBold, core.ColorReset))
	for i, db := range inst.Databases {
		core.Echo(fmt.Sprintf("  %s[%d]%s  %s", core.ColorCyan, i+1, core.ColorReset, db))
	}
	choice := strings.TrimSpace(core.SafeInput("  Select [1]: ", ""))
	if choice == "" || choice == "1" {
		return inst.Databases[0]
	}
	if idx := int(choice[0] - '1'); idx >= 0 && idx < len(inst.Databases) {
		return inst.Databases[idx]
	}
	return inst.DefaultDB
}

func buildEnvContent(h, p, u, n, w, remoteURL, retDays, tablesLine string) string {
	var sb strings.Builder
	sb.WriteString("# ══════════════════════════════════════════════════════════════\n")
	sb.WriteString("# gaet — Configuration\n")
	sb.WriteString(fmt.Sprintf("# Generated: %s\n", time.Now().Format("2006-01-02 15:04:05")))
	sb.WriteString("# ══════════════════════════════════════════════════════════════\n\n")

	sb.WriteString("# Local Database\n")
	if strings.HasPrefix(h, "/") {
		sb.WriteString(fmt.Sprintf("GAET_LOCAL_DB_HOST=%s\n", h))
		sb.WriteString(fmt.Sprintf("GAET_LOCAL_DB_PORT=%s\n", p))
		sb.WriteString(fmt.Sprintf("GAET_LOCAL_DB_USER=%s\n", u))
		sb.WriteString(fmt.Sprintf("GAET_LOCAL_DB_NAME=%s\n", n))
	} else {
		sb.WriteString(fmt.Sprintf("GAET_LOCAL_URL=postgresql://%s@%s:%s/%s\n", u, h, p, n))
	}
	if w != "" {
		sb.WriteString(fmt.Sprintf("GAET_LOCAL_DB_PASS=%s\n", w))
	} else {
		sb.WriteString("# GAET_LOCAL_DB_PASS=\n")
	}

	sb.WriteString("\n# Remote Database (Cloud)\n")
	sb.WriteString(fmt.Sprintf("GAET_REMOTE_URL=%s\n", remoteURL))

	sb.WriteString("\n# Backup\n")
	sb.WriteString(fmt.Sprintf("GAET_RETENTION_DAYS=%s\n", retDays))

	if tablesLine != "" {
		sb.WriteString(fmt.Sprintf("%s\n", tablesLine))
	}
	return sb.String()
}

func availablePresets() string {
	var names []string
	for k := range presets {
		names = append(names, k)
	}
	return strings.Join(names, ", ")
}
