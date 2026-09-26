"""Line-by-line Python port of the Pine prototype's seasonal-sigma ring buffer
(pine/quantum_edge_impulse_reversion.pine). Used only to test that the Pine ALGORITHM matches
qe.features.seasonal_sigma; it cannot test Pine syntax (no TradingView compiler here)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

NB, W = 2016, 20


def pine_seasonal_sigma(close: pd.Series) -> np.ndarray:
    ny = close.index.tz_convert("America/New_York")
    dow_sun1 = (np.asarray(ny.dayofweek) + 1) % 7 + 1          # Pine: 1 = Sunday
    hh, mm = np.asarray(ny.hour), np.asarray(ny.minute)
    bucket = (dow_sun1 - 1) * 288 + (hh * 60 + mm) // 5
    local = ny.tz_localize(None)
    local_ms = (local - pd.Timestamp("1970-01-01")) // pd.Timedelta(milliseconds=1)
    week_id = np.floor((np.floor(np.asarray(local_ms) / 86400000.0) - 10958) / 7.0).astype(int)
    hist = np.full(NB * W, np.nan)
    cur_sum = np.zeros(NB)
    cur_cnt = np.zeros(NB, int)
    cur_week = None
    c = close.to_numpy()
    out = np.full(len(c), np.nan)
    for t in range(len(c)):
        absr = abs(math.log(c[t]) - math.log(c[t - 1])) if t else float("nan")
        wk = week_id[t]
        if cur_week is None:
            cur_week = wk
        elif wk != cur_week:
            slot = cur_week % W
            for b in range(NB):
                hist[b * W + slot] = cur_sum[b] / cur_cnt[b] if cur_cnt[b] > 0 else np.nan
            cur_sum[:] = 0.0
            cur_cnt[:] = 0
            if wk - cur_week > 1:
                for w2 in range(cur_week + 1, min(wk - 1, cur_week + W) + 1):
                    hist[np.arange(NB) * W + w2 % W] = np.nan
            cur_week = wk
        v = hist[bucket[t] * W: bucket[t] * W + W]
        v = v[~np.isnan(v)]
        out[t] = np.median(v) * math.sqrt(math.pi / 2) if len(v) >= 4 else np.nan
        if not math.isnan(absr):
            cur_sum[bucket[t]] += absr
            cur_cnt[bucket[t]] += 1
    return out
