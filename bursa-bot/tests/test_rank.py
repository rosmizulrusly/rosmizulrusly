import unittest
from datetime import date, timedelta

from conftest import SRC  # noqa: F401

from bursabot.rank import AVOID, BUY, HOLD, SELL, WATCH, rank_counters
from bursabot.shariah.list_store import SACList
from bursabot.signals.trend import TrendParams
from bursabot.types import Bar, Position
from bursabot.universe import LiquidityRules

START = date(2024, 1, 1)
DAY = START + timedelta(days=399)


def series(symbol: str, prices: list[float], volume: int = 2_000_000) -> list[Bar]:
    return [
        Bar(symbol, START + timedelta(days=i), p, p * 1.01, p * 0.99, p, volume)
        for i, p in enumerate(prices)
    ]


def rising(symbol: str, start: float, step: float, n: int = 400, volume: int = 2_000_000):
    return series(symbol, [start + step * i for i in range(n)], volume)


def falling(symbol: str, start: float, step: float, n: int = 400, volume: int = 2_000_000):
    return series(symbol, [max(0.05, start - step * i) for i in range(n)], volume)


class TestRank(unittest.TestCase):
    def setUp(self):
        self.rules = LiquidityRules(
            lookback_days=20, min_avg_daily_value=500_000.0,
            min_price=0.30, min_history_days=250, max_hurdle=0.025,
        )
        self.trend = TrendParams(trend_window=200, momentum_window=120, top_n=2)
        self.sac = SACList(START, frozenset({"UP1", "UP2", "UP3", "DOWN", "PENNY", "THIN"}), True)

    def verdicts(self, history, positions=None):
        return {
            v.symbol: v
            for v in rank_counters(
                history, self.sac, DAY, positions=positions,
                rules=self.rules, trend=self.trend,
            )
        }

    def test_top_ranked_uptrends_are_buys_and_the_rest_watch(self):
        history = {
            "UP1": rising("UP1", 2.00, 0.010),
            "UP2": rising("UP2", 2.00, 0.005),
            "UP3": rising("UP3", 2.00, 0.001),
        }
        result = self.verdicts(history)
        self.assertEqual(result["UP1"].direction, BUY)
        self.assertEqual(result["UP1"].rank, 1)
        self.assertEqual(result["UP2"].direction, BUY)
        self.assertEqual(result["UP3"].direction, WATCH)

    def test_a_held_top_ranked_counter_is_hold_not_buy(self):
        history = {"UP1": rising("UP1", 2.00, 0.010)}
        result = self.verdicts(history, {"UP1": Position("UP1", 1_000, 2.0)})
        self.assertEqual(result["UP1"].direction, HOLD)

    def test_downtrend_is_sell_when_held_and_avoid_when_not(self):
        history = {"DOWN": falling("DOWN", 6.00, 0.010)}
        self.assertEqual(self.verdicts(history)["DOWN"].direction, AVOID)
        held = self.verdicts(history, {"DOWN": Position("DOWN", 1_000, 6.0)})
        self.assertEqual(held["DOWN"].direction, SELL)
        self.assertIn("moving average", held["DOWN"].reason)

    def test_non_compliant_counters_are_gated_before_any_chart_test(self):
        """Compliance is checked first, so no momentum is even computed."""
        history = {"OFFLIST": rising("OFFLIST", 2.00, 0.010)}
        result = self.verdicts(history)
        self.assertEqual(result["OFFLIST"].direction, AVOID)
        self.assertIn("SAC list", result["OFFLIST"].reason)
        self.assertIsNone(result["OFFLIST"].momentum_pct)

    def test_a_held_non_compliant_counter_is_a_sell_with_the_purification_note(self):
        history = {"OFFLIST": rising("OFFLIST", 2.00, 0.010)}
        result = self.verdicts(history, {"OFFLIST": Position("OFFLIST", 1_000, 2.0)})
        self.assertEqual(result["OFFLIST"].direction, SELL)
        self.assertIn("purification", result["OFFLIST"].reason)

    def test_penny_counters_are_rejected_on_the_cost_hurdle(self):
        rules = LiquidityRules(
            lookback_days=20, min_avg_daily_value=500_000.0,
            min_price=0.05, min_history_days=250, max_hurdle=0.025,
        )
        history = {"PENNY": rising("PENNY", 0.10, 0.0001, volume=50_000_000)}
        result = {
            v.symbol: v
            for v in rank_counters(history, self.sac, DAY, rules=rules, trend=self.trend)
        }
        self.assertEqual(result["PENNY"].direction, AVOID)
        self.assertIn("hurdle", result["PENNY"].reason)
        self.assertGreater(result["PENNY"].hurdle, 0.025)

    def test_thin_counters_are_rejected_on_liquidity(self):
        history = {"THIN": rising("THIN", 2.00, 0.010, volume=100)}
        result = self.verdicts(history)
        self.assertEqual(result["THIN"].direction, AVOID)
        self.assertIn("thin", result["THIN"].reason)

    def test_short_history_gives_no_signal_rather_than_a_direction(self):
        history = {"UP1": rising("UP1", 2.00, 0.010, n=60)}
        result = self.verdicts(history)
        self.assertEqual(result["UP1"].direction, AVOID)
        self.assertIn("history", result["UP1"].reason)

    def test_a_held_counter_failing_a_liquidity_gate_is_held_not_force_sold(self):
        """Thin is a reason not to trade it systematically, not a reason to dump it."""
        history = {"THIN": rising("THIN", 2.00, 0.010, volume=100)}
        result = self.verdicts(history, {"THIN": Position("THIN", 1_000, 2.0)})
        self.assertEqual(result["THIN"].direction, HOLD)
        self.assertIn("not a systematic position", result["THIN"].reason)

    def test_buys_are_listed_before_sells_and_avoids(self):
        history = {
            "UP1": rising("UP1", 2.00, 0.010),
            "DOWN": falling("DOWN", 6.00, 0.010),
            "THIN": rising("THIN", 2.00, 0.010, volume=100),
        }
        order = [v.direction for v in rank_counters(
            history, self.sac, DAY, rules=self.rules, trend=self.trend
        )]
        self.assertEqual(order[0], BUY)
        self.assertEqual(order[-1], AVOID)

    def test_every_counter_gets_exactly_one_verdict(self):
        history = {
            "UP1": rising("UP1", 2.00, 0.010),
            "UP2": rising("UP2", 2.00, 0.005),
            "DOWN": falling("DOWN", 6.00, 0.010),
            "THIN": rising("THIN", 2.00, 0.010, volume=100),
            "OFFLIST": rising("OFFLIST", 2.00, 0.010),
        }
        verdicts = rank_counters(history, self.sac, DAY, rules=self.rules, trend=self.trend)
        self.assertEqual(len(verdicts), len(history))
        self.assertEqual(len({v.symbol for v in verdicts}), len(history))
        for verdict in verdicts:
            self.assertTrue(verdict.reason, f"{verdict.symbol} has no stated reason")


if __name__ == "__main__":
    unittest.main()
