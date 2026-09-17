"""A deliberately dull long-only trend strategy.

Start here, not with machine learning. With ~900 listed names, thin liquidity and a
round-trip cost near 1%, a complicated model will fit noise long before it finds an
edge. This rule is simple enough that when the backtest disagrees with live results
you can tell why.

Rule: hold an equal-weighted basket of the names that are (a) above their long
moving average and (b) in the top `top_n` by trailing momentum. Rebalance monthly.
Benchmark it against buy-and-hold FBM Hijrah Shariah; if it does not win after
costs, do not trade it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence

from ..types import Bar


@dataclass(frozen=True)
class TrendParams:
    trend_window: int = 200
    momentum_window: int = 120
    top_n: int = 10
    min_momentum: float = 0.0
    """Reject names whose trailing return is below this, even if ranked highly."""


@dataclass(frozen=True)
class TrendSignal:
    symbol: str
    close: float
    moving_average: float
    momentum: float

    @property
    def above_trend(self) -> bool:
        return self.close > self.moving_average


def moving_average(bars: Sequence[Bar], window: int) -> float | None:
    if len(bars) < window:
        return None
    return sum(bar.close for bar in bars[-window:]) / window


def momentum(bars: Sequence[Bar], window: int) -> float | None:
    """Simple trailing total return over `window` bars."""
    if len(bars) <= window:
        return None
    past = bars[-window - 1].close
    if past <= 0:
        return None
    return bars[-1].close / past - 1.0


def evaluate(
    symbols: Sequence[str],
    history: Mapping[str, Sequence[Bar]],
    day: date,
    params: TrendParams,
) -> list[TrendSignal]:
    signals: list[TrendSignal] = []
    for symbol in symbols:
        bars = [bar for bar in history[symbol] if bar.day <= day]
        avg = moving_average(bars, params.trend_window)
        mom = momentum(bars, params.momentum_window)
        if avg is None or mom is None:
            continue
        signals.append(
            TrendSignal(symbol=symbol, close=bars[-1].close, moving_average=avg, momentum=mom)
        )
    return signals


def target_weights(
    symbols: Sequence[str],
    history: Mapping[str, Sequence[Bar]],
    day: date,
    params: TrendParams | None = None,
) -> dict[str, float]:
    """Equal-weight target allocation. Empty dict means go to cash."""
    params = params or TrendParams()
    eligible = [
        s
        for s in evaluate(symbols, history, day, params)
        if s.above_trend and s.momentum > params.min_momentum
    ]
    eligible.sort(key=lambda s: s.momentum, reverse=True)
    chosen = eligible[: params.top_n]
    if not chosen:
        return {}
    weight = 1.0 / len(chosen)
    return {s.symbol: weight for s in chosen}
