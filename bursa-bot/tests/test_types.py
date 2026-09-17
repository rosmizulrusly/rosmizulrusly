import unittest
from datetime import date

from conftest import SRC  # noqa: F401

from bursabot.types import Bar, Order, Position, Side


class TestOrder(unittest.TestCase):
    def test_rejects_odd_lots(self):
        with self.assertRaises(ValueError):
            Order("9001", Side.BUY, 150)

    def test_rejects_non_positive_size(self):
        with self.assertRaises(ValueError):
            Order("9001", Side.BUY, 0)

    def test_lots(self):
        self.assertEqual(Order("9001", Side.BUY, 2_500).lots, 25)


class TestPosition(unittest.TestCase):
    def test_short_position_is_rejected(self):
        with self.assertRaises(ValueError):
            Position("9001", -100, 1.0)

    def test_forced_exit_flag_follows_reference_close(self):
        position = Position("9001", 100, 1.0)
        self.assertFalse(position.is_forced_exit)
        position.reference_close = 1.2
        self.assertTrue(position.is_forced_exit)


class TestBar(unittest.TestCase):
    def test_rejects_inverted_range(self):
        with self.assertRaises(ValueError):
            Bar("9001", date(2025, 1, 2), 1.0, 0.9, 1.1, 1.0, 100)

    def test_rejects_negative_volume(self):
        with self.assertRaises(ValueError):
            Bar("9001", date(2025, 1, 2), 1.0, 1.1, 0.9, 1.0, -1)


if __name__ == "__main__":
    unittest.main()
