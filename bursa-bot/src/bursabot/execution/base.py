"""Broker interface and the compliance guard every adapter is wrapped in.

The guard lives here, not in the strategy. A strategy bug should not be able to
produce a short sale or a margined buy: those rules are enforced at the last point
before an order leaves the process, where nothing can bypass them.

Adding a real broker (moomoo MY OpenAPI via OpenD, a futures broker's FIX session)
means implementing `Broker` and wrapping it in `GuardedBroker` - nothing above this
layer changes. Confirm with your broker that automated order entry is permitted
under your account terms before you connect one.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from ..costs import FeeSchedule, compute_costs
from ..types import BOARD_LOT, Fill, Order, Position, Side


class ComplianceError(RuntimeError):
    """An order violated a hard rule and was not sent."""


@runtime_checkable
class Broker(Protocol):
    def positions(self) -> dict[str, Position]: ...

    def cash(self) -> float: ...

    def submit(self, order: Order, price: float, day: date) -> Fill: ...


class GuardedBroker:
    """Wraps any `Broker` and refuses orders that break the account's hard rules."""

    def __init__(
        self,
        inner: Broker,
        tradeable: frozenset[str] | None = None,
        fees: FeeSchedule | None = None,
        allow_forced_exits: bool = True,
    ) -> None:
        self.inner = inner
        self.tradeable = tradeable
        self.fees = fees or FeeSchedule()
        self.allow_forced_exits = allow_forced_exits

    def positions(self) -> dict[str, Position]:
        return self.inner.positions()

    def cash(self) -> float:
        return self.inner.cash()

    def check(self, order: Order, price: float) -> None:
        if order.shares % BOARD_LOT:
            raise ComplianceError(f"{order.symbol}: {order.shares} is not a whole board lot")

        held = self.inner.positions().get(order.symbol)
        held_shares = held.shares if held else 0

        if order.side is Side.SELL:
            if order.shares > held_shares:
                raise ComplianceError(
                    f"{order.symbol}: selling {order.shares} against {held_shares} held "
                    "would be a short sale, which is not permitted"
                )
            return

        # Buys: must be Shariah-compliant and fully funded from cash - never on margin.
        if self.tradeable is not None and order.symbol not in self.tradeable:
            raise ComplianceError(
                f"{order.symbol} is not on the SAC list in force; buy refused"
            )
        outlay = compute_costs(price, order.shares, self.fees).cash_out
        if outlay > self.cash() + 1e-9:
            raise ComplianceError(
                f"{order.symbol}: outlay RM{outlay:,.2f} exceeds cash RM{self.cash():,.2f}; "
                "margin financing is not permitted"
            )

    def submit(self, order: Order, price: float, day: date) -> Fill:
        self.check(order, price)
        return self.inner.submit(order, price, day)
