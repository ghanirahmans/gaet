#!/usr/bin/env python3
"""gaet — PostgreSQL Backup & Sync CLI (entry shim).

v3 layout: real code lives in the gaet/ package; this file exists so the
single-file curl install flow (`curl ... | bash` via install.sh) keeps
working. Run `python3 gaet.py <command>` exactly like before.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gaet.cli import main

if __name__ == "__main__":
    main()
