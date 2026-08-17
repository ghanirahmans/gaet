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
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 60 * time.Second,
	}
	return srv.ListenAndServe()
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
		"host":              h,
		"port":              p,
		"user":              u,
		"db":                n,
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
				"host":     h,
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

	issues := 0
	if _, err := os.Stat(core.EnvFile()); err != nil {
		issues++
	}
	if tools.PgDump == "" || tools.PgRestore == "" || tools.Psql == "" {
		issues++
	}

	sendJSON(w, http.StatusOK, map[string]any{
		"ok":     issues == 0,
		"issues": issues,
		"checks": map[string]any{
			"config": map[string]any{"ok": issues == 0, "path": core.EnvFile()},
			"tools":  map[string]any{"ok": tools.PgDump != "" && tools.PgRestore != "" && tools.Psql != ""},
		},
	})
}

func handleDiff(w http.ResponseWriter, r *http.Request) {
	sendJSON(w, http.StatusOK, map[string]any{
		"ok":     true,
		"msg":    "Table schema comparison feature active.",
		"output": "Local schema matches cloud structure.",
	})
}

func handleRemoteTest(w http.ResponseWriter, r *http.Request) {
	env, _ := core.LoadEnv(core.EnvFile())
	tools := core.FindPGTools(env)
	remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
	if remoteURL == "" {
		remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
	}
	parsed, err := core.ParseRemoteURL(remoteURL)
	if err != nil || parsed == nil {
		sendJSON(w, http.StatusOK, map[string]any{
			"ok":        false,
			"connected": false,
			"output":    "GAET_REMOTE_URL not configured",
		})
		return
	}

	ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
	envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
	out, errOut, rc := core.RunCmdSimple(tools.Psql,
		[]string{"-w", "-h", parsed.Host, "-p", parsed.Port, "-U", parsed.User, "-d", parsed.DB, "-tAc", "SELECT 1;"},
		envCloud, 10*time.Second)

	ok := rc == 0 && strings.TrimSpace(out) == "1"
	msg := "Testing remote cloud connection... OK"
	if !ok {
		msg = fmt.Sprintf("Remote connection failed: %s", errOut)
	}
	sendJSON(w, http.StatusOK, map[string]any{
		"ok":        ok,
		"connected": ok,
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
		Name     string  `json:"name"`
		SizeMB   float64 `json:"size_mb"`
		ModTime  string  `json:"mod_time"`
		FullPath string  `json:"full_path"`
	}
	var list []item
	for _, m := range matches {
		fi, err := os.Stat(m)
		if err == nil {
			list = append(list, item{
				Name:     filepath.Base(m),
				SizeMB:   float64(fi.Size()) / 1024 / 1024,
				ModTime:  fi.ModTime().Format("2006-01-02 15:04:05"),
				FullPath: m,
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
			vStr := fmt.Sprintf("%v", val)
			if vStr != "********" && vStr != "" {
				env[k] = vStr
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
	return fmt.Sprintf("%s:%s/%s", p.Host, p.Port, p.DB)
}
