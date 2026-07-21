"""Tests for gaet core utilities."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gaet import (
    parse_remote_url,
    mask_url_password,
    get_env_str,
    get_env_int,
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


if __name__ == "__main__":
    unittest.main()
