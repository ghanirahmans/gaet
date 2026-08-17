package core

import "fmt"

// GaetError is the base typed error for all gaet failures.
type GaetError struct {
	Code    int
	Message string
}

func (e *GaetError) Error() string {
	return e.Message
}

// NewError creates a GaetError.
func NewError(code int, msg string) *GaetError {
	return &GaetError{Code: code, Message: msg}
}

// NewErrorf creates a GaetError with fmt.Sprintf formatting.
func NewErrorf(code int, format string, args ...any) *GaetError {
	return &GaetError{Code: code, Message: fmt.Sprintf(format, args...)}
}

// ConfigError is raised when configuration is missing or invalid.
type ConfigError struct {
	GaetError
	Key string
}

// DBError is raised when a database operation fails.
type DBError struct {
	GaetError
	Host string
	Port string
}

// Exit codes mirroring Python constants
const (
	ExitOK        = 0
	ExitGeneral   = 1
	ExitUsage     = 2
	ExitConfig    = 80
	ExitLocalDown = 81
	ExitCloudDown = 82
	ExitLocked    = 83
	ExitTools     = 84
)
