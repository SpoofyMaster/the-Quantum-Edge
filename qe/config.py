"""Configuration loading for research settings and instrument specifications."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def load_research(path: Path | None = None) -> dict:
    with open(path or CONFIG_DIR / "research.toml", "rb") as f:
        return tomllib.load(f)


@dataclass(frozen=True)
class Instrument:
    symbol: str
    asset_class: str
    contract_size: float
    digits: int
    tick_size: float
    min_lot: float
    lot_step: float
    commission_per_lot_side_usd: float
    quote_ccy: str
    typical_raw_spread: float
    status: str
    verified_source: str = ""

    @property
    def verified(self) -> bool:
        return self.status == "VERIFIED" and bool(self.verified_source)


def load_instruments(path: Path | None = None) -> dict[str, Instrument]:
    with open(path or CONFIG_DIR / "instruments.toml", "rb") as f:
        raw = tomllib.load(f)
    return {sym: Instrument(symbol=sym, **spec) for sym, spec in raw.items()}
