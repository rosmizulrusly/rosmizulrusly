"""Local daily price storage.

Deliberately CSV and stdlib-only so the core of the bot has no third-party
dependency and its tests run anywhere. Swap in Parquet/DuckDB once the universe
grows past a few hundred names - `PriceStore` is the only place that needs to change.

Prices must be adjusted for splits, bonus issues and dividends before they land
here. Malaysian corporate actions are messy and unadjusted history will invent
overnight gaps that any momentum strategy will happily trade.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from ..types import Bar

_HEADER = ("date", "open", "high", "low", "close", "volume")


def save_bars_csv(path: Path | str, bars: Sequence[Bar]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(_HEADER)
        for bar in sorted(bars, key=lambda b: b.day):
            writer.writerow(
                [bar.day.isoformat(), bar.open, bar.high, bar.low, bar.close, bar.volume]
            )


def load_bars_csv(path: Path | str, symbol: str) -> list[Bar]:
    with Path(path).open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [
        Bar(
            symbol=symbol,
            day=date.fromisoformat(row["date"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=int(float(row["volume"])),
        )
        for row in rows
    ]


class PriceStore:
    """Daily bars on disk, one CSV per symbol."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def path_for(self, symbol: str) -> Path:
        return self.root / f"{symbol.upper()}.csv"

    def symbols(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.csv"))

    def has(self, symbol: str) -> bool:
        return self.path_for(symbol).exists()

    def write(self, symbol: str, bars: Sequence[Bar]) -> None:
        save_bars_csv(self.path_for(symbol), bars)

    def read(self, symbol: str) -> list[Bar]:
        path = self.path_for(symbol)
        if not path.exists():
            raise FileNotFoundError(f"no price history for {symbol} at {path}")
        return load_bars_csv(path, symbol.upper())

    def read_many(self, symbols: Iterable[str]) -> dict[str, list[Bar]]:
        return {s.upper(): self.read(s) for s in symbols}

    def trading_days(self, symbols: Iterable[str]) -> list[date]:
        """Union of every day on which any requested symbol traded, ascending."""
        days: set[date] = set()
        for symbol in symbols:
            days.update(bar.day for bar in self.read(symbol))
        return sorted(days)
