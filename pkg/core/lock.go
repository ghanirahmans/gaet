package core

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// FileLock represents an exclusive file-based lock using O_EXCL creation.
type FileLock struct {
	path string
	file *os.File
}

// AcquireLock attempts to obtain exclusive lock via O_EXCL file creation.
// If the lock is stale (owner process is dead), it removes and retries.
func AcquireLock() (*FileLock, error) {
	lockPath := LockPath()
	if err := EnsureDir(BackupDir()); err != nil {
		return nil, err
	}

	f, err := os.OpenFile(lockPath, os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
	if err != nil {
		if os.IsExist(err) {
			if isLockStale(lockPath) {
				os.Remove(lockPath)
				// Retry once
				f, err = os.OpenFile(lockPath, os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
				if err != nil {
					return nil, fmt.Errorf("another gaet process is running (lock: %s)", lockPath)
				}
			} else {
				return nil, fmt.Errorf("another gaet process is running (lock: %s)", lockPath)
			}
		} else {
			return nil, fmt.Errorf("cannot create lock file: %w", err)
		}
	}

	// Write current PID into the lock file
	_, _ = fmt.Fprintf(f, "%d", os.Getpid())
	return &FileLock{path: lockPath, file: f}, nil
}

// Release removes the lock file.
func (l *FileLock) Release() {
	if l == nil {
		return
	}
	if l.file != nil {
		l.file.Close()
	}
	os.Remove(l.path)
}

// isLockStale returns true if the PID stored in the lock file is not running
// or if the file is older than 1 hour (legacy lock without PID).
func isLockStale(lockPath string) bool {
	data, err := os.ReadFile(lockPath)
	if err != nil {
		// Can't read — check modification time
		fi, err2 := os.Stat(lockPath)
		if err2 != nil {
			return false
		}
		return time.Since(fi.ModTime()) > time.Hour
	}

	pidStr := strings.TrimSpace(string(data))
	if pidStr == "" {
		fi, err2 := os.Stat(lockPath)
		if err2 != nil {
			return false
		}
		return time.Since(fi.ModTime()) > time.Hour
	}

	pid, err := strconv.Atoi(pidStr)
	if err != nil || pid <= 0 {
		return false
	}

	return !processExists(pid)
}
