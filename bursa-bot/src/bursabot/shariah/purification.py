"""Purification of gains on securities removed from the SAC list.

The rule this implements: on disposal of a security that the SAC has reclassified as
Shariah non-compliant, capital gain up to the *closing price on the announcement day*
may be retained. Any excess realised above that price is channelled to charitable
bodies. Gains are computed per share and never netted against other positions - a
loss elsewhere does not reduce what is owed here.

This is a mechanical calculation, which is exactly why it belongs in code rather than
in a spreadsheet done from memory once a year. Confirm the treatment of transaction
costs and of dividends received while non-compliant with your Shariah advisor.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path


def purification_due(
    sale_price: float, reference_close: float, shares: int
) -> float:
    """Amount to channel to charity from one disposal, in MYR.

    `reference_close` is the announcement-day closing price. Selling at or below it
    owes nothing; selling above it owes the excess on every share sold.
    """
    if shares <= 0:
        raise ValueError("shares must be positive")
    if sale_price <= 0 or reference_close <= 0:
        raise ValueError("prices must be positive")
    excess = max(0.0, sale_price - reference_close)
    return round(excess * shares, 2)


@dataclass(frozen=True)
class PurificationEntry:
    symbol: str
    disposal_day: date
    shares: int
    sale_price: float
    reference_close: float
    amount: float
    paid: bool = False
    note: str = ""

    def to_json(self) -> dict:
        data = asdict(self)
        data["disposal_day"] = self.disposal_day.isoformat()
        return data

    @classmethod
    def from_json(cls, data: dict) -> "PurificationEntry":
        data = dict(data)
        data["disposal_day"] = date.fromisoformat(data["disposal_day"])
        return cls(**data)


class PurificationLedger:
    """Append-only record of amounts owed to charity and amounts settled.

    Append-only on purpose: an amount owed should never quietly disappear because a
    later run recalculated it differently.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.entries: list[PurificationEntry] = []
        if self.path.exists():
            self.entries = [
                PurificationEntry.from_json(row)
                for row in json.loads(self.path.read_text())
            ]

    def record_disposal(
        self,
        symbol: str,
        disposal_day: date,
        shares: int,
        sale_price: float,
        reference_close: float,
        note: str = "",
    ) -> PurificationEntry | None:
        """Record a disposal; returns the entry, or None when nothing is owed."""
        amount = purification_due(sale_price, reference_close, shares)
        if amount <= 0:
            return None
        entry = PurificationEntry(
            symbol=symbol,
            disposal_day=disposal_day,
            shares=shares,
            sale_price=sale_price,
            reference_close=reference_close,
            amount=amount,
            note=note,
        )
        self.entries.append(entry)
        self.flush()
        return entry

    def mark_paid(self, index: int, note: str = "") -> PurificationEntry:
        entry = self.entries[index]
        settled = PurificationEntry(
            symbol=entry.symbol,
            disposal_day=entry.disposal_day,
            shares=entry.shares,
            sale_price=entry.sale_price,
            reference_close=entry.reference_close,
            amount=entry.amount,
            paid=True,
            note=note or entry.note,
        )
        self.entries[index] = settled
        self.flush()
        return settled

    @property
    def outstanding(self) -> float:
        return round(sum(e.amount for e in self.entries if not e.paid), 2)

    @property
    def total_recorded(self) -> float:
        return round(sum(e.amount for e in self.entries), 2)

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([e.to_json() for e in self.entries], indent=2) + "\n"
        )
