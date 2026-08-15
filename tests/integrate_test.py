#!/usr/bin/env python3
"""Integration tests for gaet — tests against local PostgreSQL instance.

Run: python3 tests/integrate_test.py [--clean]
Prerequisites: PostgreSQL running on localhost with user ghaniyrahmans
"""
import subprocess, sys, os, time, tempfile, shutil
from pathlib import Path

ROOT = "/home/ghaniyrahmans/Projects/gaet"
GAET = os.path.join(ROOT, "gaet.py")
TEST_DB = "gaet_int_test"
PG_BIN = "/usr/pgsql-18/bin"
PSQL = os.path.join(PG_BIN, "psql")


def run(cmd, **kwargs):
    r = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def setup_db():
    """Create test database with schema."""
    # Remove existing DB if any
    run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-c", f"DROP DATABASE IF EXISTS {TEST_DB};"])
    run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-c", f"CREATE DATABASE {TEST_DB};"])
    # Create simple schema with FK relationship
    sql = """
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY, username VARCHAR(50) NOT NULL, email VARCHAR(120) NOT NULL, password_hash VARCHAR(255)
);
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY, user_id BIGINT REFERENCES users(id), total NUMERIC(10,2), status VARCHAR(20)
);
INSERT INTO users (username, email, password_hash) VALUES ('alice', 'alice@test.com', 'hash1'), ('bob', 'bob@test.com', 'hash2');
INSERT INTO orders (user_id, total, status) VALUES (1, 99.99, 'completed'), (2, 49.50, 'pending');
"""
    run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-d", TEST_DB, "-c", sql])


def teardown_db():
    run([PSQL, "-h", "127.0.0.1", "-U", "postgres", "-c", f"DROP DATABASE IF EXISTS {TEST_DB};"])


passed, failed = 0, 0


def check(name, cond, detail=""):
    global passed, failed
    status = "PASS" if cond else "FAIL"
    if cond:
        passed += 1
    else:
        failed += 1
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))


print("=" * 60)
print("gaet Integration Tests")
print("=" * 60)

# Setup
print("\n[Setup] Creating test database...")
setup_db()

# Test 1: gaet --version
print("\n[Test 1] gaet --version")
code, out, err = run([sys.executable, GAET, "--version"])
check("version shows 2.0.0", "2.0.0" in out and code == 0, f"rc={code}, out={out}")

# Test 2: gaet help
print("\n[Test 2] gaet help")
code, out, err = run([sys.executable, GAET, "help"])
check("help shows commands", code == 0 and len(out) > 100, out[:200])

# Test 3: gaet check (no cloud required)
print("\n[Test 3] gaet check")
code, out, err = run([sys.executable, GAET, "check"])
check("check runs without crash", code == 0, f"rc={code}")

# Test 4: gaet status
print("\n[Test 4] gaet status")
code, out, err = run([sys.executable, GAET, "status"])
check("status shows info", code == 0, f"rc={code}, stdout len={len(out)}")

# Test 5: gaet diff
print("\n[Test 5] gaet diff")
code, out, err = run([sys.executable, GAET, "diff"])
check("diff works", code == 0, f"rc={code}")

# Test 6: gaet doctor
print("\n[Test 6] gaet doctor")
code, out, err = run([sys.executable, GAET, "doctor"])
check("doctor works", code == 0, f"rc={code}")

# Test 7: gaet get/set/export
print("\n[Test 7] gaet get/set/export")
# Set a test variable (format: KEY=value)
code, out, err = run([sys.executable, GAET, "set", "TEST_INTEG_KEY=test_value_123"])
check("set works", "OK" in out or code == 0, f"rc={code}, out={out[:100]}")

# Get it back
code, out, err = run([sys.executable, GAET, "get", "TEST_INTEG_KEY"])
check("get returns value", "test_value_123" in out, f"rc={code}, out={out[:100]}")

# Delete it (empty value = delete)
code, out, err = run([sys.executable, GAET, "set", "TEST_INTEG_KEY="])
check("delete works", code == 0, f"rc={code}")

# Verify deleted
code, out, err = run([sys.executable, GAET, "get", "TEST_INTEG_KEY"])
check("deleted key not found", "not found" in out.lower() or "WARN" in out or "TEST_INTEG_KEY" not in out, out[:100])

# Export
code, out, err = run([sys.executable, GAET, "export"])
check("export works", "GAET_" in out, out[:100])

# Test 8: gaet completion (just verify no error)
print("\n[Test 8] gaet completion")
code, out, err = run([sys.executable, GAET, "completion", "--shell", "bash"])
check("completion works", code == 0, f"rc={code}")

# Test 9: gaet push/push --dry-run (with local only)
print("\n[Test 9] gaet push --dry-run")
code, out, err = run([sys.executable, GAET, "push", "--dry-run"])
check("dry-run works", code == 0, f"rc={code}, out={out[:200]}")

# Test 10: gaet log
print("\n[Test 10] gaet log")
code, out, err = run([sys.executable, GAET, "log"])
check("log works", code == 0, f"rc={code}")

# Test 11: gaet stop
print("\n[Test 11] gaet stop")
code, out, err = run([sys.executable, GAET, "stop"])
check("stop works", code == 0, f"rc={code}")

# Cleanup
print("\n[Cleanup] Removing test database...")
teardown_db()

# Summary
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
