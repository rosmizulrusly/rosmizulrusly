import unittest
from datetime import date, timedelta

from conftest import SRC  # noqa: F401

from bursabot.shariah.list_store import SACList
from bursabot.types import Bar
from bursabot.universe import (
    LiquidityRules,
    average_daily_value,
    build_universe,
    counter_hurdle,
)

START = date(2024, 1, 1)


def series(symbol: str, n: int, price: float, volume: int) -> list[Bar]:
    return [
        Bar(symbol, START + timedelta(days=i), price, price * 1.01, price * 0.99, price, volume)
        for i in range(n)
    ]


class TestUniverse(unittest.TestCase):
    def setUp(self):
        self.sac = SACList(START, frozenset({"LIQUID", "THIN", "PENNY", "NEW"}), verified=True)
        self.rules = LiquidityRules(
            lookback_days=5, min_avg_daily_value=100_000.0, min_price=0.20, min_history_days=10
        )
        self.history = {
            "LIQUID": series("LIQUID", 30, 5.00, 1_000_000),
            "THIN": series("THIN", 30, 5.00, 100),
            "PENNY": series("PENNY", 30, 0.05, 100_000_000),
            "NEW": series("NEW", 3, 5.00, 1_000_000),
            "BANNED": series("BANNED", 30, 5.00, 1_000_000),
        }
        self.day = START + timedelta(days=29)

    def test_only_liquid_compliant_names_survive(self):
        report = build_universe(self.day, self.history, self.sac, self.rules)
        self.assertEqual(report.candidates, ("LIQUID",))

    def test_non_compliant_names_are_dropped_first(self):
        report = build_universe(self.day, self.history, self.sac, self.rules)
        self.assertIn("BANNED", report.dropped_non_compliant)
        self.assertNotIn("BANNED", report.dropped_illiquid)

    def test_thin_and_penny_names_are_dropped_for_liquidity(self):
        report = build_universe(self.day, self.history, self.sac, self.rules)
        self.assertIn("THIN", report.dropped_illiquid)
        self.assertIn("PENNY", report.dropped_illiquid)

    def test_short_history_is_dropped_separately(self):
        report = build_universe(self.day, self.history, self.sac, self.rules)
        self.assertIn("NEW", report.dropped_insufficient_history)

    def test_history_after_the_evaluation_day_is_ignored(self):
        early = START + timedelta(days=12)
        report = build_universe(early, self.history, self.sac, self.rules)
        self.assertIn("LIQUID", report.candidates)

    def test_high_cost_counters_are_dropped_with_their_own_reason(self):
        rules = LiquidityRules(
            lookback_days=5, min_avg_daily_value=100_000.0, min_price=0.05,
            min_history_days=10, max_hurdle=0.025,
        )
        history = {"PENNY": series("PENNY", 30, 0.10, 100_000_000)}
        sac = SACList(START, frozenset({"PENNY"}), verified=True)
        report = build_universe(self.day, history, sac, rules)
        self.assertIn("PENNY", report.dropped_high_cost)
        self.assertNotIn("PENNY", report.dropped_illiquid)
        self.assertEqual(report.candidates, ())

    def test_hurdle_is_measured_on_at_least_one_board_lot(self):
        """A RM100 counter does not fit in a RM5,000 ticket - measure 100 shares."""
        rules = LiquidityRules(hurdle_ticket=5_000.0)
        self.assertLess(counter_hurdle(100.0, rules, None), 0.02)

    def test_average_daily_value(self):
        self.assertEqual(average_daily_value(series("X", 5, 2.0, 1_000), 5), 2_000.0)
        self.assertEqual(average_daily_value([], 5), 0.0)


if __name__ == "__main__":
    unittest.main()
