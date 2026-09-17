"""Go through every counter and say what to do with it.

This is the screener half of the bot, separate from execution: no broker, no orders,
just a direction and the reason behind it for every counter you have data for.

The gates are applied in a fixed order and the first one that fails is the reason
reported, so a verdict always names one specific cause rather than a vague "filtered".
Order matters: Shariah compliance is checked first, because a non-compliant counter is
not a candidate whatever its chart looks like.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence

from .costs import FeeSchedule
from .shariah.list_store import SACList
from .signals.trend import TrendParams, moving_average, momentum
from .types import Bar, Position
from .universe import LiquidityRules, average_daily_value, counter_hurdle

BUY = "BUY"
HOLD = "HOLD"
WATCH = "WATCH"
SELL = "SELL"
AVOID = "AVOID"


@dataclass(frozen=True)
class Verdict:
    symbol: str
    price: float
    direction: str
    reason: str
    compliant: bool
    held_shares: int = 0
    above_trend: bool | None = None
    momentum_pct: float | None = None
    adv: float = 0.0
    hurdle: float = 0.0
    rank: int | None = None

    @property
    def is_actionable(self) -> bool:
        return self.direction in {BUY, SELL}


def _gate(
    symbol: str,
    bars: Sequence[Bar],
    sac_list: SACList,
    rules: LiquidityRules,
    fees: FeeSchedule | None,
    held: int,
) -> tuple[str, str] | None:
    """Return (direction, reason) if a gate rejects this counter, else None."""
    if symbol not in sac_list:
        return (
            (SELL, "not on the SAC list - dispose, and check the purification rule")
            if held
            else (AVOID, "not on the SAC list")
        )
    if len(bars) < rules.min_history_days:
        return (
            (HOLD, f"only {len(bars)} bars of history - no signal yet")
            if held
            else (AVOID, f"only {len(bars)} bars of history")
        )

    price = bars[-1].close
    if price < rules.min_price:
        note = f"price RM{price:.3f} below the RM{rules.min_price:.2f} floor"
        return (HOLD, note + " - not a systematic position") if held else (AVOID, note)

    adv = average_daily_value(bars, rules.lookback_days)
    if adv < rules.min_avg_daily_value:
        note = f"average daily value RM{adv:,.0f} too thin"
        return (HOLD, note + " - not a systematic position") if held else (AVOID, note)

    hurdle = counter_hurdle(price, rules, fees)
    if hurdle > rules.max_hurdle:
        note = f"round-trip hurdle {hurdle:.2%} exceeds {rules.max_hurdle:.2%}"
        return (HOLD, note + " - costs eat any edge") if held else (AVOID, note)
    return None


def rank_counters(
    history: Mapping[str, Sequence[Bar]],
    sac_list: SACList,
    day: date,
    positions: Mapping[str, Position] | None = None,
    rules: LiquidityRules | None = None,
    trend: TrendParams | None = None,
    fees: FeeSchedule | None = None,
) -> list[Verdict]:
    """A verdict for every counter in `history`, best candidates first.

    `history` must already be truncated to `day` by the caller.
    """
    rules = rules or LiquidityRules()
    trend = trend or TrendParams()
    positions = positions or {}

    survivors: list[Verdict] = []
    rejected: list[Verdict] = []

    for symbol in sorted(history):
        bars = [b for b in history[symbol] if b.day <= day]
        held = positions[symbol].shares if symbol in positions else 0
        if not bars:
            rejected.append(
                Verdict(symbol, 0.0, AVOID, "no price history", symbol in sac_list, held)
            )
            continue

        price = bars[-1].close
        gated = _gate(symbol, bars, sac_list, rules, fees, held)
        if gated is not None:
            direction, reason = gated
            rejected.append(
                Verdict(
                    symbol, price, direction, reason, symbol in sac_list, held,
                    adv=average_daily_value(bars, rules.lookback_days),
                    hurdle=counter_hurdle(price, rules, fees),
                )
            )
            continue

        avg = moving_average(bars, trend.trend_window)
        mom = momentum(bars, trend.momentum_window)
        above = avg is not None and price > avg
        survivors.append(
            Verdict(
                symbol, price, WATCH, "", True, held,
                above_trend=above,
                momentum_pct=mom,
                adv=average_daily_value(bars, rules.lookback_days),
                hurdle=counter_hurdle(price, rules, fees),
            )
        )

    # Rank the counters that passed every gate by trailing momentum.
    eligible = [
        v for v in survivors
        if v.above_trend and v.momentum_pct is not None and v.momentum_pct > trend.min_momentum
    ]
    eligible.sort(key=lambda v: v.momentum_pct or 0.0, reverse=True)
    chosen = {v.symbol: i + 1 for i, v in enumerate(eligible[: trend.top_n])}

    decided: list[Verdict] = []
    for verdict in survivors:
        position = chosen.get(verdict.symbol)
        if position is not None:
            direction = HOLD if verdict.held_shares else BUY
            reason = f"trend up, momentum rank {position} of {trend.top_n}"
        elif not verdict.above_trend:
            direction = SELL if verdict.held_shares else AVOID
            reason = "below its long moving average"
        else:
            direction = WATCH
            reason = "trend up but outside the top ranks"
        decided.append(
            Verdict(
                verdict.symbol, verdict.price, direction, reason, True, verdict.held_shares,
                above_trend=verdict.above_trend, momentum_pct=verdict.momentum_pct,
                adv=verdict.adv, hurdle=verdict.hurdle, rank=position,
            )
        )

    order = {BUY: 0, HOLD: 1, WATCH: 2, SELL: 3, AVOID: 4}
    return sorted(
        decided + rejected,
        key=lambda v: (order[v.direction], v.rank or 999, -(v.momentum_pct or -9.9), v.symbol),
    )
