import unittest

from conftest import SRC  # noqa: F401

from bursabot.risk import KillSwitch, RiskLimits, exit_orders, size_orders
from bursabot.types import Position, Side


class TestLimits(unittest.TestCase):
    def test_leverage_is_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            RiskLimits(max_gross_exposure=1.5)


class TestSizing(unittest.TestCase):
    def setUp(self):
        self.prices = {"9001": 2.00, "9002": 5.00}
        self.limits = RiskLimits(min_ticket_value=1_000.0, max_adv_participation=1.0)
        self.adv = {"9001": 5_000_000.0, "9002": 5_000_000.0}

    def test_orders_are_whole_board_lots(self):
        orders = size_orders(
            {"9001": 0.5, "9002": 0.5}, {}, self.prices, 100_000.0,
            adv=self.adv, limits=self.limits,
        )
        self.assertTrue(orders)
        for order in orders:
            self.assertEqual(order.shares % 100, 0)
            self.assertIs(order.side, Side.BUY)

    def test_gross_exposure_is_capped_below_one(self):
        limits = RiskLimits(max_gross_exposure=0.5, max_position_weight=1.0,
                            min_ticket_value=1_000.0, max_adv_participation=1.0)
        orders = size_orders(
            {"9001": 1.0}, {}, self.prices, 100_000.0, adv=self.adv, limits=limits,
        )
        invested = sum(o.shares * self.prices[o.symbol] for o in orders)
        self.assertLessEqual(invested, 50_000.0)

    def test_position_weight_cap_applies(self):
        limits = RiskLimits(max_position_weight=0.1, min_ticket_value=1_000.0,
                            max_adv_participation=1.0)
        orders = size_orders(
            {"9001": 1.0}, {}, self.prices, 100_000.0, adv=self.adv, limits=limits,
        )
        self.assertLessEqual(orders[0].shares * 2.00, 10_000.0)

    def test_adv_participation_caps_illiquid_names(self):
        limits = RiskLimits(max_adv_participation=0.05, min_ticket_value=1_000.0)
        orders = size_orders(
            {"9001": 1.0}, {}, self.prices, 1_000_000.0,
            adv={"9001": 200_000.0}, limits=limits,
        )
        self.assertLessEqual(orders[0].shares * 2.00, 10_000.0)

    def test_tickets_below_the_minimum_are_dropped(self):
        limits = RiskLimits(min_ticket_value=50_000.0, max_adv_participation=1.0)
        orders = size_orders(
            {"9001": 0.01}, {}, self.prices, 100_000.0, adv=self.adv, limits=limits,
        )
        self.assertEqual(orders, [])

    def test_blocked_buying_still_allows_selling(self):
        positions = {"9001": Position("9001", 5_000, 1.50)}
        orders = size_orders(
            {"9002": 1.0}, positions, self.prices, 100_000.0,
            adv=self.adv, limits=self.limits, allow_buys=False,
        )
        self.assertTrue(orders)
        self.assertTrue(all(o.side is Side.SELL for o in orders))

    def test_small_drift_is_not_rebalanced(self):
        positions = {"9001": Position("9001", 25_000, 2.00)}
        orders = size_orders(
            {"9001": 0.5}, positions, self.prices, 100_000.0,
            adv=self.adv, limits=RiskLimits(rebalance_band=0.5, max_adv_participation=1.0),
        )
        self.assertEqual(orders, [])


class TestExitOrders(unittest.TestCase):
    def test_exit_sells_the_whole_holding_with_a_reason(self):
        positions = {"9004": Position("9004", 3_000, 1.0)}
        orders = exit_orders(positions, {"9004": "SAC removal"})
        self.assertEqual(len(orders), 1)
        self.assertIs(orders[0].side, Side.SELL)
        self.assertEqual(orders[0].shares, 3_000)
        self.assertEqual(orders[0].reason, "SAC removal")

    def test_unheld_symbols_are_ignored(self):
        self.assertEqual(exit_orders({}, {"9004": "SAC removal"}), [])


class TestKillSwitch(unittest.TestCase):
    def test_trips_past_the_daily_loss_limit(self):
        switch = KillSwitch(RiskLimits(max_daily_loss=0.03))
        self.assertFalse(switch.check(100_000.0, 98_000.0))
        self.assertTrue(switch.check(100_000.0, 96_000.0))
        self.assertIn("daily loss", switch.reason)

    def test_stays_tripped_until_reset(self):
        switch = KillSwitch(RiskLimits(max_daily_loss=0.03))
        switch.check(100_000.0, 90_000.0)
        self.assertTrue(switch.check(100_000.0, 100_000.0))
        switch.reset()
        self.assertFalse(switch.tripped)


if __name__ == "__main__":
    unittest.main()
