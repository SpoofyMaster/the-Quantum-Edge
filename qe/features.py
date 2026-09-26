"""Causal M1 features. Every value at bar t uses only bars <= t (bar t is complete at its close).

Causality is enforced by tests/test_features.py (future-perturbation test). Tick volume is a
liquidity/activity PROXY; it is not exchange volume or true order flow.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data.schema import mid, spread
from .sessions import fx_trading_day


def seasonal_sigma(df: pd.DataFrame, weeks: int = 20, min_weeks: int = 4, bucket_min: int = 5) -> pd.Series:
    """Causal expected 1-minute return sigma for each bar's time-of-week.

    Buckets are `bucket_min` minutes of the week in NEW YORK local time (DST-aware; aligns with the
    17:00 NY FX-day boundary and US data releases). For every (week, bucket) the mean |r| is
    computed; the expectation for week w is the median over the previous `weeks` weeks (w excluded),
    converted to sigma via E|r| = sigma * sqrt(2/pi). Uses only strictly earlier weeks -> causal.
    """
    m = np.log(mid(df))
    absr = m.diff().abs()
    ny = df.index.tz_convert("America/New_York")
    local = ny.tz_localize(None)
    week = ((local - pd.Timestamp("2000-01-02")).days // 7).to_numpy()  # weeks start Sunday (NY)
    dow_from_sun = (np.asarray(ny.dayofweek) + 1) % 7
    bucket = dow_from_sun * (1440 // bucket_min) + (np.asarray(ny.hour) * 60 + np.asarray(ny.minute)) // bucket_min
    tab = pd.DataFrame({"w": week, "b": bucket, "a": absr.to_numpy()}).groupby(["w", "b"])["a"].mean().unstack("b")
    tab = tab.reindex(range(int(tab.index.min()), int(tab.index.max()) + 1))
    exp = tab.rolling(weeks, min_periods=min_weeks).median().shift(1) * np.sqrt(np.pi / 2)
    key = pd.MultiIndex.from_arrays([week, bucket])
    vals = exp.stack(future_stack=True).reindex(key).to_numpy()
    return pd.Series(vals, index=df.index, name="seasonal_sigma")


def build_features(df: pd.DataFrame, seasonal: bool = True) -> pd.DataFrame:
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
    if seasonal:
        e = seasonal_sigma(df)
        e2 = e ** 2
        f["seasonal_sigma"] = e
        # impulse relative to what is NORMAL for this time of week (not just recent vol)
        f["impulse_ds5"] = f["ret_5"] / np.sqrt(e2.rolling(5, min_periods=5).sum())
        f["impulse_ds15"] = f["ret_15"] / np.sqrt(e2.rolling(15, min_periods=15).sum())
        # volatility regime: realised vs seasonal expectation over the last 60 minutes
        f["vol_regime_60"] = rv60 / np.sqrt(e2.rolling(60, min_periods=40).mean())
    return f.replace([np.inf, -np.inf], np.nan)
