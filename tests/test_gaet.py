"""Tests for gaet core utilities."""

import os
import sys
import unittest
from pathlib import Path

# src-layout: prefer the src/gaet package over the root gaet.py shim.
# Insertion order matters — root must be added FIRST so src lands ahead of it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gaet import (
    parse_remote_url,
    mask_url_password,
    get_env_str,
    get_env_int,
    get_local_db,
    _is_socket_host,
    _local_config_lines,
    _build_env_content,
    _socket_port,
    _find_socket_paths,
)


class TestParseRemoteURL(unittest.TestCase):
    def test_full_url_with_password(self):
        url = "postgresql://user:pass@host:5432/db"
        p = parse_remote_url(url)
        self.assertIsNotNone(p)
        self.assertEqual(p["user"], "user")
        self.assertEqual(p["pass"], "pass")
        self.assertEqual(p["host"], "host")
        self.assertEqual(p["port"], "5432")
        self.assertEqual(p["db"], "db")

    def test_url_without_password(self):
        url = "postgresql://user@host:5432/db"
        p = parse_remote_url(url)
        self.assertIsNotNone(p)
        self.assertEqual(p["user"], "user")
        self.assertEqual(p["pass"], "")
        self.assertEqual(p["host"], "host")
        self.assertEqual(p["port"], "5432")
        self.assertEqual(p["db"], "db")

    def test_url_with_empty_password(self):
        url = "postgresql://user:@host:5432/db"
        p = parse_remote_url(url)
        self.assertIsNotNone(p)
        self.assertEqual(p["user"], "user")
        self.assertEqual(p["pass"], "")
        self.assertEqual(p["host"], "host")
        self.assertEqual(p["port"], "5432")
        self.assertEqual(p["db"], "db")

    def test_pg_url(self):
        url = "postgres://user:pass@host:5432/db"
        p = parse_remote_url(url)
        self.assertIsNotNone(p)
        self.assertEqual(p["user"], "user")
        self.assertEqual(p["pass"], "pass")

    def test_unix_socket_url(self):
        url = "postgresql://postgres@/tmp:5433/cloud_test"
        p = parse_remote_url(url)
        self.assertIsNotNone(p)
        self.assertEqual(p["user"], "postgres")
        self.assertEqual(p["host"], "/tmp")
        self.assertEqual(p["port"], "5433")
        self.assertEqual(p["db"], "cloud_test")

    def test_empty_url(self):
        self.assertIsNone(parse_remote_url(""))

    def test_invalid_url(self):
        self.assertIsNone(parse_remote_url("not-a-url"))


class TestMaskURLPassword(unittest.TestCase):
    def test_mask_password(self):
        url = "postgresql://user:secret123@host:5432/db"
        masked = mask_url_password(url)
        self.assertNotIn("secret123", masked)
        self.assertIn(":****@", masked)

    def test_no_password(self):
        url = "postgresql://user@host:5432/db"
        self.assertEqual(mask_url_password(url), url)

    def test_empty_string(self):
        self.assertEqual(mask_url_password(""), "")


class TestGetEnvStr(unittest.TestCase):
    def setUp(self):
        self._os_key = "GAET_TEST_KEY"
        if self._os_key in os.environ:
            self._old_val = os.environ[self._os_key]
        else:
            self._old_val = None

    def tearDown(self):
        if self._old_val is not None:
            os.environ[self._os_key] = self._old_val
        elif self._os_key in os.environ:
            del os.environ[self._os_key]

    def test_os_env_priority(self):
        env = {self._os_key: "file_val"}
        os.environ[self._os_key] = "os_val"
        self.assertEqual(get_env_str(env, self._os_key, "default"), "os_val")

    def test_env_dict_fallback(self):
        env = {self._os_key: "file_val"}
        self.assertEqual(get_env_str(env, self._os_key, "default"), "file_val")

    def test_default_fallback(self):
        self.assertEqual(get_env_str({}, "NONEXISTENT", "default"), "default")

    def test_empty_default(self):
        self.assertEqual(get_env_str({}, "NONEXISTENT"), "")


class TestGetEnvInt(unittest.TestCase):
    def test_valid_int(self):
        self.assertEqual(get_env_int({"KEY": "42"}, "KEY", 0), 42)

    def test_invalid_int_returns_default(self):
        self.assertEqual(get_env_int({"KEY": "abc"}, "KEY", 10), 10)

    def test_missing_key_returns_default(self):
        self.assertEqual(get_env_int({}, "KEY", 10), 10)

    def test_empty_value_returns_default(self):
        self.assertEqual(get_env_int({"KEY": ""}, "KEY", 10), 10)


class TestLocalConfigLines(unittest.TestCase):
    """Regression tests for the socket-host config fix (v2.0.1)."""

    def test_tcp_host_uses_url(self):
        lines, pass_line, _ = _local_config_lines("127.0.0.1", "5432", "postgres", "mydb", "")
        self.assertIn("GAET_LOCAL_URL=postgresql://postgres@127.0.0.1:5432/mydb", lines)
        self.assertNotIn("GAET_LOCAL_DB_HOST", lines)
        self.assertTrue(pass_line.startswith("#"))

    def test_socket_host_uses_individual_vars(self):
        lines, pass_line, _ = _local_config_lines("/run/postgresql", "5432", "pg", "appdb", "s3cret")
        # A socket path cannot be encoded in a postgres:// URL — individual
        # vars must be written instead (v2.0.1 regression fix).
        self.assertNotIn("GAET_LOCAL_URL", lines)
        self.assertIn("GAET_LOCAL_DB_HOST=/run/postgresql", lines)
        self.assertIn("GAET_LOCAL_DB_PORT=5432", lines)
        self.assertIn("GAET_LOCAL_DB_USER=pg", lines)
        self.assertIn("GAET_LOCAL_DB_NAME=appdb", lines)
        self.assertEqual(pass_line, "GAET_LOCAL_DB_PASS=s3cret")

    def test_build_env_content_has_no_indentation(self):
        """.env must be sourceable — every line flush-left (dedent bug fix)."""
        content = _build_env_content(
            "/run/postgresql", "5432", "pg", "appdb", "pw", "", "7"
        )
        for line in content.splitlines():
            if line and not line.startswith("#"):
                # KEY=value lines must start at column 0
                self.assertFalse(line.startswith(" "), f"indented line: {line!r}")
        # socket vars present, no GAET_LOCAL_URL
        self.assertIn("GAET_LOCAL_DB_HOST=/run/postgresql", content)
        self.assertNotIn("GAET_LOCAL_URL", content)

    def test_socket_config_roundtrips_through_get_local_db(self):
        """The config written for a socket host must parse back correctly."""
        env = {
            "GAET_LOCAL_DB_HOST": "/var/run/postgresql",
            "GAET_LOCAL_DB_PORT": "5433",
            "GAET_LOCAL_DB_USER": "postgres",
            "GAET_LOCAL_DB_NAME": "mydb",
            "GAET_LOCAL_DB_PASS": "pw",
        }
        h, p, u, n, w = get_local_db(env)
        self.assertEqual(h, "/var/run/postgresql")
        self.assertEqual(p, "5433")
        self.assertEqual(u, "postgres")
        self.assertEqual(n, "mydb")
        self.assertEqual(w, "pw")

    def test_is_socket_host(self):
        self.assertTrue(_is_socket_host("/run/postgresql"))
        self.assertFalse(_is_socket_host("127.0.0.1"))
        self.assertFalse(_is_socket_host(""))


class TestSocketAutoDetect(unittest.TestCase):
    """Regression tests for the socket auto-detect fix (v2.0.1)."""

    def test_socket_port_extracts_from_filename(self):
        # Port lives in the filename, not the dir — the old code hardcoded
        # "5432" and failed every socket on a non-default port.
        self.assertEqual(_socket_port("/tmp/.s.PGSQL.5433"), "5433")
        self.assertEqual(_socket_port("/run/postgresql/.s.PGSQL.5432"), "5432")

    def test_socket_port_fallback(self):
        self.assertEqual(_socket_port("/tmp/not-a-socket"), "5432")

    def test_find_socket_paths_skips_lock_files(self):
        # A directory can't be a real socket path list; assert the filter
        # excludes *.lock when scanning real dirs.
        paths = _find_socket_paths()
        self.assertIsInstance(paths, list)
        for p in paths:
            self.assertNotIn(".lock", p)


if __name__ == "__main__":
    unittest.main()
