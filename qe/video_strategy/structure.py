"""Market-structure primitives: ATR, fractal pivots, M5 aggregation, zig-zag and the middle-timeframe context.

Implements ALGORITHM_SPECIFICATION.md sections 0, 2, 3 and 5. Everything here is causal by construction:
callers pass only bars that have closed before the decision time.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TREND, TRENDING_RANGE, RANGE, UNDEFINED = "TREND", "TRENDING_RANGE", "RANGE", "UNDEFINED"
BULL, BEAR, NEUTRAL = "BULL", "BEAR", "NEUTRAL"
HIGH, LOW = 1, -1


def true_range(h: np.ndarray, l: np.ndarray, c: np.ndarray) -> np.ndarray:
    prev_c = np.concatenate(([np.nan], c[:-1]))
    hi = np.where(np.isnan(prev_c), h, np.fmax(h, prev_c))
    lo = np.where(np.isnan(prev_c), l, np.fmin(l, prev_c))
    return hi - lo


def atr_sma(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    """Simple-mean ATR (as MT5 iATR): mean of the last n true ranges; NaN until n ranges exist."""
    tr = true_range(h, l, c)
    out = np.full(len(tr), np.nan)
    if len(tr) >= n:
        cs = np.cumsum(np.nan_to_num(tr))
        out[n - 1:] = (cs[n - 1:] - np.concatenate(([0.0], cs[:-n]))) / n
    return out


def pivot_flags(h: np.ndarray, l: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Fractal pivots (SHF-1): high k if h[k] > h[k-i] and h[k] >= h[k+i] for i = 1..n (mirror for lows).

    The flag at k depends on bars k-n..k+n, so it may only be *used* once bar k+n has closed.
    """
    m = len(h)
    ph = np.ones(m, dtype=bool)
    pl = np.ones(m, dtype=bool)
    for i in range(1, n + 1):
        left_h = np.concatenate((np.full(i, np.nan), h[:-i]))
        right_h = np.concatenate((h[i:], np.full(i, np.nan)))
        left_l = np.concatenate((np.full(i, np.nan), l[:-i]))
        right_l = np.concatenate((l[i:], np.full(i, np.nan)))
        with np.errstate(invalid="ignore"):
            ph &= (h > left_h) & (h >= right_h)
            pl &= (l < left_l) & (l <= right_l)
    return ph, pl


def prev_index(flags: np.ndarray) -> np.ndarray:
    """prev[k] = largest j <= k with flags[j], else -1."""
    idx = np.where(flags, np.arange(len(flags)), -1)
    return np.maximum.accumulate(idx) if len(idx) else idx


def aggregate(times_ns: np.ndarray, o, h, l, c, start_ns: int, minutes: int):
    """Aggregate bars into `minutes` buckets aligned to start_ns (spec 2.2). Returns (o, h, l, c) arrays."""
    if len(times_ns) == 0:
        e = np.array([])
        return e, e, e, e
    bucket = (times_ns - start_ns) // (minutes * 60 * 1_000_000_000)
    cut = np.flatnonzero(np.diff(bucket)) + 1
    starts = np.concatenate(([0], cut))
    ends = np.concatenate((cut, [len(bucket)]))
    return (o[starts], np.maximum.reduceat(h, starts), np.minimum.reduceat(l, starts), c[ends - 1])


def zigzag(o, h, l, c, theta: float):
    """Deterministic high/low zig-zag (spec 2.3). Returns (pivots, tentative, direction).

    pivots: list of (index, price, kind) with kind HIGH/LOW; tentative: (index, price) of the running extreme.
    """
    k_n = len(h)
    pivots: list[tuple[int, float, int]] = []
    if k_n == 0 or not np.isfinite(theta) or theta <= 0:
        return pivots, None, 0
    d = 0
    hi, lo, hi_i, lo_i = h[0], l[0], 0, 0
    ext, ext_i = np.nan, -1
    for k in range(1, k_n):
        if d == 0:
            if h[k] > hi:
                hi, hi_i = h[k], k
            if l[k] < lo:
                lo, lo_i = l[k], k
            if hi - lo >= theta:
                if hi_i > lo_i or (hi_i == lo_i and c[hi_i] >= o[hi_i]):
                    pivots.append((lo_i, lo, LOW))
                    d, ext, ext_i = 1, hi, hi_i
                else:
                    pivots.append((hi_i, hi, HIGH))
                    d, ext, ext_i = -1, lo, lo_i
        elif d == 1:
            if h[k] > ext:
                ext, ext_i = h[k], k
            elif ext - l[k] >= theta:
                pivots.append((ext_i, ext, HIGH))
                d, ext, ext_i = -1, l[k], k
        else:
            if l[k] < ext:
                ext, ext_i = l[k], k
            elif h[k] - ext >= theta:
                pivots.append((ext_i, ext, LOW))
                d, ext, ext_i = 1, h[k], k
    tentative = (ext_i, float(ext)) if d != 0 else None
    return pivots, tentative, d


@dataclass
class MtfContext:
    condition: str = UNDEFINED
    direction: str = NEUTRAL
    ratio_median: float = float("nan")
    n_completed_legs: int = 0
    coverage: float = 0.0
    theta: float = float("nan")
    last_down_leg: tuple[float, float] | None = None  # (start high Hs, end low Le)
    last_up_leg: tuple[float, float] | None = None    # (start low Ls, end high He)
    pivots: list = field(default_factory=list)

    @property
    def tradable(self) -> bool:
        return self.condition in (RANGE, TRENDING_RANGE)


def mtf_context(times_ns: np.ndarray, o, h, l, c, candle_open_ns: int, p) -> MtfContext:
    """Middle-timeframe context from bars strictly before the candle open (spec section 2)."""
    ctx = MtfContext()
    w0 = candle_open_ns - p.mtf_lookback_min * 60 * 1_000_000_000
    i0 = int(np.searchsorted(times_ns, w0, side="left"))
    i1 = int(np.searchsorted(times_ns, candle_open_ns, side="left"))
    sl = slice(i0, i1)
    ok = np.isfinite(h[sl]) & np.isfinite(l[sl])
    ctx.coverage = float(ok.sum()) / p.mtf_lookback_min
    if ctx.coverage < p.min_coverage:
        return ctx
    t, oo, hh, ll, cc = (a[sl][ok] for a in (times_ns, o, h, l, c))
    mo, mh, ml, mc = aggregate(t, oo, hh, ll, cc, w0, 5)
    n_atr = p.zigzag_atr_period
    if len(mh) < n_atr + 1:
        return ctx
    tr = true_range(mh, ml, mc)[1:]
    ctx.theta = p.zigzag_atr_mult * float(np.mean(tr[-n_atr:]))
    pivots, tentative, _ = zigzag(mo, mh, ml, mc, ctx.theta)
    ctx.pivots = pivots
    points = [(i, pr) for i, pr, _ in pivots] + ([tentative] if tentative else [])
    legs = [(points[i - 1][1], points[i][1]) for i in range(1, len(points))]  # (start, end), last may be in progress
    for a, b in reversed(legs):
        if b < a and ctx.last_down_leg is None:
            ctx.last_down_leg = (a, b)
        if b > a and ctx.last_up_leg is None:
            ctx.last_up_leg = (a, b)
    completed = [abs(pivots[i][1] - pivots[i - 1][1]) for i in range(1, len(pivots))]
    ctx.n_completed_legs = len(completed)
    if len(completed) < 3:
        return ctx
    ratios = [min(completed[i], completed[i - 1]) / max(completed[i], completed[i - 1])
              for i in range(1, len(completed)) if max(completed[i], completed[i - 1]) > 0]
    if len(ratios) < 2:
        return ctx
    ctx.ratio_median = float(np.median(ratios))
    if ctx.ratio_median < p.trend_max_ratio:
        ctx.condition = TREND
    elif ctx.ratio_median < p.range_min_ratio:
        ctx.condition = TRENDING_RANGE
    else:
        ctx.condition = RANGE
    highs = [pr for _, pr, k in pivots if k == HIGH]
    lows = [pr for _, pr, k in pivots if k == LOW]
    if len(highs) >= 2 and len(lows) >= 2:
        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
            ctx.direction = BULL
        elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
            ctx.direction = BEAR
    return ctx


def location_fraction(ctx: MtfContext, trade_dir: int, p) -> float:
    """Spec 3: fraction of the reference leg the extension must retrace."""
    if p.location_mode == "HALF":
        return p.min_location_retrace
    if ctx.condition == RANGE:
        return 0.75
    mtf = {BULL: 1, BEAR: -1}.get(ctx.direction, 0)
    if mtf == 0:
        return 0.75
    return 0.50 if mtf == trade_dir else 1.00


def location_level(ctx: MtfContext, trade_dir: int, p) -> float | None:
    """Price the extension extreme must reach. trade_dir -1 (sell): E >= level; +1 (buy): E <= level."""
    f = location_fraction(ctx, trade_dir, p)
    if trade_dir < 0:
        if ctx.last_down_leg is None:
            return None
        hs, le = ctx.last_down_leg
        return le + f * (hs - le)
    if ctx.last_up_leg is None:
        return None
    ls, he = ctx.last_up_leg
    return he - f * (he - ls)
