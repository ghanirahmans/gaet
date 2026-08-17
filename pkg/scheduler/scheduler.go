// Package scheduler implements `gaet auto` (push --auto) and `gaet stop` on Linux (systemd).
package scheduler

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// EnableAuto activates the platform scheduler for gaet auto-backup.
func EnableAuto(prefix string, intervalHours int, cliPath string) error {
	core.BoxTitle("Auto-backup")
	core.StatusInfo(fmt.Sprintf("Enabling auto-backup every %d hours (scheduler: %s)...", intervalHours, schedulerName()))

	switch runtime.GOOS {
	case "linux":
		return enableSystemd(prefix, intervalHours, cliPath)
	case "darwin":
		return enableLaunchd(prefix, intervalHours, cliPath)
	case "windows":
		return enableTaskScheduler(prefix, intervalHours, cliPath)
	default:
		return core.Die(fmt.Sprintf("Auto-backup not supported on %s", runtime.GOOS), core.ExitGeneral)
	}
}

// DisableAuto deactivates the platform scheduler.
func DisableAuto(prefix string) error {
	switch runtime.GOOS {
	case "linux":
		return disableSystemd(prefix)
	case "darwin":
		return disableLaunchd(prefix)
	case "windows":
		return disableTaskScheduler(prefix)
	default:
		return nil
	}
}

// IsActive returns true if the auto-backup scheduler is active.
func IsActive(prefix string) bool {
	switch runtime.GOOS {
	case "linux":
		return systemdIsActive(prefix)
	case "darwin":
		return launchdIsActive(prefix)
	case "windows":
		return taskSchedulerIsActive(prefix)
	default:
		return false
	}
}

// ─── Linux Systemd ────────────────────────────────────────────────────────

func enableSystemd(prefix string, intervalHours int, cliPath string) error {
	unitDir := filepath.Join(mustHomeDir(), ".config", "systemd", "user")
	if err := core.EnsureDir(unitDir); err != nil {
		return err
	}

	serviceName := prefix + "-backup"
	intervalSec := intervalHours * 3600

	serviceContent := fmt.Sprintf(`[Unit]
Description=Gaet Auto-backup Service
After=network.target

[Service]
Type=oneshot
ExecStart=%s push --cron
StandardOutput=append:%s
StandardError=append:%s

[Install]
WantedBy=default.target
`, cliPath, core.CronLogFile(), core.CronLogFile())

	timerContent := fmt.Sprintf(`[Unit]
Description=Gaet Auto-backup Timer
After=network.target

[Timer]
OnBootSec=60
OnUnitActiveSec=%d
Unit=%s.service

[Install]
WantedBy=timers.target
`, intervalSec, serviceName)

	svcPath := filepath.Join(unitDir, serviceName+".service")
	timerPath := filepath.Join(unitDir, serviceName+".timer")

	if err := os.WriteFile(svcPath, []byte(serviceContent), 0644); err != nil {
		return err
	}
	if err := os.WriteFile(timerPath, []byte(timerContent), 0644); err != nil {
		return err
	}

	core.RunCmdSimple("systemctl", []string{"--user", "daemon-reload"}, nil, 10e9)
	_, errOut, rc := core.RunCmdSimple("systemctl",
		[]string{"--user", "enable", "--now", serviceName + ".timer"}, nil, 15e9)
	if rc != 0 {
		return core.Die(fmt.Sprintf("Failed to enable systemd timer: %s", errOut), core.ExitGeneral)
	}

	core.StatusOK(fmt.Sprintf("Auto-backup enabled every %d hours via systemd timer", intervalHours))
	core.StatusArrow(fmt.Sprintf("Timer: %s.timer", serviceName))
	core.StatusArrow(fmt.Sprintf("Log:   %s", core.CronLogFile()))
	return nil
}

func disableSystemd(prefix string) error {
	serviceName := prefix + "-backup"
	core.RunCmdSimple("systemctl", []string{"--user", "disable", "--now", serviceName + ".timer"}, nil, 15e9)
	core.RunCmdSimple("systemctl", []string{"--user", "disable", "--now", serviceName + ".service"}, nil, 15e9)
	core.RunCmdSimple("systemctl", []string{"--user", "daemon-reload"}, nil, 10e9)
	core.StatusOK("Auto-backup scheduler stopped (systemd)")
	return nil
}

func systemdIsActive(prefix string) bool {
	_, _, rc := core.RunCmdSimple("systemctl",
		[]string{"--user", "is-active", prefix + "-backup.timer"}, nil, 5e9)
	return rc == 0
}

// ─── macOS Launchd ────────────────────────────────────────────────────────

func enableLaunchd(prefix string, intervalHours int, cliPath string) error {
	plistDir := filepath.Join(mustHomeDir(), "Library", "LaunchAgents")
	if err := core.EnsureDir(plistDir); err != nil {
		return err
	}
	label := "com." + prefix + ".backup"
	plistPath := filepath.Join(plistDir, label+".plist")
	plistContent := fmt.Sprintf(`<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>%s</string>
  <key>ProgramArguments</key>
  <array><string>%s</string><string>push</string><string>--cron</string></array>
  <key>StartInterval</key><integer>%d</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>%s</string>
  <key>StandardErrorPath</key><string>%s</string>
</dict>
</plist>
`, label, cliPath, intervalHours*3600, core.CronLogFile(), core.CronLogFile())

	if err := os.WriteFile(plistPath, []byte(plistContent), 0644); err != nil {
		return err
	}
	_, errOut, rc := core.RunCmdSimple("launchctl", []string{"load", plistPath}, nil, 10e9)
	if rc != 0 {
		return core.Die(fmt.Sprintf("Failed to load launchd plist: %s", errOut), core.ExitGeneral)
	}
	core.StatusOK(fmt.Sprintf("Auto-backup enabled every %d hours via launchd", intervalHours))
	return nil
}

func disableLaunchd(prefix string) error {
	label := "com." + prefix + ".backup"
	plistPath := filepath.Join(mustHomeDir(), "Library", "LaunchAgents", label+".plist")
	core.RunCmdSimple("launchctl", []string{"unload", plistPath}, nil, 10e9)
	os.Remove(plistPath)
	core.StatusOK("Auto-backup scheduler stopped (launchd)")
	return nil
}

func launchdIsActive(prefix string) bool {
	label := "com." + prefix + ".backup"
	out, _, rc := core.RunCmdSimple("launchctl", []string{"list", label}, nil, 5e9)
	return rc == 0 && strings.Contains(out, label)
}

// ─── Windows Task Scheduler ───────────────────────────────────────────────

func enableTaskScheduler(prefix string, intervalHours int, cliPath string) error {
	taskName := prefix + "-backup"
	_, errOut, rc := core.RunCmdSimple("schtasks",
		[]string{"/Create", "/TN", taskName, "/TR", cliPath + " push --cron",
			"/SC", "HOURLY", "/MO", fmt.Sprintf("%d", intervalHours),
			"/ST", "00:00", "/F"},
		nil, 15e9)
	if rc != 0 {
		return core.Die(fmt.Sprintf("Failed to create task: %s", errOut), core.ExitGeneral)
	}
	core.StatusOK(fmt.Sprintf("Auto-backup enabled every %d hours via Task Scheduler", intervalHours))
	return nil
}

func disableTaskScheduler(prefix string) error {
	taskName := prefix + "-backup"
	core.RunCmdSimple("schtasks", []string{"/Delete", "/TN", taskName, "/F"}, nil, 10e9)
	core.StatusOK("Auto-backup scheduler stopped (Task Scheduler)")
	return nil
}

func taskSchedulerIsActive(prefix string) bool {
	taskName := prefix + "-backup"
	_, _, rc := core.RunCmdSimple("schtasks", []string{"/Query", "/TN", taskName}, nil, 5e9)
	return rc == 0
}

// ─── helpers ──────────────────────────────────────────────────────────────

func schedulerName() string {
	switch runtime.GOOS {
	case "linux":
		return "systemd"
	case "darwin":
		return "launchd"
	case "windows":
		return "Task Scheduler"
	default:
		return "unknown"
	}
}

func mustHomeDir() string {
	h, err := os.UserHomeDir()
	if err != nil {
		h = "."
	}
	return h
}
