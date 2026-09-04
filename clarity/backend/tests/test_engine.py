"""Tests for the parts of the engine a judge is most likely to challenge.

Standard-library unittest, so this runs with ``python -m unittest`` on any
machine with Python and no install step.

    cd clarity/backend && python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest

from clarity import config
from clarity.actions import _repayment_to_target
from clarity.analytics import attribution, collateral, liquidity, lookthrough, mandate
from clarity.analytics.valuation import household_view
from clarity.contracts import Severity
from clarity.loaders import get_book
from clarity.signals import run_for_client
from clarity.signals.base import priority

BOOK = get_book()


class TestLoading(unittest.TestCase):
    def test_row_counts_match_the_data_dictionary(self) -> None:
        self.assertEqual(len(BOOK.clients), 20)
        self.assertEqual(len(BOOK.portfolios), 24)
        self.assertEqual(len(BOOK.holdings), 1015)
        self.assertEqual(len(BOOK.instruments), 62)
        self.assertEqual(len(BOOK.events), 16)
        self.assertEqual(len(BOOK.notes), 28)

    def test_no_referential_integrity_warnings(self) -> None:
        self.assertEqual(BOOK.warnings, [])

    def test_events_are_ordered_and_identified(self) -> None:
        dates = [e["event_date"] for e in BOOK.events]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(BOOK.events[0]["event_id"], "EVT-01")


class TestFx(unittest.TestCase):
    def test_direction_follows_the_quoting_convention(self) -> None:
        # USDSGD is SGD per USD, so one SGD is worth less than one USD.
        self.assertAlmostEqual(
            BOOK.usd_per_unit("SGD", "2026-08-26"), 1 / 1.352, places=6
        )
        # EURUSD is USD per EUR, so it is used as quoted.
        self.assertAlmostEqual(BOOK.usd_per_unit("EUR", "2026-08-26"), 1.092, places=6)
        self.assertEqual(BOOK.usd_per_unit("USD", "2026-08-26"), 1.0)

    def test_round_trip_conversion(self) -> None:
        amount = BOOK.convert(1_000_000, "HKD", "EUR", config.AS_OF)
        back = BOOK.convert(amount, "EUR", "HKD", config.AS_OF)
        self.assertAlmostEqual(back, 1_000_000, places=4)


class TestValuation(unittest.TestCase):
    def test_holdings_reconcile_to_portfolio_aum_at_every_snapshot(self) -> None:
        for portfolio_id, portfolio in BOOK.portfolios.items():
            for snapshot in config.SNAPSHOTS:
                rows = BOOK.holdings_by_portfolio_date.get((portfolio_id, snapshot), [])
                summed = sum(r.get("market_value_usd") or 0.0 for r in rows)
                stated = BOOK.dated(portfolio, "aum", snapshot)
                expected = BOOK.to_usd(
                    stated, portfolio.get("base_currency", "USD"), snapshot
                )
                self.assertAlmostEqual(
                    summed / expected,
                    1.0,
                    places=4,
                    msg=f"{portfolio_id} at {snapshot}",
                )

    def test_household_totals_match_the_client_file(self) -> None:
        for client_id, client in BOOK.clients.items():
            view = household_view(BOOK, client_id)
            self.assertAlmostEqual(
                view.total_usd / client["total_aum_usd"],
                1.0,
                places=4,
                msg=client_id,
            )

    def test_weights_sum_to_one_hundred(self) -> None:
        view = household_view(BOOK, "CL-0017")
        self.assertAlmostEqual(sum(p.weight_pct for p in view.positions), 100.0, places=6)


class TestAttribution(unittest.TestCase):
    def test_effects_sum_exactly_to_the_change(self) -> None:
        for client_id in BOOK.clients:
            result = attribution.attribute(BOOK, client_id)
            total = (
                result.price_effect_usd
                + result.fx_effect_usd
                + result.flow_effect_usd
            )
            # Relative tolerance: the decomposition is exact in algebra, so the
            # only difference allowed is float accumulation across positions.
            self.assertAlmostEqual(
                total,
                result.change_usd,
                delta=max(0.01, abs(result.change_usd) * 1e-9),
                msg=client_id,
            )

    def test_new_position_loss_is_a_price_effect_not_an_inflow(self) -> None:
        """CL-0014's accumulator cost HKD 25m and is marked far below that."""
        result = attribution.attribute(BOOK, "CL-0014")
        accumulator = next(
            c for c in result.contributions if c.instrument_id == "SYN-SP-0503"
        )
        self.assertGreater(accumulator.flow_effect_usd, 3_000_000)
        self.assertLess(accumulator.price_effect_usd, -1_000_000)
        self.assertAlmostEqual(
            accumulator.flow_effect_usd + accumulator.price_effect_usd,
            accumulator.end_value_usd,
            places=4,
        )


class TestLookThrough(unittest.TestCase):
    def test_golden_harbour_aggregates_three_wrappers(self) -> None:
        view = household_view(BOOK, "CL-0014")
        exposures = {e.key: e for e in lookthrough.issuer_exposures(view)}
        golden = exposures["GOLDEN_HARBOUR"]
        self.assertEqual(len(golden.legs), 3)
        self.assertEqual(
            {leg.instrument_id for leg in golden.legs},
            {"SYN-ST-0106", "SYN-FI-0207", "SYN-SP-0503"},
        )
        self.assertGreater(golden.pct_of_household, 25)
        self.assertTrue(golden.hidden)

    def test_every_issuer_leg_cites_a_source_field(self) -> None:
        for client_id in BOOK.clients:
            view = household_view(BOOK, client_id)
            for exposure in lookthrough.issuer_exposures(view):
                for leg in exposure.legs:
                    self.assertIn(
                        leg.basis_field, {"instrument_name", "underlying_reference"}
                    )

    def test_unresolved_underlying_is_disclosed_not_guessed(self) -> None:
        view = household_view(BOOK, "CL-0003")
        notes = lookthrough.unresolved_notes(view)
        self.assertTrue(any("three Asian banking majors" in n for n in notes))


class TestMandate(unittest.TestCase):
    def test_custody_portfolios_are_not_measured_against_a_mandate(self) -> None:
        review = mandate.review_portfolio(BOOK, "PF-0002")
        self.assertFalse(review.governed)
        self.assertEqual(review.band_breaches, [])

    def test_single_position_limit_only_applies_to_flagged_instruments(self) -> None:
        for client_id in BOOK.clients:
            for review in mandate.review_client(BOOK, client_id):
                for breach in review.position_breaches:
                    instrument = BOOK.instrument(breach.instrument_id)
                    self.assertEqual(
                        instrument.get("concentration_limit_applies"),
                        "Y",
                        msg=breach.instrument_id,
                    )

    def test_conservative_mandate_flags_the_inherited_equity_weight(self) -> None:
        review = mandate.review_portfolio(BOOK, "PF-0005")
        equity = next(b for b in review.band_breaches if b.asset_class == "Equity")
        self.assertEqual(equity.direction, "above")
        self.assertGreater(equity.actual_pct, 60)

    def test_exclusions_are_flagged_inside_a_binding_mandate(self) -> None:
        review = mandate.review_portfolio(BOOK, "PF-0007")
        excluded = {b.instrument_id for b in review.exclusion_breaches}
        self.assertIn("SYN-EQ-0008", excluded)
        self.assertIn("SYN-ST-0105", excluded)


class TestCollateral(unittest.TestCase):
    def test_ltv_series_matches_the_source_columns(self) -> None:
        for facility in BOOK.facilities:
            view = collateral.facility_view(BOOK, facility)
            for point in view.series:
                self.assertEqual(
                    point.ltv_pct, BOOK.dated(facility, "ltv_pct", point.snapshot)
                )

    def test_past_breaches_are_detected(self) -> None:
        cf5 = collateral.facility_view(
            BOOK, next(f for f in BOOK.facilities if f["facility_id"] == "CF-0005")
        )
        self.assertEqual([p.snapshot for p in cf5.breaches], ["2025-12-31", "2026-02-27"])
        self.assertIn("without any repayment", cf5.cure_narrative or "")

    def test_withdrawal_capacity_keeps_ltv_at_the_trigger(self) -> None:
        cf2 = collateral.facility_view(
            BOOK, next(f for f in BOOK.facilities if f["facility_id"] == "CF-0002")
        )
        capacity = collateral.withdrawal_capacity(cf2)
        current = cf2.current
        new_ltv = current.drawn / (current.lending_value - capacity) * 100
        self.assertAlmostEqual(new_ltv, cf2.margin_call_ltv_pct, places=6)

    def test_repayment_formula_hits_the_target(self) -> None:
        cf2 = collateral.facility_view(
            BOOK, next(f for f in BOOK.facilities if f["facility_id"] == "CF-0002")
        )
        advance_rate = 50.0
        target = 60.0
        proceeds = _repayment_to_target(cf2, target, advance_rate)
        current = cf2.current
        new_ltv = (
            (current.drawn - proceeds)
            / (current.lending_value - proceeds * advance_rate / 100)
            * 100
        )
        self.assertAlmostEqual(new_ltv, target, places=6)

    def test_unexplained_drawdown_is_reported(self) -> None:
        cf2 = collateral.facility_view(
            BOOK, next(f for f in BOOK.facilities if f["facility_id"] == "CF-0002")
        )
        gaps = [r for r in cf2.drawn_reconciliation if abs(r["unexplained"]) > 1000]
        self.assertEqual(len(gaps), 1)
        self.assertAlmostEqual(gaps[0]["unexplained"], 2_000_000, places=2)


class TestLiquidity(unittest.TestCase):
    def test_commitments_are_not_double_counted(self) -> None:
        view = household_view(BOOK, "CL-0017")
        result = liquidity.liquidity_view(BOOK, "CL-0017", view)
        ids = {o.id for o in result.obligations}
        self.assertNotIn("CN-016", ids)
        self.assertIn("COM-001", ids)
        self.assertTrue(any("CN-016 restates" in note for note in result.notes))

    def test_annual_instalments_are_spread_not_repeated(self) -> None:
        need = next(n for n in BOOK.cash_needs if n["need_id"] == "CN-007")
        self.assertAlmostEqual(liquidity.annual_amount(need), 1_000_000, places=2)
        recurring = next(n for n in BOOK.cash_needs if n["need_id"] == "CN-012")
        self.assertAlmostEqual(liquidity.annual_amount(recurring), 1_280_000, places=2)

    def test_pledged_assets_are_not_counted_as_withdrawable(self) -> None:
        view = household_view(BOOK, "CL-0014")
        result = liquidity.liquidity_view(BOOK, "CL-0014", view)
        self.assertLess(result.withdrawable_usd, result.readily_realisable_usd)
        self.assertLess(result.withdrawable_usd, 200_000)


class TestSignals(unittest.TestCase):
    def test_every_client_produces_scored_insights_with_reasons(self) -> None:
        for client_id in BOOK.clients:
            for insight in run_for_client(client_id, BOOK):
                self.assertGreaterEqual(insight.priority_score, 0)
                self.assertLessEqual(insight.priority_score, 100)
                self.assertTrue(insight.priority_reasons, msg=insight.id)
                self.assertTrue(insight.headline, msg=insight.id)
                self.assertTrue(insight.suggested_next_step, msg=insight.id)

    def test_no_check_raised_an_engine_error(self) -> None:
        for client_id in BOOK.clients:
            for insight in run_for_client(client_id, BOOK):
                self.assertNotIn("could not be evaluated", insight.headline)

    def test_material_findings_carry_evidence(self) -> None:
        for client_id in BOOK.clients:
            for insight in run_for_client(client_id, BOOK):
                if insight.severity in (Severity.CRITICAL, Severity.HIGH):
                    self.assertTrue(
                        insight.evidence,
                        msg=f"{insight.id} is {insight.severity.value} with no evidence",
                    )

    def test_priority_is_monotonic_in_severity(self) -> None:
        high, _ = priority(Severity.HIGH, materiality_pct=10, days_until=60)
        medium, _ = priority(Severity.MEDIUM, materiality_pct=10, days_until=60)
        self.assertGreater(high, medium)

    def test_the_book_ranks_the_facility_nearest_a_margin_call_first(self) -> None:
        tops = {
            client_id: max(
                (i.priority_score for i in run_for_client(client_id, BOOK)), default=0.0
            )
            for client_id in BOOK.clients
        }
        leader = max(tops, key=lambda k: tops[k])
        self.assertEqual(leader, "CL-0014")


if __name__ == "__main__":
    unittest.main()
