"""Start the Clarity API from the repository root.

The backend is a package rooted at ``clarity/backend``.  This small launcher
keeps that package boundary intact while making the common VS Code workspace
command work without requiring a directory change.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = REPO_ROOT / "clarity" / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

runpy.run_module("clarity.api", run_name="__main__")
