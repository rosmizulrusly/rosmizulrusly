"""Universe construction: Shariah screen first, then liquidity.

Order matters. The Shariah filter is applied before anything else so a
non-compliant name never reaches the strategy; the liquidity filter then removes
names the bot cannot actually trade. Bursa has a long tail of counters that trade a
few thousand ringgit a day - a backtest will happily "fill" you there and live
trading will not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence

from ..shariah.list_store import SACList
from ..shariah.screen import filter_universe
from ..types import Bar


@dataclass(frozen=True)
class LiquidityRules:
    lookback_days: int = 20
    min_avg_daily_value: float = 250_000.0
    """Average daily traded value in MYR over the lookback window."""

    min_price: float = 0.20
    """Below this, tick sizes and minimum brokerage dominate any edge."""

    min_history_days: int = 250
    """Enough history for a 200-day trend filter plus a buffer."""


def average_daily_value(bars: Sequence[Bar], lookback: int) -> float:
    window = bars[-lookback:]
    if not window:
        return 0.0
    return sum(bar.close * bar.volume for bar in window) / len(window)


@dataclass(frozen=True)
class UniverseReport:
    day: date
    candidates: tuple[str, ...]
    dropped_non_compliant: tuple[str, ...]
    dropped_illiquid: tuple[str, ...]
    dropped_insufficient_history: tuple[str, ...]

    def summary(self) -> str:
        return (
            f"{self.day}: {len(self.candidates)} tradeable "
            f"(-{len(self.dropped_non_compliant)} non-compliant, "
            f"-{len(self.dropped_illiquid)} illiquid, "
            f"-{len(self.dropped_insufficient_history)} short history)"
        )


def build_universe(
    day: date,
    history: Mapping[str, Sequence[Bar]],
    sac_list: SACList,
    rules: LiquidityRules | None = None,
) -> UniverseReport:
    """Tradeable names as at `day`, given history up to and including that day.

    `history` must be truncated to `day` by the caller - this function does not
    look forward, and passing it future bars will silently bias your backtest.
    """
    rules = rules or LiquidityRules()
    all_symbols = sorted(history)
    compliant = set(filter_universe(all_symbols, sac_list))

    candidates: list[str] = []
    non_compliant: list[str] = []
    illiquid: list[str] = []
    short_history: list[str] = []

    for symbol in all_symbols:
        if symbol not in compliant:
            non_compliant.append(symbol)
            continue
        bars = [bar for bar in history[symbol] if bar.day <= day]
        if len(bars) < rules.min_history_days:
            short_history.append(symbol)
            continue
        if bars[-1].close < rules.min_price:
            illiquid.append(symbol)
            continue
        if average_daily_value(bars, rules.lookback_days) < rules.min_avg_daily_value:
            illiquid.append(symbol)
            continue
        candidates.append(symbol)

    return UniverseReport(
        day=day,
        candidates=tuple(candidates),
        dropped_non_compliant=tuple(non_compliant),
        dropped_illiquid=tuple(illiquid),
        dropped_insufficient_history=tuple(short_history),
    )
