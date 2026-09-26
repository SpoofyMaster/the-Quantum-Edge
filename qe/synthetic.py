"""Synthetic M1 bid/ask generator used to test the research pipeline itself.

* Null mode (edge=0): driftless random walk with GARCH-type volatility clustering and intraday
  volatility/spread seasonality. Any strategy must show ~zero GROSS expectancy and negative NET
  expectancy here; if it does not, the pipeline leaks information or the statistics are wrong.
* Planted mode (edge>0): after a 5-minute impulse larger than `impulse_k` sigma, the next
  `edge_bars` minutes receive a drift of `edge` * sigma per minute in the impulse direction.
  Used to measure the pipeline's statistical POWER (can it find an edge that we know exists?).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def trading_minutes(start: str, end: str) -> pd.DatetimeIndex:
    idx = pd.date_range(start, end, freq="1min", tz="UTC", inclusive="left")
    dow, hr = idx.dayofweek, idx.hour
    keep = ~((dow == 5) | ((dow == 4) & (hr >= 21)) | ((dow == 6) & (hr < 22)))
    return idx[keep]


def generate(
    start: str = "2021-01-01",
    end: str = "2022-01-01",
    price0: float = 1.10,
    sigma_min: float = 0.00012,   # ~1.2 pip per minute at the seasonal baseline
    base_spread: float = 0.00002,
    garch_alpha: float = 0.05,
    garch_beta: float = 0.90,
    edge: float = 0.0,
    edge_bars: int = 20,
    impulse_k: float = 3.0,
    substeps: int = 6,
    seed: int = 7,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = trading_minutes(start, end)
    n = len(idx)
    h = idx.hour.values + idx.minute.values / 60.0
    seas = 0.6 + 0.8 * np.exp(-((h - 8.0) ** 2) / 2.0) + 1.0 * np.exp(-((h - 13.5) ** 2) / 2.0)
    z = rng.standard_normal(n)
    omega = 1.0 - garch_alpha - garch_beta
    sig = np.empty(n)
    drift = np.zeros(n)
    r = np.empty(n)
    g = 1.0
    remaining, direction = 0, 0
    last5 = np.zeros(5)
    for t in range(n):
        if t:
            g = omega + garch_alpha * (r[t - 1] / sig[t - 1]) ** 2 + garch_beta * g
        sig[t] = sigma_min * seas[t] * np.sqrt(g)
        if edge > 0 and remaining > 0:
            drift[t] = direction * edge * sig[t]
            remaining -= 1
        r[t] = drift[t] + sig[t] * z[t]
        last5[t % 5] = r[t]
        if edge > 0 and remaining == 0 and t >= 5:
            imp = last5.sum()
            if abs(imp) > impulse_k * sig[t] * np.sqrt(5):
                remaining, direction = edge_bars, int(np.sign(imp))
    # intrabar path: Brownian bridge from 0 to r[t] so bar OHLC is consistent with the minute return
    w = np.cumsum(rng.standard_normal((n, substeps)), axis=1) * (sig[:, None] / np.sqrt(substeps))
    frac = np.arange(1, substeps + 1) / substeps
    path = w - frac[None, :] * w[:, -1:] + frac[None, :] * r[:, None]
    close_log = np.log(price0) + np.cumsum(path[:, -1])
    open_log = np.concatenate([[np.log(price0)], close_log[:-1]])
    hi_log = open_log + np.maximum(path.max(1), 0.0)
    lo_log = open_log + np.minimum(path.min(1), 0.0)
    bid = {k: np.exp(v) for k, v in zip(("bo", "bh", "bl", "bc"), (open_log, hi_log, lo_log, close_log))}
    spread = base_spread * (1.0 + 1.5 / seas) * np.exp(0.3 * rng.standard_normal(n))
    df = pd.DataFrame(bid, index=idx)
    for s in "ohlc":
        df["a" + s] = df["b" + s] + spread
    df["volume"] = np.round(50 * seas * np.sqrt(np.clip(np.abs(r) / sigma_min, 0.2, None)))
    df["spread_source"] = "synthetic"
    df.index.name = "time"
    return df
