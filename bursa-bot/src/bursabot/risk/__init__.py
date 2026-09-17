"""Position sizing, exposure limits and the kill switch.

This layer is what stands between a strategy bug and your capital, so its rules are
hard limits rather than suggestions:

* gross exposure can never exceed 100% - there is no margin, by construction;
* every order is a whole board lot;
* a ticket too small to clear its own fees is dropped rather than sent;
* a position is capped as a share of the name's average daily value, because a
  backtest fill in an illiquid Bursa counter is fiction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..costs import FeeSchedule, compute_costs, round_lots
from ..types import BOARD_LOT, Order, Position, Side


@dataclass(frozen=True)
class RiskLimits:
    max_gross_exposure: float = 0.95
    """Fraction of equity that may be invested. Must stay <= 1.0: no leverage, no riba."""

    max_position_weight: float = 0.20
    max_adv_participation: float = 0.05
    """Cap a position at this fraction of the name's average daily traded value."""

    min_ticket_value: float = 3_000.0
    """Below this, fixed brokerage and stamp duty swamp any realistic edge."""

    rebalance_band: float = 0.02
    """Ignore weight drift smaller than this to avoid churning fees away."""

    max_daily_loss: float = 0.03
    """Equity drawdown within a single day that halts new buying."""

    def __post_init__(self) -> None:
        if self.max_gross_exposure > 1.0:
            raise ValueError("max_gross_exposure above 1.0 would require margin financing")
        if not 0 < self.max_position_weight <= 1.0:
            raise ValueError("max_position_weight must be in (0, 1]")


class KillSwitch:
    """Halts new buying after an intraday loss threshold is breached."""

    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits
        self.tripped = False
        self.reason = ""

    def check(self, equity_open: float, equity_now: float) -> bool:
        if equity_open <= 0:
            return self.tripped
        drawdown = (equity_open - equity_now) / equity_open
        if drawdown >= self.limits.max_daily_loss:
            self.tripped = True
            self.reason = f"daily loss {drawdown:.2%} >= limit {self.limits.max_daily_loss:.2%}"
        return self.tripped

    def reset(self) -> None:
        self.tripped = False
        self.reason = ""


def _shares_for_value(value: float, price: float) -> int:
    return round_lots(int(value // price))


def size_orders(
    targets: Mapping[str, float],
    positions: Mapping[str, Position],
    prices: Mapping[str, float],
    equity: float,
    adv: Mapping[str, float] | None = None,
    limits: RiskLimits | None = None,
    fees: FeeSchedule | None = None,
    allow_buys: bool = True,
) -> list[Order]:
    """Turn target weights into board-lot orders against current holdings.

    Sells are always allowed - a kill switch or a Shariah exit must be able to
    reduce risk even when buying is blocked.
    """
    limits = limits or RiskLimits()
    adv = adv or {}
    if equity <= 0:
        return []

    capped: dict[str, float] = {}
    for symbol, weight in targets.items():
        if weight <= 0 or symbol not in prices:
            continue
        capped[symbol] = min(weight, limits.max_position_weight)

    total = sum(capped.values())
    if total > limits.max_gross_exposure and total > 0:
        scale = limits.max_gross_exposure / total
        capped = {s: w * scale for s, w in capped.items()}

    orders: list[Order] = []
    held = {s: p.shares for s, p in positions.items() if p.shares > 0}

    for symbol in sorted(set(capped) | set(held)):
        price = prices.get(symbol)
        if price is None or price <= 0:
            continue
        target_value = capped.get(symbol, 0.0) * equity

        limit_value = adv.get(symbol)
        if limit_value is not None:
            target_value = min(target_value, limit_value * limits.max_adv_participation)

        target_shares = _shares_for_value(target_value, price)
        current_shares = held.get(symbol, 0)
        delta = target_shares - current_shares

        if delta == 0:
            continue
        drift = abs(delta * price) / equity
        if drift < limits.rebalance_band and current_shares > 0 and target_shares > 0:
            continue

        side = Side.BUY if delta > 0 else Side.SELL
        shares = round_lots(abs(delta))
        if shares < BOARD_LOT:
            continue
        if side is Side.BUY:
            if not allow_buys:
                continue
            if shares * price < limits.min_ticket_value:
                continue
            if compute_costs(price, shares, fees).total / (shares * price) > 0.01:
                # Fees alone would exceed 1% of the ticket - not worth sending.
                continue
        orders.append(Order(symbol=symbol, side=side, shares=shares, reason="rebalance"))

    return orders


def exit_orders(positions: Mapping[str, Position], symbols: Mapping[str, str]) -> list[Order]:
    """Full-size sell orders for named holdings, with the reason recorded.

    `symbols` maps symbol -> reason (for example "SAC reclassification 2025-11-28").
    """
    orders: list[Order] = []
    for symbol, reason in sorted(symbols.items()):
        position = positions.get(symbol)
        if position is None or position.shares <= 0:
            continue
        orders.append(
            Order(symbol=symbol, side=Side.SELL, shares=round_lots(position.shares), reason=reason)
        )
    return orders
