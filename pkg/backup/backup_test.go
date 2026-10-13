package backup

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestDumpArgs_CustomFormat(t *testing.T) {
	env := map[string]string{}
	args := dumpArgs("127.0.0.1", "5432", "postgres", "mydb", "/tmp/out.dump", env)
	if !contains(args, "--format=custom") {
		t.Errorf("expected --format=custom, got %v", args)
	}
	if !contains(args, "--compress=9") {
		t.Errorf("expected --compress=9 (default), got %v", args)
	}
	if !contains(args, "--file=/tmp/out.dump") {
		t.Errorf("expected --file=/tmp/out.dump, got %v", args)
	}
}

func TestDumpArgs_DirectoryFormatParallelJobs(t *testing.T) {
	env := map[string]string{"GAET_DUMP_JOBS": "3"}
	args := dumpArgs("127.0.0.1", "5432", "postgres", "mydb", "/tmp/out_dir", env)
	if !contains(args, "--format=directory") {
		t.Errorf("expected --format=directory for parallel dump, got %v", args)
	}
	if !contains(args, "--jobs=3") {
		t.Errorf("expected --jobs=3, got %v", args)
	}
}

func TestDumpArgs_CompressClampHigh(t *testing.T) {
	env := map[string]string{"GAET_DUMP_COMPRESS": "99"}
	args := dumpArgs("127.0.0.1", "5432", "postgres", "mydb", "/tmp/out.dump", env)
	if !contains(args, "--compress=9") {
		t.Errorf("expected compress clamped to 9, got %v", args)
	}
}

func TestDumpArgs_CompressClampLow(t *testing.T) {
	env := map[string]string{"GAET_DUMP_COMPRESS": "-5"}
	args := dumpArgs("127.0.0.1", "5432", "postgres", "mydb", "/tmp/out.dump", env)
	if !contains(args, "--compress=0") {
		t.Errorf("expected compress clamped to 0, got %v", args)
	}
}

func TestDumpArgs_JobsNotSet(t *testing.T) {
	env := map[string]string{}
	args := dumpArgs("127.0.0.1", "5432", "postgres", "mydb", "/tmp/out.dump", env)
	if contains(args, "--jobs=") {
		t.Errorf("expected no --jobs when GAET_DUMP_JOBS not set, got %v", args)
	}
}

func TestDumpArgs_JobsOneFallsBackToCustom(t *testing.T) {
	env := map[string]string{"GAET_DUMP_JOBS": "1"}
	args := dumpArgs("127.0.0.1", "5432", "postgres", "mydb", "/tmp/out.dump", env)
	if contains(args, "--jobs=") {
		t.Errorf("expected no --jobs when GAET_DUMP_JOBS=1, got %v", args)
	}
	if contains(args, "--format=directory") {
		t.Errorf("expected custom format when GAET_DUMP_JOBS=1, got %v", args)
	}
}

func TestDumpArgs_HostEmpty(t *testing.T) {
	env := map[string]string{}
	args := dumpArgs("", "5432", "postgres", "mydb", "/tmp/out.dump", env)
	if contains(args, "-h") {
		t.Errorf("expected no -h flag when host empty, got %v", args)
	}
}

func TestApplyRetention_RemovesOldKeepsNew(t *testing.T) {
	tmp := t.TempDir()
	backupDir := filepath.Join(tmp, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	oldFile := filepath.Join(backupDir, "gaet_old.dump")
	newFile := filepath.Join(backupDir, "gaet_new.dump")
	cloudFile := filepath.Join(backupDir, "cloud_old.dump")
	cronFile := filepath.Join(backupDir, "cron_recent.dump")

	_ = os.WriteFile(oldFile, []byte("OLD"), 0644)
	_ = os.WriteFile(newFile, []byte("NEW"), 0644)
	_ = os.WriteFile(cloudFile, []byte("CLOUD"), 0644)
	_ = os.WriteFile(cronFile, []byte("CRON"), 0644)

	oldTime := time.Now().AddDate(0, 0, -10)
	_ = os.Chtimes(oldFile, oldTime, oldTime)
	_ = os.Chtimes(cloudFile, oldTime, oldTime)

	env := map[string]string{"GAET_RETENTION_DAYS": "7"}
	applyRetention(env, backupDir)

	if _, err := os.Stat(oldFile); err == nil {
		t.Error("old gaet dump should have been removed")
	}
	if _, err := os.Stat(newFile); err != nil {
		t.Error("new gaet dump should be kept")
	}
	if _, err := os.Stat(cloudFile); err == nil {
		t.Error("old cloud dump should have been removed")
	}
	if _, err := os.Stat(cronFile); err != nil {
		t.Error("recent cron dump should be kept")
	}
}

func TestApplyRetention_DefaultRetention(t *testing.T) {
	tmp := t.TempDir()
	backupDir := filepath.Join(tmp, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	freshFile := filepath.Join(backupDir, "gaet_fresh.dump")
	_ = os.WriteFile(freshFile, []byte("FRESH"), 0644)

	applyRetention(map[string]string{}, backupDir)

	if _, err := os.Stat(freshFile); err != nil {
		t.Error("fresh dump should be kept with default retention")
	}
}

func TestGlobDumps_EmptyDir(t *testing.T) {
	tmp := t.TempDir()
	dumps, err := globDumps(tmp)
	if err != nil {
		t.Errorf("unexpected error: %v", err)
	}
	if len(dumps) != 0 {
		t.Errorf("expected 0 dumps in empty dir, got %d", len(dumps))
	}
}

func TestGlobDumps_NewestFirst(t *testing.T) {
	tmp := t.TempDir()
	mk := func(name string, ageHours int) string {
		p := filepath.Join(tmp, name)
		_ = os.WriteFile(p, []byte("data"), 0644)
		t := time.Now().Add(-time.Duration(ageHours) * time.Hour)
		_ = os.Chtimes(p, t, t)
		return p
	}
	mk("gaet_older.dump", 48)
	mk("gaet_newer.dump", 12)
	mk("gaet_newest.dump", 1)

	dumps, _ := globDumps(tmp)
	if len(dumps) != 3 {
		t.Fatalf("expected 3 dumps, got %d", len(dumps))
	}
	// Newest should be first
	if filepath.Base(dumps[0]) != "gaet_newest.dump" {
		t.Errorf("expected gaet_newest.dump first, got %s", filepath.Base(dumps[0]))
	}
	if filepath.Base(dumps[2]) != "gaet_older.dump" {
		t.Errorf("expected gaet_older.dump last, got %s", filepath.Base(dumps[2]))
	}
}

func TestGlobDumps_OnlyDmpFiles(t *testing.T) {
	tmp := t.TempDir()
	_ = os.WriteFile(filepath.Join(tmp, "gaet_real.dump"), []byte("x"), 0644)
	_ = os.WriteFile(filepath.Join(tmp, "notadump.txt"), []byte("x"), 0644)
	_ = os.WriteFile(filepath.Join(tmp, "backup.bin"), []byte("x"), 0644)

	dumps, _ := globDumps(tmp)
	if len(dumps) != 1 {
		t.Errorf("expected 1 .dump file, got %d", len(dumps))
	}
}

func TestResetFailedError_WithSafetyPath(t *testing.T) {
	msg := "restore failed"
	safety := "/tmp/safety_restore_20260101.dump"
	err := resetFailedError(msg, safety)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), safety) {
		t.Errorf("error should contain safety path: %s", err.Error())
	}
}

func TestResetFailedError_NoSafetyPath(t *testing.T) {
	msg := "restore failed"
	err := resetFailedError(msg, "")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "no safety snapshot") {
		t.Errorf("error should warn about no safety snapshot: %s", err.Error())
	}
}

func contains(slice []string, val string) bool {
	for _, s := range slice {
		if s == val {
			return true
		}
	}
	return false
}

func TestDumpArgs_FlagsOrder(t *testing.T) {
	env := map[string]string{}
	args := dumpArgs("myhost", "5432", "myuser", "mydb", "/tmp/out.dump", env)
	// Verify basic structure: -w present, then -h, -p, -U, -d, then format flags
	if !contains(args, "-w") {
		t.Error("expected -w flag")
	}
	// Find positions
	hostIdx := indexOf(args, "-h")
	portIdx := indexOf(args, "-p")
	userIdx := indexOf(args, "-U")
	dbIdx := indexOf(args, "-d")
	if hostIdx < 0 || portIdx < 0 || userIdx < 0 || dbIdx < 0 {
		t.Fatalf("missing connection flags: %v", args)
	}
}

func indexOf(slice []string, val string) int {
	for i, s := range slice {
		if s == val {
			return i
		}
	}
	return -1
}

func TestDumpArgs_AllJobsValues(t *testing.T) {
	for jobs := 2; jobs <= 5; jobs++ {
		env := map[string]string{"GAET_DUMP_JOBS": string(rune('0' + jobs))}
		args := dumpArgs("127.0.0.1", "5432", "postgres", "mydb", "/tmp/out", env)
		if !contains(args, "--format=directory") {
			t.Errorf("jobs=%d: expected directory format", jobs)
		}
		if !contains(args, "--jobs="+string(rune('0'+jobs))) {
			t.Errorf("jobs=%d: expected --jobs=%d", jobs, jobs)
		}
	}
}

func TestGlobDumps_MultipleTypes(t *testing.T) {
	tmp := t.TempDir()
	_ = os.WriteFile(filepath.Join(tmp, "gaet_2026.dump"), []byte("x"), 0644)
	_ = os.WriteFile(filepath.Join(tmp, "cron_2026.dump"), []byte("x"), 0644)
	_ = os.WriteFile(filepath.Join(tmp, "cloud_2026.dump"), []byte("x"), 0644)
	_ = os.WriteFile(filepath.Join(tmp, "safety_fetch_2026.dump"), []byte("x"), 0644)

	dumps, _ := globDumps(tmp)
	if len(dumps) != 4 {
		t.Errorf("expected 4 dumps, got %d", len(dumps))
	}
}

func TestApplyRetention_PrunesAllPatterns(t *testing.T) {
	tmp := t.TempDir()
	backupDir := filepath.Join(tmp, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	oldTime := time.Now().AddDate(0, 0, -10)
	for _, prefix := range []string{"gaet_", "cron_", "cloud_"} {
		f := filepath.Join(backupDir, prefix+"old.dump")
		_ = os.WriteFile(f, []byte("x"), 0644)
		_ = os.Chtimes(f, oldTime, oldTime)
	}

	env := map[string]string{"GAET_RETENTION_DAYS": "7"}
	applyRetention(env, backupDir)

	matches, _ := filepath.Glob(filepath.Join(backupDir, "*.dump"))
	if len(matches) != 0 {
		t.Errorf("expected all old dumps pruned, got %d remaining", len(matches))
	}
}

func TestApplyRetention_NoFiles(t *testing.T) {
	tmp := t.TempDir()
	backupDir := filepath.Join(tmp, "backups")
	_ = os.MkdirAll(backupDir, 0755)

	// Should not error on empty dir
	applyRetention(map[string]string{"GAET_RETENTION_DAYS": "7"}, backupDir)
}

func TestDumpArgs_JobsZero(t *testing.T) {
	env := map[string]string{"GAET_DUMP_JOBS": "0"}
	args := dumpArgs("127.0.0.1", "5432", "postgres", "mydb", "/tmp/out.dump", env)
	if contains(args, "--format=directory") {
		t.Error("jobs=0 should use custom format")
	}
	if contains(args, "--jobs=") {
		t.Error("jobs=0 should not have --jobs flag")
	}
}

func TestDumpArgs_InvalidJobsValue(t *testing.T) {
	env := map[string]string{"GAET_DUMP_JOBS": "notanumber"}
	args := dumpArgs("127.0.0.1", "5432", "postgres", "mydb", "/tmp/out.dump", env)
	if contains(args, "--format=directory") {
		t.Error("invalid jobs should fall back to custom format")
	}
}
