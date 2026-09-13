import unittest

from conftest import SRC  # noqa: F401  (path setup)

from bursabot.costs import (
    FeeSchedule,
    compute_costs,
    round_lots,
    round_to_tick,
    round_trip_cost_pct,
    tick_size,
)
from bursabot.types import Side


class TestTickSize(unittest.TestCase):
    def test_bands(self):
        cases = [
            (0.005, 0.005), (0.995, 0.005),
            (1.00, 0.010), (2.99, 0.010),
            (3.00, 0.020), (4.98, 0.020),
            (5.00, 0.050), (9.95, 0.050),
            (10.00, 0.100), (24.90, 0.100),
            (25.00, 0.250), (99.75, 0.250),
            (100.00, 0.500), (250.00, 0.500),
        ]
        for price, expected in cases:
            with self.subTest(price=price):
                self.assertAlmostEqual(tick_size(price), expected)

    def test_rejects_non_positive(self):
        with self.assertRaises(ValueError):
            tick_size(0)

    def test_buy_rounds_down_sell_rounds_up(self):
        self.assertAlmostEqual(round_to_tick(1.234, Side.BUY), 1.23)
        self.assertAlmostEqual(round_to_tick(1.231, Side.SELL), 1.24)

    def test_rounding_stays_on_a_valid_tick_across_a_band_edge(self):
        for price in (0.999, 2.999, 4.999, 9.999, 24.999, 99.999):
            for side in Side:
                with self.subTest(price=price, side=side):
                    snapped = round_to_tick(price, side)
                    tick = tick_size(snapped)
                    self.assertAlmostEqual(snapped / tick, round(snapped / tick), places=6)


class TestBoardLots(unittest.TestCase):
    def test_rounds_down_to_whole_lots(self):
        self.assertEqual(round_lots(1), 0)
        self.assertEqual(round_lots(99), 0)
        self.assertEqual(round_lots(100), 100)
        self.assertEqual(round_lots(1_950), 1_900)


class TestCosts(unittest.TestCase):
    def test_minimum_brokerage_applies_on_small_tickets(self):
        costs = compute_costs(1.00, 100)
        self.assertEqual(costs.brokerage, FeeSchedule().brokerage_min)

    def test_stamp_duty_rounds_up_per_thousand(self):
        self.assertEqual(compute_costs(1.00, 1_000).stamp_duty, 1.00)
        self.assertEqual(compute_costs(1.00, 1_001).stamp_duty, 2.00)

    def test_stamp_duty_and_clearing_are_capped(self):
        costs = compute_costs(100.0, 500_000)  # RM50m contract value
        self.assertEqual(costs.stamp_duty, 1_000.00)
        self.assertEqual(costs.clearing_fee, 1_000.00)

    def test_service_tax_covers_brokerage_and_clearing(self):
        sched = FeeSchedule(service_tax_on_clearing=True)
        costs = compute_costs(10.0, 10_000, sched)
        expected = round((costs.brokerage + costs.clearing_fee) * sched.service_tax_rate, 2)
        self.assertEqual(costs.service_tax, expected)

    def test_service_tax_can_exclude_clearing(self):
        sched = FeeSchedule(service_tax_on_clearing=False)
        costs = compute_costs(10.0, 10_000, sched)
        self.assertEqual(costs.service_tax, round(costs.brokerage * sched.service_tax_rate, 2))

    def test_cash_out_exceeds_cash_in(self):
        costs = compute_costs(5.0, 1_000)
        self.assertGreater(costs.cash_out, costs.contract_value)
        self.assertLess(costs.cash_in, costs.contract_value)

    def test_small_tickets_are_punitive(self):
        """The headline reason a Bursa scalping bot loses: fixed costs."""
        self.assertGreater(round_trip_cost_pct(1.00, 1_000), 0.015)
        self.assertLess(round_trip_cost_pct(10.00, 10_000), 0.006)


if __name__ == "__main__":
    unittest.main()
