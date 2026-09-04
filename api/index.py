"""Vercel Python Function entry point for the Clarity API."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "clarity" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from clarity.api import ClarityHandler as handler  # noqa: E402,F401
