// Package serve implements `gaet serve` — embedded web dashboard HTTP server.
package serve

import (
	"embed"
	"fmt"
	"io/fs"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
	"github.com/ghanirahmans/gaet/pkg/snapshots"
)

//go:embed static
var embeddedAssets embed.FS

// ServeOptions holds flags for `gaet serve`.
type ServeOptions struct {
	Host string
	Port int
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

	addr := fmt.Sprintf("%s:%d", opts.Host, opts.Port)
	core.BoxTitle("gaet serve")
	core.StatusOK(fmt.Sprintf("Dashboard starting at http://%s", addr))
	core.StatusArrow("Press Ctrl+C to stop")
	fmt.Println()

	mux := http.NewServeMux()

	// API endpoints
	mux.HandleFunc("/api/status", apiStatus)
	mux.HandleFunc("/api/snapshots", apiSnapshots)
	mux.HandleFunc("/api/logs", apiLogs)

	// Embedded static files — serve from embedded or fallback to dashboard/static/
	staticFS, err := fs.Sub(embeddedAssets, "static")
	if err == nil {
		mux.Handle("/", http.FileServer(http.FS(staticFS)))
	} else {
		// Fallback: serve from dashboard/static/ on disk
		mux.Handle("/", http.FileServer(http.Dir(filepath.Join(core.GaetAppDir(), "dashboard", "static"))))
	}

	srv := &http.Server{
		Addr:         addr,
		Handler:      mux,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
	}
	return srv.ListenAndServe()
}

func apiStatus(w http.ResponseWriter, r *http.Request) {
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

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	fmt.Fprintf(w, `{"local_ok":%v,"host":"%s","port":"%s","user":"%s","db":"%s"}`,
		localOK, h, p, u, n)
}

func apiSnapshots(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	// Reuse snapshots package logic
	backupDir := core.BackupDir()
	matches, _ := filepath.Glob(filepath.Join(backupDir, "*.dump"))
	_ = snapshots.RunSnapshots // ensure import is used
	fmt.Fprintf(w, `{"count":%d,"backup_dir":"%s"}`, len(matches), backupDir)
}

func apiLogs(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	limitStr := r.URL.Query().Get("lines")
	limit := 50
	if n, err := strconv.Atoi(limitStr); err == nil && n > 0 {
		limit = n
	}
	logFile := core.LogFile()
	if data, err := os.ReadFile(logFile); err == nil {
		lines := strings.Split(string(data), "\n")
		start := len(lines) - limit
		if start < 0 {
			start = 0
		}
		fmt.Fprint(w, strings.Join(lines[start:], "\n"))
	} else {
		fmt.Fprint(w, "No log yet.")
	}
}
