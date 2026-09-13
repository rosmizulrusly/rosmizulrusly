"""Event-driven daily backtester.

It shares the real cost model, the real sizing rules and the real broker guard with
live trading, so a strategy that is refused in production is also refused here.

Two Bursa/Shariah specifics it models that a generic backtester will not:

* the SAC list is resolved *as of* each simulated day, so the universe shrinks and
  grows exactly as it did historically;
* when a held name leaves the list, the engine forces an exit on the next trading day
  and books any gain above the announcement-day close to the purification ledger.

What it still does not model, and you should not forget: dividends, corporate actions
beyond whatever your price adjustment already applied, price limits and trading halts,
partial fills, and queue position. Treat the output as an upper bound.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Mapping, Sequence

from ..costs import FeeSchedule
from ..execution.base import ComplianceError, GuardedBroker
from ..execution.paper import PaperBroker
from ..risk import KillSwitch, RiskLimits, exit_orders, size_orders
from ..shariah.list_store import SACListStore
from ..shariah.purification import purification_due
from ..shariah.screen import reconcile_holdings
from ..signals.trend import TrendParams, target_weights
from ..types import Bar, Side
from ..universe import LiquidityRules, average_daily_value, build_universe


@dataclass(frozen=True)
class BacktestConfig:
    start: date
    end: date
    initial_cash: float = 100_000.0
    rebalance: str = "monthly"
    """'monthly' (first trading day of each month) or 'weekly' (each Monday-or-later)."""

    fees: FeeSchedule = field(default_factory=FeeSchedule)
    limits: RiskLimits = field(default_factory=RiskLimits)
    liquidity: LiquidityRules = field(default_factory=LiquidityRules)
    trend: TrendParams = field(default_factory=TrendParams)
    slippage_ticks: int = 1


@dataclass
class BacktestResult:
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    fills: list = field(default_factory=list)
    total_fees: float = 0.0
    purification_owed: float = 0.0
    forced_exits: list[tuple[date, str, float]] = field(default_factory=list)
    refused_orders: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1][1] if self.equity_curve else 0.0

    @property
    def total_return(self) -> float:
        if not self.equity_curve:
            return 0.0
        start = self.equity_curve[0][1]
        return self.final_equity / start - 1.0 if start else 0.0

    @property
    def max_drawdown(self) -> float:
        peak = float("-inf")
        worst = 0.0
        for _, equity in self.equity_curve:
            peak = max(peak, equity)
            if peak > 0:
                worst = min(worst, equity / peak - 1.0)
        return worst

    def summary(self) -> str:
        years = max(len(self.equity_curve) / 252.0, 1e-9)
        cagr = (1 + self.total_return) ** (1 / years) - 1 if self.total_return > -1 else -1.0
        return "\n".join(
            [
                f"period          {self.equity_curve[0][0]} -> {self.equity_curve[-1][0]}"
                if self.equity_curve
                else "period          (empty)",
                f"final equity    RM{self.final_equity:,.2f}",
                f"total return    {self.total_return:.2%}",
                f"CAGR (approx)   {cagr:.2%}",
                f"max drawdown    {self.max_drawdown:.2%}",
                f"trades          {len(self.fills)}",
                f"fees paid       RM{self.total_fees:,.2f}",
                f"purification    RM{self.purification_owed:,.2f} owed to charity",
                f"forced exits    {len(self.forced_exits)}",
            ]
        )


def _is_rebalance_day(day: date, previous: date | None, mode: str) -> bool:
    if previous is None:
        return True
    if mode == "weekly":
        return day.isocalendar()[1] != previous.isocalendar()[1]
    return (day.year, day.month) != (previous.year, previous.month)


def run_backtest(
    history: Mapping[str, Sequence[Bar]],
    sac_store: SACListStore,
    config: BacktestConfig,
) -> BacktestResult:
    result = BacktestResult()
    result.notes.extend(sac_store.warnings())

    days = sorted({bar.day for bars in history.values() for bar in bars})
    days = [d for d in days if config.start <= d <= config.end]
    if not days:
        raise ValueError("no price history inside the backtest window")

    broker = PaperBroker(config.initial_cash, config.fees, config.slippage_ticks)
    kill_switch = KillSwitch(config.limits)

    truncated: dict[str, list[Bar]] = {s: list(bars) for s, bars in history.items()}
    last_rebalance: date | None = None
    last_edition: date | None = None
    pending_exits: dict[str, str] = {}

    for day in days:
        closes = {
            symbol: bars[-1].close
            for symbol, bars in (
                (s, [b for b in bs if b.day <= day]) for s, bs in truncated.items()
            )
            if bars and bars[-1].day == day
        }
        marks = {**{s: p.cost_basis for s, p in broker.positions().items()}, **closes}
        equity_open = broker.equity(marks)

        # Point-in-time Shariah list. A new edition triggers the forced-exit path.
        sac_list = sac_store.as_of(day)
        guarded = GuardedBroker(broker, tradeable=sac_list.compliant, fees=config.fees)

        def execute(order):
            """Submit an order and book any purification the sale triggers.

            Every sell goes through here, not just forced exits: a reclassified
            holding can also be sold by an ordinary rebalance, and the gain above
            the announcement-day close is owed either way.
            """
            price = closes.get(order.symbol)
            if price is None:
                return None
            position = broker.positions().get(order.symbol)
            reference = position.reference_close if position else None
            fill = guarded.submit(order, price, day)
            result.fills.append(fill)
            result.total_fees += fill.fees
            if order.side is Side.SELL and reference is not None:
                result.purification_owed += purification_due(
                    fill.price, reference, fill.shares
                )
            return fill

        # Forced exits execute on the next session - an announcement is not a fill.
        if pending_exits:
            for order in exit_orders(broker.positions(), pending_exits):
                execute(order)
                pending_exits.pop(order.symbol, None)

        if last_edition != sac_list.effective_date:
            last_edition = sac_list.effective_date
            removals = reconcile_holdings(
                broker.positions(),
                sac_list,
                announcement_day=day,
                closes={s: closes[s] for s in broker.positions() if s in closes},
            )
            for notice in removals:
                broker.positions()[notice.symbol].reference_close = notice.reference_close
                pending_exits[notice.symbol] = f"SAC removal effective {sac_list.effective_date}"
                result.forced_exits.append((day, notice.symbol, notice.reference_close))

        if _is_rebalance_day(day, last_rebalance, config.rebalance):
            last_rebalance = day
            window = {s: [b for b in bs if b.day <= day] for s, bs in truncated.items()}
            universe = build_universe(day, window, sac_list, config.liquidity)
            targets = target_weights(universe.candidates, window, day, config.trend)
            adv = {
                s: average_daily_value(window[s], config.liquidity.lookback_days)
                for s in universe.candidates
            }
            equity_now = broker.equity(marks)
            blocked = kill_switch.check(equity_open, equity_now)
            orders = size_orders(
                targets,
                broker.positions(),
                closes,
                equity_now,
                adv=adv,
                limits=config.limits,
                fees=config.fees,
                allow_buys=not blocked,
            )
            # Sell first so the proceeds fund the buys - no margin is available.
            for order in sorted(orders, key=lambda o: o.side is Side.BUY):
                try:
                    execute(order)
                except ComplianceError as exc:
                    result.refused_orders.append(f"{day} {exc}")
                    continue
                pending_exits.pop(order.symbol, None)

        marks = {**{s: p.cost_basis for s, p in broker.positions().items()}, **closes}
        result.equity_curve.append((day, broker.equity(marks)))

    result.total_fees = round(result.total_fees, 2)
    result.purification_owed = round(result.purification_owed, 2)
    return result
