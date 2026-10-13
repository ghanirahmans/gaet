//go:build e2e

package e2e

import (
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// --- Binary ---

func buildBinary() string {
	root := projectRoot()
	binName := "gaet_e2e"
	if runtime.GOOS == "windows" {
		binName = "gaet_e2e.exe"
	}
	tmpBin := filepath.Join(os.TempDir(), binName)
	cmd := exec.Command("go", "build", "-o", tmpBin, "./cmd/gaet")
	cmd.Dir = root
	if out, err := cmd.CombinedOutput(); err != nil {
		panic(fmt.Sprintf("failed to build gaet binary: %v\n%s", err, out))
	}
	return tmpBin
}

func projectRoot() string {
	wd, err := os.Getwd()
	if err != nil {
		panic(err)
	}
	dir := wd
	for {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			panic("could not find go.mod")
		}
		dir = parent
	}
}

// --- runGaet helper ---

func gaetEnv(t *testing.T, gaetDir string, extra map[string]string) []string {
	t.Helper()
	env := []string{
		"GAET_DIR=" + gaetDir,
		"NO_COLOR=1",
		"GAET_TIMEOUT=120",
		"GAET_REMOTE_SSLMODE=disable",
		"CI=true",
	}
	for k, v := range extra {
		env = append(env, k+"="+v)
	}
	env = append(env, "PATH="+os.Getenv("PATH"))
	return env
}

func runGaet(t *testing.T, gaetDir string, extraEnv map[string]string, args ...string) (stdout, stderr string, exitCode int) {
	t.Helper()
	cmd := exec.Command(binaryPath, args...)
	cmd.Env = gaetEnv(t, gaetDir, extraEnv)
	var outBuf, errBuf strings.Builder
	cmd.Stdout = &outBuf
	cmd.Stderr = &errBuf
	err := cmd.Run()
	exitCode = 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			t.Fatalf("failed to run gaet: %v", err)
		}
	}
	return outBuf.String(), errBuf.String(), exitCode
}

func writeEnvFile(t *testing.T, gaetDir, content string) {
	t.Helper()
	envPath := filepath.Join(gaetDir, ".env")
	if err := os.MkdirAll(gaetDir, 0755); err != nil {
		t.Fatalf("mkdir gaetDir: %v", err)
	}
	if err := os.WriteFile(envPath, []byte(content), 0600); err != nil {
		t.Fatalf("write env file: %v", err)
	}
}

func baseEnvContent(localURL, remoteURL string) string {
	return fmt.Sprintf("# gaet test config\nGAET_LOCAL_URL=%s\nGAET_REMOTE_URL=%s\nGAET_RETENTION_DAYS=7\n", localURL, remoteURL)
}

// --- DB helpers (using psql CLI for zero-dependency) ---

// psqlConnArgs returns psql connection arguments for a DSN.
func psqlConnArgs(dsn string) []string {
	parsed, err := core.ParseRemoteURL(dsn)
	if err != nil {
		return nil
	}
	return []string{
		"-h", parsed.Host,
		"-p", parsed.Port,
		"-U", parsed.User,
		"-d", parsed.DB,
	}
}

// psqlEnv returns the environment for psql, setting PGPASSWORD if present.
func psqlEnv(dsn string) []string {
	parsed, err := core.ParseRemoteURL(dsn)
	if err != nil {
		return []string{"PATH=" + os.Getenv("PATH"), "PGSSLMODE=disable"}
	}
	env := []string{"PATH=" + os.Getenv("PATH"), "PGSSLMODE=disable"}
	if parsed.Password != "" {
		env = append(env, "PGPASSWORD="+parsed.Password)
	}
	return env
}

// dbExec runs SQL on the given DSN via psql.
func dbExec(t *testing.T, dsn, sql string) {
	t.Helper()
	args := append(psqlConnArgs(dsn), "-v", "ON_ERROR_STOP=1", "-c", sql)
	cmd := exec.Command("psql", args...)
	cmd.Env = psqlEnv(dsn)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("psql exec failed: %v\noutput: %s", err, out)
	}
}

// dbQuerySafe runs a query and returns the trimmed stdout, not failing on empty results.
func dbQuerySafe(t *testing.T, dsn, sql string) string {
	t.Helper()
	args := append(psqlConnArgs(dsn), "-v", "ON_ERROR_STOP=1", "-tA", "-c", sql)
	cmd := exec.Command("psql", args...)
	cmd.Env = psqlEnv(dsn)
	out, _ := cmd.Output()
	return strings.TrimSpace(string(out))
}

// dbQuery runs a query and returns the trimmed stdout.
func dbQuery(t *testing.T, dsn, sql string) string {
	t.Helper()
	args := append(psqlConnArgs(dsn), "-v", "ON_ERROR_STOP=1", "-tA", "-c", sql)
	cmd := exec.Command("psql", args...)
	cmd.Env = psqlEnv(dsn)
	out, err := cmd.Output()
	if err != nil {
		t.Fatalf("psql query failed: %v\noutput: %s", err, out)
	}
	return strings.TrimSpace(string(out))
}

// dbQueryInt runs a query expected to return a single integer.
func dbQueryInt(t *testing.T, dsn, sql string) int {
	t.Helper()
	out := dbQuery(t, dsn, sql)
	var n int
	fmt.Sscanf(out, "%d", &n)
	return n
}

func seedDB(t *testing.T, dsn string) {
	t.Helper()
	seedPath := filepath.Join(projectRoot(), "sandbox", "seed-data.sql")
	data, err := os.ReadFile(seedPath)
	if err != nil {
		t.Fatalf("read seed-data.sql: %v", err)
	}
	dbExec(t, dsn, string(data))
}

// cleanupDB drops all test tables from the schema using the sandbox SQL script.
func cleanupDB(t *testing.T, dsn string) {
	t.Helper()
	// Dynamically discover and drop all tables (handles schema drift / extra tables)
	out := dbQuerySafe(t, dsn, `SELECT string_agg('"' || tablename || '"', ', ' ORDER BY tablename) FROM pg_tables WHERE schemaname='public'`)
	if out != "" && out != "0" && out != "NULL" {
		dbExec(t, dsn, "DROP TABLE IF EXISTS " + out + " CASCADE;")
	}
}

// resetDBs drops all tables from both DBs and reseeds from sandbox/seed-data.sql.
func resetDBs(t *testing.T) {
	t.Helper()
	cleanupDB(t, testRemoteURL)
	cleanupDB(t, testLocalURL)
	seedDB(t, testRemoteURL)
	seedDB(t, testLocalURL)
}

// resetDBsClean drops all tables and does NOT reseed — for tests that need empty DBs.
func resetDBsClean(t *testing.T) {
	t.Helper()
	cleanupDB(t, testRemoteURL)
	cleanupDB(t, testLocalURL)
}

// assertRowCounts verifies table row counts against expectedCounts on the given DSN.
func assertRowCounts(t *testing.T, dsn string) {
	t.Helper()
	for table, expected := range expectedCounts {
		got := dbQueryInt(t, dsn, fmt.Sprintf("SELECT count(*) FROM %s", table))
		if got != expected {
			t.Errorf("table %s: expected %d rows, got %d", table, expected, got)
		}
	}
}

func getTableRowCount(t *testing.T, dsn, table string) int {
	t.Helper()
	return dbQueryInt(t, dsn, fmt.Sprintf("SELECT count(*) FROM %s", table))
}

func tableExists(t *testing.T, dsn, table string) bool {
	t.Helper()
	result := dbQuery(t, dsn, fmt.Sprintf("SELECT to_regclass('%s') IS NOT NULL", table))
	return result == "t" || result == "true"
}

func listTables(t *testing.T, dsn string) []string {
	t.Helper()
	out := dbQuerySafe(t, dsn, "SELECT string_agg(tablename, ',' ORDER BY tablename) FROM pg_tables WHERE schemaname='public'")
	if out == "" || out == "0" {
		return nil
	}
	parts := strings.Split(out, ",")
	var tables []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			tables = append(tables, p)
		}
	}
	return tables
}

// waitForDB polls a DSN until psql can connect or timeout.
func waitForDB(dsn string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		cmd := exec.Command("psql")
		cmd.Env = psqlEnv(dsn)
		args := append(psqlConnArgs(dsn), "-tAc", "SELECT 1;")
		cmd.Args = append(cmd.Args, args...)
		if out, err := cmd.CombinedOutput(); err == nil {
			if strings.TrimSpace(string(out)) == "1" {
				return nil
			}
		}
		time.Sleep(500 * time.Millisecond)
	}
	return fmt.Errorf("timeout waiting for DB at %s", dsn)
}

// toolShim creates a temporary script that always exits with code 1,
// simulating a failing database tool. Returns the path to use for
// GAET_PG_DUMP / GAET_PG_RESTORE / GAET_PSQL env vars.
func toolShim(t *testing.T, name string, exitCode int) string {
	t.Helper()
	shimPath := filepath.Join(t.TempDir(), name)
	script := fmt.Sprintf("#!/bin/sh\nexit %d\n", exitCode)
	if err := os.WriteFile(shimPath, []byte(script), 0755); err != nil {
		t.Fatalf("write tool shim: %v", err)
	}
	return shimPath
}

// toolShimScript creates a script that echoes given stderr and exits nonzero.
func toolShimScript(t *testing.T, name, stderrMsg string, exitCode int) string {
	t.Helper()
	shimPath := filepath.Join(t.TempDir(), name)
	content := fmt.Sprintf("#!/bin/sh\necho '%s' >&2\nexit %d\n", stderrMsg, exitCode)
	if err := os.WriteFile(shimPath, []byte(content), 0755); err != nil {
		t.Fatalf("write tool shim: %v", err)
	}
	return shimPath
}

// pollJob polls /api/jobs/{id} until finished or timeout.
func pollJob(t *testing.T, baseURL, jobID string) map[string]any {
	t.Helper()
	deadline := time.Now().Add(30 * time.Second)
	for time.Now().Before(deadline) {
		resp, err := http.Get(baseURL + "/api/jobs/" + jobID)
		if err != nil {
			t.Fatalf("poll job: %v", err)
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var data map[string]any
		if err := json.Unmarshal(body, &data); err != nil {
			t.Fatalf("unmarshal job: %v\nbody: %s", err, body)
		}
		job, ok := data["job"].(map[string]any)
		if !ok {
			t.Fatalf("job field not found in response: %v", data)
		}
		status, ok := job["status"].(string)
		if !ok {
			t.Fatalf("status field not found: %v", job)
		}
		if status == "success" || status == "failed" {
			return data
		}
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatal("job did not finish within 30s")
	return nil
}

// ensureDBAvailable skips the test if no DB is available (in local mode).
func ensureDBAvailable(t *testing.T) {
	t.Helper()
	if !dbAvailable {
		t.Skip("no Postgres available (set E2E_LOCAL_URL/E2E_REMOTE_URL or run with Docker)")
	}
}

// verifyDump checks a .dump file via pg_restore --list.
func verifyDump(path string) error {
	cmd := exec.Command("pg_restore", "--list", path)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("%w: %s", err, out)
	}
	return nil
}

// setupTestEnv creates a fresh gaetDir with .env and returns the dir.
func setupTestEnv(t *testing.T) string {
	t.Helper()
	gaetDir := t.TempDir()
	writeEnvFile(t, gaetDir, baseEnvContent(testLocalURL, testRemoteURL))
	return gaetDir
}

// withResetDBs is a wrapper that resets DBs before and after a test.
func withResetDBs(t *testing.T) {
	t.Helper()
	ensureDBAvailable(t)
	resetDBs(t)
}

// startServe starts the gaet binary's `serve` subcommand on a free port
// and returns the base URL. It handles cleanup on test completion.
func startServe(t *testing.T, gaetDir string) string {
	t.Helper()
	// Find a free port
	port := freePort()
	cmd := exec.Command(binaryPath, "serve", "--port", fmt.Sprintf("%d", port), "--host", "127.0.0.1", "--no-open")
	cmd.Env = gaetEnv(t, gaetDir, nil)
	if err := cmd.Start(); err != nil {
		t.Fatalf("start serve: %v", err)
	}
	t.Cleanup(func() {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
	})

	baseURL := fmt.Sprintf("http://127.0.0.1:%d", port)

	// Wait for the server to be ready
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		resp, err := http.Get(baseURL + "/api/status")
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return baseURL
			}
		}
		time.Sleep(200 * time.Millisecond)
	}
	t.Fatal("serve did not start within 10s")
	return baseURL
}

// freePort returns a random free port number.
func freePort() int {
	// Listen on port 0 to get a free port, then close and return it.
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		// Fallback to a fixed port
		return 16161
	}
	defer l.Close()
	return l.Addr().(*net.TCPAddr).Port
}
