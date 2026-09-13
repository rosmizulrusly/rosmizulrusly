"""TOML configuration, loaded with the stdlib `tomllib`.

Everything here has a working default, so the bot runs without a config file; the
file exists so that broker fees and risk limits are recorded in version control
rather than living in someone's head.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

from .costs import FeeSchedule
from .risk import RiskLimits
from .signals.trend import TrendParams
from .universe import LiquidityRules

T = TypeVar("T")


def _build(cls: type[T], data: dict[str, Any]) -> T:
    if not is_dataclass(cls):  # pragma: no cover - defensive
        raise TypeError(f"{cls} is not a dataclass")
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown {cls.__name__} settings: {', '.join(sorted(unknown))}")
    return cls(**data)  # type: ignore[arg-type]


@dataclass
class Settings:
    data_dir: Path = Path("data/prices")
    sac_dir: Path = Path("data/sac_lists")
    calendar_file: Path = Path("data/calendar/holidays.json")
    ledger_file: Path = Path("data/purification_ledger.json")
    initial_cash: float = 100_000.0
    rebalance: str = "monthly"
    fees: FeeSchedule = field(default_factory=FeeSchedule)
    limits: RiskLimits = field(default_factory=RiskLimits)
    liquidity: LiquidityRules = field(default_factory=LiquidityRules)
    trend: TrendParams = field(default_factory=TrendParams)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Settings":
        if path is None or not Path(path).exists():
            return cls()
        raw = tomllib.loads(Path(path).read_text())
        paths = raw.get("paths", {})
        account = raw.get("account", {})
        return cls(
            data_dir=Path(paths.get("data_dir", "data/prices")),
            sac_dir=Path(paths.get("sac_dir", "data/sac_lists")),
            calendar_file=Path(paths.get("calendar_file", "data/calendar/holidays.json")),
            ledger_file=Path(paths.get("ledger_file", "data/purification_ledger.json")),
            initial_cash=float(account.get("initial_cash", 100_000.0)),
            rebalance=str(account.get("rebalance", "monthly")),
            fees=_build(FeeSchedule, raw.get("fees", {})),
            limits=_build(RiskLimits, raw.get("limits", {})),
            liquidity=_build(LiquidityRules, raw.get("liquidity", {})),
            trend=_build(TrendParams, raw.get("trend", {})),
        )
