#!/usr/bin/env python3
"""gaet — PostgreSQL Backup & Sync CLI (entry shim).

v3 layout: real code lives in the src/gaet package; this file exists so the
single-file curl install flow (`curl ... | bash` via install.sh) keeps
working. Run `python3 gaet.py <command>` exactly like before.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
# package candidates, in order:
#   <repo>/src            — source checkout
#   <install_root>/gaet_pkg — installed (install.sh puts the package HERE,
#                             NOT beside the binary: file `gaet` and dir
#                             `gaet/` cannot share a name in one dir)
for _cand in (os.path.join(_ROOT, "src"),
              os.path.join(_ROOT, "gaet_pkg"),
              _ROOT):
    if os.path.isdir(os.path.join(_cand, "gaet")):
        sys.path.insert(0, _cand)
        break

from gaet.cli import main

if __name__ == "__main__":
    main()
