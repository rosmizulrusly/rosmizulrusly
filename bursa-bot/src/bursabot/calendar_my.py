"""Bursa Malaysia trading calendar and session clock (Asia/Kuala_Lumpur).

Bursa trades two sessions a day. Getting this wrong is how a scheduler ends up
submitting orders into a closed market or a pre-opening auction, so the calendar
refuses to guess: a year with no holiday data raises rather than assuming the
market is open.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MYT = ZoneInfo("Asia/Kuala_Lumpur")

PRE_OPENING = (time(8, 30), time(9, 0))
MORNING_SESSION = (time(9, 0), time(12, 30))
AFTERNOON_SESSION = (time(14, 30), time(17, 0))
SETTLEMENT_DAYS = 2
"""Bursa equities settle T+2."""

DEFAULT_HOLIDAYS = Path(__file__).resolve().parents[2] / "data" / "calendar" / "holidays.json"


class CalendarDataMissing(RuntimeError):
    """Raised when asked about a date with no holiday data - never assume "open"."""


@dataclass(frozen=True)
class TradingCalendar:
    holidays: frozenset[date]
    covered_years: frozenset[int]
    unverified_years: frozenset[int]

    @classmethod
    def load(cls, path: Path | str | None = None) -> "TradingCalendar":
        raw = json.loads(Path(path or DEFAULT_HOLIDAYS).read_text())
        holidays: set[date] = set()
        covered: set[int] = set()
        unverified: set[int] = set()
        for year, entry in raw["years"].items():
            covered.add(int(year))
            if not entry.get("verified", False):
                unverified.add(int(year))
            holidays.update(date.fromisoformat(d) for d in entry["days"])
        return cls(frozenset(holidays), frozenset(covered), frozenset(unverified))

    def _require(self, day: date) -> None:
        if day.year not in self.covered_years:
            raise CalendarDataMissing(
                f"no Bursa holiday data for {day.year}; add it to holidays.json "
                "and verify it against the official Bursa trading calendar"
            )

    def is_trading_day(self, day: date) -> bool:
        self._require(day)
        return day.weekday() < 5 and day not in self.holidays

    def next_trading_day(self, day: date) -> date:
        nxt = day + timedelta(days=1)
        while not self.is_trading_day(nxt):
            nxt += timedelta(days=1)
        return nxt

    def settlement_date(self, trade_day: date) -> date:
        """T+2 settlement date for a trade executed on `trade_day`."""
        settle = trade_day
        for _ in range(SETTLEMENT_DAYS):
            settle = self.next_trading_day(settle)
        return settle

    def session(self, moment: datetime) -> str:
        """Return 'closed', 'pre-opening', 'morning' or 'afternoon' for a MYT instant."""
        local = moment.astimezone(MYT)
        if not self.is_trading_day(local.date()):
            return "closed"
        clock = local.time()
        for name, (start, end) in (
            ("pre-opening", PRE_OPENING),
            ("morning", MORNING_SESSION),
            ("afternoon", AFTERNOON_SESSION),
        ):
            if start <= clock < end:
                return name
        return "closed"

    def is_open(self, moment: datetime) -> bool:
        """True only during continuous trading - the pre-opening auction is not open."""
        return self.session(moment) in {"morning", "afternoon"}

    def warnings(self) -> list[str]:
        if not self.unverified_years:
            return []
        years = ", ".join(str(y) for y in sorted(self.unverified_years))
        return [
            f"Holiday data for {years} is marked unverified. Confirm it against "
            "Bursa's official trading calendar before live trading."
        ]
