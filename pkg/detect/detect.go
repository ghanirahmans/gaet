// Package detect provides local PostgreSQL auto-discovery via Unix socket and TCP probing.
package detect

import (
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// DBInstance holds information about a discovered database instance.
type DBInstance = PGInstance

// DetectLocalDB discovers running database instances.
func DetectLocalDB(psqlPath string) []DBInstance {
	return DetectLocalPG(psqlPath)
}

// PGInstance holds information about a discovered PostgreSQL instance.
type PGInstance struct {
	Host      string   `json:"host"`
	Port      string   `json:"port"`
	User      string   `json:"user"`
	Databases []string `json:"databases"`
	DefaultDB string   `json:"default_db"`
	IsSocket  bool     `json:"is_socket"`
}

// DetectLocalPG discovers running PostgreSQL instances (socket first, then TCP fallback).
func DetectLocalPG(psqlPath string) []PGInstance {
	if psqlPath == "" {
		return nil
	}

	var results []PGInstance
	seenPorts := map[string]bool{}

	usersToTry := buildUserList()

	// 1. Unix socket scan
	for _, sockPath := range core.FindSocketPaths() {
		port := core.SocketPort(sockPath)
		if seenPorts[port] {
			continue
		}
		host := filepath.Dir(sockPath)
		for _, user := range usersToTry {
			stdout, _, rc := core.RunCmdSimple(psqlPath,
				[]string{"-w", "-h", host, "-p", port, "-U", user, "-d", "postgres", "-tAc", "SELECT current_database();"},
				map[string]string{"PGPASSWORD": ""}, 3*time.Second)
			if rc == 0 && strings.TrimSpace(stdout) != "" {
				db := strings.TrimSpace(stdout)
				dbs := listDatabases(psqlPath, host, port, user)
				if len(dbs) == 0 {
					dbs = []string{db}
				}
				results = append(results, PGInstance{
					Host:      host,
					Port:      port,
					User:      user,
					Databases: dbs,
					DefaultDB: db,
					IsSocket:  true,
				})
				seenPorts[port] = true
				break
			}
		}
	}

	// 2. TCP ports fallback
	for _, port := range []string{"5432", "5433", "5434", "5435", "5436"} {
		if seenPorts[port] {
			continue
		}
		for _, user := range usersToTry {
			stdout, _, rc := core.RunCmdSimple(psqlPath,
				[]string{"-w", "-h", "127.0.0.1", "-p", port, "-U", user, "-d", "postgres", "-tAc", "SELECT current_database();"},
				map[string]string{"PGPASSWORD": ""}, 3*time.Second)
			if rc == 0 && strings.TrimSpace(stdout) != "" {
				db := strings.TrimSpace(stdout)
				dbs := listDatabasesTCP(psqlPath, "127.0.0.1", port, user)
				if len(dbs) == 0 {
					dbs = []string{db}
				}
				results = append(results, PGInstance{
					Host:      "127.0.0.1",
					Port:      port,
					User:      user,
					Databases: dbs,
					DefaultDB: db,
					IsSocket:  false,
				})
				break
			}
		}
	}

	return results
}

func buildUserList() []string {
	users := []string{"postgres", "root"}
	if cur, err := currentUser(); err == nil && cur != "" {
		found := false
		for _, u := range users {
			if u == cur {
				found = true
				break
			}
		}
		if !found {
			users = append([]string{cur}, users...)
		}
	}
	return users
}

func currentUser() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	// Simplest approach: use $USER env
	if u := os.Getenv("USER"); u != "" {
		return u, nil
	}
	// Fallback: parse home dir basename
	return filepath.Base(home), nil
}

func listDatabases(psqlPath, host, port, user string) []string {
	stdout, _, rc := core.RunCmdSimple(psqlPath,
		[]string{"-w", "-h", host, "-p", port, "-U", user, "-d", "postgres", "-tAc",
			"SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"},
		map[string]string{"PGPASSWORD": ""}, 3*time.Second)
	if rc != 0 || strings.TrimSpace(stdout) == "" {
		return nil
	}
	var dbs []string
	for _, line := range strings.Split(strings.TrimSpace(stdout), "\n") {
		d := strings.TrimSpace(line)
		if d != "" {
			dbs = append(dbs, d)
		}
	}
	return dbs
}

func listDatabasesTCP(psqlPath, host, port, user string) []string {
	return listDatabases(psqlPath, host, port, user)
}
