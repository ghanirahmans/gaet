package core

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
)

// PGTools holds paths to pg_dump, pg_restore, psql.
type PGTools struct {
	PgDump    string
	PgRestore string
	Psql      string
}

// FindPGTools locates pg_dump, pg_restore, psql.
// Priority: env vars > pg0 install > PATH > platform-specific dirs.
func FindPGTools(env map[string]string) PGTools {
	t := PGTools{
		PgDump:    GetEnvStr(env, "GAET_PG_DUMP", ""),
		PgRestore: GetEnvStr(env, "GAET_PG_RESTORE", ""),
		Psql:      GetEnvStr(env, "GAET_PSQL", ""),
	}

	if t.PgDump != "" && t.PgRestore != "" && t.Psql != "" {
		return t
	}

	home, _ := os.UserHomeDir()

	// pg0 discovery (Linux/macOS — hindsight setup)
	pg0Base := filepath.Join(home, ".pg0", "installation")
	if fi, err := os.Stat(pg0Base); err == nil && fi.IsDir() {
		if entries, err := os.ReadDir(pg0Base); err == nil {
			// Sort versions descending
			var versions []string
			for _, e := range entries {
				if e.IsDir() {
					versions = append(versions, e.Name())
				}
			}
			sort.Sort(sort.Reverse(sort.StringSlice(versions)))
			if len(versions) > 0 {
				binDir := filepath.Join(pg0Base, versions[0], "bin")
				tryFill(&t, binDir, "")
			}
		}
	}

	// PATH
	if t.PgDump == "" {
		t.PgDump, _ = which("pg_dump")
	}
	if t.PgRestore == "" {
		t.PgRestore, _ = which("pg_restore")
	}
	if t.Psql == "" {
		t.Psql, _ = which("psql")
	}

	// Windows common paths
	if runtime.GOOS == "windows" {
		for _, root := range []string{
			`C:\Program Files\PostgreSQL`,
			`C:\Program Files (x86)\PostgreSQL`,
		} {
			entries, err := os.ReadDir(root)
			if err != nil {
				continue
			}
			var versions []string
			for _, e := range entries {
				if e.IsDir() {
					versions = append(versions, e.Name())
				}
			}
			sort.Sort(sort.Reverse(sort.StringSlice(versions)))
			if len(versions) > 0 {
				binDir := filepath.Join(root, versions[0], "bin")
				tryFill(&t, binDir, ".exe")
				break
			}
		}
	}

	// macOS Homebrew / Postgres.app
	if runtime.GOOS == "darwin" {
		for _, d := range []string{
			"/opt/homebrew/bin",
			"/usr/local/bin",
			"/opt/homebrew/opt/libpq/bin",
			"/usr/local/opt/libpq/bin",
		} {
			tryFill(&t, d, "")
		}
		// Postgres.app versions
		appBase := "/Applications/Postgres.app/Contents/Versions"
		if entries, err := os.ReadDir(appBase); err == nil {
			var vers []string
			for _, e := range entries {
				if e.IsDir() {
					vers = append(vers, e.Name())
				}
			}
			sort.Sort(sort.Reverse(sort.StringSlice(vers)))
			for _, v := range vers {
				tryFill(&t, filepath.Join(appBase, v, "bin"), "")
			}
		}
	}

	return t
}

// GetLocalDB returns local DB connection params.
// Priority: GAET_LOCAL_URL -> GAET_LOCAL_DB_* overrides -> defaults.
func GetLocalDB(env map[string]string) (host, port, user, db, pass string) {
	// First check GAET_LOCAL_URL if present
	if urlVal := GetEnvStr(env, "GAET_LOCAL_URL", ""); urlVal != "" {
		if p, err := ParseRemoteURL(urlVal); err == nil {
			host = p.Host
			port = p.Port
			user = p.User
			db   = p.DB
			pass = p.Password
		}
	}

	// Individual GAET_LOCAL_DB_* vars override if non-empty
	if h := GetEnvStr(env, "GAET_LOCAL_DB_HOST", ""); h != "" { host = h }
	if p := GetEnvStr(env, "GAET_LOCAL_DB_PORT", ""); p != "" { port = p }
	if u := GetEnvStr(env, "GAET_LOCAL_DB_USER", ""); u != "" { user = u }
	if d := GetEnvStr(env, "GAET_LOCAL_DB_NAME", ""); d != "" { db = d }
	if w := GetEnvStr(env, "GAET_LOCAL_DB_PASS", ""); w != "" { pass = w }

	// Fallback to PGPASSWORD / GAET_LOCAL_PASS if pass is still empty
	if pass == "" {
		if p := GetEnvStr(env, "GAET_LOCAL_PASS", ""); p != "" {
			pass = p
		} else if p := GetEnvStr(env, "PGPASSWORD", ""); p != "" {
			pass = p
		}
	}

	// Defaults if still empty
	if host == "" { host = DefLocalHost }
	if port == "" { port = DefLocalPort }
	if user == "" { user = DefLocalUser }
	if db   == "" { db   = DefLocalDB }

	return
}

// tryFill fills missing tool paths from a directory.
func tryFill(t *PGTools, dir, ext string) {
	if t.PgDump == "" {
		if p := filepath.Join(dir, "pg_dump"+ext); fileExists(p) {
			t.PgDump = p
		}
	}
	if t.PgRestore == "" {
		if p := filepath.Join(dir, "pg_restore"+ext); fileExists(p) {
			t.PgRestore = p
		}
	}
	if t.Psql == "" {
		if p := filepath.Join(dir, "psql"+ext); fileExists(p) {
			t.Psql = p
		}
	}
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func which(name string) (string, bool) {
	p, err := exec.LookPath(name)
	if err != nil {
		return "", false
	}
	return p, true
}

// FindSocketPaths scans common Unix socket directories for .s.PGSQL.* files.
func FindSocketPaths() []string {
	home, _ := os.UserHomeDir()
	dirs := []string{
		"/run/postgresql",
		"/var/run/postgresql",
		"/tmp",
		"/private/tmp",
		filepath.Join(home, ".pg0", "sockets"),
	}
	var paths []string
	for _, d := range dirs {
		entries, err := os.ReadDir(d)
		if err != nil {
			continue
		}
		for _, e := range entries {
			name := e.Name()
			if strings.HasPrefix(name, ".s.PGSQL.") && !strings.HasSuffix(name, ".lock") {
				paths = append(paths, filepath.Join(d, name))
			}
		}
	}
	return paths
}

// SocketPort extracts the port from a .s.PGSQL.<port> socket filename.
func SocketPort(sockPath string) string {
	name := filepath.Base(sockPath)
	if strings.HasPrefix(name, ".s.PGSQL.") {
		port := name[len(".s.PGSQL."):]
		allDigit := true
		for _, c := range port {
			if c < '0' || c > '9' {
				allDigit = false
				break
			}
		}
		if allDigit && port != "" {
			return port
		}
	}
	return "5432"
}
