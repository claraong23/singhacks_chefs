from __future__ import annotations

import unittest

from clarity.analytics.lookthrough import Exposure
from clarity.analytics.scenarios import DEFAULT_SCENARIOS, Scenario, apply_theme_shock, calculate_impacts


class TestEventSensitivities(unittest.TestCase):
    def setUp(self) -> None:
        self.theme = Exposure(
            key="energy_hormuz", name="Energy and the Strait of Hormuz",
            kind="theme", attributed_usd=2_000_000, pct_of_household=20.0,
            legs=[], hidden=False,
        )

    def test_applies_shock_to_value_and_household_percentage(self) -> None:
        result = apply_theme_shock(self.theme, Scenario("test", "Test", "energy_hormuz", -10.0, "Test shock"))
        self.assertEqual(result.impact_usd, -200_000)
        self.assertEqual(result.impact_pct_of_household, -2.0)

    def test_ignores_themes_below_materiality_floor(self) -> None:
        scenario = Scenario("test", "Test", "energy_hormuz", -10.0, "Test shock")
        small = Exposure(self.theme.key, self.theme.name, self.theme.kind, self.theme.attributed_usd, 9.9, [], False)
        self.assertEqual(calculate_impacts([small], (scenario,)), [])

    def test_impacts_are_sorted_by_absolute_amount(self) -> None:
        scenarios = (
            Scenario("small", "Small", "energy_hormuz", -5.0, "Small"),
            Scenario("large", "Large", "energy_hormuz", -20.0, "Large"),
        )
        self.assertEqual([item.scenario.key for item in calculate_impacts([self.theme], scenarios)], ["large", "small"])

    def test_defaults_cover_repository_backed_events(self) -> None:
        by_key = {scenario.key: scenario for scenario in DEFAULT_SCENARIOS}
        self.assertEqual(by_key["technology_drawdown"].theme_key, "us_tech_ai")
        self.assertEqual(by_key["rates_remain_higher"].theme_key, "duration")


if __name__ == "__main__":
    unittest.main()
