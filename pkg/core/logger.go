package core

import (
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"time"
)

const maxLogSizeBytes = 5 * 1024 * 1024 // 5 MB

// AppendLog writes a timestamped line to the main log file.
// Rotates the file if it exceeds 5 MB.
func AppendLog(msg string) {
	logPath := LogFile()
	if err := EnsureDir(BackupDir()); err != nil {
		return
	}
	rotateIfNeeded(logPath)
	line := fmt.Sprintf("[%s] %s\n", time.Now().Format("2006-01-02 15:04:05"), msg)
	f, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()
	_, _ = f.WriteString(line)
	// Also print to stdout
	if !Quiet {
		fmt.Print(line)
	}
}

// AppendCronLog writes a timestamped line to the cron log file only.
func AppendCronLog(msg string) {
	logPath := CronLogFile()
	if err := EnsureDir(BackupDir()); err != nil {
		return
	}
	rotateIfNeeded(logPath)
	line := fmt.Sprintf("[%s] %s\n", time.Now().Format("2006-01-02 15:04:05"), msg)
	f, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()
	_, _ = f.WriteString(line)
}

// rotateIfNeeded renames log → log.old when it exceeds maxLogSizeBytes.
func rotateIfNeeded(path string) {
	fi, err := os.Stat(path)
	if err != nil || fi.Size() < maxLogSizeBytes {
		return
	}
	oldPath := path + ".old"
	_ = os.Rename(path, oldPath)
}

// NewSlogLogger returns a structured slog logger writing to the main log file.
func NewSlogLogger() *slog.Logger {
	logPath := filepath.Join(BackupDir(), "gaet-slog.log")
	_ = EnsureDir(BackupDir())
	f, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return slog.Default()
	}
	return slog.New(slog.NewJSONHandler(f, &slog.HandlerOptions{Level: slog.LevelInfo}))
}
