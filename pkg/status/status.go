// Package status implements `gaet status`, `gaet check`, and `gaet doctor`.
package status

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// CheckOptions holds flags for `gaet check`.
type CheckOptions struct {
	JSON bool
}

// RunCheck implements `gaet check`.
func RunCheck(opts CheckOptions) error {
	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		return err
	}
	tools := core.FindPGTools(env)

	if opts.JSON {
		// JSON mode: collect result silently, output pure JSON to stdout
		oldQuiet := core.Quiet
		oldPlain := core.Plain
		core.Quiet = true
		core.Plain = true
		result := runCheckInner(env, tools, true)
		core.Quiet = oldQuiet
		core.Plain = oldPlain
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.Encode(result)
		return nil
	}

	core.BoxTitle("gaet check")
	result := runCheckInner(env, tools, false)
	if !result["ok"].(bool) {
		core.PrintDocsFooter()
		return core.Die("", core.ExitGeneral)
	}
	core.PrintDocsFooter()
	return nil
}

func runCheckInner(env map[string]string, tools core.DBTools, silent bool) map[string]any {
	print := func(fn func()) { if !silent { fn() } }
	result := map[string]any{"ok": true, "checks": map[string]any{}}
	checks := result["checks"].(map[string]any)
	var failedChecks []string

	// Tools
	toolsOK := tools.PgDump != "" && tools.PgRestore != "" && tools.Psql != ""
	checks["tools"] = map[string]any{
		"ok": toolsOK, "pg_dump": tools.PgDump,
		"pg_restore": tools.PgRestore, "psql": tools.Psql,
	}
	if !toolsOK {
		result["ok"] = false
		failedChecks = append(failedChecks, "Database client tools (pg_dump, pg_restore, psql)")
		print(func() {
			core.StatusFail("Database client tools not found (pg_dump, pg_restore, psql)")
			core.PrintPGToolsInstructions()
		})
	} else {
		print(func() {
			core.StatusOK("Database client tools found")
			core.StatusArrow(fmt.Sprintf("pg_dump    %s", tools.PgDump))
			core.StatusArrow(fmt.Sprintf("pg_restore %s", tools.PgRestore))
			core.StatusArrow(fmt.Sprintf("psql       %s", tools.Psql))
		})
	}

	// Local DB
	h, p, u, n, w := core.GetLocalDB(env)
	localOK := false
	if tools.Psql != "" {
		_, localOK = testLocalDB(tools.Psql, h, p, u, n, w, "SELECT 1;", 5*time.Second)
	}
	checks["local_db"] = map[string]any{"ok": localOK, "host": core.CleanHost(h), "port": p, "user": u, "database": n}
	if localOK {
		print(func() { core.StatusOK(fmt.Sprintf("Local database %s", core.FormatConnTarget(u, h, p, n))) })
	} else {
		result["ok"] = false
		failedChecks = append(failedChecks, fmt.Sprintf("Local database connection (%s)", core.FormatConnTarget(u, h, p, n)))
		print(func() { core.StatusFail(fmt.Sprintf("Cannot connect to local database %s", core.FormatConnTarget(u, h, p, n))) })
	}

	// Remote DB
	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	parsed, parseErr := core.ParseRemoteURL(remoteURL)
	if parseErr == nil && parsed != nil {
		ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
		envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB, "-tAc", "SELECT 1;"},
			envCloud, 10*time.Second)
		remoteOK := rc == 0 && strings.TrimSpace(out) == "1"
		checks["remote_db"] = map[string]any{"configured": true, "reachable": remoteOK,
			"host": parsed.Host, "port": parsed.Port, "db": parsed.DB}
		if remoteOK {
			print(func() { core.StatusOK(fmt.Sprintf("Cloud database %s@%s/%s", parsed.User, parsed.Host, parsed.DB)) })
		} else {
			result["ok"] = false
			failedChecks = append(failedChecks, fmt.Sprintf("Cloud database connection (%s@%s/%s)", parsed.User, parsed.Host, parsed.DB))
			print(func() {
				core.StatusFail(fmt.Sprintf("Cannot connect to cloud database %s@%s/%s", parsed.User, parsed.Host, parsed.DB))
			})
		}
	} else {
		checks["remote_db"] = map[string]any{"configured": false, "reachable": false}
		print(func() { core.StatusWarn("Cloud database not configured (set GAET_REMOTE_URL)") })
	}

	// Backup dir
	backupDir := core.BackupDir()
	_ = core.EnsureDir(backupDir)
	matches, _ := filepath.Glob(filepath.Join(backupDir, "*.dump"))
	checks["backup_dir"] = map[string]any{"ok": true, "count": len(matches)}
	print(func() {
		core.StatusOK(fmt.Sprintf("Backup directory: %s (%d snapshots)", backupDir, len(matches)))
		fmt.Println()
		if len(failedChecks) == 0 {
			core.StatusOK("All checks passed!")
		} else {
			core.StatusWarn(fmt.Sprintf("Checks failed (%d issue(s) found):", len(failedChecks)))
			for _, item := range failedChecks {
				core.StatusArrow(fmt.Sprintf("Failed: %s", item))
			}
		}
	})
	return result
}


// StatusOptions holds flags for `gaet status`.
type StatusOptions struct {
	JSON bool
}

// RunStatus implements `gaet status`.
func RunStatus(opts StatusOptions) error {
	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		return err
	}
	tools := core.FindPGTools(env)

	if opts.JSON {
		data := buildStatusJSON(env, tools)
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(data)
	}

	h, p, u, n, w := core.GetLocalDB(env)
	core.BoxTitle("gaet status")

	// Last backup
	backupDir := core.BackupDir()
	matches, _ := filepath.Glob(filepath.Join(backupDir, "gaet_*.dump"))
	if len(matches) > 0 {
		newest := latestFile(matches)
		fi, _ := os.Stat(newest)
		mtime := fi.ModTime().Format("2006-01-02 15:04:05")
		sizeMB := float64(fi.Size()) / 1024 / 1024
		core.StatusOK(fmt.Sprintf("Last backup: %s (%.1f MB)", mtime, sizeMB))
	} else {
		core.StatusWarn("No previous backups found")
	}
	allMatches, _ := filepath.Glob(filepath.Join(backupDir, "*.dump"))
	core.StatusArrow(fmt.Sprintf("Total backups: %d", len(allMatches)))
	fmt.Println()

	// Local DB
	core.BoxSection("Local Database")
	if tools.Psql != "" {
		out, ok := testLocalDB(tools.Psql, h, p, u, n, w, "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';", 10*time.Second)
		if ok {
			core.StatusOK(fmt.Sprintf("%s tables in local database", out))
		} else {
			core.StatusWarn("Local database unavailable")
		}
	}

	// Cloud DB
	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	if parsed, err := core.ParseRemoteURL(remoteURL); err == nil {
		fmt.Println()
		core.BoxSection("Cloud Database")
		ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
		envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB, "-tAc",
				"SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"},
			envCloud, 10*time.Second)
		if rc == 0 {
			core.StatusOK(fmt.Sprintf("%s tables in cloud database", strings.TrimSpace(out)))
		} else {
			core.StatusWarn("Cloud database unreachable")
		}
	}

	fmt.Println()
	core.PrintDocsFooter()
	return nil
}

// DiffOptions holds flags for `gaet diff`.
type DiffOptions struct {
	JSON bool
}

// RunDiff implements `gaet diff` — comparing table counts between local DB and cloud DB.
func RunDiff(opts DiffOptions) error {
	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		return err
	}
	tools := core.FindPGTools(env)

	h, p, u, n, w := core.GetLocalDB(env)
	localCount := 0
	localOK := false
	if tools.Psql != "" {
		out, ok := testLocalDB(tools.Psql, h, p, u, n, w, "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';", 10*time.Second)
		if ok {
			localOK = true
			fmt.Sscanf(out, "%d", &localCount)
		}
	}

	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	cloudCount := 0
	cloudOK := false
	parsed, parseErr := core.ParseRemoteURL(remoteURL)
	if parseErr == nil && tools.Psql != "" {
		ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
		envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB, "-tAc",
				"SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"},
			envCloud, 10*time.Second)
		if rc == 0 {
			cloudOK = true
			fmt.Sscanf(strings.TrimSpace(out), "%d", &cloudCount)
		}
	}

	if opts.JSON {
		res := map[string]any{
			"command":  "diff",
			"local_db": map[string]any{"ok": localOK, "table_count": localCount},
			"cloud_db": map[string]any{"ok": cloudOK, "table_count": cloudCount},
		}
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(res)
	}

	core.BoxTitle("gaet diff")
	if localOK {
		core.StatusOK(fmt.Sprintf("Local DB: %d tables (%s@%s:%s/%s)", localCount, u, h, p, n))
	} else {
		core.StatusWarn(fmt.Sprintf("Local DB: unreachable (%s:%s/%s)", h, p, n))
	}

	if cloudOK && parsed != nil {
		core.StatusOK(fmt.Sprintf("Cloud DB: %d tables (%s@%s:%s/%s)", cloudCount, parsed.User, parsed.Host, parsed.Port, parsed.DB))
	} else if parsed != nil {
		core.StatusWarn("Cloud DB: unreachable")
	} else {
		core.StatusWarn("Cloud DB: not configured")
	}

	fmt.Println()
	if localOK && cloudOK {
		diff := localCount - cloudCount
		if diff == 0 {
			core.StatusOK("Local DB and Cloud DB schemas are in sync!")
		} else if diff > 0 {
			core.StatusWarn(fmt.Sprintf("Local DB has %d more table(s) than Cloud DB", diff))
		} else {
			core.StatusWarn(fmt.Sprintf("Cloud DB has %d more table(s) than Local DB", -diff))
		}
	}

	core.PrintDocsFooter()
	return nil
}

// DoctorOptions holds flags for `gaet doctor`.
type DoctorOptions struct {
	JSON bool
}

// RunDoctor implements `gaet doctor`.
func RunDoctor(opts DoctorOptions) error {
	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		return err
	}
	tools := core.FindPGTools(env)

	issues := 0
	result := map[string]any{"checks": map[string]any{}, "ok": true}
	checks := result["checks"].(map[string]any)

	// Config
	envFile := core.EnvFile()
	configOK := fileExists(envFile)
	checks["config"] = map[string]any{"ok": configOK, "path": envFile}
	if !configOK {
		issues++
	}

	// Tools
	toolsOK := tools.PgDump != "" && tools.PgRestore != "" && tools.Psql != ""
	checks["tools"] = map[string]any{"ok": toolsOK, "pg_dump": tools.PgDump, "pg_restore": tools.PgRestore, "psql": tools.Psql}
	if !toolsOK {
		issues++
	}

	// Local DB
	h, p, u, n, w := core.GetLocalDB(env)
	localOK := false
	if tools.Psql != "" {
		_, localOK = testLocalDB(tools.Psql, h, p, u, n, w, "SELECT 1;", 5*time.Second)
	}
	checks["local_db"] = map[string]any{"ok": localOK, "host": h, "port": p, "user": u, "database": n}
	if !localOK {
		issues++
	}

	// Backups
	backupDir := core.BackupDir()
	backups, _ := filepath.Glob(filepath.Join(backupDir, "gaet_*.dump"))
	backupCount := len(backups)
	backupOK := backupCount > 0
	checks["backups"] = map[string]any{"ok": backupOK, "count": backupCount}
	if !backupOK {
		issues++
	}

	result["ok"] = issues == 0
	result["issues"] = issues

	if opts.JSON {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(result)
	}

	core.BoxTitle("gaet doctor")
	core.BoxSection("Config")
	if configOK {
		core.StatusOK(fmt.Sprintf("Config file: %s", envFile))
	} else {
		core.StatusFail("Config file not found — run 'gaet init'")
	}

	core.BoxSection("PostgreSQL Tools")
	for name, path := range map[string]string{"pg_dump": tools.PgDump, "pg_restore": tools.PgRestore, "psql": tools.Psql} {
		if path != "" {
			core.StatusOK(fmt.Sprintf("%s found: %s", name, path))
		} else {
			core.StatusFail(fmt.Sprintf("%s not found", name))
		}
	}

	core.BoxSection("Local Database")
	if localOK {
		core.StatusOK(fmt.Sprintf("Connected to %s@%s:%s/%s", u, h, p, n))
	} else {
		core.StatusFail(fmt.Sprintf("Cannot connect to %s:%s/%s", h, p, n))
	}

	core.BoxSection("Backups")
	if backupOK {
		core.StatusOK(fmt.Sprintf("%d backup(s) found in %s", backupCount, backupDir))
	} else {
		core.StatusWarn("No backups found — run 'gaet push' to create your first backup")
	}

	fmt.Println()
	if issues == 0 {
		core.StatusOK("All checks passed!")
	} else {
		core.StatusWarn(fmt.Sprintf("%d issue(s) found", issues))
	}
	core.PrintDocsFooter()
	return nil
}

// CheckLocalDB verifies local DB connection; returns (host,port,user,db,pass) or error.
func CheckLocalDB(env map[string]string, tools core.DBTools) (h, p, u, n, w string, err error) {
	h, p, u, n, w = core.GetLocalDB(env)
	if tools.Psql == "" {
		err = core.Die("psql not found", core.ExitTools)
		return
	}
	_, localOK := testLocalDB(tools.Psql, h, p, u, n, w, "SELECT 1;", 5*time.Second)
	if !localOK {
		err = core.Die(fmt.Sprintf("Cannot connect to local database %s:%s/%s", h, p, n), core.ExitLocalDown)
	}
	return
}

func buildStatusJSON(env map[string]string, tools core.DBTools) map[string]any {
	h, p, u, n, w := core.GetLocalDB(env)
	result := map[string]any{"local": map[string]any{"host": h, "port": p, "user": u, "db": n}, "ok": false}
	if tools.Psql != "" {
		_, localOK := testLocalDB(tools.Psql, h, p, u, n, w, "SELECT 1;", 5*time.Second)
		result["local_ok"] = localOK
	}
	return result
}

func testLocalDB(psql, host, port, user, db, pass, query string, timeout time.Duration) (string, bool) {
	envDB := core.PGEnv(user, pass, "")
	out, _, rc := core.RunCmdSimple(psql,
		[]string{"-w", "-h", host, "-p", port, "-U", user, "-d", db, "-tAc", query},
		envDB, timeout)
	if rc == 0 {
		return strings.TrimSpace(out), true
	}
	if host == "127.0.0.1" || host == "localhost" || strings.HasPrefix(host, "/") || host == "" {
		fbOut, _, fbRc := core.RunCmdSimple(psql,
			[]string{"-w", "-p", port, "-U", user, "-d", db, "-tAc", query},
			envDB, timeout)
		if fbRc == 0 {
			return strings.TrimSpace(fbOut), true
		}
	}
	return "", false
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func latestFile(files []string) string {
	best := files[0]
	bestMod := time.Time{}
	for _, f := range files {
		fi, err := os.Stat(f)
		if err == nil && fi.ModTime().After(bestMod) {
			best = f
			bestMod = fi.ModTime()
		}
	}
	return best
}
