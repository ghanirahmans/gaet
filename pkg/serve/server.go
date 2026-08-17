// Package serve implements `gaet serve` — pure Go embedded web dashboard HTTP server.
package serve

import (
	"embed"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/ghanirahmans/gaet/pkg/backup"
	"github.com/ghanirahmans/gaet/pkg/core"
	"github.com/ghanirahmans/gaet/pkg/detect"
	"github.com/ghanirahmans/gaet/pkg/scheduler"
)

//go:embed static/*
var embeddedAssets embed.FS

// ServeOptions holds flags for `gaet serve`.
type ServeOptions struct {
	Host   string
	Port   int
	NoOpen bool
	Auto   bool
	Stop   bool
}

// RunServe starts the embedded web dashboard HTTP server.
func RunServe(opts ServeOptions) error {
	if opts.Host == "" {
		opts.Host = core.DefDashboardHost
	}
	if opts.Port == 0 {
		env, _ := core.LoadEnv(core.EnvFile())
		opts.Port = core.GetEnvInt(env, "GAET_DASHBOARD_PORT", core.DefDashboardPort)
	}

	if opts.Stop {
		env, _ := core.LoadEnv(core.EnvFile())
		prefix := core.GetEnvStr(env, "GAET_SERVICE_PREFIX", core.DefServicePrefix)
		return scheduler.DisableServeAuto(prefix)
	}

	addr := fmt.Sprintf("%s:%d", opts.Host, opts.Port)
	url := fmt.Sprintf("http://%s", addr)

	if opts.Auto {
		env, _ := core.LoadEnv(core.EnvFile())
		prefix := core.GetEnvStr(env, "GAET_SERVICE_PREFIX", core.DefServicePrefix)
		return scheduler.EnableServeAuto(prefix, opts.Host, opts.Port, "")
	}

	core.BoxTitle("gaet serve")
	core.StatusOK(fmt.Sprintf("Dashboard active at %s", url))
	core.StatusArrow("Press Ctrl+C to stop dashboard server")
	fmt.Println()

	if !opts.NoOpen && !core.IsPlain() && !core.Quiet {
		go func() {
			time.Sleep(200 * time.Millisecond)
			core.OpenBrowser(url)
		}()
	}

	mux := http.NewServeMux()

	// ── REST API Router ──────────────────────────────────────────────────
	mux.HandleFunc("/api/status", handleStatus)
	mux.HandleFunc("/api/check", handleCheck)
	mux.HandleFunc("/api/doctor", handleDoctor)
	mux.HandleFunc("/api/diff", handleDiff)
	mux.HandleFunc("/api/local/test", handleLocalTest)
	mux.HandleFunc("/api/remote/test", handleRemoteTest)
	mux.HandleFunc("/api/export", handleExport)
	mux.HandleFunc("/api/detect", handleDetect)
	mux.HandleFunc("/api/snapshots", handleSnapshots)
	mux.HandleFunc("/api/snapshots/download", handleSnapshotDownload)
	mux.HandleFunc("/api/snapshots/delete", handleSnapshotDelete)
	mux.HandleFunc("/api/logs", handleLogs)
	mux.HandleFunc("/api/config", handleConfig)
	mux.HandleFunc("/api/push", handlePush)
	mux.HandleFunc("/api/fetch", handleFetch)
	mux.HandleFunc("/api/restore", handleRestore)
	mux.HandleFunc("/api/stop", handleStop)

	// ── Static Assets (Embedded) ─────────────────────────────────────────
	staticFS, err := fs.Sub(embeddedAssets, "static")
	if err == nil {
		fileServer := http.FileServer(http.FS(staticFS))
		mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
			if strings.HasPrefix(r.URL.Path, "/api/") {
				http.NotFound(w, r)
				return
			}
			fileServer.ServeHTTP(w, r)
		})
	} else {
		// Fallback to disk if embedded FS fails
		mux.Handle("/", http.FileServer(http.Dir(filepath.Join(core.GaetAppDir(), "dashboard", "static"))))
	}

	srv := &http.Server{
		Addr:         addr,
		Handler:      corsMiddleware(mux),
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 60 * time.Second,
	}
	return srv.ListenAndServe()
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// ── Handler Implementations ──────────────────────────────────────────────

func handleStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		sendJSON(w, http.StatusMethodNotAllowed, map[string]any{"error": "Method not allowed"})
		return
	}
	env, _ := core.LoadEnv(core.EnvFile())
	tools := core.FindPGTools(env)
	h, p, u, n, ww := core.GetLocalDB(env)

	localOK := false
	if tools.Psql != "" {
		envDB := core.PGEnv(u, ww, "")
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"},
			envDB, 5*time.Second)
		localOK = rc == 0 && strings.TrimSpace(out) == "1"
	}

	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	parsed, _ := core.ParseRemoteURL(remoteURL)
	remoteConfigured := parsed != nil

	sendJSON(w, http.StatusOK, map[string]any{
		"local_ok":          localOK,
		"host":              core.CleanHost(h),
		"port":              p,
		"user":              u,
		"db":                n,
		"has_pass":          ww != "",
		"remote_configured": remoteConfigured,
		"remote_host":       fmtRemoteHost(parsed),
		"env_file":          core.EnvFile(),
	})
}

func handleCheck(w http.ResponseWriter, r *http.Request) {
	env, _ := core.LoadEnv(core.EnvFile())
	tools := core.FindPGTools(env)

	// Collect checks quietly
	oldQuiet := core.Quiet
	core.Quiet = true
	h, p, u, n, wPass := core.GetLocalDB(env)
	localOK := false
	if tools.Psql != "" {
		envDB := core.PGEnv(u, wPass, "")
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"},
			envDB, 5*time.Second)
		localOK = rc == 0 && strings.TrimSpace(out) == "1"
	}
	core.Quiet = oldQuiet

	matches, _ := filepath.Glob(filepath.Join(core.BackupDir(), "*.dump"))
	sendJSON(w, http.StatusOK, map[string]any{
		"ok": localOK,
		"checks": map[string]any{
			"tools": map[string]any{
				"ok":         tools.PgDump != "" && tools.PgRestore != "" && tools.Psql != "",
				"pg_dump":    tools.PgDump,
				"pg_restore": tools.PgRestore,
				"psql":       tools.Psql,
			},
			"local_db": map[string]any{
				"ok":       localOK,
				"host":     core.CleanHost(h),
				"port":     p,
				"user":     u,
				"database": n,
			},
			"backup_dir": map[string]any{
				"ok":    true,
				"count": len(matches),
			},
		},
	})
}

func handleDoctor(w http.ResponseWriter, r *http.Request) {
	env, _ := core.LoadEnv(core.EnvFile())
	tools := core.FindPGTools(env)
	h, p, u, n, wPass := core.GetLocalDB(env)

	var sb strings.Builder
	sb.WriteString("Gaet Diagnostic Health Report\n")
	sb.WriteString(strings.Repeat("─", 50) + "\n\n")

	issues := 0

	// 1. Environment Config
	if _, err := os.Stat(core.EnvFile()); err == nil {
		sb.WriteString(fmt.Sprintf("[ OK ] Configuration file : %s\n", core.EnvFile()))
	} else {
		issues++
		sb.WriteString(fmt.Sprintf("[FAIL] Configuration file : %s (Missing)\n", core.EnvFile()))
	}

	// 2. PostgreSQL Binaries
	if tools.PgDump != "" && tools.PgRestore != "" && tools.Psql != "" {
		sb.WriteString("[ OK ] PostgreSQL binaries  : Found (pg_dump, pg_restore, psql)\n")
		sb.WriteString(fmt.Sprintf("       - psql       : %s\n", tools.Psql))
		sb.WriteString(fmt.Sprintf("       - pg_dump    : %s\n", tools.PgDump))
		sb.WriteString(fmt.Sprintf("       - pg_restore : %s\n", tools.PgRestore))
	} else {
		issues++
		sb.WriteString("[FAIL] PostgreSQL binaries  : Missing pg_dump/pg_restore/psql\n")
	}

	// 3. Local PostgreSQL DB
	localOK := false
	if tools.Psql != "" {
		envDB := core.PGEnv(u, wPass, "")
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"},
			envDB, 5*time.Second)
		localOK = rc == 0 && strings.TrimSpace(out) == "1"
		if !localOK && (h == "127.0.0.1" || h == "localhost" || strings.HasPrefix(h, "/") || h == "") {
			fbOut, _, fbRc := core.RunCmdSimple(tools.Psql,
				[]string{"-w", "-p", p, "-U", u, "-d", n, "-tAc", "SELECT 1;"},
				envDB, 5*time.Second)
			localOK = fbRc == 0 && strings.TrimSpace(fbOut) == "1"
		}
	}
	cleanLocal := core.FormatConnTarget(u, h, p, n)
	if localOK {
		sb.WriteString(fmt.Sprintf("[ OK ] Local Database      : %s (Reachable)\n", cleanLocal))
	} else {
		issues++
		sb.WriteString(fmt.Sprintf("[FAIL] Local Database      : %s (Connection Refused)\n", cleanLocal))
	}

	// 4. Remote Cloud DB
	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	if parsed, err := core.ParseRemoteURL(remoteURL); err == nil && parsed != nil {
		ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
		envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
		out, _, rc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB, "-tAc", "SELECT 1;"},
			envCloud, 5*time.Second)
		cleanRemote := core.FormatConnTarget(parsed.User, parsed.Host, parsed.Port, parsed.DB)
		if rc == 0 && strings.TrimSpace(out) == "1" {
			sb.WriteString(fmt.Sprintf("[ OK ] Cloud Target DB     : %s (Reachable)\n", cleanRemote))
		} else {
			issues++
			sb.WriteString(fmt.Sprintf("[FAIL] Cloud Target DB     : %s (Connection Refused)\n", cleanRemote))
		}
	} else {
		sb.WriteString("[WARN] Cloud Target DB     : Unconfigured (Set GAET_REMOTE_URL in Settings)\n")
	}

	// 5. Backup Directory
	backupDir := core.BackupDir()
	matches, _ := filepath.Glob(filepath.Join(backupDir, "*.dump"))
	sb.WriteString(fmt.Sprintf("[ OK ] Backup Storage Vault: %s (%d snapshot dumps)\n", backupDir, len(matches)))

	sb.WriteString("\n" + strings.Repeat("─", 50) + "\n")
	if issues == 0 {
		sb.WriteString("[ OK ] All diagnostic checks passed cleanly with zero errors!\n")
	} else {
		sb.WriteString(fmt.Sprintf("[WARN] Diagnostic completed with %d issue(s) detected.\n", issues))
	}

	sendJSON(w, http.StatusOK, map[string]any{
		"ok":     issues == 0,
		"issues": issues,
		"output": sb.String(),
	})
}

func handleDiff(w http.ResponseWriter, r *http.Request) {
	env, _ := core.LoadEnv(core.EnvFile())
	tools := core.FindPGTools(env)
	h, p, u, n, wPass := core.GetLocalDB(env)

	var sb strings.Builder
	sb.WriteString("Gaet Schema & Table Diff Analysis\n")
	sb.WriteString(strings.Repeat("─", 58) + "\n\n")

	cleanLocal := core.FormatConnTarget(u, h, p, n)
	sb.WriteString(fmt.Sprintf("Local DB  : %s\n", cleanLocal))

	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	parsed, _ := core.ParseRemoteURL(remoteURL)
	if parsed == nil {
		sb.WriteString("Cloud DB  : Unconfigured\n\n")
		sb.WriteString("[WARN] Cannot run schema diff: GAET_REMOTE_URL is not configured.\n")
		sb.WriteString("       Please configure your Remote Database connection in Settings.\n")
		sendJSON(w, http.StatusOK, map[string]any{"ok": false, "output": sb.String()})
		return
	}

	cleanRemote := core.FormatConnTarget(parsed.User, parsed.Host, parsed.Port, parsed.DB)
	sb.WriteString(fmt.Sprintf("Cloud DB  : %s\n\n", cleanRemote))

	if tools.Psql == "" {
		sb.WriteString("[FAIL] PostgreSQL psql binary not found.\n")
		sendJSON(w, http.StatusOK, map[string]any{"ok": false, "output": sb.String()})
		return
	}

	// Query local table list
	envLocal := core.PGEnv(u, wPass, "")
	outLocal, _, rcLocal := core.RunCmdSimple(tools.Psql,
		[]string{"-w", "-h", h, "-p", p, "-U", u, "-d", n, "-tAc",
			"SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"},
		envLocal, 8*time.Second)
	if rcLocal != 0 && (h == "127.0.0.1" || h == "localhost" || strings.HasPrefix(h, "/") || h == "") {
		fbOut, _, fbRc := core.RunCmdSimple(tools.Psql,
			[]string{"-w", "-p", p, "-U", u, "-d", n, "-tAc",
				"SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"},
			envLocal, 8*time.Second)
		if fbRc == 0 {
			rcLocal = 0
			outLocal = fbOut
		}
	}

	// Query remote table list
	ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
	envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
	outRemote, _, rcRemote := core.RunCmdSimple(tools.Psql,
		[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB, "-tAc",
			"SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"},
		envCloud, 8*time.Second)

	if rcLocal != 0 {
		sb.WriteString("[FAIL] Failed to query local database tables.\n")
		sendJSON(w, http.StatusOK, map[string]any{"ok": false, "output": sb.String()})
		return
	}
	if rcRemote != 0 {
		sb.WriteString("[FAIL] Failed to query cloud database tables.\n")
		sendJSON(w, http.StatusOK, map[string]any{"ok": false, "output": sb.String()})
		return
	}

	localTables := filterEmptyLines(strings.Split(strings.TrimSpace(outLocal), "\n"))
	remoteTables := filterEmptyLines(strings.Split(strings.TrimSpace(outRemote), "\n"))

	localMap := make(map[string]bool)
	for _, t := range localTables {
		localMap[t] = true
	}
	remoteMap := make(map[string]bool)
	for _, t := range remoteTables {
		remoteMap[t] = true
	}

	allTables := make(map[string]bool)
	for _, t := range localTables {
		allTables[t] = true
	}
	for _, t := range remoteTables {
		allTables[t] = true
	}

	if len(allTables) == 0 {
		sb.WriteString("[NOTE] No public tables found in local or remote database.\n")
		sendJSON(w, http.StatusOK, map[string]any{"ok": true, "output": sb.String()})
		return
	}

	sb.WriteString(fmt.Sprintf("%-28s %-12s %-12s %s\n", "Table Name", "Local", "Cloud", "Sync Status"))
	sb.WriteString(strings.Repeat("─", 58) + "\n")

	diffCount := 0
	for t := range allTables {
		inLocal := localMap[t]
		inRemote := remoteMap[t]
		locStr := "EXISTS"
		if !inLocal {
			locStr = "MISSING"
		}
		remStr := "EXISTS"
		if !inRemote {
			remStr = "MISSING"
		}

		status := "[ OK ] Synced"
		if !inLocal || !inRemote {
			status = "[ WARN ] Diff"
			diffCount++
		}
		sb.WriteString(fmt.Sprintf("%-28s %-12s %-12s %s\n", t, locStr, remStr, status))
	}

	sb.WriteString(strings.Repeat("─", 58) + "\n")
	if diffCount == 0 {
		sb.WriteString(fmt.Sprintf("[ OK ] All %d tables are perfectly synchronized!\n", len(localTables)))
	} else {
		sb.WriteString(fmt.Sprintf("[WARN] Detected %d schema difference(s) between Local & Cloud DB.\n", diffCount))
	}

	sendJSON(w, http.StatusOK, map[string]any{"ok": diffCount == 0, "output": sb.String()})
}

func filterEmptyLines(lines []string) []string {
	var res []string
	for _, l := range lines {
		t := strings.TrimSpace(l)
		if t != "" {
			res = append(res, t)
		}
	}
	return res
}

func handleLocalTest(w http.ResponseWriter, r *http.Request) {
	env, _ := core.LoadEnv(core.EnvFile())
	tools := core.FindPGTools(env)
	body := readJSONBody(r)

	h, p, u, n, wPass := core.GetLocalDB(env)

	localURL := ""
	if reqUrl, ok := body["url"].(string); ok && reqUrl != "" {
		localURL = reqUrl
	} else if reqUrl, ok := body["local_url"].(string); ok && reqUrl != "" {
		localURL = reqUrl
	}

	if localURL != "" {
		if parsed, err := core.ParseRemoteURL(localURL); err == nil && parsed != nil {
			h = parsed.Host
			p = parsed.Port
			u = parsed.User
			n = parsed.DB
			if parsed.Password != "" {
				wPass = parsed.Password
			}
		}
	}

	envLocal := core.PGEnv(u, wPass, "")
	args := []string{"-w", "-d", n, "-tAc", "SELECT 1;"}
	if h != "" {
		args = append([]string{"-h", h, "-p", p, "-U", u}, args...)
	}
	out, errOut, rc := core.RunCmdSimple(tools.Psql, args, envLocal, 8*time.Second)

	// Fallback to local Unix socket auth if TCP fails
	if rc != 0 && (h == "127.0.0.1" || h == "localhost" || strings.HasPrefix(h, "/") || h == "") {
		fbArgs := []string{"-w", "-d", n, "-tAc", "SELECT 1;"}
		if p != "" {
			fbArgs = append([]string{"-p", p, "-U", u}, fbArgs...)
		}
		fbOut, fbErr, fbRc := core.RunCmdSimple(tools.Psql, fbArgs, envLocal, 5*time.Second)
		if fbRc == 0 && strings.TrimSpace(fbOut) == "1" {
			rc = 0
			out = fbOut
			errOut = ""
		} else if fbErr != "" {
			errOut = fbErr
		}
	}

	ok := rc == 0 && strings.TrimSpace(out) == "1"
	cleanTarget := core.FormatConnTarget(u, h, p, n)
	msg := fmt.Sprintf("Local PostgreSQL ping successful! (%s)", cleanTarget)
	if !ok {
		cleanErr := strings.TrimSpace(errOut)
		if strings.Contains(cleanErr, "no password supplied") {
			cleanErr += " (Hint: Password required for TCP auth, or check PostgreSQL authentication setup)"
		}
		msg = fmt.Sprintf("Local connection failed: %s", cleanErr)
		if msg == "Local connection failed: " {
			msg = "Local connection failed. Verify PostgreSQL is running."
		}
	}
	sendJSON(w, http.StatusOK, map[string]any{
		"ok":        ok,
		"connected": ok,
		"msg":       msg,
		"output":    msg,
	})
}

func handleRemoteTest(w http.ResponseWriter, r *http.Request) {
	env, _ := core.LoadEnv(core.EnvFile())
	tools := core.FindPGTools(env)
	body := readJSONBody(r)

	remoteURL := ""
	if u, ok := body["url"].(string); ok && u != "" {
		remoteURL = u
	} else if u, ok := body["remote_url"].(string); ok && u != "" {
		remoteURL = u
	} else {
		remoteURL = core.GetEnvStr(env, "GAET_REMOTE_URL", "")
		if remoteURL == "" {
			remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
		}
	}

	ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
	if s, ok := body["sslmode"].(string); ok && s != "" {
		ssl = s
	}

	parsed, err := core.ParseRemoteURL(remoteURL)
	if err != nil || parsed == nil {
		sendJSON(w, http.StatusOK, map[string]any{
			"ok":        false,
			"connected": false,
			"msg":       "Invalid or empty remote cloud URL",
		})
		return
	}

	envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
	out, errOut, rc := core.RunCmdSimple(tools.Psql,
		[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB, "-tAc", "SELECT 1;"},
		envCloud, 10*time.Second)

	ok := rc == 0 && strings.TrimSpace(out) == "1"
	cleanTarget := core.FormatConnTarget(parsed.User, parsed.Host, parsed.Port, parsed.DB)
	msg := fmt.Sprintf("Remote cloud database ping successful! (%s)", cleanTarget)
	if !ok {
		msg = fmt.Sprintf("Remote connection failed: %s", strings.TrimSpace(errOut))
	}
	sendJSON(w, http.StatusOK, map[string]any{
		"ok":        ok,
		"connected": ok,
		"msg":       msg,
		"output":    msg,
	})
}

func handleExport(w http.ResponseWriter, r *http.Request) {
	env, _ := core.LoadEnv(core.EnvFile())
	var sb strings.Builder
	for k, v := range env {
		sb.WriteString(fmt.Sprintf("export %s=%q\n", k, v))
	}
	sendJSON(w, http.StatusOK, map[string]any{
		"ok":       true,
		"env_vars": sb.String(),
	})
}

func handleDetect(w http.ResponseWriter, r *http.Request) {
	env, _ := core.LoadEnv(core.EnvFile())
	tools := core.FindPGTools(env)
	instances := detect.DetectLocalPG(tools.Psql)
	sendJSON(w, http.StatusOK, map[string]any{
		"ok":        true,
		"instances": instances,
	})
}

func handleSnapshots(w http.ResponseWriter, r *http.Request) {
	backupDir := core.BackupDir()
	matches, _ := filepath.Glob(filepath.Join(backupDir, "*.dump"))

	type item struct {
		Name      string  `json:"name"`
		Filename  string  `json:"filename"`
		SizeMB    float64 `json:"size_mb"`
		ModTime   string  `json:"mod_time"`
		CreatedAt string  `json:"created_at"`
		FullPath  string  `json:"full_path"`
	}
	var list []item
	for _, m := range matches {
		fi, err := os.Stat(m)
		if err == nil {
			fn := filepath.Base(m)
			mt := fi.ModTime().Format("2006-01-02 15:04:05")
			list = append(list, item{
				Name:      fn,
				Filename:  fn,
				SizeMB:    float64(fi.Size()) / 1024 / 1024,
				ModTime:   mt,
				CreatedAt: mt,
				FullPath:  m,
			})
		}
	}
	sendJSON(w, http.StatusOK, map[string]any{
		"count":      len(list),
		"snapshots":  list,
		"backup_dir": backupDir,
	})
}

func handleSnapshotDownload(w http.ResponseWriter, r *http.Request) {
	filename := r.URL.Query().Get("file")
	if filename == "" || strings.Contains(filename, "..") || strings.Contains(filename, "/") || strings.Contains(filename, "\\") {
		sendJSON(w, http.StatusBadRequest, map[string]any{"error": "Invalid filename requested"})
		return
	}
	filePath := filepath.Join(core.BackupDir(), filename)
	fi, err := os.Stat(filePath)
	if err != nil {
		sendJSON(w, http.StatusNotFound, map[string]any{"error": fmt.Sprintf("Snapshot '%s' not found", filename)})
		return
	}

	w.Header().Set("Content-Type", "application/octet-stream")
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s"`, filename))
	w.Header().Set("Content-Length", fmt.Sprintf("%d", fi.Size()))

	f, openErr := os.Open(filePath)
	if openErr != nil {
		sendJSON(w, http.StatusInternalServerError, map[string]any{"error": openErr.Error()})
		return
	}
	defer f.Close()
	_, _ = io.Copy(w, f)
}

func handleSnapshotDelete(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		sendJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "msg": "Method not allowed"})
		return
	}
	filename := r.URL.Query().Get("file")
	if filename == "" {
		body := readJSONBody(r)
		if f, ok := body["filename"].(string); ok {
			filename = f
		} else if f, ok := body["file"].(string); ok {
			filename = f
		}
	}

	if filename == "" || strings.Contains(filename, "..") || strings.Contains(filename, "/") || strings.Contains(filename, "\\") {
		sendJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "msg": "Invalid filename requested"})
		return
	}

	filePath := filepath.Join(core.BackupDir(), filename)
	if err := os.Remove(filePath); err != nil {
		sendJSON(w, http.StatusNotFound, map[string]any{"ok": false, "msg": fmt.Sprintf("Failed to delete snapshot: %v", err)})
		return
	}
	sendJSON(w, http.StatusOK, map[string]any{"ok": true, "msg": fmt.Sprintf("Snapshot '%s' deleted successfully.", filename)})
}

func handleLogs(w http.ResponseWriter, r *http.Request) {
	limitStr := r.URL.Query().Get("lines")
	limit := 100
	if n, err := strconv.Atoi(limitStr); err == nil && n > 0 {
		limit = n
	}

	var logLines []string
	for _, fName := range []string{"cron.log", "gaet.log"} {
		fPath := filepath.Join(core.BackupDir(), fName)
		if data, err := os.ReadFile(fPath); err == nil {
			lines := strings.Split(string(data), "\n")
			for _, line := range lines {
				if strings.TrimSpace(line) != "" {
					logLines = append(logLines, line)
				}
			}
		}
	}

	start := len(logLines) - limit
	if start < 0 {
		start = 0
	}
	resLines := logLines[start:]
	if len(resLines) == 0 {
		resLines = []string{"No log entries found."}
	}
	sendJSON(w, http.StatusOK, map[string]any{"logs": resLines})
}

func handleConfig(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		env, _ := core.LoadEnv(core.EnvFile())
		masked := make(map[string]string)
		for k, v := range env {
			if strings.Contains(k, "PASS") || strings.Contains(k, "SECRET") || strings.Contains(k, "URL") {
				masked[k] = core.MaskURLPassword(v)
			} else {
				masked[k] = v
			}
		}
		sendJSON(w, http.StatusOK, map[string]any{
			"config":        env,
			"masked_config": masked,
			"env_file":      core.EnvFile(),
		})

	case http.MethodPost:
		body := readJSONBody(r)
		cfgMap, ok := body["config"].(map[string]any)
		if !ok || len(cfgMap) == 0 {
			sendJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "msg": "No configuration parameters provided"})
			return
		}

		env, _ := core.LoadEnv(core.EnvFile())
		for k, val := range cfgMap {
			vStr := strings.TrimSpace(fmt.Sprintf("%v", val))
			if vStr == "********" || strings.Contains(vStr, "****") || strings.Contains(vStr, "***") {
				continue
			}
			if vStr == "" {
				delete(env, k)
				_ = os.Unsetenv(k)
			} else {
				env[k] = vStr
				_ = os.Setenv(k, vStr)
			}
		}

		// Also extract GAET_LOCAL_URL into process env if present
		if localURL, ok := env["GAET_LOCAL_URL"]; ok && localURL != "" {
			if p, err := core.ParseRemoteURL(localURL); err == nil {
				if p.Host != "" { env["GAET_LOCAL_DB_HOST"] = p.Host; _ = os.Setenv("GAET_LOCAL_DB_HOST", p.Host) }
				if p.Port != "" { env["GAET_LOCAL_DB_PORT"] = p.Port; _ = os.Setenv("GAET_LOCAL_DB_PORT", p.Port) }
				if p.User != "" { env["GAET_LOCAL_DB_USER"] = p.User; _ = os.Setenv("GAET_LOCAL_DB_USER", p.User) }
				if p.DB != "" { env["GAET_LOCAL_DB_NAME"] = p.DB; _ = os.Setenv("GAET_LOCAL_DB_NAME", p.DB) }
				if p.Password != "" { env["GAET_LOCAL_DB_PASS"] = p.Password; _ = os.Setenv("GAET_LOCAL_DB_PASS", p.Password) }
			}
		}

		var lines []string
		lines = append(lines, "# gaet configuration\n")
		for k, v := range env {
			lines = append(lines, fmt.Sprintf("%s=%s\n", k, v))
		}
		_ = core.EnsureDir(core.GaetDir())
		if err := os.WriteFile(core.EnvFile(), []byte(strings.Join(lines, "")), 0600); err != nil {
			sendJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "msg": fmt.Sprintf("Failed to save configuration: %v", err)})
			return
		}
		sendJSON(w, http.StatusOK, map[string]any{"ok": true, "msg": "Configuration updated successfully!"})

	default:
		sendJSON(w, http.StatusMethodNotAllowed, map[string]any{"error": "Method not allowed"})
	}
}

func handlePush(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		sendJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "msg": "Method not allowed"})
		return
	}
	body := readJSONBody(r)
	dryRun, _ := body["dry_run"].(bool)

	err := backup.RunPush(backup.PushOptions{DryRun: dryRun})
	if err != nil {
		sendJSON(w, http.StatusOK, map[string]any{"ok": false, "msg": fmt.Sprintf("Push failed: %v", err)})
		return
	}
	sendJSON(w, http.StatusOK, map[string]any{"ok": true, "msg": "Cloud push completed successfully!"})
}

func handleFetch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		sendJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "msg": "Method not allowed"})
		return
	}
	err := backup.RunFetch(backup.FetchOptions{Yes: true})
	if err != nil {
		sendJSON(w, http.StatusOK, map[string]any{"ok": false, "msg": fmt.Sprintf("Fetch failed: %v", err)})
		return
	}
	sendJSON(w, http.StatusOK, map[string]any{"ok": true, "msg": "Cloud fetch completed successfully!"})
}

func handleRestore(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		sendJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "msg": "Method not allowed"})
		return
	}
	body := readJSONBody(r)
	target := "latest"
	if f, ok := body["filename"].(string); ok && f != "" {
		target = f
	} else if f, ok := body["file"].(string); ok && f != "" {
		target = f
	}

	err := backup.RunRestore(backup.RestoreOptions{Target: target, Yes: true})
	if err != nil {
		sendJSON(w, http.StatusOK, map[string]any{"ok": false, "msg": fmt.Sprintf("Restore failed: %v", err)})
		return
	}
	sendJSON(w, http.StatusOK, map[string]any{"ok": true, "msg": fmt.Sprintf("Restored from '%s' successfully!", target)})
}

func handleStop(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		sendJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "msg": "Method not allowed"})
		return
	}
	env, _ := core.LoadEnv(core.EnvFile())
	prefix := core.GetEnvStr(env, "GAET_SERVICE_PREFIX", core.DefServicePrefix)
	err := scheduler.DisableAuto(prefix)
	if err != nil {
		sendJSON(w, http.StatusOK, map[string]any{"ok": false, "msg": fmt.Sprintf("Failed to stop scheduler: %v", err)})
		return
	}
	sendJSON(w, http.StatusOK, map[string]any{"ok": true, "msg": "Auto-backup scheduler stopped successfully!"})
}

// ── Helpers ──────────────────────────────────────────────────────────────

func sendJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func readJSONBody(r *http.Request) map[string]any {
	result := make(map[string]any)
	if r.Body == nil {
		return result
	}
	defer r.Body.Close()
	data, err := io.ReadAll(r.Body)
	if err != nil || len(data) == 0 {
		return result
	}
	_ = json.Unmarshal(data, &result)
	return result
}

func fmtRemoteHost(p *core.PGConnInfo) string {
	if p == nil {
		return ""
	}
	host := p.Host
	if strings.HasPrefix(host, "/") {
		host = "127.0.0.1"
	}
	user := p.User
	if user == "" {
		user = "postgres"
	}
	if p.Password != "" {
		return fmt.Sprintf("%s:••••••@%s:%s/%s", user, host, p.Port, p.DB)
	}
	return fmt.Sprintf("%s@%s:%s/%s", user, host, p.Port, p.DB)
}
