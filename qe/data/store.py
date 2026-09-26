"""Local M1 store: data/m1/{SYMBOL}/{YYYY-MM}.parquet (git-ignored). Reads are guarded by the
final-test lock so research code cannot accidentally load locked data."""
from __future__ import annotations

import pandas as pd

from ..config import ROOT, load_research
from ..validation import final_test_start, guard_final_test

M1_DIR = ROOT / "data" / "m1"


def available_months(symbol: str) -> list[str]:
    d = M1_DIR / symbol
    return sorted(p.stem for p in d.glob("*.parquet")) if d.exists() else []


# ASSUMPTION (not measured): relative spread by New York local hour for bid-only sources.
# Shape follows the published pattern (Ito & Hashimoto 2006: widest around the NY close / early Asia).
# Multiplies config typical_raw_spread. Stress tests must also scale the whole profile.
NY_HOUR_SPREAD_MULT = {16: 2.0, 17: 4.0, 18: 2.5, 19: 1.5, 20: 1.5, 21: 1.5, 22: 1.5, 23: 1.5,
                       0: 1.5, 1: 1.25, 2: 1.0}


def apply_spread_model(df: pd.DataFrame, base_spread: float, scale: float = 1.0) -> pd.DataFrame:
    """Rebuild the ask side of a bid-only frame with a time-of-day spread profile (flagged 'assumed')."""
    hrs = df.index.tz_convert("America/New_York").hour
    mult = pd.Series(hrs, index=df.index).map(NY_HOUR_SPREAD_MULT).fillna(1.0).to_numpy()
    sp = base_spread * scale * mult
    out = df.copy()
    for c in "ohlc":
        out["a" + c] = out["b" + c] + sp
    out["spread_source"] = "assumed"
    return out


def load_m1(symbol: str, start: str, end: str | None = None, cfg: dict | None = None,
            spread_scale: float = 1.0) -> pd.DataFrame:
    """Load [start, end) M1 bars. `end` defaults to the final-test start (locked period excluded).

    Bid-only ('assumed' spread) data gets the time-of-day spread model applied, scaled by `spread_scale`.
    """
    cfg = cfg or load_research()
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC") if end else final_test_start(cfg)
    months = pd.period_range(start_ts.tz_convert(None), (end_ts - pd.Timedelta(minutes=1)).tz_convert(None), freq="M")
    parts = []
    for m in months:
        f = M1_DIR / symbol / f"{m.strftime('%Y-%m')}.parquet"
        if f.exists():
            parts.append(pd.read_parquet(f))
    if not parts:
        raise FileNotFoundError(f"no M1 data for {symbol} in [{start}, {end_ts})")
    df = pd.concat(parts).sort_index()
    df = df[(df.index >= start_ts) & (df.index < end_ts)]
    df = df[~df.index.duplicated(keep="first")]
    guard_final_test(df.index, cfg)
    if "spread_source" in df and (df["spread_source"] == "assumed").all():
        from ..config import load_instruments
        df = apply_spread_model(df, load_instruments()[symbol].typical_raw_spread, spread_scale)
    return df
