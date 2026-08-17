// Package log implements `gaet log`.
package log

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// LogOptions holds flags for `gaet log`.
type LogOptions struct {
	Lines  int
	Filter string
	Since  string
	Follow bool
}

// RunLog implements `gaet log`.
func RunLog(opts LogOptions) error {
	if opts.Lines <= 0 {
		opts.Lines = 30
	}

	logFile := core.LogFile()
	cronLog := core.CronLogFile()

	if opts.Follow {
		return followLogs(logFile, cronLog, opts.Filter)
	}

	if !fileExists(logFile) && !fileExists(cronLog) {
		core.StatusWarn("No log yet. Run 'gaet push' first.")
		return nil
	}

	// Collect all lines from both files
	var all []string
	for _, src := range []string{logFile, cronLog} {
		lines, err := readLines(src)
		if err == nil {
			all = append(all, lines...)
		}
	}

	// Apply filters
	filtered := all
	if opts.Filter != "" {
		var f2 []string
		for _, l := range filtered {
			if strings.Contains(strings.ToLower(l), strings.ToLower(opts.Filter)) {
				f2 = append(f2, l)
			}
		}
		filtered = f2
	}
	if opts.Since != "" {
		var f2 []string
		for _, l := range filtered {
			if strings.HasPrefix(l, "["+opts.Since) || strings.Contains(l, opts.Since) {
				f2 = append(f2, l)
			}
		}
		filtered = f2
	}

	core.BoxTitle("gaet log")
	total := len(all)
	showing := opts.Lines
	if showing > len(filtered) {
		showing = len(filtered)
	}
	core.Echo(fmt.Sprintf("  %s%d total lines, showing %d%s", core.ColorDim, total, showing, core.ColorReset))
	fmt.Println()

	if len(filtered) == 0 {
		if opts.Filter != "" || opts.Since != "" {
			core.StatusWarn(fmt.Sprintf("No lines matching filter '%s'", opts.Filter+opts.Since))
		}
		return nil
	}

	start := len(filtered) - showing
	if start < 0 {
		start = 0
	}
	for _, line := range filtered[start:] {
		fmt.Printf("  %s│%s %s\n", core.ColorDim, core.ColorReset, strings.TrimRight(line, "\r\n"))
	}
	return nil
}

func followLogs(logFile, cronLog, filter string) error {
	core.Echo(fmt.Sprintf("  %sFollowing log (Ctrl+C to stop)%s", core.ColorDim, core.ColorReset))
	fmt.Println()
	positions := map[string]int64{logFile: 0, cronLog: 0}
	for {
		for _, src := range []string{logFile, cronLog} {
			f, err := os.Open(src)
			if err != nil {
				continue
			}
			f.Seek(positions[src], 0)
			scanner := bufio.NewScanner(f)
			for scanner.Scan() {
				line := scanner.Text()
				if filter != "" && !strings.Contains(strings.ToLower(line), strings.ToLower(filter)) {
					continue
				}
				fmt.Printf("  %s│%s %s\n", core.ColorDim, core.ColorReset, line)
			}
			pos, _ := f.Seek(0, 1)
			positions[src] = pos
			f.Close()
		}
		time.Sleep(time.Second)
	}
}

func readLines(path string) ([]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var lines []string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}
	return lines, scanner.Err()
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
