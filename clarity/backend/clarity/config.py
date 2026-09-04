"""Static configuration for the Clarity wealth-intelligence engine.

Everything here is deliberately explicit rather than inferred, so a reviewer can
see the conventions the numbers were computed under.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# clarity/backend/clarity/config.py -> repo root is three levels up.
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("CLARITY_DATA_DIR", REPO_ROOT))
FIXTURES_DIR = REPO_ROOT / "clarity" / "fixtures"

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

#: The dataset's "today". Every ageing calculation is relative to this date, not
#: to the machine clock, so the demo is reproducible.
AS_OF = "2026-08-26"

#: The five dated snapshots, oldest first. Comparing these is where the
#: explanation capability lives; a single snapshot cannot support it.
SNAPSHOTS: tuple[str, ...] = (
    "2025-12-31",
    "2026-02-27",
    "2026-03-31",
    "2026-06-30",
    "2026-08-26",
)

SNAPSHOT_LABELS: dict[str, str] = {
    "2025-12-31": "Year-end 2025",
    "2026-02-27": "Pre-conflict",
    "2026-03-31": "Post-Hormuz",
    "2026-06-30": "Half-year",
    "2026-08-26": "Today",
}

PRIOR_SNAPSHOT = SNAPSHOTS[-2]
BASELINE_SNAPSHOT = SNAPSHOTS[0]

# ---------------------------------------------------------------------------
# Domain vocabulary
# ---------------------------------------------------------------------------

ASSET_CLASSES: tuple[str, ...] = (
    "Cash and Equivalents",
    "Fixed Income",
    "Equity",
    "Alternatives",
    "Commodities",
    "Structured Products",
)

#: Ordered from most to least sellable. Used to bucket what a client can
#: actually raise, and to constrain any funding suggestion.
LIQUIDITY_TIERS: tuple[str, ...] = (
    "Daily",
    "Weekly",
    "Monthly",
    "Quarterly Gate",
    "Illiquid",
)

#: Tiers we are willing to describe as "readily realisable" inside 30 days.
READILY_REALISABLE = ("Daily", "Weekly")

#: Custody portfolios sit in the wealth view but are not governed by a bank
#: mandate, so mandate breach checks must skip them.
UNMANAGED_SERVICE_MODELS = ("Custody",)

# ---------------------------------------------------------------------------
# Thresholds (all inspectable, all quoted in the evidence payload)
# ---------------------------------------------------------------------------

#: A mandate breach smaller than this is reported as drift, not a breach.
MANDATE_TOLERANCE_PCT = 0.5

#: Household single-name exposure above this is worth a conversation even when
#: no individual mandate limit is broken.
HOUSEHOLD_CONCENTRATION_WARN_PCT = 15.0
HOUSEHOLD_CONCENTRATION_HIGH_PCT = 25.0

#: Distance to the margin-call trigger, in LTV percentage points.
LTV_WARN_HEADROOM_PP = 10.0
LTV_CRITICAL_HEADROOM_PP = 5.0

#: Cash needs falling inside this horizon are treated as funding pressure.
NEAR_TERM_MONTHS = 18

#: Coverage ratio (readily realisable assets ÷ near-term obligations) below
#: which we raise a liquidity signal.
LIQUIDITY_COVER_WARN = 1.5
LIQUIDITY_COVER_CRITICAL = 1.0

#: A KYC review this many days past due is flagged as an admin action.
KYC_OVERDUE_WARN_DAYS = 0
