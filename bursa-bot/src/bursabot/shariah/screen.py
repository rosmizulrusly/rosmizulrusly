"""The universe screen and the reclassification (forced exit) path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping

from ..types import Position
from .list_store import SACList, SACListStore


def is_tradeable(symbol: str, sac_list: SACList) -> bool:
    return symbol in sac_list


def filter_universe(symbols: Iterable[str], sac_list: SACList) -> list[str]:
    """Keep only Shariah-compliant names, preserving input order.

    Call this before signal generation, not after. Filtering afterwards means the
    strategy has already reasoned about names it must never hold, and one missed
    call site is enough to place a non-compliant order.
    """
    return [s for s in symbols if is_tradeable(s, sac_list)]


@dataclass(frozen=True)
class ForcedExit:
    """A holding that must be sold because the SAC removed it from the list.

    `reference_close` is the closing price on the announcement day. Capital gain up
    to that level may be retained; any excess realised above it on a later sale is
    to be channelled to charity (see `purification`).
    """

    symbol: str
    shares: int
    announcement_day: date
    reference_close: float
    cost_basis: float

    @property
    def under_water(self) -> bool:
        """True if the name is below cost at announcement.

        Common guidance permits holding such a position until it breaks even rather
        than crystallising a loss. That is a decision for the investor and their
        Shariah advisor, so this is surfaced rather than acted on automatically.
        """
        return self.reference_close < self.cost_basis


def reconcile_holdings(
    positions: Mapping[str, Position],
    sac_list: SACList,
    announcement_day: date,
    closes: Mapping[str, float],
) -> list[ForcedExit]:
    """Find holdings that are no longer on the SAC list.

    Run this the moment a new edition is published. `closes` must be the closing
    prices on `announcement_day` - they set the purification reference level and
    cannot be reconstructed later from a different day's price.
    """
    exits: list[ForcedExit] = []
    for symbol, position in positions.items():
        if position.shares <= 0 or is_tradeable(symbol, sac_list):
            continue
        if symbol not in closes:
            raise KeyError(
                f"no {announcement_day} close for {symbol}; the announcement-day "
                "close is required to compute purification and must not be guessed"
            )
        exits.append(
            ForcedExit(
                symbol=symbol,
                shares=position.shares,
                announcement_day=announcement_day,
                reference_close=closes[symbol],
                cost_basis=position.cost_basis,
            )
        )
    return exits


def mark_reclassified(position: Position, exit_notice: ForcedExit) -> Position:
    """Stamp the announcement-day close onto a position so a later sale can purify."""
    position.reference_close = exit_notice.reference_close
    return position


def screen_changes(store: SACListStore, previous: date, current: date) -> tuple[frozenset[str], frozenset[str]]:
    """(added, removed) between the editions in force on two dates."""
    diff = store.diff(store.as_of(previous), store.as_of(current))
    return diff.added, diff.removed
