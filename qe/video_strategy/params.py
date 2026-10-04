"""Strategy parameters. Defaults = the "VIDEO" profile (research/ALGORITHM_SPECIFICATION.md section 9)."""
from __future__ import annotations

from dataclasses import dataclass, replace

SESSION_PRESETS = ("ASIA2_TO_LONDON4", "STRICT", "ALL")
LOCATION_MODES = ("HALF", "CONDITION_AWARE")
BREAK_MODES = ("CLOSE", "WICK")
DXY_MODES = ("FULL", "MIRROR_DIRECTION", "OFF")
ENTRY_MODES = ("BREAK", "PULLBACK_50")
TARGET_MODES = ("EXT50", "FIXED_R")


@dataclass(frozen=True)
class Params:
    # candle / timing (MKT-4, EXT-2, SHF-3)
    candle_minutes: int = 60
    min_ext_minutes: int = 18
    max_ext_pullback: float = 0.50
    shift_start_min: int = 22
    shift_end_min: int = 52
    session_preset: str = "ASIA2_TO_LONDON4"
    # middle-timeframe context (CTX-1..5)
    mtf_lookback_min: int = 300
    min_coverage: float = 0.80
    zigzag_atr_mult: float = 2.0
    zigzag_atr_period: int = 14
    trend_max_ratio: float = 0.50
    range_min_ratio: float = 0.75
    # location (EXT-4) and optional extension filters (EXT-5, EXT-6)
    location_mode: str = "HALF"
    min_location_retrace: float = 0.50
    require_prev_candle_break: bool = False
    min_ext_atr_mult: float = 0.0
    # shift (SHF-1, SHF-2)
    pivot_strength: int = 2
    break_confirm: str = "CLOSE"
    min_break_atr: float = 0.0
    # correlation gate (COR-1..3)
    dxy_mode: str = "FULL"
    # orders (ENT, SL, TP, MGT)
    entry_mode: str = "BREAK"
    stop_buffer_atr: float = 0.10
    stop_buffer_price: float = 0.0
    target_mode: str = "EXT50"
    fixed_r: float = 1.0
    adjust_sell_tp_for_spread: bool = True
    max_hold_minutes: int = 120
    atr_period_m1: int = 14

    def __post_init__(self) -> None:
        if self.session_preset not in SESSION_PRESETS:
            raise ValueError(f"session_preset {self.session_preset}")
        if self.location_mode not in LOCATION_MODES:
            raise ValueError(f"location_mode {self.location_mode}")
        if self.break_confirm not in BREAK_MODES:
            raise ValueError(f"break_confirm {self.break_confirm}")
        if self.dxy_mode not in DXY_MODES:
            raise ValueError(f"dxy_mode {self.dxy_mode}")
        if self.entry_mode not in ENTRY_MODES:
            raise ValueError(f"entry_mode {self.entry_mode}")
        if self.target_mode not in TARGET_MODES:
            raise ValueError(f"target_mode {self.target_mode}")
        if not (60 % self.candle_minutes == 0 and self.candle_minutes >= 5):
            raise ValueError("candle_minutes must divide 60")
        if not (0 < self.shift_start_min <= self.shift_end_min <= self.candle_minutes):
            raise ValueError("shift window must satisfy 0 < start <= end <= candle_minutes")
        if self.pivot_strength < 1:
            raise ValueError("pivot_strength >= 1")
        if self.max_hold_minutes > 120:
            raise ValueError("project rule: positions are closed within 120 minutes")


def m15_preset(base: Params | None = None) -> Params:
    """Experimental 15-minute candle variant (A-07): the H1 timings scaled by 1/4 and rounded."""
    return replace(base or Params(), candle_minutes=15, min_ext_minutes=5, shift_start_min=6, shift_end_min=13)
