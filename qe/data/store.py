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


def load_m1(symbol: str, start: str, end: str | None = None, cfg: dict | None = None) -> pd.DataFrame:
    """Load [start, end) M1 bars. `end` defaults to the final-test start (locked period excluded)."""
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
    return df
