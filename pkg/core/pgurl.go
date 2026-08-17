package core

import (
	"fmt"
	"regexp"
	"strings"
)

// PostgreSQL connection info parsed from a URL.
type PGConnInfo struct {
	User     string
	Password string
	Host     string
	Port     string
	DB       string
}

var pgURLRE = regexp.MustCompile(`(?i)^postgres(?:ql)?://(.+)$`)

// ParseRemoteURL parses a PostgreSQL URL (postgresql://user:pass@host:port/db).
// Passwords may contain '@' — we split at the last '@'.
func ParseRemoteURL(url string) (*PGConnInfo, error) {
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

	return &PGConnInfo{
		User:     user,
		Password: password,
		Host:     host,
		Port:     port,
		DB:       db,
	}, nil
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
