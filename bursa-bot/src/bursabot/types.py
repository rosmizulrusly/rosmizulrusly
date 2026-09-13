"""Core value types shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

BOARD_LOT = 100
"""Bursa normal-market board lot. Odd lots (1-99) trade in a separate, illiquid market."""


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class Bar:
    """One daily OHLCV observation, prices in MYR, already adjusted for corporate actions."""

    symbol: str
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: int

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError(f"{self.symbol} {self.day}: low {self.low} above high {self.high}")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError(f"{self.symbol} {self.day}: non-positive price")
        if self.volume < 0:
            raise ValueError(f"{self.symbol} {self.day}: negative volume")


@dataclass(frozen=True)
class Order:
    symbol: str
    side: Side
    shares: int
    limit: float | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.shares <= 0:
            raise ValueError("order shares must be positive")
        if self.shares % BOARD_LOT:
            raise ValueError(f"{self.shares} shares is not a whole board lot of {BOARD_LOT}")
        if self.limit is not None and self.limit <= 0:
            raise ValueError("limit price must be positive")

    @property
    def lots(self) -> int:
        return self.shares // BOARD_LOT


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: Side
    shares: int
    price: float
    day: date
    fees: float


@dataclass
class Position:
    """A long holding. `shares` is never negative - shorting is not supported."""

    symbol: str
    shares: int
    cost_basis: float
    """Average entry price per share, fees included."""

    reference_close: float | None = None
    """Closing price on the day the SAC announced this name as non-compliant.

    Set by `shariah.screen.mark_reclassified`. Gains above this level on a later
    sale are not yours to keep - see `shariah.purification`.
    """

    def __post_init__(self) -> None:
        if self.shares < 0:
            raise ValueError(f"{self.symbol}: short positions are not permitted")

    @property
    def is_forced_exit(self) -> bool:
        return self.reference_close is not None
