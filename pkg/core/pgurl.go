package core

import (
	"fmt"
	"regexp"
	"strings"
)

// DBConnInfo connection info parsed from a database connection URL.
type DBConnInfo struct {
	User     string
	Password string
	Host     string
	Port     string
	DB       string
}

// PGConnInfo is a backward-compatible alias for DBConnInfo.
type PGConnInfo = DBConnInfo

var pgURLRE = regexp.MustCompile(`(?i)^postgres(?:ql)?://(.+)$`)

// ParseConnURL parses a database URL (postgresql://user:pass@host:port/db).
// Passwords may contain '@' — we split at the last '@'.
func ParseConnURL(url string) (*DBConnInfo, error) {
	if url == "" {
		return nil, fmt.Errorf("empty URL")
	}
	m := pgURLRE.FindStringSubmatch(url)
	if m == nil {
		return nil, fmt.Errorf("not a postgresql:// URL")
	}
	rest := m[1]

	// Credentials vs host: split at the last '@'
	atIdx := strings.LastIndex(rest, "@")
	if atIdx < 0 {
		return nil, fmt.Errorf("missing @ in URL")
	}
	userinfo := rest[:atIdx]
	hostpart := rest[atIdx+1:]

	if userinfo == "" || hostpart == "" {
		return nil, fmt.Errorf("invalid URL structure")
	}

	var user, password string
	if ci := strings.IndexByte(userinfo, ':'); ci >= 0 {
		user = userinfo[:ci]
		password = userinfo[ci+1:]
	} else {
		user = userinfo
	}

	// host:port/db — split at last '/'
	slashIdx := strings.LastIndex(hostpart, "/")
	if slashIdx < 0 {
		return nil, fmt.Errorf("missing database in URL")
	}
	hostport := hostpart[:slashIdx]
	db := hostpart[slashIdx+1:]

	// Strip query string from db
	if qi := strings.IndexByte(db, '?'); qi >= 0 {
		db = db[:qi]
	}
	if db == "" || hostport == "" {
		return nil, fmt.Errorf("missing host or database")
	}

	var host, port string
	if ci := strings.LastIndex(hostport, ":"); ci >= 0 {
		host = hostport[:ci]
		port = hostport[ci+1:]
		// Validate port is numeric
		for _, c := range port {
			if c < '0' || c > '9' {
				host = hostport
				port = "5432"
				break
			}
		}
	} else {
		host = hostport
		port = "5432"
	}

	if host == "" {
		return nil, fmt.Errorf("missing host in URL")
	}

	return &DBConnInfo{
		User:     user,
		Password: password,
		Host:     host,
		Port:     port,
		DB:       db,
	}, nil
}

// ParseRemoteURL is a backward-compatible alias for ParseConnURL.
func ParseRemoteURL(url string) (*DBConnInfo, error) {
	return ParseConnURL(url)
}

// MaskURLPassword replaces the password in a PG URL with ****
func MaskURLPassword(url string) string {
	re := regexp.MustCompile(`(postgres(?:ql)?://[^:]+):([^@]+)@`)
	return re.ReplaceAllString(url, "$1:****@")
}

var validIdentRE = regexp.MustCompile(`^[a-zA-Z_][a-zA-Z0-9_]*$`)

// ValidateTableName returns true if name is a safe PostgreSQL identifier.
func ValidateTableName(name string) bool {
	return validIdentRE.MatchString(name)
}

// CleanHost returns 127.0.0.1 if host is a Unix domain socket path (starts with /) or empty.
func CleanHost(host string) string {
	if host == "" || strings.HasPrefix(host, "/") {
		return "127.0.0.1"
	}
	return host
}

// FormatConnTarget formats connection details (user, host, port, db) into clean user@host:port/db string, converting socket paths to 127.0.0.1.
func FormatConnTarget(user, host, port, db string) string {
	ch := CleanHost(host)
	if port != "" {
		return fmt.Sprintf("%s@%s:%s/%s", user, ch, port, db)
	}
	return fmt.Sprintf("%s@%s/%s", user, ch, db)
}
