"""Shariah compliance layer.

The Shariah Advisory Council (SAC) of the Securities Commission Malaysia publishes
the List of Shariah-Compliant Securities twice a year, effective the last Friday of
May and of November. That list is the authority used here - this package applies it,
it does not make Shariah rulings.

Three things this layer exists to enforce mechanically:

* the universe filter runs before signals, so a non-compliant name cannot be bought;
* backtests resolve the list *as of* the simulated day, never today's list;
* a name removed from the list triggers a forced exit and a purification calculation.

If you follow a stricter standard than the SAC (AAOIFI, for instance, requires
dividend purification even for listed-compliant companies), tighten the screen here.
"""

from .list_store import SACList, SACListStore, PointInTimeError, ListDiff
from .purification import PurificationEntry, PurificationLedger, purification_due
from .screen import ForcedExit, filter_universe, is_tradeable, reconcile_holdings

__all__ = [
    "SACList",
    "SACListStore",
    "PointInTimeError",
    "ListDiff",
    "PurificationEntry",
    "PurificationLedger",
    "purification_due",
    "ForcedExit",
    "filter_universe",
    "is_tradeable",
    "reconcile_holdings",
]
