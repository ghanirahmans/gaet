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
	if opts.JSON {
		core.Quiet = true
		core.Plain = true
	}
	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		return err
	}
	tools := core.FindPGTools(env)
	result := runCheckInner(env, tools)
	if opts.JSON {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.Encode(result)
		if !result["ok"].(bool) {
			os.Exit(1)
		}
		return nil
	}
	core.PrintDocsFooter()
	return nil
}

func runCheckInner(env map[string]string, tools core.PGTools) map[string]any {
	result := map[string]any{"ok": true, "checks": map[string]any{}}
	checks := result["checks"].(map[string]any)

	// Tools
	toolsOK := tools.PgDump != "" && tools.PgRestore != "" && tools.Psql != ""
	checks["tools"] = map[string]any{
		"ok": toolsOK, "pg_dump": tools.PgDump,
		"pg_restore": tools.PgRestore, "psql": tools.Psql,
	}
	if !toolsOK {
		result["ok"] = false
		core.StatusFail("PostgreSQL tools not found (pg_dump, pg_restore, psql)")
	} else {
		core.StatusOK("PostgreSQL tools found")
		core.StatusArrow(fmt.Sprintf("pg_dump    %s", tools.PgDump))
		core.StatusArrow(fmt.Sprintf("pg_restore %s", tools.PgRestore))
		core.StatusArrow(fmt.Sprintf("psql       %s", tools.Psql))
	}

	// Local DB
	h, p, u, n, w := core.GetLocalDB(env)
	localOK := false
	if tools.Psql != "" {
		envDB := core.PGEnv(u, w, "")
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"},
			envDB, 5*time.Second)
		localOK = rc == 0 && strings.TrimSpace(out) == "1"
	}
	checks["local_db"] = map[string]any{"ok": localOK, "host": h, "port": p, "user": u, "database": n}
	if localOK {
		core.StatusOK(fmt.Sprintf("Local database %s@%s:%s/%s", u, h, p, n))
	} else {
		result["ok"] = false
		core.StatusFail(fmt.Sprintf("Cannot connect to local database %s:%s/%s", h, p, n))
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
			core.StatusOK(fmt.Sprintf("Cloud database %s@%s/%s", parsed.User, parsed.Host, parsed.DB))
		} else {
			result["ok"] = false
			core.StatusFail(fmt.Sprintf("Cannot connect to cloud database %s@%s/%s", parsed.User, parsed.Host, parsed.DB))
		}
	} else {
		checks["remote_db"] = map[string]any{"configured": false, "reachable": false}
		core.StatusWarn("Cloud database not configured (set GAET_REMOTE_URL)")
	}

	// Backup dir
	backupDir := core.BackupDir()
	_ = core.EnsureDir(backupDir)
	matches, _ := filepath.Glob(filepath.Join(backupDir, "*.dump"))
	checks["backup_dir"] = map[string]any{"ok": true, "count": len(matches)}
	core.StatusOK(fmt.Sprintf("Backup directory: %s (%d snapshots)", backupDir, len(matches)))

	fmt.Println()
	if result["ok"].(bool) {
		core.StatusOK("All checks passed!")
	} else {
		core.StatusWarn("Some checks failed — fix before backup.")
	}
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
		envDB := core.PGEnv(u, w, "")
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
				"SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"},
			envDB, 10*time.Second)
		if rc == 0 {
			core.StatusOK(fmt.Sprintf("%s tables in local database", strings.TrimSpace(out)))
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
		envDB := core.PGEnv(u, w, "")
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"},
			envDB, 5*time.Second)
		localOK = rc == 0 && strings.TrimSpace(out) == "1"
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
func CheckLocalDB(env map[string]string, tools core.PGTools) (h, p, u, n, w string, err error) {
	h, p, u, n, w = core.GetLocalDB(env)
	if tools.Psql == "" {
		err = core.Die("psql not found", core.ExitTools)
		return
	}
	envDB := core.PGEnv(u, w, "")
	out, _, rc := core.RunCmdSimple(tools.Psql,
		[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"},
		envDB, 5*time.Second)
	if rc != 0 || strings.TrimSpace(out) != "1" {
		err = core.Die(fmt.Sprintf("Cannot connect to local database %s:%s/%s", h, p, n), core.ExitLocalDown)
	}
	return
}

func buildStatusJSON(env map[string]string, tools core.PGTools) map[string]any {
	h, p, u, n, w := core.GetLocalDB(env)
	result := map[string]any{"local": map[string]any{"host": h, "port": p, "user": u, "db": n}, "ok": false}
	if tools.Psql != "" {
		envDB := core.PGEnv(u, w, "")
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"},
			envDB, 5*time.Second)
		result["local_ok"] = rc == 0 && strings.TrimSpace(out) == "1"
	}
	return result
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
