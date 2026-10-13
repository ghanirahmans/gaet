//go:build e2e

package e2e

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"
)

var (
	testLocalURL  string
	testRemoteURL string
	binaryPath    string
	dbAvailable   bool
)

// expectedCounts holds the canonical row counts from seed-data.sql.
var expectedCounts = map[string]int{
	"users":         1000,
	"products":      500,
	"orders":        3000,
	"payments":      3000,
	"order_items":   6000,
	"audit_log":     2000,
	"system_config": 5,
}

func TestMain(m *testing.M) {
	tdb, ok := bootstrapDB()
	dbAvailable = ok
	if ok {
		testLocalURL = tdb.localURL
		testRemoteURL = tdb.remoteURL
		if tdb.stopFn != nil {
			defer tdb.stopFn()
		}
		binaryPath = buildBinary()
	}
	code := m.Run()
	os.Exit(code)
}

// testDB holds resolved DB URLs and optional cleanup.
type testDB struct {
	localURL  string
	remoteURL string
	stopFn    func()
}

type dbURLs struct {
	local  string
	remote string
}

// bootstrapDB resolves test DB URLs or starts a Docker Postgres container.
func bootstrapDB() (*testDB, bool) {
	// Service mode: CI provides E2E_LOCAL_URL + E2E_REMOTE_URL
	if os.Getenv("E2E_LOCAL_URL") != "" && os.Getenv("E2E_REMOTE_URL") != "" {
		localURL := os.Getenv("E2E_LOCAL_URL")
		remoteURL := os.Getenv("E2E_REMOTE_URL")
		if err := waitForDB(localURL, 30*time.Second); err != nil {
			if os.Getenv("E2E_REQUIRED") == "1" {
				panic(fmt.Sprintf("E2E_REQUIRED=1: local DB unreachable at %s: %v", localURL, err))
			}
			return nil, false
		}
		if err := waitForDB(remoteURL, 30*time.Second); err != nil {
			if os.Getenv("E2E_REQUIRED") == "1" {
				panic(fmt.Sprintf("E2E_REQUIRED=1: remote DB unreachable at %s: %v", remoteURL, err))
			}
			return nil, false
		}
		return &testDB{localURL: localURL, remoteURL: remoteURL}, true
	}

	// Local mode: detect a running Postgres or start via Docker
	urls, stopFn, ok := detectOrStartPostgres()
	if !ok {
		if os.Getenv("E2E_REQUIRED") == "1" {
			panic("E2E_REQUIRED=1: no Postgres available for E2E tests (set E2E_LOCAL_URL/E2E_REMOTE_URL or run with Docker)")
		}
		return nil, false
	}
	setupTestDBs(urls)
	return &testDB{localURL: urls.local, remoteURL: urls.remote, stopFn: stopFn}, true
}

// detectOrStartPostgres tries: (1) Docker container, (2) local dev Postgres.
func detectOrStartPostgres() (dbURLs, func(), bool) {
	if dockerAvailable() {
		if urls, stopFn, ok := startDockerPostgres(); ok {
			return urls, stopFn, true
		}
	}

	// Try connecting to a local dev Postgres on common ports
	for _, port := range []string{"5432", "5433", "5434"} {
		for _, user := range []string{"gaet", "postgres", "ghaniyrahmans"} {
			dsn := fmt.Sprintf("postgresql://%s@127.0.0.1:%s/postgres", user, port)
			if err := waitForDB(dsn, 2*time.Second); err == nil {
				urls := dbURLs{
					local:  fmt.Sprintf("postgresql://%s@127.0.0.1:%s/gaet_local", user, port),
					remote: fmt.Sprintf("postgresql://%s@127.0.0.1:%s/gaet_remote", user, port),
				}
				return urls, nil, true
			}
		}
	}

	return dbURLs{}, nil, false
}

func dockerAvailable() bool {
	_, err := exec.LookPath("docker")
	return err == nil
}

// startDockerPostgres starts a postgres:16-alpine container on a random port.
func startDockerPostgres() (dbURLs, func(), bool) {
	port := "5433"

	run := func(args ...string) (string, error) {
		cmd := exec.Command("docker", args...)
		out, err := cmd.CombinedOutput()
		return strings.TrimSpace(string(out)), err
	}

	containerName := fmt.Sprintf("gaet-e2e-%d", time.Now().UnixNano())
	out, err := run("run", "--rm", "-d",
		"--name", containerName,
		"-e", "POSTGRES_PASSWORD=testpass",
		"-e", "POSTGRES_USER=gaet",
		"-e", "POSTGRES_DB=postgres",
		"-p", fmt.Sprintf("%s:5432", port),
		"postgres:16-alpine",
	)
	if err != nil {
		return dbURLs{}, nil, false
	}
	containerID := strings.TrimSpace(out)

	urls := dbURLs{
		local:  fmt.Sprintf("postgresql://gaet:testpass@127.0.0.1:%s/gaet_local", port),
		remote: fmt.Sprintf("postgresql://gaet:testpass@127.0.0.1:%s/gaet_remote", port),
	}

	err = waitForDB(urls.local, 30*time.Second)
	if err != nil {
		_ = exec.Command("docker", "stop", containerID).Run()
		return dbURLs{}, nil, false
	}

	runPSQL := func(dbname string, sql string) {
		env := []string{"PATH=" + os.Getenv("PATH"), "PGPASSWORD=testpass", "PGSSLMODE=disable"}
		cmd := exec.Command("psql", "-h", "127.0.0.1", "-p", port, "-U", "gaet", "-d", dbname, "-v", "ON_ERROR_STOP=1", "-c", sql)
		cmd.Env = env
		cmd.Run()
	}
	runPSQL("postgres", "CREATE DATABASE gaet_local;")
	runPSQL("postgres", "CREATE DATABASE gaet_remote;")

	stopFn := func() {
		_ = exec.Command("docker", "stop", containerID).Run()
	}

	return urls, stopFn, true
}

// setupTestDBs creates gaet_local and gaet_remote databases on a local Postgres.
func setupTestDBs(urls dbURLs) {
	p, err := parseDSN(urls.local)
	if err != nil {
		return
	}
	env := []string{"PATH=" + os.Getenv("PATH"), "PGSSLMODE=disable"}
	if p.pass != "" {
		env = append(env, "PGPASSWORD="+p.pass)
	}
	for _, dbname := range []string{"gaet_local", "gaet_remote"} {
		cmd := exec.Command("psql", "-h", p.host, "-p", p.port, "-U", p.user, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", fmt.Sprintf("CREATE DATABASE %s;", dbname))
		cmd.Env = env
		if out, err := cmd.CombinedOutput(); err != nil {
			// Database might already exist — that's fine
			if !strings.Contains(string(out), "already exists") {
				// Ignore, the test will fail with a clear error if DB doesn't exist
			}
		}
	}
}

type parsedDSN struct {
	user, pass, host, port, db string
}

func parseDSN(dsn string) (*parsedDSN, error) {
	s := strings.TrimPrefix(dsn, "postgresql://")
	atIdx := strings.LastIndex(s, "@")
	if atIdx < 0 {
		return nil, fmt.Errorf("no @ in DSN")
	}
	creds := s[:atIdx]
	hostpart := s[atIdx+1:]

	var user, pass string
	if colon := strings.Index(creds, ":"); colon >= 0 {
		user = creds[:colon]
		pass = creds[colon+1:]
	} else {
		user = creds
	}

	slashIdx := strings.Index(hostpart, "/")
	var hostport string
	if slashIdx >= 0 {
		hostport = hostpart[:slashIdx]
	} else {
		hostport = hostpart
	}

	var host, port string
	if colon := strings.LastIndex(hostport, ":"); colon >= 0 {
		host = hostport[:colon]
		port = hostport[colon+1:]
	} else {
		host = hostport
		port = "5432"
	}

	return &parsedDSN{user: user, pass: pass, host: host, port: port}, nil
}
