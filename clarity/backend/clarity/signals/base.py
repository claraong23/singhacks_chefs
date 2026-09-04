"""Signal plumbing: shared context, priority scoring and the registry.

A *signal* is a deterministic check that looks at one client and returns zero or
more :class:`~clarity.contracts.Insight` objects. Signals never call a language
model and never invent a number. They are ordinary Python functions, so each one
can be unit-tested against a fixture.

The priority score is deliberately simple arithmetic over three inputs, and
every insight carries the reasons that produced it. An RM who cannot explain why
a client is at the top of her list will not trust the list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Callable, Iterable

from .. import config
from ..analytics import attribution as attribution_mod
from ..analytics import collateral as collateral_mod
from ..analytics import liquidity as liquidity_mod
from ..analytics import lookthrough, mandate as mandate_mod, valuation
from ..contracts import Category, Insight, Severity
from ..loaders import DataBook, days_between, get_book


@dataclass
class SignalContext:
    """Everything a signal needs about one client, computed once."""

    book: DataBook
    client_id: str
    snapshot: str = config.AS_OF

    @property
    def client(self) -> dict[str, Any]:
        return self.book.client(self.client_id)

    @cached_property
    def view(self) -> valuation.HouseholdView:
        return valuation.household_view(self.book, self.client_id, self.snapshot)

    @cached_property
    def view_prior(self) -> valuation.HouseholdView:
        return valuation.household_view(
            self.book, self.client_id, config.PRIOR_SNAPSHOT
        )

    @cached_property
    def timeseries(self) -> list[valuation.SnapshotPoint]:
        return valuation.household_timeseries(self.book, self.client_id)

    @cached_property
    def mandate_reviews(self) -> list[mandate_mod.MandateReview]:
        return mandate_mod.review_client(self.book, self.client_id, self.snapshot)

    @cached_property
    def facilities(self) -> list[collateral_mod.FacilityView]:
        return collateral_mod.client_facilities(self.book, self.client_id)

    @cached_property
    def liquidity(self) -> liquidity_mod.LiquidityView:
        return liquidity_mod.liquidity_view(self.book, self.client_id, self.view)

    @cached_property
    def ytd(self) -> attribution_mod.AttributionResult:
        return attribution_mod.attribute(
            self.book, self.client_id, config.BASELINE_SNAPSHOT, self.snapshot
        )

    @cached_property
    def recent(self) -> attribution_mod.AttributionResult:
        return attribution_mod.attribute(
            self.book, self.client_id, config.PRIOR_SNAPSHOT, self.snapshot
        )

    @cached_property
    def issuer_exposures(self) -> list[lookthrough.Exposure]:
        return lookthrough.issuer_exposures(self.view)

    @cached_property
    def theme_exposures(self) -> list[lookthrough.Exposure]:
        return lookthrough.theme_exposures(self.view)

    @cached_property
    def notes(self) -> list[dict[str, Any]]:
        return self.book.notes_by_client.get(self.client_id, [])

    @cached_property
    def waiver_notes(self) -> list[dict[str, Any]]:
        return mandate_mod.waiver_notes(self.book, self.client_id)

    def theme(self, key: str) -> lookthrough.Exposure | None:
        for exposure in self.theme_exposures:
            if exposure.key == key:
                return exposure
        return None

    def notes_matching(self, *terms: str) -> list[dict[str, Any]]:
        lowered = [t.lower() for t in terms]
        return [
            n
            for n in self.notes
            if any(t in (n.get("note") or "").lower() for t in lowered)
        ]

    def days_until(self, when: str | None) -> int | None:
        return None if not when else days_between(config.AS_OF, when)


# ---------------------------------------------------------------------------
# Priority scoring
# ---------------------------------------------------------------------------


def _urgency(days: int | None) -> tuple[float, str]:
    if days is None:
        return 0.30, "No dated deadline; scored as background risk"
    if days < 0:
        return 1.00, f"Already {abs(days)} days past due"
    if days == 0:
        return 1.00, "Live today"
    if days <= 30:
        return 1.00, f"Due in {days} days"
    if days <= 90:
        return 0.80, f"Due in {days} days"
    if days <= 180:
        return 0.60, f"Due in about {round(days / 30)} months"
    if days <= 365:
        return 0.40, f"Due in about {round(days / 30)} months"
    return 0.20, f"Due in about {round(days / 365, 1)} years"


def priority(
    severity: Severity,
    *,
    materiality_pct: float | None = None,
    days_until: int | None = None,
    amount_usd: float | None = None,
) -> tuple[float, list[str]]:
    """Blend severity, size and time pressure into a 0-100 score.

    Weights are 45 / 30 / 25. They are a judgement, not a discovery, and are
    stated here so a reviewer can disagree with them explicitly.
    """
    severity_component = severity.weight
    reasons = [f"Severity {severity.value} (weight {severity_component:.2f})"]

    if materiality_pct is None:
        materiality = 0.35
        reasons.append("Size not quantified; scored at the book average")
    else:
        materiality = min(1.0, max(0.0, materiality_pct / 30.0))
        detail = f"Affects {materiality_pct:.1f}% of household wealth"
        if amount_usd:
            detail += f" (USD {amount_usd:,.0f})"
        reasons.append(detail)

    urgency, urgency_reason = _urgency(days_until)
    reasons.append(urgency_reason)

    score = 100 * (0.45 * severity_component + 0.30 * materiality + 0.25 * urgency)
    return score, reasons


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SignalFn = Callable[[SignalContext], Iterable[Insight]]

_REGISTRY: list[tuple[str, SignalFn]] = []


def signal(name: str) -> Callable[[SignalFn], SignalFn]:
    """Register a check. Order of registration does not affect ranking."""

    def decorator(fn: SignalFn) -> SignalFn:
        _REGISTRY.append((name, fn))
        return fn

    return decorator


def registered() -> list[tuple[str, SignalFn]]:
    return list(_REGISTRY)


def run_for_client(
    client_id: str, book: DataBook | None = None, snapshot: str = config.AS_OF
) -> list[Insight]:
    """Run every registered check against one client, ranked by priority."""
    ctx = SignalContext(book=book or get_book(), client_id=client_id, snapshot=snapshot)
    insights: list[Insight] = []
    for name, fn in _REGISTRY:
        try:
            produced = list(fn(ctx) or [])
        except Exception as exc:  # a broken check must not take down the book
            insights.append(
                Insight(
                    id=f"{client_id}-{name}-error",
                    client_id=client_id,
                    category=Category.DATA_QUALITY,
                    severity=Severity.INFO,
                    headline=f"Check '{name}' could not be evaluated",
                    summary=(
                        "This check failed to run, so anything it would have found is "
                        f"missing from this client's list. Error: {exc}"
                    ),
                    priority_score=1.0,
                    priority_reasons=["Engine error, surfaced rather than hidden"],
                )
            )
            continue
        insights.extend(produced)

    insights.sort(key=lambda i: (-i.priority_score, i.id))
    return insights


def run_for_book(book: DataBook | None = None) -> dict[str, list[Insight]]:
    book = book or get_book()
    return {cid: run_for_client(cid, book) for cid in book.clients}
