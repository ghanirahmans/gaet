package core

import (
	"encoding/json"
	"fmt"
	"os"
	"time"
)

const maxLogSizeBytes = 5 * 1024 * 1024 // 5 MB

// LogEntry defines a structured JSON log entry saved to gaet.log.
type LogEntry struct {
	Timestamp string                 `json:"timestamp"`
	Level     string                 `json:"level"`               // INFO, WARN, ERROR
	Category  string                 `json:"category"`            // BACKUP, CONFIG, REMOTE, SCHEDULER, SNAPSHOT
	Action    string                 `json:"action"`              // PUSH, FETCH, RESTORE, INIT, REMOTE_SET, SCHEDULE_ENABLE, etc.
	Status    string                 `json:"status"`              // SUCCESS, FAILED
	Message   string                 `json:"message,omitempty"`
	Details   map[string]interface{} `json:"details,omitempty"`
}

// WriteJSONLog appends a structured JSON LogEntry to gaet.log.
func WriteJSONLog(entry LogEntry) {
	if entry.Timestamp == "" {
		entry.Timestamp = time.Now().Format("2006-01-02 15:04:05")
	}
	if entry.Level == "" {
		entry.Level = "INFO"
	}

	data, err := json.Marshal(entry)
	if err != nil {
		return
	}

	logPath := LogFile()
	if err := EnsureDir(BackupDir()); err != nil {
		return
	}
	rotateIfNeeded(logPath)

	line := string(data) + "\n"
	f, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	defer f.Close()
	_, _ = f.WriteString(line)

	if !Quiet {
		fmt.Print(line)
	}
}

// AppendLog writes a text message as a structured JSON log entry for backward compatibility.
func AppendLog(msg string) {
	WriteJSONLog(LogEntry{
		Level:    "INFO",
		Category: "GENERAL",
		Action:   "EVENT",
		Status:   "SUCCESS",
		Message:  msg,
	})
}

// AppendCronLog writes a timestamped line to the cron log file.
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
