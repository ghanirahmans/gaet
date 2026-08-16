"""Unit tests for gaet init UX, menu navigation, and error explanations."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src layout to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gaet.init import (
    _explain_connection_failure,
    _local_db_menu,
    _cmd_init_inner,
    cmd_init,
    PRESETS,
)


class TestExplainConnectionFailure(unittest.TestCase):
    def test_password_authentication_failed(self):
        err = "psql: error: connection to server at '127.0.0.1', port 5432 failed: FATAL: password authentication failed for user 'postgres'"
        explanation = _explain_connection_failure(err, "127.0.0.1", "5432", "postgres", "mydb")
        self.assertIn("Password untuk user 'postgres' salah", explanation)

    def test_role_does_not_exist(self):
        err = "FATAL: role 'alice' does not exist"
        explanation = _explain_connection_failure(err, "127.0.0.1", "5432", "alice", "mydb")
        self.assertIn("User 'alice' tidak ditemukan", explanation)

    def test_database_does_not_exist(self):
        err = "FATAL: database 'unknown_db' does not exist"
        explanation = _explain_connection_failure(err, "127.0.0.1", "5432", "postgres", "unknown_db")
        self.assertIn("Database 'unknown_db' tidak ditemukan", explanation)

    def test_connection_refused(self):
        err = "could not connect to server: Connection refused"
        explanation = _explain_connection_failure(err, "127.0.0.1", "5432", "postgres", "mydb")
        self.assertIn("PostgreSQL server tidak aktif", explanation)


class TestLocalDBMenu(unittest.TestCase):
    def setUp(self):
        self.detected = [
            {"host": "127.0.0.1", "port": "5432", "user": "postgres", "databases": "postgres, app_db", "default_db": "app_db"},
            {"host": "/run/postgresql", "port": "5433", "user": "dev", "databases": "dev_db", "default_db": "dev_db"},
        ]

    @patch("gaet.init.safe_input", side_effect=["1", "2"])
    def test_select_instance_1_directly(self, mock_input):
        h, p, u, n, w = _local_db_menu(self.detected, "", "", "", "", "")
        self.assertEqual(h, "127.0.0.1")
        self.assertEqual(p, "5432")
        self.assertEqual(u, "postgres")
        self.assertEqual(n, "app_db")

    @patch("gaet.init.safe_input", return_value="2")
    def test_select_instance_2_directly(self, mock_input):
        h, p, u, n, w = _local_db_menu(self.detected, "", "", "", "", "")
        self.assertEqual(h, "/run/postgresql")
        self.assertEqual(p, "5433")
        self.assertEqual(u, "dev")
        self.assertEqual(n, "dev_db")

    @patch("gaet.init.safe_input", return_value="D")
    def test_select_defaults(self, mock_input):
        h, p, u, n, w = _local_db_menu([], "", "", "myuser", "mydb", "secret")
        self.assertEqual(h, "127.0.0.1")
        self.assertEqual(p, "5432")
        self.assertEqual(u, "myuser")

    @patch("gaet.init.safe_input", return_value="Q")
    def test_quit_choice_exits(self, mock_input):
        with self.assertRaises(SystemExit):
            _local_db_menu(self.detected, "", "", "", "", "")


class TestCmdInitSignalGuard(unittest.TestCase):
    @patch("gaet.init._cmd_init_inner", side_effect=KeyboardInterrupt)
    def test_cmd_init_handles_keyboard_interrupt_cleanly(self, mock_inner):
        args = MagicMock()
        with self.assertRaises(SystemExit) as cm:
            cmd_init(args)
        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
