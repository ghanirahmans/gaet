"""Unit tests for gaet remote and gaet snapshots commands."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src layout to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gaet.remote import cmd_remote
from gaet.snapshots import cmd_snapshots


class TestGaetRemote(unittest.TestCase):
    def setUp(self):
        self.args = MagicMock()
        self.args.remote_action = "show"
        self.args.url = None
        self.args.json = False

    @patch("gaet.remote.set_env_key")
    def test_remote_set_url_success(self, mock_set_key):
        self.args.remote_action = "set-url"
        self.args.url = "postgresql://user:pass@127.0.0.1:5432/mydb"
        cmd_remote(self.args)
        mock_set_key.assert_called_with("GAET_REMOTE_URL", "postgresql://user:pass@127.0.0.1:5432/mydb")

    @patch("gaet.remote.set_env_key")
    def test_remote_set_url_invalid_dies(self, mock_set_key):
        self.args.remote_action = "set-url"
        self.args.url = "invalid_url_format"
        with self.assertRaises(SystemExit):
            cmd_remote(self.args)

    @patch("gaet.remote.set_env_key")
    def test_remote_remove(self, mock_set_key):
        self.args.remote_action = "remove"
        cmd_remote(self.args)
        mock_set_key.assert_called_with("GAET_REMOTE_URL", "")


class TestGaetSnapshots(unittest.TestCase):
    def setUp(self):
        self.args = MagicMock()
        self.args.json = False

    @patch("pathlib.Path.glob", return_value=[])
    def test_snapshots_empty(self, mock_glob):
        cmd_snapshots(self.args)

    def test_snapshots_with_files(self):
        fake_dump = MagicMock()
        fake_dump.name = "gaet_20260816_120000.dump"
        fake_dump.stat.return_value.st_size = 2097152
        fake_dump.stat.return_value.st_mtime = 1700000000

        with patch("pathlib.Path.glob", return_value=[fake_dump]):
            cmd_snapshots(self.args)


if __name__ == "__main__":
    unittest.main()
