import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from conftest import SRC  # noqa: F401

from bursabot.portfolio import Portfolio


def write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload))
    return path


class TestPortfolio(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = write(
            Path(self.tmp.name) / "portfolio.json",
            {
                "broker": "M+ Online (Malacca Securities)",
                "updated": "2026-09-13",
                "cash": 5_000.0,
                "holdings": [
                    {"symbol": "5285", "shares": 2_000, "cost_basis": 4.35},
                    {"symbol": "6012", "shares": 3_000, "cost_basis": 3.61},
                ],
            },
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_loads_holdings_and_cash(self):
        portfolio = Portfolio.load(self.path)
        self.assertEqual(portfolio.cash, 5_000.0)
        self.assertEqual(portfolio.symbols, ["5285", "6012"])
        self.assertEqual(portfolio.holdings["5285"].shares, 2_000)
        self.assertEqual(portfolio.updated, date(2026, 9, 13))

    def test_symbols_are_normalised(self):
        path = write(
            Path(self.tmp.name) / "lower.json",
            {"cash": 0, "holdings": [{"symbol": " 5285 ", "shares": 100, "cost_basis": 1.0}]},
        )
        self.assertEqual(Portfolio.load(path).symbols, ["5285"])

    def test_duplicate_counters_are_rejected(self):
        path = write(
            Path(self.tmp.name) / "dupe.json",
            {
                "cash": 0,
                "holdings": [
                    {"symbol": "5285", "shares": 100, "cost_basis": 1.0},
                    {"symbol": "5285", "shares": 200, "cost_basis": 2.0},
                ],
            },
        )
        with self.assertRaises(ValueError):
            Portfolio.load(path)

    def test_missing_file_explains_the_fix(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            Portfolio.load(Path(self.tmp.name) / "nope.json")
        self.assertIn("portfolio.example.json", str(ctx.exception))

    def test_equity_marks_to_market(self):
        portfolio = Portfolio.load(self.path)
        self.assertEqual(portfolio.equity({"5285": 5.00, "6012": 4.00}), 5_000 + 10_000 + 12_000)

    def test_unpriced_holdings_fall_back_to_cost_and_are_reported(self):
        portfolio = Portfolio.load(self.path)
        self.assertEqual(portfolio.unpriced({"5285": 5.00}), ["6012"])
        self.assertEqual(
            portfolio.equity({"5285": 5.00}), 5_000 + 10_000 + round(3_000 * 3.61, 2)
        )

    def test_reference_close_survives_a_save_load_round_trip(self):
        portfolio = Portfolio.load(self.path)
        portfolio.holdings["5285"].reference_close = 4.90
        out = Path(self.tmp.name) / "out.json"
        portfolio.save(out)
        reloaded = Portfolio.load(out)
        self.assertEqual(reloaded.holdings["5285"].reference_close, 4.90)
        self.assertIsNone(reloaded.holdings["6012"].reference_close)
        self.assertEqual(reloaded.cash, portfolio.cash)


if __name__ == "__main__":
    unittest.main()
