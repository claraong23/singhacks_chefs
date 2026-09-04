"""Source data loading and normalisation.

Deliberately stdlib-only. The dataset is 1,015 holdings rows; pandas buys us
nothing here and costs us a dependency that has to work on four laptops the
morning of a demo. Everything downstream of this module is plain Python, so the
analytics can be imported by a notebook, a test, an API or a Streamlit fallback
without changing.

Loading is strict about two things and forgiving about everything else:

* Identifiers are the join keys. Display names are never used to join.
* Numbers are coerced once, here. Nothing downstream parses a string.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from functools import cached_property
from pathlib import Path
from typing import Any, Iterable

from . import config

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _num(value: Any) -> float | None:
    """Coerce a CSV cell to float, returning None for blanks and non-numerics."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"none", "n/a", "na", "null", "-"}:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_date(value: str) -> date | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def days_between(start: str, end: str) -> int | None:
    a, b = parse_date(start), parse_date(end)
    if a is None or b is None:
        return None
    return (b - a).days


def months_between(start: str, end: str) -> float | None:
    d = days_between(start, end)
    return None if d is None else d / 30.4375


#: Columns that are numeric wherever they appear.
_NUMERIC_HINTS = (
    "quantity",
    "price",
    "market_value",
    "weight",
    "cost",
    "pnl",
    "lending_value",
    "advance_rate",
    "amount",
    "aum",
    "pct",
    "limit",
    "drawn",
    "headroom",
    "committed",
    "called",
    "uncalled",
    "value",
    "score",
    "age",
    "years",
    "rate",
    "min_",
    "max_",
    "target_",
    "total_",
)


def _coerce_row(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, raw in row.items():
        if key is None:
            continue
        k = key.strip()
        value = _clean(raw)
        if any(hint in k for hint in _NUMERIC_HINTS):
            n = _num(value)
            out[k] = n if n is not None else (value or None)
        else:
            out[k] = value
    return out


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [_coerce_row(r) for r in csv.DictReader(fh)]


# ---------------------------------------------------------------------------
# The loaded book
# ---------------------------------------------------------------------------


@dataclass
class DataBook:
    """Every source file, normalised and indexed.

    Constructed once per process. Treat as read-only.
    """

    data_dir: Path = field(default_factory=lambda: config.DATA_DIR)

    clients: dict[str, dict[str, Any]] = field(default_factory=dict)
    portfolios: dict[str, dict[str, Any]] = field(default_factory=dict)
    instruments: dict[str, dict[str, Any]] = field(default_factory=dict)
    holdings: list[dict[str, Any]] = field(default_factory=list)
    transactions: list[dict[str, Any]] = field(default_factory=list)
    facilities: list[dict[str, Any]] = field(default_factory=list)
    commitments: list[dict[str, Any]] = field(default_factory=list)
    cash_needs: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)
    market: list[dict[str, Any]] = field(default_factory=list)
    mandates: dict[str, dict[str, Any]] = field(default_factory=dict)

    warnings: list[str] = field(default_factory=list)

    # -- construction -------------------------------------------------------

    @classmethod
    def load(cls, data_dir: Path | str | None = None) -> "DataBook":
        book = cls(data_dir=Path(data_dir) if data_dir else config.DATA_DIR)
        book._load()
        return book

    def _path(self, name: str) -> Path:
        p = self.data_dir / name
        if p.exists():
            return p
        nested = self.data_dir / "data" / name
        if nested.exists():
            return nested
        raise FileNotFoundError(f"Cannot find {name} under {self.data_dir}")

    def _load(self) -> None:
        self.clients = {r["client_id"]: r for r in read_csv(self._path("clients.csv"))}
        self.portfolios = {
            r["portfolio_id"]: r for r in read_csv(self._path("portfolios.csv"))
        }
        self.instruments = {
            r["instrument_id"]: r for r in read_csv(self._path("instruments.csv"))
        }
        self.holdings = read_csv(self._path("holdings.csv"))
        self.transactions = read_csv(self._path("transactions.csv"))
        self.facilities = read_csv(self._path("credit_facilities.csv"))
        self.commitments = read_csv(self._path("commitments.csv"))
        self.cash_needs = read_csv(self._path("planned_cash_needs.csv"))
        self.market = read_csv(self._path("market_context.csv"))
        self._load_events()
        self._load_mandates()
        self._load_notes()
        self._check_integrity()

    def _load_events(self) -> None:
        rows = read_csv(self._path("event_log.csv"))
        rows.sort(key=lambda r: r.get("event_date") or "")
        for i, row in enumerate(rows, start=1):
            row["event_id"] = f"EVT-{i:02d}"
            row["transmission_channels"] = [
                c.strip()
                for c in _clean(row.get("primary_transmission")).split(",")
                if c.strip()
            ]
        self.events = rows

    def _load_mandates(self) -> None:
        by_code: dict[str, dict[str, Any]] = {}
        for row in read_csv(self._path("mandates.csv")):
            code = row["mandate_code"]
            entry = by_code.setdefault(
                code,
                {
                    "mandate_code": code,
                    "mandate_name": row.get("mandate_name"),
                    "notes": row.get("mandate_notes"),
                    "max_single_position_pct": row.get("max_single_position_pct"),
                    "bands": {},
                },
            )
            entry["bands"][row["asset_class"]] = {
                "min_pct": row.get("min_pct"),
                "target_pct": row.get("target_pct"),
                "max_pct": row.get("max_pct"),
            }
        self.mandates = by_code

    def _load_notes(self) -> None:
        with self._path("rm_notes.json").open(encoding="utf-8") as fh:
            self.notes = json.load(fh)
        self.notes.sort(key=lambda n: n.get("note_date", ""))

    def _check_integrity(self) -> None:
        """Record referential and freshness problems rather than crashing.

        The dataset ships with a small number of deliberate real-world
        artefacts. Surfacing them is worth more than silently coping.
        """
        for h in self.holdings:
            if h.get("instrument_id") not in self.instruments:
                self.warnings.append(
                    f"holdings row references unknown instrument {h.get('instrument_id')}"
                )
            if h.get("portfolio_id") not in self.portfolios:
                self.warnings.append(
                    f"holdings row references unknown portfolio {h.get('portfolio_id')}"
                )
        for p in self.portfolios.values():
            if p.get("client_id") not in self.clients:
                self.warnings.append(
                    f"portfolio {p['portfolio_id']} references unknown client"
                )
        # Deduplicate while preserving order.
        seen: set[str] = set()
        self.warnings = [w for w in self.warnings if not (w in seen or seen.add(w))]

    # -- indices ------------------------------------------------------------

    @cached_property
    def portfolios_by_client(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {cid: [] for cid in self.clients}
        for p in self.portfolios.values():
            out.setdefault(p["client_id"], []).append(p)
        for group in out.values():
            group.sort(key=lambda p: p["portfolio_id"])
        return out

    @cached_property
    def holdings_by_client_date(self) -> dict[tuple[str, str], list[dict[str, Any]]]:
        out: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for h in self.holdings:
            out.setdefault((h["client_id"], h["snapshot_date"]), []).append(h)
        return out

    @cached_property
    def holdings_by_portfolio_date(self) -> dict[tuple[str, str], list[dict[str, Any]]]:
        out: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for h in self.holdings:
            out.setdefault((h["portfolio_id"], h["snapshot_date"]), []).append(h)
        return out

    @cached_property
    def notes_by_client(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for n in self.notes:
            out.setdefault(n["client_id"], []).append(n)
        return out

    @cached_property
    def transactions_by_client(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for t in self.transactions:
            out.setdefault(t["client_id"], []).append(t)
        for group in out.values():
            group.sort(key=lambda t: t.get("trade_date") or "")
        return out

    @cached_property
    def facilities_by_client(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for f in self.facilities:
            out.setdefault(f["client_id"], []).append(f)
        return out

    @cached_property
    def commitments_by_client(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for c in self.commitments:
            out.setdefault(c["client_id"], []).append(c)
        return out

    @cached_property
    def cash_needs_by_client(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for c in self.cash_needs:
            out.setdefault(c["client_id"], []).append(c)
        for group in out.values():
            group.sort(key=lambda c: c.get("due_from") or "")
        return out

    @cached_property
    def market_by_series(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for row in self.market:
            out.setdefault(row["series_id"], {})[row["snapshot_date"]] = row["value"]
        return out

    @cached_property
    def market_meta(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in self.market:
            out.setdefault(
                row["series_id"],
                {
                    "series_id": row["series_id"],
                    "series_name": row["series_name"],
                    "category": row["category"],
                    "unit": row["unit"],
                },
            )
        return out

    @cached_property
    def events_by_id(self) -> dict[str, dict[str, Any]]:
        return {e["event_id"]: e for e in self.events}

    # -- lookups ------------------------------------------------------------

    def client(self, client_id: str) -> dict[str, Any]:
        return self.clients[client_id]

    def instrument(self, instrument_id: str) -> dict[str, Any]:
        return self.instruments.get(instrument_id, {"instrument_id": instrument_id})

    def mandate_for(self, portfolio_id: str) -> dict[str, Any] | None:
        pf = self.portfolios.get(portfolio_id)
        if not pf:
            return None
        return self.mandates.get(pf.get("mandate_code"))

    def is_mandated(self, portfolio_id: str) -> bool:
        """Custody accounts are part of the wealth view but carry no mandate."""
        pf = self.portfolios.get(portfolio_id, {})
        return pf.get("service_model") not in config.UNMANAGED_SERVICE_MODELS

    def market_value(self, series_id: str, snapshot: str) -> float | None:
        return self.market_by_series.get(series_id, {}).get(snapshot)

    # -- FX -----------------------------------------------------------------

    def usd_per_unit(self, currency: str, snapshot: str) -> float | None:
        """USD value of one unit of ``currency`` at ``snapshot``.

        ``market_context.csv`` quotes each pair in market convention, so the
        direction has to be read off the series id rather than assumed.
        """
        ccy = (currency or "").upper()
        if ccy == "USD":
            return 1.0
        # Pairs quoted as USD per foreign unit.
        for series in (f"{ccy}USD",):
            rate = self.market_value(series, snapshot)
            if rate is not None:
                return rate
        # Pairs quoted as foreign units per USD.
        rate = self.market_value(f"USD{ccy}", snapshot)
        if rate:
            return 1.0 / rate
        return None

    def convert(
        self, amount: float, from_ccy: str, to_ccy: str, snapshot: str
    ) -> float | None:
        if amount is None:
            return None
        src = self.usd_per_unit(from_ccy, snapshot)
        dst = self.usd_per_unit(to_ccy, snapshot)
        if src is None or dst is None:
            return None
        return amount * src / dst

    def to_usd(self, amount: float, currency: str, snapshot: str) -> float | None:
        rate = self.usd_per_unit(currency, snapshot)
        return None if rate is None else amount * rate

    # -- snapshot-aware column access ---------------------------------------

    @staticmethod
    def dated(row: dict[str, Any], prefix: str, snapshot: str) -> Any:
        """Read a ``prefix_YYYY-MM-DD`` column, e.g. ``aum_2026-08-26``."""
        return row.get(f"{prefix}_{snapshot}")

    def snapshot_series(
        self, row: dict[str, Any], prefix: str, snapshots: Iterable[str] | None = None
    ) -> list[tuple[str, Any]]:
        return [
            (s, self.dated(row, prefix, s)) for s in (snapshots or config.SNAPSHOTS)
        ]


_CACHE: DataBook | None = None


def get_book(refresh: bool = False) -> DataBook:
    """Process-wide singleton. Loading takes about 30ms; caching keeps the API snappy."""
    global _CACHE
    if _CACHE is None or refresh:
        _CACHE = DataBook.load()
    return _CACHE
