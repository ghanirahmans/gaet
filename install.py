#!/usr/bin/env python3
"""
gaet — PostgreSQL backup & sync tool
Universal installer — detects OS, installs deps, configures, and builds.

Usage:
    python install.py              interactive
    python install.py --yes        auto-pilot
    python install.py --help       options
"""

import sys
import os

# Ensure scripts/ is in path
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)

try:
    from scripts.installer import main_cli
except ImportError:
    # Running from same directory
    try:
        from installer import main_cli
    except ImportError:
        print("Error: scripts/installer.py not found.")
        print("Jalankan dari folder root proyek gaet.")
        sys.exit(1)

if __name__ == "__main__":
    main_cli()
