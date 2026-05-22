#!/usr/bin/env python3
"""LoopX controller CLI facade.

The implementation lives in ``loopx_controller_core.py`` so this historical
entrypoint stays small while existing commands and imports keep working.
"""

from pathlib import Path
import sys


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from loopx_controller_core import *  # noqa: F401,F403,E402


if __name__ == "__main__":
    sys.exit(main())
