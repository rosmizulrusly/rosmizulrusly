import unittest
from datetime import date

from conftest import SRC  # noqa: F401

from bursabot.execution import AlertOnlyBroker, ComplianceError, GuardedBroker, PaperBroker
from bursabot.types import Order, Position, Side

DAY = date(2025, 6, 2)


class TestGuard(unittest.TestCase):
    def setUp(self):
        self.inner = PaperBroker(50_000.0)
        self.guard = GuardedBroker(self.inner, tradeable=frozenset({"9001"}))

    def test_short_selling_is_refused(self):
        with self.assertRaises(ComplianceError) as ctx:
            self.guard.submit(Order("9001", Side.SELL, 1_000), 2.00, DAY)
        self.assertIn("short sale", str(ctx.exception))

    def test_selling_more_than_held_is_refused(self):
        self.guard.submit(Order("9001", Side.BUY, 1_000), 2.00, DAY)
        with self.assertRaises(ComplianceError):
            self.guard.submit(Order("9001", Side.SELL, 1_100), 2.00, DAY)

    def test_buying_beyond_cash_is_refused_as_margin(self):
        with self.assertRaises(ComplianceError) as ctx:
            self.guard.submit(Order("9001", Side.BUY, 100_000), 2.00, DAY)
        self.assertIn("margin", str(ctx.exception))

    def test_non_compliant_symbol_cannot_be_bought(self):
        with self.assertRaises(ComplianceError) as ctx:
            self.guard.submit(Order("9999", Side.BUY, 100), 2.00, DAY)
        self.assertIn("SAC list", str(ctx.exception))

    def test_a_non_compliant_holding_can_still_be_sold(self):
        """The forced-exit path must not be blocked by the buy-side screen."""
        self.inner.submit(Order("9999", Side.BUY, 1_000), 2.00, DAY)
        fill = self.guard.submit(Order("9999", Side.SELL, 1_000), 2.20, DAY)
        self.assertEqual(fill.shares, 1_000)


class TestPaperBroker(unittest.TestCase):
    def test_fills_cross_the_spread_against_you(self):
        broker = PaperBroker(50_000.0, slippage_ticks=1)
        self.assertGreater(broker.fill_price(2.00, Side.BUY), 2.00)
        self.assertLess(broker.fill_price(2.00, Side.SELL), 2.00)

    def test_round_trip_at_a_flat_price_loses_money_to_costs(self):
        broker = PaperBroker(50_000.0)
        broker.submit(Order("9001", Side.BUY, 2_000), 5.00, DAY)
        broker.submit(Order("9001", Side.SELL, 2_000), 5.00, DAY)
        self.assertLess(broker.cash(), 50_000.0)
        self.assertEqual(broker.positions(), {})

    def test_cost_basis_averages_across_buys(self):
        broker = PaperBroker(50_000.0)
        broker.submit(Order("9001", Side.BUY, 1_000), 2.00, DAY)
        broker.submit(Order("9001", Side.BUY, 1_000), 3.00, DAY)
        position = broker.positions()["9001"]
        self.assertEqual(position.shares, 2_000)
        self.assertGreater(position.cost_basis, 2.00)
        self.assertLess(position.cost_basis, 3.10)

    def test_equity_marks_positions_to_market(self):
        broker = PaperBroker(50_000.0)
        broker.submit(Order("9001", Side.BUY, 1_000), 2.00, DAY)
        self.assertGreater(broker.equity({"9001": 4.00}), broker.equity({"9001": 2.00}))


class TestAlertOnlyBroker(unittest.TestCase):
    def test_it_reports_rather_than_executes(self):
        messages: list[str] = []
        broker = AlertOnlyBroker(positions={}, cash=10_000.0, sink=messages.append)
        broker.submit(Order("9001", Side.BUY, 1_000, reason="rebalance"), 2.00, DAY)
        self.assertEqual(len(messages), 1)
        self.assertIn("BUY 1,000 9001", messages[0])
        self.assertIn("rebalance", messages[0])
        self.assertEqual(broker.positions(), {})  # nothing moved

    def test_sell_alert_quotes_net_proceeds(self):
        messages: list[str] = []
        broker = AlertOnlyBroker(
            positions={"9001": Position("9001", 1_000, 2.0)}, cash=0.0, sink=messages.append
        )
        broker.submit(Order("9001", Side.SELL, 1_000), 2.50, DAY)
        self.assertIn("proceeds", messages[0])


if __name__ == "__main__":
    unittest.main()
