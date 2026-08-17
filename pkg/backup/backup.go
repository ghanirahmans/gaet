// Package backup implements `gaet push`, `gaet fetch`, and `gaet restore`.
package backup

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// PushOptions holds flags for `gaet push`.
type PushOptions struct {
	DryRun bool
	JSON   bool
	Notify string
}

// RunPush implements `gaet push`.
func RunPush(opts PushOptions) error {
	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		return err
	}
	tools := core.FindPGTools(env)
	h, p, u, n, w := core.GetLocalDB(env)
	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	parsed, _ := core.ParseRemoteURL(remoteURL)
	timeout := time.Duration(core.GetEnvInt(env, "GAET_PG_TIMEOUT", core.DefPGTimeout)) * time.Second

	if opts.DryRun {
		core.BoxTitle("gaet push --dry-run")
		core.BoxSection("Simulation Details")
		core.StatusArrow(fmt.Sprintf("Source: %s", core.FormatConnTarget(u, h, p, n)))
		if parsed != nil {
			core.StatusArrow(fmt.Sprintf("Target: %s", core.FormatConnTarget(parsed.User, parsed.Host, parsed.Port, parsed.DB)))
		} else {
			core.StatusWarn("Target: Cloud not configured")
		}
		core.StatusArrow(fmt.Sprintf("Retention: %d days", core.GetEnvInt(env, "GAET_RETENTION_DAYS", core.DefRetentionDays)))
		core.Echo("")
		core.StatusInfo("Dry-run mode: no changes will be made")
		return nil
	}

	if tools.PgDump == "" || tools.PgRestore == "" || tools.Psql == "" {
		return core.Die("PostgreSQL tools (pg_dump, pg_restore, psql) not found. Install postgresql-client.", core.ExitTools)
	}
	if parsed == nil {
		return core.Die("GAET_REMOTE_URL not configured. Run: gaet init", core.ExitConfig)
	}

	lock, lErr := core.AcquireLock()
	if lErr != nil {
		return core.Die(lErr.Error(), core.ExitLocked)
	}
	defer lock.Release()

	core.WriteJSONLog(core.LogEntry{
		Level:    "INFO",
		Category: "BACKUP",
		Action:   "PUSH",
		Status:   "STARTED",
		Message:  fmt.Sprintf("Push started: %s", core.FormatConnTarget(u, h, p, n)),
		Details:  map[string]interface{}{"host": core.CleanHost(h), "port": p, "database": n},
	})
	core.BoxTitle("gaet push")

	backupDir := core.BackupDir()
	_ = core.EnsureDir(backupDir)
	timestamp := time.Now().Format("20060102_150405")
	backupFile := filepath.Join(backupDir, "gaet_"+timestamp+".dump")

	core.StatusInfo(fmt.Sprintf("Dumping local database %s...", core.FormatConnTarget(u, h, p, n)))
	envLocal := core.PGEnv(u, w, "")
	_, errOut, rc := core.RunCmdSimple(tools.PgDump,
		[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n,
			"--format=custom", "--compress=9", "--file=" + backupFile},
		envLocal, timeout)
	if (rc != 0 || !fileExists(backupFile)) && (h == "127.0.0.1" || h == "localhost" || strings.HasPrefix(h, "/")) {
		fbArgs := []string{"-w", "-p", p, "-U", u, "-d", n,
			"--format=custom", "--compress=9", "--file=" + backupFile}
		_, fbErrOut, fbRc := core.RunCmdSimple(tools.PgDump, fbArgs, envLocal, timeout)
		if fbRc == 0 && fileExists(backupFile) {
			rc = 0
			errOut = ""
		} else if fbErrOut != "" {
			errOut = fbErrOut
		}
	}
	if rc != 0 || !fileExists(backupFile) {
		os.Remove(backupFile)
		return core.Die(fmt.Sprintf("Local dump failed: %s", errOut), core.ExitLocalDown)
	}

	fi, _ := os.Stat(backupFile)
	sizeMB := float64(fi.Size()) / 1024 / 1024
	core.StatusOK(fmt.Sprintf("Dump saved (%.1f MB)", sizeMB))

	_, _, rcCheck := core.RunCmdSimple(tools.PgRestore, []string{"--list", backupFile}, nil, 30*time.Second)
	if rcCheck != 0 {
		os.Remove(backupFile)
		return core.Die("Dump integrity check failed", core.ExitGeneral)
	}

	ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
	core.StatusInfo(fmt.Sprintf("Syncing to cloud %s...", core.FormatConnTarget(parsed.User, parsed.Host, parsed.Port, parsed.DB)))

	if ok, errMsg := resetTargetObjects(tools.Psql, parsed.Host, parsed.Port, parsed.User, parsed.DB, parsed.Password, ssl); !ok {
		return core.Die(fmt.Sprintf("Failed to clean cloud database: %s", errMsg), core.ExitCloudDown)
	}

	envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
	_, errOut3, rc3 := core.RunCmdSimple(tools.PgRestore,
		[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB,
			"--no-owner", "--no-acl", backupFile},
		envCloud, timeout)

	if rc3 != 0 {
		return core.Die(fmt.Sprintf("Cloud sync failed (rc=%d): %s", rc3, lastNLines(errOut3, 3)), core.ExitCloudDown)
	}
	core.StatusOK("Synchronization complete!")
	applyRetention(env, backupDir)
	cleanTarget := core.FormatConnTarget(parsed.User, parsed.Host, parsed.Port, parsed.DB)
	core.StatusOK(fmt.Sprintf("Push complete — %.1f MB synced to %s", sizeMB, cleanTarget))
	core.WriteJSONLog(core.LogEntry{
		Level:    "INFO",
		Category: "BACKUP",
		Action:   "PUSH",
		Status:   "SUCCESS",
		Message:  fmt.Sprintf("Push complete — %.1f MB synced to %s", sizeMB, cleanTarget),
		Details:  map[string]interface{}{"size_mb": sizeMB, "snapshot": filepath.Base(backupFile)},
	})

	if opts.JSON {
		return jsonPrint(map[string]any{"command": "push", "ok": true, "size_mb": sizeMB})
	}
	return nil
}

// FetchOptions holds flags for `gaet fetch`.
type FetchOptions struct {
	DryRun bool
	JSON   bool
	Yes    bool
}

// RunFetch implements `gaet fetch`.
func RunFetch(opts FetchOptions) error {
	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		return err
	}
	tools := core.FindPGTools(env)
	h, p, u, n, w := core.GetLocalDB(env)
	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	parsed, _ := core.ParseRemoteURL(remoteURL)
	timeout := time.Duration(core.GetEnvInt(env, "GAET_PG_TIMEOUT", core.DefPGTimeout)) * time.Second

	if opts.DryRun {
		core.BoxTitle("gaet fetch --dry-run")
		if parsed != nil {
			core.StatusArrow(fmt.Sprintf("Cloud: %s", core.FormatConnTarget(parsed.User, parsed.Host, parsed.Port, parsed.DB)))
		} else {
			core.StatusWarn("Cloud: not configured")
		}
		core.StatusArrow(fmt.Sprintf("Local: %s", core.FormatConnTarget(u, h, p, n)))
		core.StatusInfo("Dry-run: no changes will be made")
		return nil
	}

	if tools.PgDump == "" || tools.PgRestore == "" || tools.Psql == "" {
		return core.Die("PostgreSQL tools not found.", core.ExitTools)
	}
	if parsed == nil {
		return core.Die("GAET_REMOTE_URL not configured. Run: gaet init", core.ExitConfig)
	}
	if !opts.Yes {
		if !core.IsStdinTTY() {
			return core.Die("gaet fetch in non-interactive mode requires --yes flag", core.ExitConfig)
		}
		core.StatusWarn(fmt.Sprintf("WARNING: This will OVERWRITE local database '%s'!", core.FormatConnTarget(u, h, p, n)))
		ans := core.SafeInput("  Type 'yes' to proceed: ", "")
		if strings.ToLower(strings.TrimSpace(ans)) != "yes" {
			core.Echo("  Fetch cancelled.")
			return nil
		}
	}

	lock, lErr := core.AcquireLock()
	if lErr != nil {
		return core.Die(lErr.Error(), core.ExitLocked)
	}
	defer lock.Release()

	core.WriteJSONLog(core.LogEntry{
		Level:    "INFO",
		Category: "BACKUP",
		Action:   "FETCH",
		Status:   "STARTED",
		Message:  fmt.Sprintf("Fetch started: cloud -> local DB '%s'", n),
	})
	core.BoxTitle("gaet fetch")
	ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
	backupDir := core.BackupDir()
	_ = core.EnsureDir(backupDir)
	fetchFile := filepath.Join(backupDir, "cloud_"+time.Now().Format("20060102_150405")+".dump")

	core.StatusInfo("Dumping cloud database...")
	envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
	_, errOut, rc := core.RunCmdSimple(tools.PgDump,
		[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB,
			"--format=custom", "--compress=9", "--file=" + fetchFile},
		envCloud, timeout)
	if rc != 0 || !fileExists(fetchFile) {
		os.Remove(fetchFile)
		return core.Die(fmt.Sprintf("Cloud dump failed: %s", errOut), core.ExitCloudDown)
	}
	fi, _ := os.Stat(fetchFile)
	core.StatusOK(fmt.Sprintf("Cloud dump saved (%.1f MB)", float64(fi.Size())/1024/1024))

	if ok, errMsg := resetTargetObjects(tools.Psql, h, p, u, n, w, ""); !ok {
		return core.Die(fmt.Sprintf("Failed to clean local database: %s", errMsg), core.ExitLocalDown)
	}

	core.StatusInfo("Restoring to local database...")
	envLocal := core.PGEnv(u, w, "")
	_, errOut3, rc3 := core.RunCmdSimple(tools.PgRestore,
		[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, fetchFile},
		envLocal, timeout)
	if rc3 != 0 && (h == "127.0.0.1" || h == "localhost" || strings.HasPrefix(h, "/")) {
		fbArgs := []string{"-w", "-p", p, "-U", u, "-d", n, fetchFile}
		_, fbErrOut3, fbRc3 := core.RunCmdSimple(tools.PgRestore, fbArgs, envLocal, timeout)
		if fbRc3 == 0 {
			rc3 = 0
			errOut3 = ""
		} else if fbErrOut3 != "" {
			errOut3 = fbErrOut3
		}
	}
	os.Remove(fetchFile)

	if rc3 != 0 {
		return core.Die(fmt.Sprintf("Local restore failed (rc=%d): %s", rc3, lastNLines(errOut3, 3)), core.ExitLocalDown)
	}
	core.StatusOK(fmt.Sprintf("Fetch complete — local database '%s' updated", n))
	core.WriteJSONLog(core.LogEntry{
		Level:    "INFO",
		Category: "BACKUP",
		Action:   "FETCH",
		Status:   "SUCCESS",
		Message:  fmt.Sprintf("Fetch complete — local database '%s' updated", n),
		Details:  map[string]interface{}{"database": n},
	})
	return nil
}

// RestoreOptions holds flags for `gaet restore`.
type RestoreOptions struct {
	Target string
	DryRun bool
	JSON   bool
	Yes    bool
}

// RunRestore implements `gaet restore`.
func RunRestore(opts RestoreOptions) error {
	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		return err
	}
	tools := core.FindPGTools(env)
	if tools.PgRestore == "" || tools.Psql == "" {
		return core.Die("PostgreSQL tools not found.", core.ExitTools)
	}

	backupDir := core.BackupDir()
	dumps, _ := globDumps(backupDir)
	if len(dumps) == 0 {
		return core.Die(fmt.Sprintf("No snapshots found in %s. Run 'gaet push' first.", backupDir), core.ExitGeneral)
	}

	target := opts.Target
	if target == "" || strings.ToLower(target) == "latest" || strings.ToLower(target) == "last" {
		target = dumps[0]
	} else {
		found := ""
		for _, d := range dumps {
			if filepath.Base(d) == target || strings.Contains(filepath.Base(d), target) {
				found = d
				break
			}
		}
		if found == "" && fileExists(target) {
			found = target
		}
		if found == "" {
			return core.Die(fmt.Sprintf("Snapshot '%s' not found in %s", target, backupDir), core.ExitGeneral)
		}
		target = found
	}

	fi, err := os.Stat(target)
	if err != nil {
		return core.Die(fmt.Sprintf("Cannot stat snapshot: %v", err), core.ExitGeneral)
	}
	sizeMB := float64(fi.Size()) / 1024 / 1024
	h, p, u, n, w := core.GetLocalDB(env)
	timeout := time.Duration(core.GetEnvInt(env, "GAET_PG_TIMEOUT", core.DefPGTimeout)) * time.Second

	if opts.DryRun {
		core.BoxTitle("gaet restore --dry-run")
		core.StatusArrow(fmt.Sprintf("Snapshot: %s", filepath.Base(target)))
		core.StatusArrow(fmt.Sprintf("Size:     %.1f MB", sizeMB))
		core.StatusArrow(fmt.Sprintf("Target:   %s@%s:%s/%s", u, h, p, n))
		core.Echo("")
		core.StatusInfo("Dry-run mode: no changes will be made")
		return nil
	}

	if !opts.Yes {
		if !core.IsStdinTTY() {
			return core.Die("'gaet restore' in non-interactive mode requires --yes flag", core.ExitConfig)
		}
		core.BoxTitle("gaet restore")
		core.StatusWarn(fmt.Sprintf("DESTRUCTIVE: All tables in '%s' will be DROPPED!", n))
		core.StatusArrow(fmt.Sprintf("Snapshot: %s (%.1f MB)", filepath.Base(target), sizeMB))
		core.StatusArrow(fmt.Sprintf("Target DB: %s@%s:%s/%s", u, h, p, n))
		ans := core.SafeInput("  Type 'yes' to proceed: ", "")
		if strings.ToLower(strings.TrimSpace(ans)) != "yes" {
			core.Echo("  Restore cancelled.")
			return nil
		}
	}

	lock, lErr := core.AcquireLock()
	if lErr != nil {
		return core.Die(lErr.Error(), core.ExitLocked)
	}
	defer lock.Release()

	core.BoxTitle("gaet restore")
	core.WriteJSONLog(core.LogEntry{
		Level:    "INFO",
		Category: "BACKUP",
		Action:   "RESTORE",
		Status:   "STARTED",
		Message:  fmt.Sprintf("Restore started from %s", filepath.Base(target)),
		Details:  map[string]interface{}{"target": filepath.Base(target), "database": n},
	})
	core.StatusInfo("Verifying snapshot integrity...")
	_, _, rcCheck := core.RunCmdSimple(tools.PgRestore, []string{"--list", target}, nil, 30*time.Second)
	if rcCheck != 0 {
		return core.Die(fmt.Sprintf("Snapshot '%s' is corrupt", filepath.Base(target)), core.ExitConfig)
	}
	core.StatusOK("Snapshot integrity valid")

	if ok, errMsg := resetTargetObjects(tools.Psql, h, p, u, n, w, ""); !ok {
		return core.Die(fmt.Sprintf("Failed to reset local database: %s", errMsg), core.ExitGeneral)
	}

	core.StatusInfo("Restoring database from snapshot...")
	envLocal := core.PGEnv(u, w, "")
	_, errOut, rc := core.RunCmdSimple(tools.PgRestore,
		[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, target},
		envLocal, timeout)
	if rc != 0 && (h == "127.0.0.1" || h == "localhost" || strings.HasPrefix(h, "/")) {
		fbArgs := []string{"-w", "-p", p, "-U", u, "-d", n, target}
		_, fbErrOut, fbRc := core.RunCmdSimple(tools.PgRestore, fbArgs, envLocal, timeout)
		if fbRc == 0 {
			rc = 0
			errOut = ""
		} else if fbErrOut != "" {
			errOut = fbErrOut
		}
	}

	if rc != 0 {
		return core.Die(fmt.Sprintf("Restore failed (rc=%d): %s", rc, lastNLines(errOut, 3)), core.ExitGeneral)
	}
	core.StatusOK("Snapshot restore complete!")
	core.Echo("")
	core.BoxSection("Restore Summary")
	core.StatusOK(fmt.Sprintf("Database '%s' restored from %s", n, filepath.Base(target)))
	core.WriteJSONLog(core.LogEntry{
		Level:    "INFO",
		Category: "BACKUP",
		Action:   "RESTORE",
		Status:   "SUCCESS",
		Message:  fmt.Sprintf("Restore complete from %s", filepath.Base(target)),
		Details:  map[string]interface{}{"target": filepath.Base(target), "database": n},
	})
	return nil
}

// RunPushCron is the cron-mode push (logs to cron.log only).
func RunPushCron() error {
	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		core.AppendCronLog(fmt.Sprintf("[cron] Cannot load env: %v", err))
		return err
	}
	tools := core.FindPGTools(env)
	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	parsed, err := core.ParseRemoteURL(remoteURL)
	if err != nil {
		core.AppendCronLog("[cron] GAET_REMOTE_URL is not configured")
		return fmt.Errorf("remote URL not configured")
	}
	h, p, u, n, w := core.GetLocalDB(env)
	ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
	timeout := time.Duration(core.GetEnvInt(env, "GAET_PG_TIMEOUT", core.DefPGTimeout)) * time.Second

	lock, lErr := core.AcquireLock()
	if lErr != nil {
		core.AppendCronLog(fmt.Sprintf("[cron] Lock failed: %v", lErr))
		return lErr
	}
	defer lock.Release()

	backupDir := core.BackupDir()
	_ = core.EnsureDir(backupDir)
	cronFile := filepath.Join(backupDir, "cron_"+time.Now().Format("20060102_150405")+".dump")
	core.AppendCronLog("[cron] Starting auto-backup...")

	envLocal := core.PGEnv(u, w, "")
	_, _, rc := core.RunCmdSimple(tools.PgDump,
		[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n,
			"--format=custom", "--compress=9", "--file=" + cronFile},
		envLocal, timeout)
	if (rc != 0 || !fileExists(cronFile)) && w == "" {
		fbArgs := []string{"-w", "-p", p, "-U", u, "-d", n,
			"--format=custom", "--compress=9", "--file=" + cronFile}
		_, _, fbRc := core.RunCmdSimple(tools.PgDump, fbArgs, envLocal, timeout)
		if fbRc == 0 && fileExists(cronFile) {
			rc = 0
		}
	}
	if rc != 0 || !fileExists(cronFile) {
		os.Remove(cronFile)
		core.AppendCronLog("[cron] Local dump failed!")
		return fmt.Errorf("dump failed")
	}
	_, _, rcCheck := core.RunCmdSimple(tools.PgRestore, []string{"--list", cronFile}, nil, 30*time.Second)
	if rcCheck != 0 {
		os.Remove(cronFile)
		core.AppendCronLog("[cron] Corrupted dump")
		return fmt.Errorf("dump corrupted")
	}
	envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
	_, _, rc2 := core.RunCmdSimple(tools.PgRestore,
		[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB,
			"--clean", "--if-exists", "--no-owner", "--no-acl", cronFile},
		envCloud, timeout)
	fi, _ := os.Stat(cronFile)
	os.Remove(cronFile)
	if rc2 == 0 {
		core.AppendCronLog(fmt.Sprintf("[cron] Backup success (%.1f MB)", float64(fi.Size())/1024/1024))
	} else {
		core.AppendCronLog("[cron] Restore issue encountered")
	}
	return nil
}

// ─── helpers ───────────────────────────────────────────────────────────────

func resetTargetObjects(psql, host, port, user, db, passwd, sslMode string) (bool, string) {
	sql := "DO $$ DECLARE r record; BEGIN " +
		"FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname='public') " +
		"LOOP EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename); END LOOP; " +
		"FOR r IN (SELECT viewname FROM pg_views WHERE schemaname='public') " +
		"LOOP EXECUTE format('DROP VIEW IF EXISTS public.%I CASCADE', r.viewname); END LOOP; " +
		"FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public') " +
		"LOOP EXECUTE format('DROP SEQUENCE IF EXISTS public.%I CASCADE', r.sequence_name); END LOOP; " +
		"END $$;"
	env := core.PGEnv(user, passwd, sslMode)
	_, errOut, rc := core.RunCmdSimple(psql,
		[]string{"-w", "-h", host, "-p", port, "-U", user, "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql},
		env, 30*time.Second)
	if rc != 0 && (host == "127.0.0.1" || host == "localhost" || strings.HasPrefix(host, "/")) {
		_, fbErrOut, fbRc := core.RunCmdSimple(psql,
			[]string{"-w", "-p", port, "-U", user, "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql},
			env, 30*time.Second)
		if fbRc == 0 {
			return true, ""
		}
		if fbErrOut != "" {
			errOut = fbErrOut
		}
	}
	if rc != 0 {
		return false, errOut
	}
	return true, ""
}

func applyRetention(env map[string]string, backupDir string) {
	days := core.GetEnvInt(env, "GAET_RETENTION_DAYS", core.DefRetentionDays)
	cutoff := time.Now().AddDate(0, 0, -days)
	for _, pattern := range []string{"gaet_*.dump", "cron_*.dump", "cloud_*.dump"} {
		matches, _ := filepath.Glob(filepath.Join(backupDir, pattern))
		for _, f := range matches {
			fi, err := os.Stat(f)
			if err == nil && fi.ModTime().Before(cutoff) {
				os.Remove(f)
			}
		}
	}
}

func globDumps(dir string) ([]string, error) {
	matches, err := filepath.Glob(filepath.Join(dir, "*.dump"))
	if err != nil {
		return nil, err
	}
	type dump struct {
		path    string
		modTime time.Time
	}
	var list []dump
	for _, m := range matches {
		fi, err := os.Stat(m)
		if err == nil {
			list = append(list, dump{m, fi.ModTime()})
		}
	}
	for i := 0; i < len(list)-1; i++ {
		for j := i + 1; j < len(list); j++ {
			if list[j].modTime.After(list[i].modTime) {
				list[i], list[j] = list[j], list[i]
			}
		}
	}
	result := make([]string, len(list))
	for i, d := range list {
		result[i] = d.path
	}
	return result, nil
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func lastNLines(s string, n int) string {
	lines := strings.Split(strings.TrimSpace(s), "\n")
	if len(lines) <= n {
		return strings.TrimSpace(s)
	}
	return strings.Join(lines[len(lines)-n:], "\n")
}

func jsonPrint(v any) error {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	return enc.Encode(v)
}
