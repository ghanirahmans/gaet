// Package config implements `gaet get` and `gaet set` commands.
package config

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"sort"
	"strings"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// ConfigKey describes a supported configuration variable.
type ConfigKey struct {
	Key     string
	Type    string
	Default string
	Desc    string
	Example string
}

// All supported config keys.
var allKeys = []ConfigKey{
	{"GAET_LOCAL_URL", "URL", "127.0.0.1:5432", "Full connection URL (postgresql://user:pass@host:port/db)", "postgresql://user:pass@127.0.0.1:5432/mydb"},
	{"GAET_LOCAL_DB_HOST", "String", "127.0.0.1", "Host / socket path for PostgreSQL", "127.0.0.1"},
	{"GAET_LOCAL_DB_PORT", "Integer", "5432", "PostgreSQL listener port", "5432"},
	{"GAET_LOCAL_DB_USER", "String", "postgres", "Local database username", "postgres"},
	{"GAET_LOCAL_DB_NAME", "String", "postgres", "Local database name to backup", "my_app_db"},
	{"GAET_LOCAL_DB_PASS", "String", "(empty)", "Local PostgreSQL password", "mysecretpass"},
	{"GAET_REMOTE_URL", "URL", "(empty)", "Cloud PostgreSQL URL (Supabase/Neon/RDS/VPS)", "postgresql://user:pass@host:5432/db"},
	{"GAET_REMOTE_SSLMODE", "String", "require", "Cloud SSL mode (require/verify-full/disable)", "require"},
	{"GAET_RETENTION_DAYS", "Integer", "7", "Days to retain local .dump backups", "14"},
	{"GAET_PG_TIMEOUT", "Integer", "120", "Max timeout for pg_dump/pg_restore (seconds)", "1800"},
	{"GAET_TABLES", "String", "(all)", "Comma-separated table filter list", "users,orders,products"},
}

var keySchema = func() map[string]ConfigKey {
	m := make(map[string]ConfigKey, len(allKeys))
	for _, k := range allKeys {
		m[k.Key] = k
	}
	return m
}()

var lineKeyRE = regexp.MustCompile(`^(?:export\s+)?([^=]+)=`)

// RunGet implements `gaet get [keys...]`.
func RunGet(keys []string, showList, jsonOut bool) error {
	if showList {
		showSchema()
		return nil
	}

	envFile := core.EnvFile()
	if _, err := os.Stat(envFile); os.IsNotExist(err) {
		core.StatusWarn(fmt.Sprintf("No configuration file found at %s", envFile))
		core.Echo(fmt.Sprintf("  %sRun 'gaet init' to configure.%s", core.ColorDim, core.ColorReset))
		return nil
	}

	env, err := core.LoadEnv(envFile)
	if err != nil {
		return err
	}

	if jsonOut {
		data := make(map[string]string)
		for k, v := range env {
			data[k] = v
		}
		return jsonPrint(data)
	}

	keysToShow := keys
	if len(keysToShow) == 0 {
		for k := range env {
			keysToShow = append(keysToShow, k)
		}
		sort.Strings(keysToShow)
	}

	core.BoxTitle("gaet get")
	for _, key := range keysToShow {
		val, ok := env[key]
		if !ok {
			if s, found := keySchema[key]; found {
				core.Echo(fmt.Sprintf("  %s[INFO]%s  %s%-22s%s (not set — default: %s)",
					core.ColorBCyan, core.ColorReset,
					core.ColorCyan, key, core.ColorReset, s.Default))
			} else {
				core.StatusWarn(fmt.Sprintf("Key '%s' not found in .env", key))
			}
			continue
		}
		display := maskValue(key, val)
		core.StatusOK(fmt.Sprintf("%s%-22s%s = %s", core.ColorCyan, key, core.ColorReset, display))
	}
	fmt.Println()
	return nil
}

// RunSet implements `gaet set KEY=value [...]`.
func RunSet(vars []string, showList bool) error {
	if showList || len(vars) == 0 {
		showSchema()
		return nil
	}

	if err := core.EnsureDir(core.GaetDir()); err != nil {
		return err
	}

	updates := make(map[string]string)
	deletions := make(map[string]bool)

	for _, v := range vars {
		idx := strings.IndexByte(v, '=')
		if idx < 0 {
			return fmt.Errorf("invalid format: %q — use KEY=value", v)
		}
		key := strings.TrimSpace(v[:idx])
		val := strings.TrimSpace(v[idx+1:])
		if key == "" {
			return fmt.Errorf("key cannot be empty")
		}
		if val == "" {
			deletions[key] = true
		} else {
			updates[key] = val
		}
	}

	// If setting individual local DB vars, remove GAET_LOCAL_URL to avoid conflict
	localDBKeys := map[string]bool{
		"GAET_LOCAL_DB_HOST": true, "GAET_LOCAL_DB_PORT": true,
		"GAET_LOCAL_DB_USER": true, "GAET_LOCAL_DB_NAME": true,
		"GAET_LOCAL_DB_PASS": true,
	}
	for k := range updates {
		if localDBKeys[k] {
			deletions["GAET_LOCAL_URL"] = true
			break
		}
	}

	envFile := core.EnvFile()
	var lines []string
	existingKeys := map[string]bool{}

	if f, err := os.Open(envFile); err == nil {
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			orig := scanner.Text()
			m := lineKeyRE.FindStringSubmatch(strings.TrimSpace(orig))
			if m != nil {
				k := strings.TrimSpace(m[1])
				existingKeys[k] = true
				if deletions[k] {
					continue
				}
				if newVal, ok := updates[k]; ok {
					lines = append(lines, fmt.Sprintf("export %s=%s", k, newVal))
					continue
				}
			}
			lines = append(lines, orig)
		}
		f.Close()
	}

	// Add new keys not already present
	for k, v := range updates {
		if !existingKeys[k] && !deletions[k] {
			lines = append(lines, fmt.Sprintf("export %s=%s", k, v))
		}
	}

	content := strings.Join(lines, "\n") + "\n"
	if err := core.WriteEnvContent(envFile, content); err != nil {
		return err
	}

	core.WriteJSONLog(core.LogEntry{
		Level:    "INFO",
		Category: "CONFIG",
		Action:   "CONFIG_SET",
		Status:   "SUCCESS",
		Message:  fmt.Sprintf("Updated %d config key(s)", len(updates)+len(deletions)),
	})

	core.BoxTitle("gaet set")
	for k, v := range updates {
		display := maskValue(k, v)
		core.StatusOK(fmt.Sprintf("%s%-22s%s = %s", core.ColorCyan, k, core.ColorReset, display))
	}
	for k := range deletions {
		if _, inUpdates := updates[k]; !inUpdates {
			core.StatusOK(fmt.Sprintf("%s%-22s%s = %s(deleted)%s",
				core.ColorCyan, k, core.ColorReset, core.ColorYellow, core.ColorReset))
		}
	}
	fmt.Println()
	core.StatusInfo(fmt.Sprintf("Configuration saved to: %s", envFile))
	fmt.Println()
	return nil
}

func showSchema() {
	core.BoxTitle("gaet Config Reference")
	for _, k := range allKeys {
		core.Echo(fmt.Sprintf("  %s%-24s%s %s[%-7s]%s %s",
			core.ColorCyan, k.Key, core.ColorReset,
			core.ColorYellow, k.Type, core.ColorReset,
			k.Desc))
	}
	fmt.Println()
	core.StatusInfo("Usage: gaet set KEY=value  |  Example: gaet set GAET_RETENTION_DAYS=14")
	fmt.Println()
}

func maskValue(key, val string) string {
	lk := strings.ToLower(key)
	if strings.Contains(lk, "pass") || strings.HasSuffix(lk, "url") || key == "GAET_REMOTE_URL" {
		if len(val) > 20 {
			return val[:10] + "***" + val[len(val)-5:]
		}
		return "***"
	}
	return val
}

func jsonPrint(v any) error {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	return enc.Encode(v)
}
