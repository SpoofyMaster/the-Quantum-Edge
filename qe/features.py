"""Causal M1 features. Every value at bar t uses only bars <= t (bar t is complete at its close).

Causality is enforced by tests/test_features.py (future-perturbation test). Tick volume is a
liquidity/activity PROXY; it is not exchange volume or true order flow.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data.schema import mid, spread
from .sessions import fx_trading_day


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    m = np.log(mid(df))
    r1 = m.diff()
    f = pd.DataFrame(index=df.index)
    for k in (1, 5, 15, 60):
        f[f"ret_{k}"] = m.diff(k)
    rv15 = r1.rolling(15, min_periods=10).std()
    rv60 = r1.rolling(60, min_periods=40).std()
    rv240 = r1.rolling(240, min_periods=160).std()
    f["rv_60"] = rv60
    f["rv_ratio_15_240"] = rv15 / rv240
    f["impulse_z5"] = f["ret_5"] / (rv60 * np.sqrt(5))
    f["impulse_z15"] = f["ret_15"] / (rv60 * np.sqrt(15))
    # Kaufman efficiency ratio: 1 = straight-line move, 0 = pure noise
    for k in (15, 60):
        f[f"eff_{k}"] = m.diff(k).abs() / r1.abs().rolling(k, min_periods=k).sum()
    # bar-range expansion and close location within the bar
    rng_ = (df.bh + df.ah) / 2 - (df.bl + df.al) / 2
    f["range_z"] = rng_ / rng_.rolling(60, min_periods=40).mean()
    f["close_loc"] = ((df.bc + df.ac) / 2 - (df.bl + df.al) / 2) / rng_.replace(0, np.nan)
    # activity proxy: signed tick-volume imbalance over 15 bars
    sv = np.sign(r1) * df.volume
    f["tv_imbalance_15"] = sv.rolling(15, min_periods=10).sum() / df.volume.rolling(15, min_periods=10).sum()
    f["tv_z"] = df.volume / df.volume.rolling(240, min_periods=160).mean()
    # spread relative to its own recent median (liquidity deterioration)
    sp = spread(df)
    f["spread_rel"] = sp / sp.rolling(1440, min_periods=240).median()
    # distance to PREVIOUS FX-day high/low, in units of rv60 * sqrt(60)
    day = pd.Series(fx_trading_day(df.index), index=df.index)
    mh = pd.Series(mid(df, "h").values, index=df.index)
    ml = pd.Series(mid(df, "l").values, index=df.index)
    dh = mh.groupby(day.values).max()
    dl = ml.groupby(day.values).min()
    days = pd.Index(sorted(dh.index))
    prev_h = pd.Series(dh.reindex(days).shift(1).values, index=days)
    prev_l = pd.Series(dl.reindex(days).shift(1).values, index=days)
    scale = rv60 * np.sqrt(60) * np.exp(m)
    mc = mid(df)
    f["dist_prev_high"] = (mc - day.map(prev_h).values) / scale
    f["dist_prev_low"] = (mc - day.map(prev_l).values) / scale
    # time-of-day (UTC) cyclic encoding
    tod = (df.index.hour * 60 + df.index.minute).values / 1440.0
    f["tod_sin"] = np.sin(2 * np.pi * tod)
    f["tod_cos"] = np.cos(2 * np.pi * tod)
    return f.replace([np.inf, -np.inf], np.nan)
