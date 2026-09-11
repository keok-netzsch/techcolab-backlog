"""Launcher bundled with the Claude Code skill.

The deterministic implementation is installed at DA_SHARE_SCRIPT by
install-da-share.ps1. Keeping this small launcher in the skill lets the skill use
its own known directory while the implementation remains outside Claude's config.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

target = os.environ.get("DA_SHARE_SCRIPT")
if not target:
    print("ERROR: DA_SHARE_SCRIPT is not set. Run install-da-share.ps1 first.", file=sys.stderr)
    raise SystemExit(2)

target_path = Path(target).resolve()
if target_path == Path(__file__).resolve() or not target_path.is_file():
    print("ERROR: DA_SHARE_SCRIPT does not point to an installed D&A intake program.", file=sys.stderr)
    raise SystemExit(2)

sys.argv[0] = str(target_path)
runpy.run_path(str(target_path), run_name="__main__")
