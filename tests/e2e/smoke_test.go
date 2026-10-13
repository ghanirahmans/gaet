//go:build e2e

package e2e

import (
	"testing"
)

func TestE2E_BootstrapSmoke(t *testing.T) {
	ensureDBAvailable(t)
	if testLocalURL == "" {
		t.Fatal("testLocalURL is empty")
	}
	if testRemoteURL == "" {
		t.Fatal("testRemoteURL is empty")
	}
	t.Logf("local URL: %s", testLocalURL)
	t.Logf("remote URL: %s", testRemoteURL)
	t.Logf("binary: %s", binaryPath)
}

func TestE2E_SeedAndVerify(t *testing.T) {
	ensureDBAvailable(t)
	resetDBs(t)
	assertRowCounts(t, testRemoteURL)
	assertRowCounts(t, testLocalURL)
}