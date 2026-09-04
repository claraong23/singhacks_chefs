"""Signal checks.

Importing this package registers every check. Add a new module here and it
appears in the book automatically.
"""

from . import explain, governance, opportunities, planning, quality, risk, scenarios  # noqa: F401
from .base import (  # noqa: F401
    SignalContext,
    priority,
    registered,
    run_for_book,
    run_for_client,
    signal,
)

__all__ = [
    "SignalContext",
    "priority",
    "registered",
    "run_for_book",
    "run_for_client",
    "signal",
]
