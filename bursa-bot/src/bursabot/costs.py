"""Bursa Malaysia transaction costs, tick sizes and board-lot rounding.

Every figure here is a *default* taken from public sources and must be confirmed
against your own broker's contract notes and Bursa's published schedule before
you trade real money. Fees are the difference between a profitable strategy and
an unprofitable one on this market, so they are modelled explicitly rather than
approximated with a single basis-point number.

Round-trip cost on a small Bursa ticket is typically 0.3%-1%+. Any strategy whose
per-trade edge is thinner than that is not viable here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .types import BOARD_LOT, Side

# (upper bound exclusive, tick). Prices at or above the last bound use FALLBACK_TICK.
_TICK_BANDS: tuple[tuple[float, float], ...] = (
    (1.00, 0.005),
    (3.00, 0.010),
    (5.00, 0.020),
    (10.00, 0.050),
    (25.00, 0.100),
    (100.00, 0.250),
)
FALLBACK_TICK = 0.500


def tick_size(price: float) -> float:
    """Minimum price increment for a security trading at `price` (MYR)."""
    if price <= 0:
        raise ValueError("price must be positive")
    for upper, tick in _TICK_BANDS:
        if price < upper:
            return tick
    return FALLBACK_TICK


def round_to_tick(price: float, side: Side) -> float:
    """Snap a limit price to a valid tick, conservatively for the given side.

    A buy limit rounds *down* and a sell limit rounds *up*, so rounding never
    silently makes an order more aggressive than the strategy intended.
    """
    tick = tick_size(price)
    steps = price / tick
    snapped = (math.floor(steps) if side is Side.BUY else math.ceil(steps)) * tick
    # Rounding can cross a band boundary (e.g. 3.00 down to 2.99); re-snap once.
    if tick_size(snapped) != tick:
        tick = tick_size(snapped)
        steps = price / tick
        snapped = (math.floor(steps) if side is Side.BUY else math.ceil(steps)) * tick
    return round(snapped, 4)


def round_lots(shares: int) -> int:
    """Round a share count down to a whole board lot. Odd lots are not traded."""
    if shares < 0:
        raise ValueError("shares must not be negative")
    return (shares // BOARD_LOT) * BOARD_LOT


@dataclass(frozen=True)
class FeeSchedule:
    """Per-side transaction costs. Defaults approximate a cheap Malaysian online broker.

    Confirm all of these with your broker before relying on them:

    * `brokerage_rate` / `brokerage_min` vary widely (roughly 0.05%-0.42%, minimum
      RM7-RM12 online). Islamic accounts on Bursa Malaysia-i may price differently.
    * `clearing_rate` and `stamp_duty_*` are exchange/government charges and apply to
      *both* the buy and the sell.
    * `service_tax_on_clearing` differs between brokers - some apply SST to the
      clearing fee as well as to brokerage.
    """

    brokerage_rate: float = 0.0010
    brokerage_min: float = 8.00
    clearing_rate: float = 0.0003
    clearing_cap: float = 1000.00
    stamp_duty_per_1000: float = 1.00
    stamp_duty_cap: float = 1000.00
    service_tax_rate: float = 0.08
    service_tax_on_clearing: bool = True


@dataclass(frozen=True)
class CostBreakdown:
    contract_value: float
    brokerage: float
    clearing_fee: float
    stamp_duty: float
    service_tax: float

    @property
    def total(self) -> float:
        return round(
            self.brokerage + self.clearing_fee + self.stamp_duty + self.service_tax, 2
        )

    @property
    def cash_out(self) -> float:
        """What a buy costs you in total, fees included."""
        return round(self.contract_value + self.total, 2)

    @property
    def cash_in(self) -> float:
        """What a sell nets you after fees."""
        return round(self.contract_value - self.total, 2)


def compute_costs(
    price: float, shares: int, schedule: FeeSchedule | None = None
) -> CostBreakdown:
    """Cost of one side of a trade (a buy or a sell), in MYR."""
    if price <= 0 or shares <= 0:
        raise ValueError("price and shares must be positive")
    sched = schedule or FeeSchedule()

    contract_value = price * shares
    brokerage = max(sched.brokerage_min, contract_value * sched.brokerage_rate)
    clearing = min(contract_value * sched.clearing_rate, sched.clearing_cap)
    # Stamp duty is charged per RM1,000 of contract value or part thereof.
    stamp = min(
        math.ceil(contract_value / 1000.0) * sched.stamp_duty_per_1000,
        sched.stamp_duty_cap,
    )
    taxable = brokerage + (clearing if sched.service_tax_on_clearing else 0.0)
    tax = taxable * sched.service_tax_rate

    return CostBreakdown(
        contract_value=round(contract_value, 2),
        brokerage=round(brokerage, 2),
        clearing_fee=round(clearing, 2),
        stamp_duty=round(stamp, 2),
        service_tax=round(tax, 2),
    )


def round_trip_cost_pct(
    price: float, shares: int, schedule: FeeSchedule | None = None
) -> float:
    """Buy-plus-sell *fees* as a fraction of contract value, assuming a flat price."""
    one_side = compute_costs(price, shares, schedule)
    return (one_side.total * 2) / one_side.contract_value


def spread_cost_pct(price: float) -> float:
    """One tick as a fraction of price.

    On a penny counter this dominates everything else. At RM0.20 the tick is half a
    sen, so a single tick is 2.5% of the price - wider than most strategies' entire
    expected edge, before a sen of brokerage is paid.
    """
    return tick_size(price) / price


def hurdle_pct(
    price: float,
    shares: int,
    schedule: FeeSchedule | None = None,
    spread_ticks: float = 1.0,
) -> float:
    """Total round-trip drag: fees on both sides plus crossing the spread.

    `spread_ticks` is the spread paid across the *whole* round trip - one tick by
    default, which assumes you buy at the ask and sell at the bid on a one-tick
    market. Thin counters are routinely several ticks wide, so raise it for those.

    This is the real hurdle. A strategy whose expected move per trade is smaller
    than this number loses money no matter how good its signal looks in a backtest.
    """
    return round_trip_cost_pct(price, shares, schedule) + spread_ticks * spread_cost_pct(price)
