"""Optional Yahoo Finance loader for Bursa history.

Bursa tickers carry a `.KL` suffix on Yahoo (`1155.KL`), and the index is `^KLSE`.
Free data is fine for end-of-day backtesting and is *not* fine for intraday work -
it is typically delayed. Check the adjustment quality on any name with a recent
bonus issue or share consolidation before trusting it.

`yfinance` is an optional dependency: install with `pip install -e '.[data]'`.
"""

from __future__ import annotations

from datetime import date

from ..types import Bar

YAHOO_SUFFIX = ".KL"
KLCI_TICKER = "^KLSE"


def to_yahoo_ticker(symbol: str) -> str:
    """`1155` -> `1155.KL`; anything already suffixed is returned unchanged."""
    symbol = symbol.strip().upper()
    return symbol if symbol.endswith(YAHOO_SUFFIX) or symbol.startswith("^") else symbol + YAHOO_SUFFIX


def fetch_daily(symbol: str, start: date, end: date) -> list[Bar]:
    """Download adjusted daily bars. Raises ImportError if yfinance is absent."""
    try:
        import yfinance  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "yfinance is not installed; run `pip install -e '.[data]'` "
            "or supply CSVs to PriceStore yourself"
        ) from exc

    frame = yfinance.download(
        to_yahoo_ticker(symbol),
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
    )
    if frame.empty:
        return []
    if hasattr(frame.columns, "droplevel") and frame.columns.nlevels > 1:
        frame = frame.droplevel(1, axis=1)

    bars: list[Bar] = []
    for index, row in frame.iterrows():
        bars.append(
            Bar(
                symbol=symbol.upper(),
                day=index.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )
        )
    return bars


def fetch_daily_batch(
    symbols: list[str], start: date, end: date
) -> tuple[dict[str, list[Bar]], dict[str, str]]:
    """Download several counters in one request.

    Returns (bars by symbol, errors by symbol). Counters that come back empty are
    reported rather than raised, so one delisted or mistyped code cannot abort a
    market-wide download.
    """
    try:
        import yfinance  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "yfinance is not installed; run `pip install -e '.[data]'`"
        ) from exc

    tickers = {to_yahoo_ticker(s): s.upper() for s in symbols}
    frame = yfinance.download(
        list(tickers),
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )

    bars: dict[str, list[Bar]] = {}
    errors: dict[str, str] = {}
    for ticker, symbol in tickers.items():
        try:
            sub = frame[ticker] if getattr(frame.columns, "nlevels", 1) > 1 else frame
            sub = sub.dropna(how="all")
        except KeyError:
            errors[symbol] = "no data returned"
            continue
        if sub.empty:
            errors[symbol] = "no data returned"
            continue
        rows: list[Bar] = []
        for index, row in sub.iterrows():
            try:
                rows.append(
                    Bar(
                        symbol=symbol,
                        day=index.date(),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(row["Volume"]),
                    )
                )
            except (ValueError, TypeError):
                continue  # a single bad bar must not discard the whole series
        if rows:
            bars[symbol] = rows
        else:
            errors[symbol] = "no usable bars"
    return bars, errors
