"""Unit tests for gaet restore command."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src layout to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gaet.backup import cmd_restore


class TestGaetRestore(unittest.TestCase):
    def setUp(self):
        self.args = MagicMock()
        self.args.dry_run = False
        self.args.yes = False
        self.args.json = False
        self.args.target = "latest"

    @patch("pathlib.Path.glob", return_value=[])
    def test_restore_no_dump_files_dies(self, mock_glob):
        with self.assertRaises(SystemExit):
            cmd_restore(self.args)

    @patch("gaet.backup.find_pg_tools", return_value={"pg_dump": "/usr/bin/pg_dump", "pg_restore": "/usr/bin/pg_restore", "psql": "/usr/bin/psql"})
    @patch("gaet.backup.check_tools", return_value=True)
    @patch("gaet.backup.check_local_db", return_value=("127.0.0.1", "5432", "postgres", "mydb", "secret"))
    def test_restore_dry_run(self, mock_db, mock_tools, mock_find):
        fake_dump = MagicMock()
        fake_dump.name = "gaet_20260816_120000.dump"
        fake_dump.stat.return_value.st_size = 1048576
        fake_dump.stat.return_value.st_mtime = 1000

        self.args.dry_run = True
        with patch("pathlib.Path.glob", return_value=[fake_dump]):
            cmd_restore(self.args)

    @patch("sys.stdin.isatty", return_value=False)
    @patch("gaet.backup.find_pg_tools", return_value={"pg_dump": "/usr/bin/pg_dump", "pg_restore": "/usr/bin/pg_restore", "psql": "/usr/bin/psql"})
    @patch("gaet.backup.check_tools", return_value=True)
    @patch("gaet.backup.check_local_db", return_value=("127.0.0.1", "5432", "postgres", "mydb", "secret"))
    def test_restore_non_tty_without_yes_dies(self, mock_db, mock_tools, mock_find, mock_tty):
        fake_dump = MagicMock()
        fake_dump.name = "gaet_20260816_120000.dump"
        fake_dump.stat.return_value.st_size = 1048576
        fake_dump.stat.return_value.st_mtime = 1000

        with patch("pathlib.Path.glob", return_value=[fake_dump]):
            with self.assertRaises(SystemExit):
                cmd_restore(self.args)


if __name__ == "__main__":
    unittest.main()
