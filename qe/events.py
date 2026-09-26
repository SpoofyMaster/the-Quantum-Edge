"""Causal event definitions for the market hypotheses (H-01..H-05, H-08).

Each builder returns {name: (mask, direction)} where mask is a boolean Series over bars (event at
the CLOSE of the bar) and direction is +1/-1 (hypothesised trade direction). All inputs are causal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data.schema import mid
from .sessions import fx_trading_day

ROUND = {"EURUSD": 0.0050, "GBPUSD": 0.0050, "USDJPY": 0.50, "XAUUSD": 10.0, "XAGUSD": 0.50}


def first_true(mask: pd.Series) -> pd.Series:
    """True only on the first bar of each run of True values."""
    return mask & ~mask.shift(1, fill_value=False)


def events_impulse(f, ses, k):
    z = f["impulse_ds5"]
    trig = first_true(z.abs() > k).fillna(False)
    d = np.sign(z)
    active = ses.london | ses.newyork
    out = {}
    out[f"H01_impulse_k{k}_active_cont"] = (trig & active, d)
    out[f"H02_impulse_k{k}_quiet_revert"] = (trig & ~active & ~ses.rollover_blackout, -d)
    # H-11 (generated from EXP005 on the dev period, where H-01 continuation was significantly
    # NEGATIVE): fade the impulse in active sessions. Must be confirmed out of sample.
    out[f"H11_impulse_k{k}_active_fade"] = (trig & active, -d)
    return out


def events_london_range_break(df, m, ses):
    loc = df.index.tz_convert("Europe/London")
    mins = np.asarray(loc.hour * 60 + loc.minute)
    day = pd.Index(loc.date)
    in_range = (mins >= 480) & (mins < 510)
    hi = pd.Series(np.where(in_range, (df.bh + df.ah).values / 2, np.nan), index=df.index).groupby(day).transform("max")
    lo = pd.Series(np.where(in_range, (df.bl + df.al).values / 2, np.nan), index=df.index).groupby(day).transform("min")
    window = (mins >= 510) & (mins < 720)
    up = (m > hi) & window
    dn = (m < lo) & window
    brk = up | dn
    # first break of the day only
    first = brk & (brk.groupby(day).cumsum() == 1)
    d = pd.Series(np.where(up, 1.0, -1.0), index=df.index)
    return {"H03_london_open_range_break": (first, d)}


def events_prev_day_sweep(df, f):
    m = mid(df)
    mh = (df.bh + df.ah) / 2
    ml = (df.bl + df.al) / 2
    day = pd.Series(fx_trading_day(df.index), index=df.index)
    dh = mh.groupby(day.values).max()
    dl = ml.groupby(day.values).min()
    ph = day.map(dh.shift(1))
    pl = day.map(dl.shift(1))
    sweep_hi = (mh > ph) & (m < ph)
    sweep_lo = (ml < pl) & (m > pl)
    # first occurrence per FX day
    fh = sweep_hi & (sweep_hi.groupby(day.values).cumsum() == 1)
    fl = sweep_lo & (sweep_lo.groupby(day.values).cumsum() == 1)
    d = pd.Series(np.where(fh, -1.0, 1.0), index=df.index)
    return {"H04_prev_day_sweep_revert": (fh | fl, d)}


def events_round_break(df, f, sym):
    step = ROUND[sym]
    m = mid(df)
    lvl = np.floor(m / step)
    crossed = lvl != lvl.shift(1)
    d = np.sign(lvl - lvl.shift(1))
    expand = f["range_z"] > 1.5
    return {"H05_round_break_expansion_cont": (crossed & expand & (lvl.diff().abs() == 1), d)}


def events_fix(df, sym):
    """H-08: USD strengthens into the London 16:00 fix (15:30->16:00) and weakens after (16:00->16:30)."""
    if "USD" not in sym:
        return {}
    usd_up_is_price_up = sym.startswith("USD")
    loc = df.index.tz_convert("Europe/London")
    wd = np.asarray(loc.dayofweek) < 5
    pre = pd.Series((np.asarray(loc.hour) == 15) & (np.asarray(loc.minute) == 29) & wd, index=df.index)
    post = pd.Series((np.asarray(loc.hour) == 15) & (np.asarray(loc.minute) == 59) & wd, index=df.index)
    d_usd_up = 1.0 if usd_up_is_price_up else -1.0
    return {"H08_fix_usd_up_into_fix": (pre, pd.Series(d_usd_up, index=df.index)),
            "H08_fix_usd_down_after_fix": (post, pd.Series(-d_usd_up, index=df.index))}


def all_events(df: pd.DataFrame, f: pd.DataFrame, ses: pd.DataFrame, sym: str, ks=(3, 4, 5)) -> dict:
    fams = {}
    for k in ks:
        fams.update(events_impulse(f, ses, k))
    fams.update(events_london_range_break(df, mid(df), ses))
    fams.update(events_prev_day_sweep(df, f))
    fams.update(events_round_break(df, f, sym))
    fams.update(events_fix(df, sym))
    return fams
