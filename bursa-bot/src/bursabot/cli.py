"""Command line entry point: `bursabot <command>` (or `python -m bursabot.cli`)."""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from .backtest import BacktestConfig, run_backtest
from .calendar_my import MYT, CalendarDataMissing, TradingCalendar
from .config import Settings
from .costs import compute_costs, round_trip_cost_pct, tick_size
from .data.store import PriceStore
from .shariah.list_store import SACListStore
from .shariah.purification import PurificationLedger
from .types import Bar
from .universe import build_universe

BANNER = (
    "bursabot - Shariah-screened, long-only, no-margin, no-short.\n"
    "Not investment advice. Verify fees, holidays and the SAC list against primary "
    "sources before risking money.\n"
)


def _warn(lines: list[str]) -> None:
    for line in lines:
        print(f"  WARNING: {line}")


def cmd_costs(args: argparse.Namespace) -> int:
    settings = Settings.load(args.config)
    breakdown = compute_costs(args.price, args.shares, settings.fees)
    print(f"{args.shares:,} shares @ RM{args.price:.3f}  (tick RM{tick_size(args.price):.3f})")
    print(f"  contract value  RM{breakdown.contract_value:,.2f}")
    print(f"  brokerage       RM{breakdown.brokerage:,.2f}")
    print(f"  clearing fee    RM{breakdown.clearing_fee:,.2f}")
    print(f"  stamp duty      RM{breakdown.stamp_duty:,.2f}")
    print(f"  service tax     RM{breakdown.service_tax:,.2f}")
    print(f"  one side total  RM{breakdown.total:,.2f}")
    print(f"  round trip      {round_trip_cost_pct(args.price, args.shares, settings.fees):.3%} of value")
    return 0


def cmd_calendar(args: argparse.Namespace) -> int:
    settings = Settings.load(args.config)
    calendar = TradingCalendar.load(settings.calendar_file)
    _warn(calendar.warnings())
    day = date.fromisoformat(args.date) if args.date else datetime.now(MYT).date()
    try:
        trading = calendar.is_trading_day(day)
    except CalendarDataMissing as exc:
        print(f"  ERROR: {exc}")
        return 1
    print(f"{day}: {'trading day' if trading else 'market closed'}")
    if trading:
        print(f"  session now     {calendar.session(datetime.now(MYT))}")
        print(f"  settles (T+2)   {calendar.settlement_date(day)}")
    print(f"  next open       {calendar.next_trading_day(day)}")
    return 0


def cmd_sac_import(args: argparse.Namespace) -> int:
    """Convert a plain list of stock codes into a point-in-time SAC list edition."""
    codes = [
        line.strip().upper()
        for line in Path(args.codes).read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if not codes:
        print("  ERROR: no codes found")
        return 1
    effective = date.fromisoformat(args.effective)
    out = Path(args.out_dir) / f"{effective.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "effective_date": effective.isoformat(),
                "source": args.source,
                "verified": False,
                "compliant": sorted(set(codes)),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {out} with {len(set(codes))} securities")
    print("  Check the count against the SC's press release, then set \"verified\": true.")
    return 0


def cmd_sac_diff(args: argparse.Namespace) -> int:
    settings = Settings.load(args.config)
    store = SACListStore.load(settings.sac_dir)
    _warn(store.warnings())
    diff = store.latest_diff()
    print(f"{diff.previous} -> {diff.current}")
    print(f"  added   ({len(diff.added)}): {', '.join(sorted(diff.added)) or '-'}")
    print(f"  removed ({len(diff.removed)}): {', '.join(sorted(diff.removed)) or '-'}")
    if diff.removed:
        print(
            "\n  Any holding in the removed list must be exited. Record the "
            "announcement-day close for each one - gains above it are owed to charity."
        )
    return 0


def cmd_screen(args: argparse.Namespace) -> int:
    settings = Settings.load(args.config)
    store = SACListStore.load(settings.sac_dir)
    prices = PriceStore(settings.data_dir)
    symbols = prices.symbols()
    if not symbols:
        print(f"  ERROR: no price CSVs in {settings.data_dir}; run `bursabot demo-data` first")
        return 1
    day = date.fromisoformat(args.date) if args.date else max(prices.trading_days(symbols))
    history = prices.read_many(symbols)
    report = build_universe(day, history, store.as_of(day), settings.liquidity)
    _warn(store.warnings())
    print(report.summary())
    print(f"  tradeable: {', '.join(report.candidates) or '-'}")
    if report.dropped_non_compliant:
        print(f"  not on SAC list: {', '.join(report.dropped_non_compliant)}")
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    settings = Settings.load(args.config)
    ledger = PurificationLedger(settings.ledger_file)
    if not ledger.entries:
        print("purification ledger is empty")
        return 0
    for i, entry in enumerate(ledger.entries):
        status = "paid" if entry.paid else "OUTSTANDING"
        print(
            f"[{i}] {entry.disposal_day} {entry.symbol} {entry.shares:,} sh "
            f"@ RM{entry.sale_price:.3f} vs ref RM{entry.reference_close:.3f} "
            f"-> RM{entry.amount:,.2f} {status}"
        )
    print(f"\ntotal recorded RM{ledger.total_recorded:,.2f}, outstanding RM{ledger.outstanding:,.2f}")
    return 0


def cmd_demo_data(args: argparse.Namespace) -> int:
    """Generate synthetic price history so the pipeline runs without a download.

    This is fabricated random-walk data for wiring up the plumbing. Never draw a
    conclusion about a strategy from it.
    """
    settings = Settings.load(args.config)
    store = SACListStore.load(settings.sac_dir)
    prices = PriceStore(settings.data_dir)
    rng = random.Random(args.seed)

    symbols = sorted(set().union(*(set(e.compliant) for e in store.editions)))
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    for symbol in symbols:
        price = rng.uniform(0.60, 12.0)
        drift = rng.uniform(-0.0004, 0.0008)
        bars: list[Bar] = []
        day = start
        while day <= end:
            if day.weekday() < 5:
                price = max(0.05, price * (1 + rng.gauss(drift, 0.016)))
                high = price * (1 + abs(rng.gauss(0, 0.006)))
                low = price * (1 - abs(rng.gauss(0, 0.006)))
                bars.append(
                    Bar(
                        symbol=symbol,
                        day=day,
                        open=round(rng.uniform(low, high), 3),
                        high=round(high, 3),
                        low=round(low, 3),
                        close=round(price, 3),
                        volume=int(rng.uniform(200_000, 4_000_000)),
                    )
                )
            day += timedelta(days=1)
        prices.write(symbol, bars)

    print(f"wrote {len(symbols)} synthetic symbols to {settings.data_dir} ({start} to {end})")
    print("  SYNTHETIC DATA - for plumbing only, not for evaluating a strategy.")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    settings = Settings.load(args.config)
    store = SACListStore.load(settings.sac_dir)
    prices = PriceStore(settings.data_dir)
    symbols = prices.symbols()
    if not symbols:
        print(f"  ERROR: no price CSVs in {settings.data_dir}; run `bursabot demo-data` first")
        return 1
    history = prices.read_many(symbols)
    available = prices.trading_days(symbols)

    # Never start before the earliest SAC edition: screening with a later list is
    # look-ahead bias, and the store refuses it outright.
    earliest = max(min(available), store.editions[0].effective_date)
    if args.start is None and earliest > min(available):
        print(
            f"  note: start clamped to {earliest}, the first SAC edition held. "
            "Import older editions to backtest further back."
        )

    config = BacktestConfig(
        start=date.fromisoformat(args.start) if args.start else earliest,
        end=date.fromisoformat(args.end) if args.end else max(available),
        initial_cash=args.cash or settings.initial_cash,
        rebalance=settings.rebalance,
        fees=settings.fees,
        limits=settings.limits,
        liquidity=settings.liquidity,
        trend=settings.trend,
    )
    result = run_backtest(history, store, config)
    _warn(result.notes)
    print(result.summary())
    if result.forced_exits:
        print("\nforced exits (SAC reclassification):")
        for day, symbol, reference in result.forced_exits:
            print(f"  {day} {symbol} reference close RM{reference:.3f}")
    if result.refused_orders:
        print(f"\n{len(result.refused_orders)} orders refused by the compliance guard:")
        for line in result.refused_orders[:10]:
            print(f"  {line}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bursabot", description=BANNER)
    parser.add_argument("--config", default="config.toml", help="path to config.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("costs", help="show the full fee breakdown for one trade")
    p.add_argument("price", type=float)
    p.add_argument("shares", type=int)
    p.set_defaults(func=cmd_costs)

    p = sub.add_parser("calendar", help="check whether Bursa is open")
    p.add_argument("--date")
    p.set_defaults(func=cmd_calendar)

    p = sub.add_parser("sac-import", help="convert a code list into a SAC list edition")
    p.add_argument("--codes", required=True, help="text file, one stock code per line")
    p.add_argument("--effective", required=True, help="YYYY-MM-DD effective date")
    p.add_argument("--source", default="SC SAC list")
    p.add_argument("--out-dir", default="data/sac_lists")
    p.set_defaults(func=cmd_sac_import)

    p = sub.add_parser("sac-diff", help="what the latest SAC edition added and removed")
    p.set_defaults(func=cmd_sac_diff)

    p = sub.add_parser("screen", help="build the tradeable universe for a date")
    p.add_argument("--date")
    p.set_defaults(func=cmd_screen)

    p = sub.add_parser("ledger", help="show the purification (charity) ledger")
    p.set_defaults(func=cmd_ledger)

    p = sub.add_parser("demo-data", help="generate synthetic prices so the demo runs")
    p.add_argument("--start", default="2023-01-02")
    p.add_argument("--end", default="2026-06-30")
    p.add_argument("--seed", type=int, default=7)
    p.set_defaults(func=cmd_demo_data)

    p = sub.add_parser("backtest", help="run the strategy over stored history")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--cash", type=float)
    p.set_defaults(func=cmd_backtest)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
