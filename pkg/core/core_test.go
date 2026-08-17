// Package core_test contains unit tests for pkg/core — parity with Python tests/test_gaet.py
package core_test

import (
	"os"
	"strings"
	"testing"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// ═══════════════════════════════════════════════════════
// TestParseRemoteURL — parity: TestParseRemoteURL (py)
// ═══════════════════════════════════════════════════════

func TestParseRemoteURL_FullURLWithPassword(t *testing.T) {
	p, err := core.ParseRemoteURL("postgresql://user:pass@host:5432/db")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	assertEqual(t, p.User, "user")
	assertEqual(t, p.Password, "pass")
	assertEqual(t, p.Host, "host")
	assertEqual(t, p.Port, "5432")
	assertEqual(t, p.DB, "db")
}

func TestParseRemoteURL_WithoutPassword(t *testing.T) {
	p, err := core.ParseRemoteURL("postgresql://user@host:5432/db")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	assertEqual(t, p.User, "user")
	assertEqual(t, p.Password, "")
	assertEqual(t, p.Host, "host")
	assertEqual(t, p.Port, "5432")
	assertEqual(t, p.DB, "db")
}

func TestParseRemoteURL_EmptyPassword(t *testing.T) {
	p, err := core.ParseRemoteURL("postgresql://user:@host:5432/db")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	assertEqual(t, p.User, "user")
	assertEqual(t, p.Password, "")
	assertEqual(t, p.Host, "host")
	assertEqual(t, p.Port, "5432")
	assertEqual(t, p.DB, "db")
}

func TestParseRemoteURL_PostgresScheme(t *testing.T) {
	p, err := core.ParseRemoteURL("postgres://user:pass@host:5432/db")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	assertEqual(t, p.User, "user")
	assertEqual(t, p.Password, "pass")
}

func TestParseRemoteURL_EmptyURL(t *testing.T) {
	_, err := core.ParseRemoteURL("")
	if err == nil {
		t.Fatal("expected error for empty URL, got nil")
	}
}

func TestParseRemoteURL_InvalidURL(t *testing.T) {
	_, err := core.ParseRemoteURL("not-a-url")
	if err == nil {
		t.Fatal("expected error for invalid URL, got nil")
	}
}

func TestParseRemoteURL_AtSignInPassword(t *testing.T) {
	// Password contains '@' — must split at the LAST '@'
	p, err := core.ParseRemoteURL("postgresql://user:p@ss@host:5432/db")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	assertEqual(t, p.User, "user")
	assertEqual(t, p.Password, "p@ss")
	assertEqual(t, p.Host, "host")
}

func TestParseRemoteURL_DefaultPort(t *testing.T) {
	// URL without explicit port — should default to 5432
	p, err := core.ParseRemoteURL("postgresql://user:pass@host/db")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	assertEqual(t, p.Port, "5432")
}

func TestParseRemoteURL_QueryStringStripped(t *testing.T) {
	p, err := core.ParseRemoteURL("postgresql://user:pass@host:5432/db?sslmode=require")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	assertEqual(t, p.DB, "db")
}

// ═══════════════════════════════════════════════════════
// TestMaskURLPassword — parity: TestMaskURLPassword (py)
// ═══════════════════════════════════════════════════════

func TestMaskURLPassword_WithPassword(t *testing.T) {
	url := "postgresql://user:secret123@host:5432/db"
	masked := core.MaskURLPassword(url)
	if strings.Contains(masked, "secret123") {
		t.Errorf("password leaked in masked URL: %s", masked)
	}
	if !strings.Contains(masked, ":****@") {
		t.Errorf("expected ':****@' in masked URL, got: %s", masked)
	}
}

func TestMaskURLPassword_NoPassword(t *testing.T) {
	url := "postgresql://user@host:5432/db"
	masked := core.MaskURLPassword(url)
	// No password to mask — URL should be returned unchanged
	if masked != url {
		t.Errorf("URL without password should be unchanged\ngot: %s\nwant: %s", masked, url)
	}
}

func TestMaskURLPassword_Empty(t *testing.T) {
	masked := core.MaskURLPassword("")
	if masked != "" {
		t.Errorf("empty URL should return empty, got: %s", masked)
	}
}

// ═══════════════════════════════════════════════════════
// TestGetEnvStr — parity: TestGetEnvStr (py)
// ═══════════════════════════════════════════════════════

func TestGetEnvStr_OSEnvPriority(t *testing.T) {
	key := "GAET_TEST_KEY_STR_PRIO"
	t.Setenv(key, "os_val")
	env := map[string]string{key: "file_val"}
	got := core.GetEnvStr(env, key, "default")
	assertEqual(t, got, "os_val")
}

func TestGetEnvStr_EnvDictFallback(t *testing.T) {
	key := "GAET_TEST_KEY_STR_DICT"
	os.Unsetenv(key)
	env := map[string]string{key: "file_val"}
	got := core.GetEnvStr(env, key, "default")
	assertEqual(t, got, "file_val")
}

func TestGetEnvStr_DefaultFallback(t *testing.T) {
	got := core.GetEnvStr(map[string]string{}, "GAET_NONEXISTENT_XYZ", "default")
	assertEqual(t, got, "default")
}

func TestGetEnvStr_EmptyDefault(t *testing.T) {
	got := core.GetEnvStr(map[string]string{}, "GAET_NONEXISTENT_XYZ", "")
	assertEqual(t, got, "")
}

// ═══════════════════════════════════════════════════════
// TestGetEnvInt — parity: TestGetEnvInt (py)
// ═══════════════════════════════════════════════════════

func TestGetEnvInt_ValidInt(t *testing.T) {
	got := core.GetEnvInt(map[string]string{"KEY": "42"}, "KEY", 0)
	if got != 42 {
		t.Errorf("expected 42, got %d", got)
	}
}

func TestGetEnvInt_InvalidIntReturnsDefault(t *testing.T) {
	got := core.GetEnvInt(map[string]string{"KEY": "abc"}, "KEY", 10)
	if got != 10 {
		t.Errorf("expected default 10, got %d", got)
	}
}

func TestGetEnvInt_MissingKeyReturnsDefault(t *testing.T) {
	got := core.GetEnvInt(map[string]string{}, "KEY", 10)
	if got != 10 {
		t.Errorf("expected default 10, got %d", got)
	}
}

func TestGetEnvInt_EmptyValueReturnsDefault(t *testing.T) {
	got := core.GetEnvInt(map[string]string{"KEY": ""}, "KEY", 10)
	if got != 10 {
		t.Errorf("expected default 10, got %d", got)
	}
}

// ═══════════════════════════════════════════════════════
// TestSocketPort — parity: TestSocketAutoDetect (py)
// ═══════════════════════════════════════════════════════

func TestSocketPort_ExtractsFromFilename(t *testing.T) {
	assertEqual(t, core.SocketPort("/tmp/.s.PGSQL.5433"), "5433")
	assertEqual(t, core.SocketPort("/run/postgresql/.s.PGSQL.5432"), "5432")
}

func TestSocketPort_Fallback(t *testing.T) {
	assertEqual(t, core.SocketPort("/tmp/not-a-socket"), "5432")
}

func TestFindSocketPaths_ExcludesLockFiles(t *testing.T) {
	paths := core.FindSocketPaths()
	for _, p := range paths {
		if strings.HasSuffix(p, ".lock") {
			t.Errorf("FindSocketPaths returned a .lock file: %s", p)
		}
	}
}

// ═══════════════════════════════════════════════════════
// TestGetLocalDB — parity: TestLocalConfigLines (py)
// ═══════════════════════════════════════════════════════

func TestGetLocalDB_IndividualVars(t *testing.T) {
	env := map[string]string{
		"GAET_LOCAL_DB_HOST": "/var/run/postgresql",
		"GAET_LOCAL_DB_PORT": "5433",
		"GAET_LOCAL_DB_USER": "postgres",
		"GAET_LOCAL_DB_NAME": "mydb",
		"GAET_LOCAL_DB_PASS": "pw",
	}
	h, p, u, n, w := core.GetLocalDB(env)
	assertEqual(t, h, "/var/run/postgresql")
	assertEqual(t, p, "5433")
	assertEqual(t, u, "postgres")
	assertEqual(t, n, "mydb")
	assertEqual(t, w, "pw")
}

func TestGetLocalDB_FromURL(t *testing.T) {
	env := map[string]string{
		"GAET_LOCAL_URL": "postgresql://alice:pw@127.0.0.1:5432/testdb",
	}
	h, p, u, n, w := core.GetLocalDB(env)
	assertEqual(t, h, "127.0.0.1")
	assertEqual(t, p, "5432")
	assertEqual(t, u, "alice")
	assertEqual(t, n, "testdb")
	assertEqual(t, w, "pw")
}

func TestGetLocalDB_Defaults(t *testing.T) {
	h, p, u, n, _ := core.GetLocalDB(map[string]string{})
	assertEqual(t, h, "127.0.0.1")
	assertEqual(t, p, "5432")
	assertEqual(t, u, "postgres")
	assertEqual(t, n, "postgres")
}

func TestGetLocalDB_IndividualVarsOverrideURL(t *testing.T) {
	// Individual vars take priority over GAET_LOCAL_URL
	env := map[string]string{
		"GAET_LOCAL_DB_HOST": "myhost",
		"GAET_LOCAL_URL":     "postgresql://other:pw@otherhost:5432/otherdb",
	}
	h, _, _, _, _ := core.GetLocalDB(env)
	assertEqual(t, h, "myhost")
}

// ═══════════════════════════════════════════════════════
// TestLoadEnv — env file parser
// ═══════════════════════════════════════════════════════

func TestLoadEnv_ParsesExportSyntax(t *testing.T) {
	tmp := writeTempEnv(t, "export GAET_FOO=bar\nexport GAET_BAZ=qux\n")
	env, err := core.LoadEnv(tmp)
	if err != nil {
		t.Fatalf("LoadEnv error: %v", err)
	}
	assertEqual(t, env["GAET_FOO"], "bar")
	assertEqual(t, env["GAET_BAZ"], "qux")
}

func TestLoadEnv_ParsesPlainKeyValue(t *testing.T) {
	tmp := writeTempEnv(t, "GAET_KEY=value\n")
	env, err := core.LoadEnv(tmp)
	if err != nil {
		t.Fatalf("LoadEnv error: %v", err)
	}
	assertEqual(t, env["GAET_KEY"], "value")
}

func TestLoadEnv_SkipsComments(t *testing.T) {
	tmp := writeTempEnv(t, "# This is a comment\nGAET_REAL=yes\n")
	env, err := core.LoadEnv(tmp)
	if err != nil {
		t.Fatalf("LoadEnv error: %v", err)
	}
	if _, ok := env["# This is a comment"]; ok {
		t.Error("LoadEnv should skip comment lines")
	}
	assertEqual(t, env["GAET_REAL"], "yes")
}

func TestLoadEnv_SkipsEmptyLines(t *testing.T) {
	tmp := writeTempEnv(t, "\nGAET_A=1\n\n")
	env, err := core.LoadEnv(tmp)
	if err != nil {
		t.Fatalf("LoadEnv error: %v", err)
	}
	if len(env) != 1 {
		t.Errorf("expected 1 key, got %d: %v", len(env), env)
	}
}

func TestLoadEnv_StripsSurroundingQuotes(t *testing.T) {
	tmp := writeTempEnv(t, "GAET_Q=\"hello world\"\nGAET_S='single'\n")
	env, err := core.LoadEnv(tmp)
	if err != nil {
		t.Fatalf("LoadEnv error: %v", err)
	}
	assertEqual(t, env["GAET_Q"], "hello world")
	assertEqual(t, env["GAET_S"], "single")
}

func TestLoadEnv_NonExistentFile(t *testing.T) {
	env, err := core.LoadEnv("/nonexistent/path/.env.xyz")
	if err != nil {
		t.Fatalf("should not error for missing file, got: %v", err)
	}
	if len(env) != 0 {
		t.Errorf("expected empty map for missing file, got %v", env)
	}
}

// ═══════════════════════════════════════════════════════
// TestPGEnv
// ═══════════════════════════════════════════════════════

func TestPGEnv_WithPassword(t *testing.T) {
	env := core.PGEnv("user", "secret", "require")
	if env["PGPASSWORD"] != "secret" {
		t.Errorf("PGPASSWORD mismatch: %v", env)
	}
	if env["PGSSLMODE"] != "require" {
		t.Errorf("PGSSLMODE mismatch: %v", env)
	}
}

func TestPGEnv_EmptyPasswordOmitted(t *testing.T) {
	env := core.PGEnv("user", "", "")
	if _, ok := env["PGPASSWORD"]; ok {
		t.Error("PGPASSWORD should not be set when password is empty")
	}
}

// ═══════════════════════════════════════════════════════
// TestPaths
// ═══════════════════════════════════════════════════════

func TestGaetDir_ContainsGaetInPath(t *testing.T) {
	d := core.GaetDir()
	if !strings.Contains(d, "gaet") {
		t.Errorf("GaetDir should contain 'gaet', got: %s", d)
	}
}

func TestBackupDir_IsSubdirOfGaetDir(t *testing.T) {
	if !strings.HasPrefix(core.BackupDir(), core.GaetDir()) {
		t.Errorf("BackupDir should be under GaetDir\nBackupDir: %s\nGaetDir: %s",
			core.BackupDir(), core.GaetDir())
	}
}

func TestEnvFile_EndsWithEnv(t *testing.T) {
	if !strings.HasSuffix(core.EnvFile(), ".env") {
		t.Errorf("EnvFile should end with .env, got: %s", core.EnvFile())
	}
}

// ═══════════════════════════════════════════════════════
// TestSetEnvKey
// ═══════════════════════════════════════════════════════

func TestSetEnvKey_AddsNewKey(t *testing.T) {
	tmp := writeTempEnv(t, "export GAET_A=1\n")
	if err := core.SetEnvKey(tmp, "GAET_B", "2"); err != nil {
		t.Fatalf("SetEnvKey error: %v", err)
	}
	env, _ := core.LoadEnv(tmp)
	assertEqual(t, env["GAET_B"], "2")
	assertEqual(t, env["GAET_A"], "1") // existing key preserved
}

func TestSetEnvKey_UpdatesExistingKey(t *testing.T) {
	tmp := writeTempEnv(t, "export GAET_A=old\n")
	if err := core.SetEnvKey(tmp, "GAET_A", "new"); err != nil {
		t.Fatalf("SetEnvKey error: %v", err)
	}
	env, _ := core.LoadEnv(tmp)
	assertEqual(t, env["GAET_A"], "new")
}

func TestSetEnvKey_DeletesKeyOnEmptyValue(t *testing.T) {
	tmp := writeTempEnv(t, "export GAET_A=1\nexport GAET_B=2\n")
	if err := core.SetEnvKey(tmp, "GAET_A", ""); err != nil {
		t.Fatalf("SetEnvKey error: %v", err)
	}
	env, _ := core.LoadEnv(tmp)
	if _, ok := env["GAET_A"]; ok {
		t.Error("GAET_A should have been deleted")
	}
	assertEqual(t, env["GAET_B"], "2") // other key preserved
}

// ═══════════════════════════════════════════════════════
// TestValidateTableName
// ═══════════════════════════════════════════════════════

func TestValidateTableName_ValidNames(t *testing.T) {
	for _, name := range []string{"users", "my_table", "Table1", "_private"} {
		if !core.ValidateTableName(name) {
			t.Errorf("ValidateTableName(%q) = false, want true", name)
		}
	}
}

func TestValidateTableName_InvalidNames(t *testing.T) {
	for _, name := range []string{"", "1table", "my-table", "my table", "drop;table"} {
		if core.ValidateTableName(name) {
			t.Errorf("ValidateTableName(%q) = true, want false", name)
		}
	}
}

// ═══════════════════════════════════════════════════════
// TestEnsureDir
// ═══════════════════════════════════════════════════════

func TestEnsureDir_CreatesNestedDirs(t *testing.T) {
	tmp := t.TempDir()
	target := tmp + "/a/b/c"
	if err := core.EnsureDir(target); err != nil {
		t.Fatalf("EnsureDir error: %v", err)
	}
	if _, err := os.Stat(target); err != nil {
		t.Errorf("directory not created: %v", err)
	}
}

func TestEnsureDir_IdempotentOnExisting(t *testing.T) {
	tmp := t.TempDir()
	if err := core.EnsureDir(tmp); err != nil {
		t.Fatalf("EnsureDir should be idempotent on existing dir: %v", err)
	}
}

// ═══════════════════════════════════════════════════════
// helper utilities
// ═══════════════════════════════════════════════════════

func assertEqual(t *testing.T, got, want string) {
	t.Helper()
	if got != want {
		t.Errorf("\ngot:  %q\nwant: %q", got, want)
	}
}

func writeTempEnv(t *testing.T, content string) string {
	t.Helper()
	f, err := os.CreateTemp(t.TempDir(), ".env")
	if err != nil {
		t.Fatalf("create temp env: %v", err)
	}
	f.WriteString(content)
	f.Close()
	return f.Name()
}
