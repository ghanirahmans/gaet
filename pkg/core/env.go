package core

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// LoadEnv parses a .env file (KEY=val, export KEY=val, #comments).
// Returns empty map if file doesn't exist — not an error.
func LoadEnv(filePath string) (map[string]string, error) {
	envMap := make(map[string]string)

	f, err := os.Open(filePath)
	if err != nil {
		if os.IsNotExist(err) {
			return envMap, nil
		}
		return nil, fmt.Errorf("failed to open env file %q: %w", filePath, err)
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		// Handle "export KEY=value"
		line = strings.TrimPrefix(line, "export ")
		line = strings.TrimSpace(line)
		idx := strings.IndexByte(line, '=')
		if idx < 0 {
			continue
		}
		key := strings.TrimSpace(line[:idx])
		val := strings.TrimSpace(line[idx+1:])
		// Strip surrounding quotes
		if len(val) >= 2 {
			if (val[0] == '"' && val[len(val)-1] == '"') ||
				(val[0] == '\'' && val[len(val)-1] == '\'') {
				val = val[1 : len(val)-1]
			}
		}
		// Strip inline comments (# after value)
		if ci := strings.Index(val, " #"); ci >= 0 {
			val = strings.TrimSpace(val[:ci])
		}
		if key != "" {
			envMap[key] = val
		}
	}
	return envMap, scanner.Err()
}

// GetEnvStr reads a key from the env map, with OS environment override and fallback default.
func GetEnvStr(env map[string]string, key, defaultVal string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	if v, ok := env[key]; ok {
		return v
	}
	return defaultVal
}

// GetEnvInt reads an integer key from the env map.
func GetEnvInt(env map[string]string, key string, defaultVal int) int {
	s := GetEnvStr(env, key, "")
	if s != "" {
		var n int
		if _, err := fmt.Sscanf(s, "%d", &n); err == nil {
			return n
		}
	}
	return defaultVal
}

// SetEnvKey updates or appends a single KEY=value in the .env file,
// preserving comments and the 0600 permission.
func SetEnvKey(filePath, key, value string) error {
	// Read existing lines
	var lines []string
	found := false

	if f, err := os.Open(filePath); err == nil {
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			orig := scanner.Text()
			stripped := strings.TrimPrefix(strings.TrimSpace(orig), "export ")
			idx := strings.IndexByte(stripped, '=')
			if idx > 0 {
				k := strings.TrimSpace(stripped[:idx])
				if k == key {
					if value != "" {
						lines = append(lines, fmt.Sprintf("export %s=%s", key, value))
					}
					found = true
					continue
				}
			}
			lines = append(lines, orig)
		}
		if scanErr := scanner.Err(); scanErr != nil {
			f.Close()
			return fmt.Errorf("read env file: %w", scanErr)
		}
		f.Close()
	}

	if !found && value != "" {
		lines = append(lines, fmt.Sprintf("export %s=%s", key, value))
	}

	return writeEnvFile(filePath, strings.Join(lines, "\n")+"\n")
}

// WriteEnvContent atomically writes content to the .env file with 0600 perms.
func WriteEnvContent(filePath, content string) error {
	return writeEnvFile(filePath, content)
}

func writeEnvFile(filePath, content string) error {
	f, err := os.OpenFile(filePath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0600)
	if err != nil {
		return fmt.Errorf("write env file: %w", err)
	}
	defer f.Close()
	_, err = f.WriteString(content)
	return err
}
