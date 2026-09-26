"""Statistical evaluation: bootstrap CIs, (probabilistic / deflated) Sharpe, Monte Carlo drawdowns,
probability calibration, and trade summaries.

References:
  Politis & Romano (1994) stationary bootstrap.
  Bailey & Lopez de Prado (2012) Probabilistic Sharpe Ratio; (2014) Deflated Sharpe Ratio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as st

EULER_GAMMA = 0.5772156649015329


def stationary_bootstrap_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Politis-Romano stationary bootstrap: geometric block lengths with mean `mean_block`, wrap-around."""
    new = rng.random(n) < 1.0 / mean_block
    new[0] = True
    block = np.cumsum(new) - 1
    starts = rng.integers(n, size=int(block[-1]) + 1)
    first_pos = np.flatnonzero(new)
    offset = np.arange(n) - first_pos[block]
    return (starts[block] + offset) % n


def bootstrap_ci(x, stat=np.mean, B: int = 2000, mean_block: float = 5.0, alpha: float = 0.05,
                 seed: int = 0) -> tuple[float, float, float]:
    """Stationary-bootstrap percentile CI. Returns (point, lo, hi)."""
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    if len(x) < 2:
        return float(stat(x)) if len(x) else np.nan, np.nan, np.nan
    bs = np.array([stat(x[stationary_bootstrap_indices(len(x), mean_block, rng)]) for _ in range(B)])
    return float(stat(x)), float(np.quantile(bs, alpha / 2)), float(np.quantile(bs, 1 - alpha / 2))


def sharpe(x) -> float:
    x = np.asarray(x, float)
    s = x.std(ddof=1)
    return float(x.mean() / s) if s > 0 else np.nan


def probabilistic_sharpe(x, sr_benchmark: float = 0.0) -> float:
    """P(true per-period SR > benchmark) accounting for skew and kurtosis (Bailey & LdP 2012)."""
    x = np.asarray(x, float)
    n = len(x)
    sr = sharpe(x)
    g3 = st.skew(x)
    g4 = st.kurtosis(x, fisher=False)
    denom = np.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    return float(st.norm.cdf((sr - sr_benchmark) * np.sqrt(n - 1) / denom))


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """Expected maximum of n_trials SR estimates under the null (Bailey & LdP 2014)."""
    if n_trials <= 1:
        return 0.0
    z1 = st.norm.ppf(1 - 1.0 / n_trials)
    z2 = st.norm.ppf(1 - 1.0 / (n_trials * np.e))
    return float(np.sqrt(var_sr) * ((1 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe(x, n_trials: int, var_sr_trials: float) -> float:
    return probabilistic_sharpe(x, expected_max_sharpe(n_trials, var_sr_trials))


def max_drawdown(pnl) -> float:
    eq = np.cumsum(np.asarray(pnl, float))
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    return float((peak - eq).max()) if len(eq) else 0.0


def mc_drawdown(pnl, B: int = 2000, seed: int = 0, mean_block: float = 5.0) -> dict:
    """Distribution of max drawdown under block-resampled trade sequences."""
    x = np.asarray(pnl, float)
    rng = np.random.default_rng(seed)
    dd = np.array([max_drawdown(x[stationary_bootstrap_indices(len(x), mean_block, rng)]) for _ in range(B)])
    return {"dd_median": float(np.median(dd)), "dd_p95": float(np.quantile(dd, 0.95)),
            "dd_p99": float(np.quantile(dd, 0.99))}


def brier(p, y) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    return float(np.mean((p - y) ** 2))


def reliability(p, y, bins: int = 10) -> tuple[pd.DataFrame, float]:
    """Reliability table and expected calibration error (equal-count bins)."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    q = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    b = np.clip(np.searchsorted(q, p, side="right") - 1, 0, len(q) - 2)
    tab = pd.DataFrame({"b": b, "p": p, "y": y}).groupby("b").agg(p_mean=("p", "mean"), y_rate=("y", "mean"), n=("y", "size"))
    ece = float((tab.n * (tab.p_mean - tab.y_rate).abs()).sum() / tab.n.sum())
    return tab, ece


def trade_summary(trades: pd.DataFrame, equity0: float) -> dict:
    if trades.empty:
        return {"trades": 0}
    pnl = trades.pnl_usd.to_numpy()
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    ev, lo, hi = bootstrap_ci(trades.R.to_numpy(), B=1000)
    return {
        "trades": int(len(trades)),
        "net_profit_usd": float(pnl.sum()),
        "net_return_pct": float(100 * pnl.sum() / equity0),
        "win_rate": float((pnl > 0).mean()),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else np.inf,
        "ev_R": ev, "ev_R_ci95": [lo, hi],
        "commission_usd": float(trades.commission_usd.sum()),
        "avg_bars_held": float(trades.bars.mean()),
        "max_drawdown_pct": float(100 * max_drawdown(pnl) / equity0),
        "sharpe_per_trade": sharpe(trades.R.to_numpy()),
        "psr_vs_0": probabilistic_sharpe(trades.R.to_numpy()),
    }
