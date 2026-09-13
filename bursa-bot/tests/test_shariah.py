import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from conftest import SRC  # noqa: F401

from bursabot.shariah import (
    PointInTimeError,
    PurificationLedger,
    SACListStore,
    filter_universe,
    is_tradeable,
    purification_due,
    reconcile_holdings,
)
from bursabot.shariah.list_store import SACList
from bursabot.types import Position


def _write_editions(root: Path, editions: dict[str, list[str]]) -> SACListStore:
    for effective, codes in editions.items():
        (root / f"{effective}.json").write_text(
            json.dumps(
                {
                    "effective_date": effective,
                    "source": "test",
                    "verified": True,
                    "compliant": codes,
                }
            )
        )
    return SACListStore.load(root)


class TestPointInTime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = _write_editions(
            Path(self.tmp.name),
            {
                "2024-05-31": ["A", "B", "C"],
                "2024-11-29": ["A", "C", "D"],
            },
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolves_the_edition_in_force(self):
        self.assertEqual(self.store.as_of(date(2024, 5, 31)).effective_date, date(2024, 5, 31))
        self.assertEqual(self.store.as_of(date(2024, 11, 28)).effective_date, date(2024, 5, 31))
        self.assertEqual(self.store.as_of(date(2024, 11, 29)).effective_date, date(2024, 11, 29))
        self.assertEqual(self.store.as_of(date(2030, 1, 1)).effective_date, date(2024, 11, 29))

    def test_refuses_dates_before_the_first_edition(self):
        """Screening pre-list history with a later list is look-ahead bias."""
        with self.assertRaises(PointInTimeError):
            self.store.as_of(date(2024, 5, 30))

    def test_diff_reports_additions_and_removals(self):
        diff = self.store.latest_diff()
        self.assertEqual(diff.added, frozenset({"D"}))
        self.assertEqual(diff.removed, frozenset({"B"}))

    def test_verified_editions_produce_no_warning(self):
        self.assertEqual(self.store.warnings(), [])

    def test_missing_directory_is_an_error(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(FileNotFoundError):
                SACListStore.load(empty)


class TestScreen(unittest.TestCase):
    def setUp(self):
        self.sac = SACList(date(2025, 5, 30), frozenset({"9001", "9002"}), verified=True)

    def test_membership_is_case_and_space_insensitive(self):
        self.assertTrue(is_tradeable(" 9001 ", self.sac))
        self.assertFalse(is_tradeable("9999", self.sac))

    def test_filter_preserves_order_and_drops_non_compliant(self):
        self.assertEqual(filter_universe(["9002", "9999", "9001"], self.sac), ["9002", "9001"])

    def test_reconcile_flags_only_holdings_off_the_list(self):
        positions = {
            "9001": Position("9001", 1_000, 1.0),
            "9999": Position("9999", 500, 2.0),
        }
        exits = reconcile_holdings(
            positions, self.sac, date(2025, 5, 30), {"9001": 1.5, "9999": 2.5}
        )
        self.assertEqual([e.symbol for e in exits], ["9999"])
        self.assertEqual(exits[0].reference_close, 2.5)
        self.assertFalse(exits[0].under_water)

    def test_reconcile_refuses_to_guess_a_missing_close(self):
        positions = {"9999": Position("9999", 500, 2.0)}
        with self.assertRaises(KeyError):
            reconcile_holdings(positions, self.sac, date(2025, 5, 30), {})

    def test_under_water_holdings_are_flagged(self):
        positions = {"9999": Position("9999", 500, 3.0)}
        exits = reconcile_holdings(positions, self.sac, date(2025, 5, 30), {"9999": 2.0})
        self.assertTrue(exits[0].under_water)


class TestPurification(unittest.TestCase):
    def test_gain_up_to_the_reference_close_is_retained(self):
        self.assertEqual(purification_due(2.50, 2.50, 1_000), 0.0)
        self.assertEqual(purification_due(2.00, 2.50, 1_000), 0.0)

    def test_excess_above_the_reference_close_is_owed_in_full(self):
        self.assertEqual(purification_due(2.80, 2.50, 1_000), 300.00)

    def test_rejects_bad_inputs(self):
        for args in ((2.5, 2.5, 0), (0.0, 2.5, 100), (2.5, -1.0, 100)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                purification_due(*args)

    def test_ledger_persists_and_tracks_outstanding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            ledger = PurificationLedger(path)
            self.assertIsNone(ledger.record_disposal("9001", date(2025, 6, 2), 100, 1.0, 1.5))
            entry = ledger.record_disposal("9004", date(2025, 6, 2), 1_000, 2.80, 2.50)
            self.assertEqual(entry.amount, 300.00)
            self.assertEqual(ledger.outstanding, 300.00)

            reloaded = PurificationLedger(path)
            self.assertEqual(len(reloaded.entries), 1)
            self.assertEqual(reloaded.outstanding, 300.00)
            reloaded.mark_paid(0, note="donated")
            self.assertEqual(reloaded.outstanding, 0.0)
            self.assertEqual(reloaded.total_recorded, 300.00)
            self.assertEqual(PurificationLedger(path).outstanding, 0.0)


if __name__ == "__main__":
    unittest.main()
