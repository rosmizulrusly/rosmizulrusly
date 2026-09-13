"""Your actual holdings, read from a JSON file.

M+ Online has no public order-placement API, so the bot cannot see your account.
You keep this file in step with your contract notes by hand. That is a feature at
this stage: reconciling it each week is how you notice the bot and reality drifting
apart before real money depends on them agreeing.

`cost_basis` should be your all-in entry price per share (contract value plus
brokerage, clearing fee, stamp duty and SST, divided by shares) - that is what the
purification and P&L figures assume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Mapping

from .types import Position


@dataclass
class Portfolio:
    cash: float = 0.0
    holdings: dict[str, Position] = field(default_factory=dict)
    broker: str = ""
    updated: date | None = None

    @classmethod
    def load(cls, path: Path | str) -> "Portfolio":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"no portfolio at {path}. Copy portfolio.example.json and fill in "
                "your counters from your M+ Online holdings page."
            )
        raw = json.loads(path.read_text())
        holdings: dict[str, Position] = {}
        for entry in raw.get("holdings", []):
            symbol = str(entry["symbol"]).strip().upper()
            if symbol in holdings:
                raise ValueError(f"{symbol} appears twice in {path}; combine the lines")
            holdings[symbol] = Position(
                symbol=symbol,
                shares=int(entry["shares"]),
                cost_basis=float(entry["cost_basis"]),
                reference_close=(
                    float(entry["reference_close"]) if entry.get("reference_close") else None
                ),
            )
        return cls(
            cash=float(raw.get("cash", 0.0)),
            holdings=holdings,
            broker=str(raw.get("broker", "")),
            updated=date.fromisoformat(raw["updated"]) if raw.get("updated") else None,
        )

    def save(self, path: Path | str) -> None:
        Path(path).write_text(
            json.dumps(
                {
                    "broker": self.broker,
                    "updated": (self.updated or date.today()).isoformat(),
                    "cash": round(self.cash, 2),
                    "holdings": [
                        {
                            "symbol": symbol,
                            "shares": position.shares,
                            "cost_basis": round(position.cost_basis, 4),
                            **(
                                {"reference_close": position.reference_close}
                                if position.reference_close is not None
                                else {}
                            ),
                        }
                        for symbol, position in sorted(self.holdings.items())
                    ],
                },
                indent=2,
            )
            + "\n"
        )

    def market_value(self, marks: Mapping[str, float]) -> float:
        return round(
            sum(
                position.shares * marks.get(symbol, position.cost_basis)
                for symbol, position in self.holdings.items()
            ),
            2,
        )

    def equity(self, marks: Mapping[str, float]) -> float:
        return round(self.cash + self.market_value(marks), 2)

    def unpriced(self, marks: Mapping[str, float]) -> list[str]:
        """Holdings with no current price - they are marked at cost, which flatters."""
        return sorted(s for s in self.holdings if s not in marks)

    @property
    def symbols(self) -> list[str]:
        return sorted(self.holdings)
