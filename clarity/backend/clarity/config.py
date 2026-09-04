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
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
API_TOKEN = os.environ.get("CLARITY_API_TOKEN", "").strip()

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

# Low/info market findings below this share of household wealth are filtered as
# immaterial. High and critical findings are never suppressed by this rule.
ALERT_MIN_MATERIALITY_PCT = 0.10

# A dismissed alert reopens when its measured amount changes by at least this
# percentage, or when its severity increases. The original decision is retained.
ALERT_REOPEN_CHANGE_PCT = 10.0

#: Distance to the margin-call trigger, in LTV percentage points.
LTV_WARN_HEADROOM_PP = 10.0
LTV_CRITICAL_HEADROOM_PP = 5.0

#: Cash needs falling inside this horizon are treated as funding pressure.
NEAR_TERM_MONTHS = 18

#: Coverage ratio (readily realisable assets ÷ near-term obligations) below
#: which we raise a liquidity signal.
LIQUIDITY_COVER_WARN = 1.5
LIQUIDITY_COVER_CRITICAL = 1.0

# Scenario shocks are deliberately labelled as assumptions in every insight.
from .contracts import Assumption

SCENARIO_SHOCK_ASSUMPTION = Assumption(
    statement="The scenario applies the same percentage move to every instrument mapped to the theme.",
    basis="A simple sensitivity is appropriate for the first prototype; it is not a forecast or a stress-model calibration.",
    impact_if_wrong="Actual instruments may have different betas, payoffs, currencies, or nonlinear structured-product terms.",
)

#: A KYC review this many days past due is flagged as an admin action.
KYC_OVERDUE_WARN_DAYS = 0
