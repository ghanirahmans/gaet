// Package snapshots implements `gaet snapshots`.
package snapshots

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// SnapshotInfo holds metadata about a single dump file.
type SnapshotInfo struct {
	Filename  string  `json:"filename"`
	Path      string  `json:"path"`
	SizeMB    float64 `json:"size_mb"`
	CreatedAt string  `json:"created_at"`
	IsLatest  bool    `json:"is_latest,omitempty"`
}

// RunSnapshots implements `gaet snapshots`.
func RunSnapshots(jsonOut bool) error {
	env, _ := core.LoadEnv(core.EnvFile())
	retention := core.GetEnvInt(env, "GAET_RETENTION_DAYS", core.DefRetentionDays)
	backupDir := core.BackupDir()

	matches, _ := filepath.Glob(filepath.Join(backupDir, "*.dump"))
	var infos []SnapshotInfo
	totalBytes := int64(0)

	type entry struct {
		path    string
		modTime time.Time
	}
	var entries []entry
	for _, m := range matches {
		fi, err := os.Stat(m)
		if err == nil {
			entries = append(entries, entry{m, fi.ModTime()})
		}
	}
	sort.Slice(entries, func(i, j int) bool {
		return entries[i].modTime.After(entries[j].modTime)
	})

	for i, e := range entries {
		fi, _ := os.Stat(e.path)
		totalBytes += fi.Size()
		infos = append(infos, SnapshotInfo{
			Filename:  filepath.Base(e.path),
			Path:      e.path,
			SizeMB:    float64(fi.Size()) / 1024 / 1024,
			CreatedAt: e.modTime.Format("2006-01-02 15:04:05"),
			IsLatest:  i == 0,
		})
	}
	totalMB := float64(totalBytes) / 1024 / 1024

	if jsonOut {
		result := map[string]any{
			"command":       "snapshots",
			"count":         len(infos),
			"total_size_mb": fmt.Sprintf("%.1f", totalMB),
			"retention_days": retention,
			"snapshots":     infos,
		}
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(result)
	}

	core.BoxTitle("gaet snapshots")
	if len(infos) == 0 {
		core.StatusWarn(fmt.Sprintf("No local backup snapshots found in %s.", backupDir))
		core.Echo(fmt.Sprintf("  Run: %sgaet push%s to create your first snapshot.", core.ColorCyan, core.ColorReset))
		fmt.Println()
		return nil
	}

	core.BoxSection(fmt.Sprintf("Local Snapshots (%d files, %.1f MB total)", len(infos), totalMB))
	fmt.Printf("  %s%-4s %-32s %-10s %-20s%s\n",
		core.ColorBold, "No", "Snapshot File", "Size", "Created At", core.ColorReset)
	fmt.Printf("  %s%s%s\n", core.ColorDim, repeatChar('─', 68), core.ColorReset)

	for i, snap := range infos {
		latest := ""
		if i == 0 {
			latest = fmt.Sprintf(" %s(latest)%s", core.ColorBGreen, core.ColorReset)
		}
		fmt.Printf("  %s[%d]%s  %-32s %5.1f MB  %-20s%s\n",
			core.ColorCyan, i+1, core.ColorReset,
			truncate(snap.Filename, 32),
			snap.SizeMB,
			snap.CreatedAt,
			latest)
	}
	fmt.Println()
	core.StatusInfo(fmt.Sprintf("Auto-retention: %d days", retention))
	core.StatusInfo(fmt.Sprintf("Run: gaet restore <filename.dump> to restore a snapshot"))
	core.PrintDocsFooter()
	return nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n-3] + "..."
}

func repeatChar(c rune, n int) string {
	r := make([]rune, n)
	for i := range r {
		r[i] = c
	}
	return string(r)
}
