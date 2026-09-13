"""Simulated broker used by the backtester and by paper trading.

Fills are modelled pessimistically: you cross the spread by one tick and pay full
fees. Optimistic fill assumptions are the single most common reason a Bursa backtest
looks nothing like the live account.
"""

from __future__ import annotations

from datetime import date

from ..costs import FeeSchedule, compute_costs, tick_size
from ..types import Fill, Order, Position, Side


class PaperBroker:
    def __init__(self, cash: float, fees: FeeSchedule | None = None, slippage_ticks: int = 1) -> None:
        self._cash = float(cash)
        self._positions: dict[str, Position] = {}
        self.fees = fees or FeeSchedule()
        self.slippage_ticks = slippage_ticks
        self.fills: list[Fill] = []

    def positions(self) -> dict[str, Position]:
        return self._positions

    def cash(self) -> float:
        return round(self._cash, 2)

    def fill_price(self, price: float, side: Side) -> float:
        adjustment = tick_size(price) * self.slippage_ticks
        return round(price + adjustment if side is Side.BUY else price - adjustment, 4)

    def equity(self, marks: dict[str, float]) -> float:
        holdings = sum(
            position.shares * marks.get(symbol, position.cost_basis)
            for symbol, position in self._positions.items()
        )
        return round(self._cash + holdings, 2)

    def submit(self, order: Order, price: float, day: date) -> Fill:
        executed = self.fill_price(price, order.side)
        costs = compute_costs(executed, order.shares, self.fees)

        if order.side is Side.BUY:
            self._cash -= costs.cash_out
            existing = self._positions.get(order.symbol)
            if existing and existing.shares:
                total_cost = existing.cost_basis * existing.shares + costs.cash_out
                shares = existing.shares + order.shares
                existing.shares = shares
                existing.cost_basis = total_cost / shares
            else:
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    shares=order.shares,
                    cost_basis=costs.cash_out / order.shares,
                )
        else:
            position = self._positions.get(order.symbol)
            if position is None or position.shares < order.shares:
                raise ValueError(f"{order.symbol}: cannot sell more than held")
            self._cash += costs.cash_in
            position.shares -= order.shares
            if position.shares == 0:
                del self._positions[order.symbol]

        fill = Fill(
            symbol=order.symbol,
            side=order.side,
            shares=order.shares,
            price=executed,
            day=day,
            fees=costs.total,
        )
        self.fills.append(fill)
        return fill
