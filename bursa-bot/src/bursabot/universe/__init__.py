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

from ..costs import FeeSchedule, hurdle_pct, round_lots
from ..shariah.list_store import SACList
from ..shariah.screen import filter_universe
from ..types import BOARD_LOT, Bar


@dataclass(frozen=True)
class LiquidityRules:
    lookback_days: int = 20
    min_avg_daily_value: float = 250_000.0
    """Average daily traded value in MYR over the lookback window."""

    min_price: float = 0.20
    """Below this, tick sizes and minimum brokerage dominate any edge."""

    min_history_days: int = 250
    """Enough history for a 200-day trend filter plus a buffer."""

    max_hurdle: float = 0.025
    """Reject counters whose round-trip cost exceeds this fraction of the position.

    This is the gate that matters most on Bursa and the one generic screeners lack.
    Above about RM0.50 Bursa's tick bands keep the hurdle in a 1.0%-1.6% band
    whatever the price. Below that it climbs fast: 2.3% at RM0.30, 3.1% at RM0.20,
    5.6% at RM0.10, because a half-sen tick is a large slice of a small price. The
    default rejects the hopeless end; tighten it to taste.
    """

    hurdle_ticket: float = 5_000.0
    """Ticket size the hurdle is measured at. Smaller tickets face a worse hurdle."""

    hurdle_spread_ticks: float = 1.0
    """Ticks of spread assumed across a round trip. Raise for thin counters."""


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
    dropped_high_cost: tuple[str, ...] = ()

    def summary(self) -> str:
        return (
            f"{self.day}: {len(self.candidates)} tradeable "
            f"(-{len(self.dropped_non_compliant)} non-compliant, "
            f"-{len(self.dropped_illiquid)} illiquid, "
            f"-{len(self.dropped_high_cost)} cost hurdle, "
            f"-{len(self.dropped_insufficient_history)} short history)"
        )


def counter_hurdle(price: float, rules: LiquidityRules, fees: FeeSchedule | None) -> float:
    """Round-trip drag on a `hurdle_ticket`-sized position in this counter.

    Measured on at least one board lot: a RM100 counter cannot be bought in a
    RM5,000 ticket at all, and its cost drag is still whatever 100 shares costs.
    """
    shares = max(round_lots(int(rules.hurdle_ticket // price)), BOARD_LOT)
    return hurdle_pct(price, shares, fees, rules.hurdle_spread_ticks)


def build_universe(
    day: date,
    history: Mapping[str, Sequence[Bar]],
    sac_list: SACList,
    rules: LiquidityRules | None = None,
    fees: FeeSchedule | None = None,
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
    high_cost: list[str] = []

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
        if counter_hurdle(bars[-1].close, rules, fees) > rules.max_hurdle:
            high_cost.append(symbol)
            continue
        candidates.append(symbol)

    return UniverseReport(
        day=day,
        candidates=tuple(candidates),
        dropped_non_compliant=tuple(non_compliant),
        dropped_illiquid=tuple(illiquid),
        dropped_insufficient_history=tuple(short_history),
        dropped_high_cost=tuple(high_cost),
    )
