"""Alert-only broker: the bot decides, you place the order.

Start here. It needs no broker API, it is unambiguously permitted under every
broker's terms, and it forces you to watch the strategy's decisions for a few months
before any code is allowed to move real money.

`sink` is any callable taking a string - `print`, a logger, or a Telegram send.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from ..costs import FeeSchedule, compute_costs
from ..types import Fill, Order, Position, Side


class AlertOnlyBroker:
    def __init__(
        self,
        positions: dict[str, Position] | None = None,
        cash: float = 0.0,
        sink: Callable[[str], None] = print,
        fees: FeeSchedule | None = None,
    ) -> None:
        self._positions = positions or {}
        self._cash = cash
        self.sink = sink
        self.fees = fees or FeeSchedule()
        self.alerts: list[str] = []

    def positions(self) -> dict[str, Position]:
        return self._positions

    def cash(self) -> float:
        return self._cash

    def adjust_cash(self, delta: float) -> None:
        """Credit expected sale proceeds within one run.

        Holdings are left untouched - nothing has actually been sold. This exists so
        that buy recommendations later in the same run are funded by the sells
        recommended earlier, instead of being refused as unaffordable.
        """
        self._cash += delta

    def submit(self, order: Order, price: float, day: date) -> Fill:
        costs = compute_costs(price, order.shares, self.fees)
        cash_line = (
            f"outlay ~RM{costs.cash_out:,.2f}"
            if order.side is Side.BUY
            else f"proceeds ~RM{costs.cash_in:,.2f}"
        )
        message = (
            f"[{day}] {order.side.value} {order.shares:,} {order.symbol} "
            f"@ ~RM{price:.3f} ({order.lots} lots, {cash_line}, "
            f"fees RM{costs.total:,.2f})"
            + (f" - {order.reason}" if order.reason else "")
        )
        self.alerts.append(message)
        self.sink(message)
        # Nothing is executed: the fill is a record of what was recommended.
        return Fill(
            symbol=order.symbol,
            side=order.side,
            shares=order.shares,
            price=price,
            day=day,
            fees=costs.total,
        )
