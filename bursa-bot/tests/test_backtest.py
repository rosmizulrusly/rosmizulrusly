import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from conftest import SRC  # noqa: F401

from bursabot.backtest import BacktestConfig, run_backtest
from bursabot.risk import RiskLimits
from bursabot.shariah.list_store import SACListStore
from bursabot.signals.trend import TrendParams
from bursabot.types import Bar
from bursabot.universe import LiquidityRules

FIRST_EDITION = date(2024, 1, 1)
# Deliberately mid-month: the announcement must not coincide with a rebalance,
# so the forced-exit path (not the ordinary rebalance) is what sells the name.
SECOND_EDITION = date(2024, 6, 5)


def business_days(start: date, count: int) -> list[date]:
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def rising(symbol: str, days: list[date], start_price: float, step: float) -> list[Bar]:
    bars = []
    for i, day in enumerate(days):
        price = start_price + step * i
        bars.append(Bar(symbol, day, price, price * 1.005, price * 0.995, price, 2_000_000))
    return bars


class TestBacktest(unittest.TestCase):
    def _editions(self, second_edition: date) -> Path:
        root = Path(self.tmp.name) / second_edition.isoformat()
        root.mkdir(parents=True, exist_ok=True)
        for effective, codes in (
            (FIRST_EDITION, ["KEEP", "DROP"]),
            (second_edition, ["KEEP"]),
        ):
            (root / f"{effective.isoformat()}.json").write_text(
                json.dumps(
                    {
                        "effective_date": effective.isoformat(),
                        "source": "test",
                        "verified": True,
                        "compliant": codes,
                    }
                )
            )
        return root

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SACListStore.load(self._editions(SECOND_EDITION))

        self.days = business_days(FIRST_EDITION, 180)
        self.history = {
            "KEEP": rising("KEEP", self.days, 2.00, 0.004),
            "DROP": rising("DROP", self.days, 3.00, 0.010),
        }
        self.config = BacktestConfig(
            start=self.days[0],
            end=self.days[-1],
            initial_cash=100_000.0,
            liquidity=LiquidityRules(
                lookback_days=5, min_avg_daily_value=0.0, min_price=0.05, min_history_days=20
            ),
            trend=TrendParams(trend_window=10, momentum_window=10, top_n=2),
            limits=RiskLimits(max_position_weight=0.5, min_ticket_value=1_000.0,
                              max_adv_participation=1.0),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_it_trades_and_produces_an_equity_curve(self):
        result = run_backtest(self.history, self.store, self.config)
        self.assertEqual(len(result.equity_curve), len(self.days))
        self.assertTrue(result.fills)
        self.assertGreater(result.total_fees, 0.0)

    def test_reclassified_holding_is_force_exited_and_purified(self):
        # Slippage off so the assertion is about the purification rule, not the
        # fill model - one tick of slippage can exceed a day's move on a cheap name.
        config = replace(self.config, slippage_ticks=0)
        result = run_backtest(self.history, self.store, config)
        exited = [symbol for _, symbol, _ in result.forced_exits]
        self.assertIn("DROP", exited)

        # DROP keeps rising after the announcement, so selling later owes charity.
        self.assertGreater(result.purification_owed, 0.0)

        sells_after = [
            f for f in result.fills if f.symbol == "DROP" and f.day >= SECOND_EDITION
        ]
        self.assertTrue(sells_after)

    def test_selling_on_the_announcement_day_owes_nothing(self):
        """Exit at the reference close and there is no excess gain to purify."""
        store = SACListStore.load(self._editions(second_edition=date(2024, 6, 3)))
        config = replace(self.config, slippage_ticks=0)
        result = run_backtest(self.history, store, config)
        self.assertTrue(result.forced_exits)
        self.assertEqual(result.purification_owed, 0.0)

    def test_nothing_is_bought_after_removal(self):
        result = run_backtest(self.history, self.store, self.config)
        late_buys = [
            f
            for f in result.fills
            if f.symbol == "DROP" and f.day > SECOND_EDITION and f.side.value == "BUY"
        ]
        self.assertEqual(late_buys, [])

    def test_never_leveraged(self):
        result = run_backtest(self.history, self.store, self.config)
        self.assertTrue(all(equity > 0 for _, equity in result.equity_curve))

    def test_window_outside_available_history_is_an_error(self):
        config = BacktestConfig(start=date(2030, 1, 1), end=date(2030, 12, 31))
        with self.assertRaises(ValueError):
            run_backtest(self.history, self.store, config)

    def test_backtesting_before_the_first_edition_is_refused(self):
        from bursabot.shariah.list_store import PointInTimeError

        history = {"KEEP": rising("KEEP", business_days(date(2023, 1, 2), 60), 2.0, 0.01)}
        config = BacktestConfig(start=date(2023, 1, 2), end=date(2023, 3, 31))
        with self.assertRaises(PointInTimeError):
            run_backtest(history, self.store, config)


if __name__ == "__main__":
    unittest.main()
