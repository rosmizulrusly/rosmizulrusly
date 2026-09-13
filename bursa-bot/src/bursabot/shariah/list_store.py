"""Point-in-time storage of the SAC List of Shariah-Compliant Securities.

The whole point of this module is the word *point-in-time*. Screening ten years of
price history against today's list is look-ahead bias: you would be "knowing" in
2019 which companies stay compliant through 2026, which flatters a backtest badly.
`SACListStore.as_of` therefore returns only the list that was actually in force on
the day being simulated, and raises if no such list exists.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_LIST_DIR = Path(__file__).resolve().parents[3] / "data" / "sac_lists"


class PointInTimeError(LookupError):
    """Raised when no SAC list was in force on the requested date."""


@dataclass(frozen=True)
class SACList:
    """One published edition of the SAC list."""

    effective_date: date
    compliant: frozenset[str]
    source: str = ""
    verified: bool = False
    """False for the sample data shipped with this repo. Set true for real downloads."""

    def __contains__(self, symbol: str) -> bool:
        return symbol.strip().upper() in self.compliant

    def __len__(self) -> int:
        return len(self.compliant)

    @classmethod
    def from_file(cls, path: Path) -> "SACList":
        raw = json.loads(path.read_text())
        return cls(
            effective_date=date.fromisoformat(raw["effective_date"]),
            compliant=frozenset(s.strip().upper() for s in raw["compliant"]),
            source=raw.get("source", ""),
            verified=bool(raw.get("verified", False)),
        )


@dataclass(frozen=True)
class ListDiff:
    """What changed between two consecutive editions."""

    previous: date
    current: date
    added: frozenset[str]
    removed: frozenset[str]

    @property
    def is_empty(self) -> bool:
        return not self.added and not self.removed


@dataclass(frozen=True)
class SACListStore:
    editions: tuple[SACList, ...]
    """Ordered oldest first."""

    @classmethod
    def load(cls, directory: Path | str | None = None) -> "SACListStore":
        path = Path(directory or DEFAULT_LIST_DIR)
        files = sorted(path.glob("*.json"))
        if not files:
            raise FileNotFoundError(
                f"no SAC list editions in {path}. Download them from "
                "https://www.sc.com.my/development/icm/icm-publications/"
                "list-of-shariah-compliant-securities and convert with "
                "`bursabot sac-import`."
            )
        editions = tuple(sorted((SACList.from_file(f) for f in files), key=lambda e: e.effective_date))
        return cls(editions)

    @property
    def effective_dates(self) -> list[date]:
        return [e.effective_date for e in self.editions]

    def as_of(self, day: date) -> SACList:
        """The edition in force on `day` - the latest one effective on or before it."""
        idx = bisect_right(self.effective_dates, day)
        if idx == 0:
            raise PointInTimeError(
                f"no SAC list was in force on {day}; earliest edition held is "
                f"{self.editions[0].effective_date}. Backtesting before that date "
                "would require screening with a future list (look-ahead bias)."
            )
        return self.editions[idx - 1]

    def latest(self) -> SACList:
        return self.editions[-1]

    def diff(self, previous: SACList, current: SACList) -> ListDiff:
        return ListDiff(
            previous=previous.effective_date,
            current=current.effective_date,
            added=frozenset(current.compliant - previous.compliant),
            removed=frozenset(previous.compliant - current.compliant),
        )

    def latest_diff(self) -> ListDiff:
        """Changes introduced by the most recent edition."""
        if len(self.editions) < 2:
            raise PointInTimeError("need at least two editions to diff")
        return self.diff(self.editions[-2], self.editions[-1])

    def warnings(self) -> list[str]:
        unverified = [e for e in self.editions if not e.verified]
        if not unverified:
            return []
        dates = ", ".join(str(e.effective_date) for e in unverified)
        return [
            f"SAC list editions {dates} are marked unverified (sample data). "
            "Replace them with the real published lists before trading."
        ]
