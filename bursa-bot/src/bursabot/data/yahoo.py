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
