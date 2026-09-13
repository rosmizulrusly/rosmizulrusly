import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from conftest import SRC  # noqa: F401

from bursabot.calendar_my import MYT, CalendarDataMissing, TradingCalendar


class TestCalendar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "holidays.json"
        path.write_text(
            json.dumps(
                {
                    "years": {
                        "2026": {
                            "verified": True,
                            "days": ["2026-08-31", "2026-09-16"],
                        }
                    }
                }
            )
        )
        self.cal = TradingCalendar.load(path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_weekends_and_holidays_are_closed(self):
        self.assertFalse(self.cal.is_trading_day(date(2026, 9, 12)))  # Saturday
        self.assertFalse(self.cal.is_trading_day(date(2026, 9, 16)))  # Malaysia Day
        self.assertTrue(self.cal.is_trading_day(date(2026, 9, 15)))

    def test_missing_year_raises_rather_than_assuming_open(self):
        with self.assertRaises(CalendarDataMissing):
            self.cal.is_trading_day(date(2031, 1, 5))

    def test_sessions(self):
        day = date(2026, 9, 15)
        cases = {
            (8, 15): "closed",
            (8, 45): "pre-opening",
            (9, 0): "morning",
            (12, 29): "morning",
            (12, 30): "closed",
            (14, 0): "closed",
            (14, 30): "afternoon",
            (16, 59): "afternoon",
            (17, 0): "closed",
        }
        for (hour, minute), expected in cases.items():
            moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=MYT)
            with self.subTest(time=f"{hour:02d}:{minute:02d}"):
                self.assertEqual(self.cal.session(moment), expected)

    def test_pre_opening_is_not_open_for_trading(self):
        moment = datetime(2026, 9, 15, 8, 45, tzinfo=MYT)
        self.assertEqual(self.cal.session(moment), "pre-opening")
        self.assertFalse(self.cal.is_open(moment))

    def test_settlement_skips_weekends_and_holidays(self):
        # Mon 14 Sep -> Tue 15th, Wed 16th is Malaysia Day -> settles Thu 17th.
        self.assertEqual(self.cal.settlement_date(date(2026, 9, 14)), date(2026, 9, 17))

    def test_unverified_years_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.json"
            path.write_text(json.dumps({"years": {"2026": {"verified": False, "days": []}}}))
            self.assertTrue(TradingCalendar.load(path).warnings())


if __name__ == "__main__":
    unittest.main()
