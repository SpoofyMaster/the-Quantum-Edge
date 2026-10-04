"""Per-candle state machine, extension/shift detection, DXY gate and trade simulation.

Implements ALGORITHM_SPECIFICATION.md sections 4, 6, 7 and 8 and the state machine of STRATEGY_RULEBOOK.md (M).
Decisions are taken at the close of M1 bar t using bars <= t only. Fills happen at bar t+1 or later.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields

import numpy as np
import pandas as pd

from ..config import Instrument
from ..costs import commission_round_trip, value_per_price_unit
from ..risk import OpenPosition, RiskManager, size_position
from ..sessions import session_frame
from .params import Params
from .sessions import is_trading_candle
from .structure import atr_sma, location_level, mtf_context, pivot_flags, prev_index

NS_MIN = 60 * 1_000_000_000
SELL, BUY = -1, 1

# reason codes (STRATEGY_RULEBOOK.md section J)
INV_SESSION = "INV_SESSION"
INV_CONTEXT_TREND = "INV_CONTEXT_TREND"
INV_CONTEXT_UNDEFINED = "INV_CONTEXT_UNDEFINED"
INV_NO_EXTENSION = "INV_NO_EXTENSION"
INV_LOCATION = "INV_LOCATION"
INV_NO_SHIFT = "INV_NO_SHIFT"
INV_DXY_SAME_DIRECTION = "INV_DXY_SAME_DIRECTION"
INV_DXY_NO_INVERSION = "INV_DXY_NO_INVERSION"
INV_DXY_NO_DATA = "INV_DXY_NO_DATA"
INV_TARGET_REACHED = "INV_TARGET_REACHED"
INV_NO_PULLBACK = "INV_NO_PULLBACK"
INV_STRUCTURE_BROKEN = "INV_STRUCTURE_BROKEN"
INV_STALE = "INV_STALE"
SAFE_POSITION_OPEN = "SAFE_POSITION_OPEN"
SAFE_RISK = "SAFE_RISK"
SAFE_SIZE = "SAFE_SIZE"
TRADE = "TRADE"


# ------------------------------------------------------------------------------------------------
# Extension tracker (spec 4). sign = +1 tracks a bullish extension (sell setup), -1 a bearish one (buy setup).
# ------------------------------------------------------------------------------------------------
class ExtTracker:
    __slots__ = ("sign", "E", "e", "O", "o", "PB", "run", "run_i", "dd", "rm")

    def __init__(self, sign: int) -> None:
        self.sign = sign
        self.reset()

    def reset(self) -> None:
        self.E = np.nan       # extreme (max high for +1, min low for -1)
        self.e = -1           # first bar index that set the extreme
        self.O = np.nan       # origin (min low before e for +1, max high for -1)
        self.o = -1           # last bar index of the origin
        self.PB = 0.0         # max internal pullback / extension size over (o, e]
        self.run = np.nan     # running origin candidate since the candle open
        self.run_i = -1
        self.dd = 0.0         # max pullback since run_i
        self.rm = np.nan      # running extreme since run_i (excluding the current bar when measuring dd)

    def update(self, k: int, h: float, l: float) -> None:
        if not (np.isfinite(h) and np.isfinite(l)):
            return
        if self.sign > 0:
            if self.run_i < 0 or l <= self.run:
                self.run, self.run_i, self.dd, self.rm = l, k, 0.0, h
            else:
                self.dd = max(self.dd, self.rm - l)
                self.rm = max(self.rm, h)
            if self.e < 0 or h > self.E:
                self.E, self.e, self.O, self.o = h, k, self.run, self.run_i
                size = self.E - self.O
                self.PB = self.dd / size if size > 0 else 0.0
        else:
            if self.run_i < 0 or h >= self.run:
                self.run, self.run_i, self.dd, self.rm = h, k, 0.0, l
            else:
                self.dd = max(self.dd, h - self.rm)
                self.rm = min(self.rm, l)
            if self.e < 0 or l < self.E:
                self.E, self.e, self.O, self.o = l, k, self.run, self.run_i
                size = self.O - self.E
                self.PB = self.dd / size if size > 0 else 0.0

    @property
    def size(self) -> float:
        return (self.E - self.O) * self.sign if self.e >= 0 else 0.0


@dataclass
class Arrays:
    t: np.ndarray            # int64 ns, bar open time (UTC)
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    ph_prev: np.ndarray      # last pivot-high index <= k
    pl_prev: np.ndarray      # last pivot-low index <= k


def make_arrays(times_ns, o, h, l, c, pivot_strength: int) -> Arrays:
    ph, pl = pivot_flags(h, l, pivot_strength)
    return Arrays(times_ns, o, h, l, c, prev_index(ph), prev_index(pl))


def find_shift(a: Arrays, ext: ExtTracker, t: int, n: int, wick: bool, min_break: float):
    """Type-3 shift against `ext` at bar t (spec 6). Returns (protected_idx, protected_price) or None.

    For a bullish extension the shift is bearish: close below the most recent known pivot low between the origin and
    the extreme, which itself follows a pivot high (the high that the extension took out).
    """
    if ext.e < 0 or t <= ext.e:
        return None
    lim = min(ext.e - 1, t - n)
    if lim < 0:
        return None
    if ext.sign > 0:
        k = int(a.pl_prev[lim])
        if k < ext.o:
            return None
        lim2 = min(k - 1, t - n)
        if lim2 < 0 or a.ph_prev[lim2] < ext.o:
            return None
        level = a.l[k]
        px = a.l[t] if wick else a.c[t]
        return (k, level) if px < level - min_break else None
    k = int(a.ph_prev[lim])
    if k < ext.o:
        return None
    lim2 = min(k - 1, t - n)
    if lim2 < 0 or a.pl_prev[lim2] < ext.o:
        return None
    level = a.h[k]
    px = a.h[t] if wick else a.c[t]
    return (k, level) if px > level + min_break else None


# ------------------------------------------------------------------------------------------------
# Results
# ------------------------------------------------------------------------------------------------
@dataclass
class SetupRecord:
    setup_id: int
    tf: int
    candle_open: pd.Timestamp
    condition: str = ""
    ratio_median: float = float("nan")
    reason: str = ""
    direction: int = 0
    signal_time: pd.Timestamp | None = None
    shift_minute: int = 0
    ext_E: float = float("nan")
    ext_O: float = float("nan")
    ext_minutes: float = float("nan")
    ext_pullback: float = float("nan")
    protected: float = float("nan")
    gate: str = ""
    notes: list = field(default_factory=list)


@dataclass
class RunResult:
    trades: pd.DataFrame
    setups: pd.DataFrame
    counters: dict


# ------------------------------------------------------------------------------------------------
# Candle tracker (one per candle timeframe, spec M)
# ------------------------------------------------------------------------------------------------
class CandleTracker:
    def __init__(self, p: Params, gold: Arrays, dxy: Arrays | None, atr_m1: np.ndarray):
        self.p = p
        self.g = gold
        self.x = dxy
        self.atr = atr_m1
        self.period_ns = p.candle_minutes * NS_MIN
        self.candle = None
        self.rec: SetupRecord | None = None
        self.active = False
        self.done_dirs: set[int] = set()
        self.evaluated: dict[int, int] = {}
        self.flags: dict[str, bool] = {}
        self.gate_reason = ""
        self.g_bull, self.g_bear = ExtTracker(1), ExtTracker(-1)
        self.x_bull, self.x_bear = ExtTracker(1), ExtTracker(-1)
        self.x_shift_up = -1     # last DXY bullish shift bar in this candle
        self.x_shift_dn = -1     # last DXY bearish shift bar in this candle
        self.x_open = np.nan
        self.x_hi = np.nan
        self.x_lo = np.nan
        self.ctx_g = None
        self.ctx_x = None
        self.loc_sell = None
        self.loc_buy = None
        self.x_loc_buy = None
        self.x_loc_sell = None
        self.prev_candle_high = np.nan
        self.prev_candle_low = np.nan

    # -- candle lifecycle ---------------------------------------------------------------------
    def start(self, candle_ns: int, setup_id: int) -> None:
        p = self.p
        self.candle = candle_ns
        i0 = int(np.searchsorted(self.g.t, candle_ns - self.period_ns))
        i1 = int(np.searchsorted(self.g.t, candle_ns))
        self.prev_candle_high = float(np.max(self.g.h[i0:i1])) if i1 > i0 else np.nan
        self.prev_candle_low = float(np.min(self.g.l[i0:i1])) if i1 > i0 else np.nan
        ts = pd.Timestamp(candle_ns, tz="UTC")
        self.rec = SetupRecord(setup_id, p.candle_minutes, ts)
        self.done_dirs = set()
        self.evaluated = {}
        self.flags = {}
        self.gate_reason = ""
        for tr in (self.g_bull, self.g_bear, self.x_bull, self.x_bear):
            tr.reset()
        self.x_shift_up = self.x_shift_dn = -1
        self.x_open = self.x_hi = self.x_lo = np.nan
        self.active = is_trading_candle(ts, p.session_preset)
        if not self.active:
            self.rec.reason = INV_SESSION
            return
        g = self.g
        self.ctx_g = mtf_context(g.t, g.o, g.h, g.l, g.c, candle_ns, p)
        self.rec.condition = self.ctx_g.condition
        self.rec.ratio_median = self.ctx_g.ratio_median
        if self.ctx_g.condition == "TREND":
            self.active, self.rec.reason = False, INV_CONTEXT_TREND
            return
        if not self.ctx_g.tradable:
            self.active, self.rec.reason = False, INV_CONTEXT_UNDEFINED
            return
        self.loc_sell = location_level(self.ctx_g, SELL, p)
        self.loc_buy = location_level(self.ctx_g, BUY, p)
        if self.x is not None and p.dxy_mode != "OFF":
            x = self.x
            self.ctx_x = mtf_context(x.t, x.o, x.h, x.l, x.c, candle_ns, p)
            self.x_loc_buy = location_level(self.ctx_x, BUY, p)
            self.x_loc_sell = location_level(self.ctx_x, SELL, p)

    def finish(self) -> SetupRecord | None:
        rec = self.rec
        if rec is None:
            return None
        if not rec.reason:
            if self.gate_reason:
                rec.reason = self.gate_reason
            elif self.flags.get("valid_ext"):
                rec.reason = INV_NO_SHIFT
            elif self.flags.get("ext_no_location"):
                rec.reason = INV_LOCATION
            else:
                rec.reason = INV_NO_EXTENSION
        self.rec = None
        self.active = False
        return rec

    # -- per bar ------------------------------------------------------------------------------
    def minute(self, t: int) -> int:
        return int((self.g.t[t] - self.candle) // NS_MIN) + 1

    def ext_valid(self, ext: ExtTracker) -> bool:
        p = self.p
        if ext.e < 0 or ext.size <= 0:
            return False
        dur = (self.g.t[ext.e] - self.g.t[ext.o]) // NS_MIN + 1
        if dur < p.min_ext_minutes or ext.PB >= p.max_ext_pullback:
            return False
        if p.min_ext_atr_mult > 0:
            a = self.atr[ext.e]
            if not np.isfinite(a) or ext.size < p.min_ext_atr_mult * a:
                return False
        if p.require_prev_candle_break:
            ref = self.prev_candle_high if ext.sign > 0 else self.prev_candle_low
            if not np.isfinite(ref) or (ext.E - ref) * ext.sign <= 0:
                return False
        level = self.loc_sell if ext.sign > 0 else self.loc_buy
        if level is None or (ext.E - level) * ext.sign < 0:
            self.flags["ext_no_location"] = True
            return False
        return True

    def update_bar(self, t: int) -> None:
        g = self.g
        self.g_bull.update(t, g.h[t], g.l[t])
        self.g_bear.update(t, g.h[t], g.l[t])
        if self.x is None:
            return
        x = self.x
        if not (np.isfinite(x.h[t]) and np.isfinite(x.l[t])):
            return
        if not np.isfinite(self.x_open):
            self.x_open = x.o[t]
            self.x_hi, self.x_lo = x.h[t], x.l[t]
        else:
            self.x_hi, self.x_lo = max(self.x_hi, x.h[t]), min(self.x_lo, x.l[t])
        self.x_bull.update(t, x.h[t], x.l[t])
        self.x_bear.update(t, x.h[t], x.l[t])
        n, wick = self.p.pivot_strength, self.p.break_confirm == "WICK"
        if find_shift(x, self.x_bear, t, n, wick, 0.0):     # DXY drove down, then broke a high -> bullish DXY shift
            self.x_shift_up = t
        if find_shift(x, self.x_bull, t, n, wick, 0.0):     # DXY drove up, then broke a low -> bearish DXY shift
            self.x_shift_dn = t

    def dxy_close_at(self, k: int) -> float:
        x = self.x
        lo = max(int(np.searchsorted(self.g.t, self.candle)), 0)
        for j in range(k, lo - 1, -1):
            if np.isfinite(x.c[j]):
                return x.c[j]
        return np.nan

    def gate(self, direction: int, ext: ExtTracker, t: int) -> str:
        """COR-1..3 (spec 7). Returns '' if passed, else the INV_* reason."""
        p = self.p
        if p.dxy_mode == "OFF":
            return ""
        if self.x is None or not np.isfinite(self.x_open):
            return INV_DXY_NO_DATA
        x0, xh, xl = self.x_open, self.x_hi, self.x_lo
        xe = self.dxy_close_at(ext.e)
        if not np.isfinite(xe):
            return INV_DXY_NO_DATA
        if direction == SELL:      # gold sell needs a DXY buy setup: DXY drove DOWN
            if not ((x0 - xl) > (xh - x0) and xe < x0):
                return INV_DXY_SAME_DIRECTION
            if self.x_loc_buy is None or xl > self.x_loc_buy:
                return INV_DXY_NO_INVERSION
            if p.dxy_mode == "FULL" and not (self.x_shift_up > self.x_bear.e and self.x_shift_up <= t):
                return INV_DXY_NO_INVERSION
        else:                      # gold buy needs a DXY sell setup: DXY drove UP
            if not ((xh - x0) > (x0 - xl) and xe > x0):
                return INV_DXY_SAME_DIRECTION
            if self.x_loc_sell is None or xh < self.x_loc_sell:
                return INV_DXY_NO_INVERSION
            if p.dxy_mode == "FULL" and not (self.x_shift_dn > self.x_bull.e and self.x_shift_dn <= t):
                return INV_DXY_NO_INVERSION
        return ""

    def check_signals(self, t: int):
        """Return a list of (direction, ext, protected) signals at bar t (after gate)."""
        p = self.p
        out = []
        m = self.minute(t)
        for direction, ext in ((SELL, self.g_bull), (BUY, self.g_bear)):
            if direction in self.done_dirs:
                continue
            if not self.ext_valid(ext):
                continue
            self.flags["valid_ext"] = True
            if not (p.shift_start_min <= m <= p.shift_end_min):
                continue
            a = self.atr[t]
            min_break = p.min_break_atr * a if (p.min_break_atr > 0 and np.isfinite(a)) else 0.0
            sh = find_shift(self.g, ext, t, p.pivot_strength, p.break_confirm == "WICK", min_break)
            if sh is None:
                continue
            if self.evaluated.get(direction) == ext.e:
                continue                       # this extreme was already evaluated (SHF-5)
            self.evaluated[direction] = ext.e
            reason = self.gate(direction, ext, t)
            rec = self.rec
            rec.notes.append((int(t), direction, reason or "gate_ok"))
            if reason:
                self.gate_reason = reason
                continue
            self.done_dirs.add(direction)
            out.append((direction, ext, sh))
        return out


# ------------------------------------------------------------------------------------------------
# Execution simulation (spec 8) — same conventions as qe/labels.py
# ------------------------------------------------------------------------------------------------
@dataclass
class Book:
    bo: np.ndarray
    bh: np.ndarray
    bl: np.ndarray
    bc: np.ndarray
    ao: np.ndarray
    ah: np.ndarray
    al: np.ndarray
    ac: np.ndarray


def run_exit(b: Book, fill: int, direction: int, entry: float, sl: float, tp: float, last: int, slip: float,
             check_gap_on_fill_bar: bool = False):
    """Walk bars fill..last (inclusive). Stop first, then target, then time exit at the close of `last`.

    Returns (exit_idx, exit_price, outcome) with outcome 1 target, -1 stop, 0 time.
    """
    if direction > 0:
        hi, lo, op, cl = b.bh, b.bl, b.bo, b.bc
    else:
        hi, lo, op, cl = b.ah, b.al, b.ao, b.ac
    for j in range(fill, last + 1):
        gap_ok = j > fill or check_gap_on_fill_bar
        if direction > 0:
            if gap_ok and op[j] <= sl:
                return j, op[j] - slip, -1
            if lo[j] <= sl:
                return j, sl - slip, -1
            if hi[j] >= tp:
                return j, tp, 1
        else:
            if gap_ok and op[j] >= sl:
                return j, op[j] + slip, -1
            if hi[j] >= sl:
                return j, sl + slip, -1
            if lo[j] <= tp:
                return j, tp, 1
    return last, cl[last] - direction * slip, 0


def _bars_to_blackout(blackout: np.ndarray) -> np.ndarray:
    n = len(blackout)
    out = np.full(n, n, dtype=np.int64)
    nxt = n
    for i in range(n - 1, -1, -1):
        if blackout[i]:
            nxt = i
        out[i] = nxt - i
    return out


# ------------------------------------------------------------------------------------------------
# Driver
# ------------------------------------------------------------------------------------------------
def run(gold: pd.DataFrame, dxy: pd.DataFrame | None, params_list: list[Params], inst: Instrument, cfg: dict,
        equity: float = 100_000.0, risk_pct: float = 0.20, daily_loss_pct: float = 1.00,
        slippage_ticks: float = 1.0, record_setups: bool = True) -> RunResult:
    """Run one or more candle trackers (CandleMode) over gold M1 bid/ask bars with an aligned DXY frame.

    gold: columns bo bh bl bc ao ah al ac, tz-aware UTC minute index. dxy: columns o h l c (any index; aligned here).
    """
    if gold.index.tz is None:
        raise ValueError("gold index must be tz-aware UTC")
    strengths = {p.pivot_strength for p in params_list}
    if len(strengths) != 1:
        raise ValueError("all trackers must share pivot_strength")
    n_piv = strengths.pop()
    times = gold.index.as_unit("ns").asi8.astype(np.int64)   # pandas 3 defaults to microsecond indexes
    book = Book(*(gold[c].to_numpy(float) for c in ("bo", "bh", "bl", "bc", "ao", "ah", "al", "ac")))
    g = make_arrays(times, book.bo, book.bh, book.bl, book.bc, n_piv)
    atr = atr_sma(book.bh, book.bl, book.bc, params_list[0].atr_period_m1)
    xa = None
    if dxy is not None and len(dxy):
        dx = dxy.reindex(gold.index)
        xa = make_arrays(times, *(dx[c].to_numpy(float) for c in ("o", "h", "l", "c")), n_piv)
    ses = session_frame(gold.index, cfg)
    fxday = ses["fx_day"].to_numpy()
    to_bo = _bars_to_blackout(ses["rollover_blackout"].to_numpy())
    slip = slippage_ticks * inst.tick_size

    trackers = [CandleTracker(p, g, xa, atr) for p in params_list]
    # bars belonging to a candle that is in session for at least one tracker
    active_any = np.zeros(len(times), dtype=bool)
    for tr in trackers:
        cid = times - (times % tr.period_ns)
        uniq, inv = np.unique(cid, return_inverse=True)
        ok = np.array([is_trading_candle(pd.Timestamp(u, tz="UTC"), tr.p.session_preset) for u in uniq])
        active_any |= ok[inv]
    idxs = np.flatnonzero(active_any)

    rm = RiskManager(equity=equity, risk_per_trade_pct=risk_pct, max_daily_loss_pct=daily_loss_pct,
                     max_open_risk_pct=risk_pct * 3, max_positions=1)
    trades: list[dict] = []
    setups: list[SetupRecord] = []
    counters: dict[str, int] = {}
    pending: tuple | None = None           # (release_idx, pnl, record) of the open position / pending order
    setup_id = 0

    def bump(k: str) -> None:
        counters[k] = counters.get(k, 0) + 1

    def close_pending(t: int) -> None:
        nonlocal pending
        if pending is not None and t >= pending[0]:
            rel, pnl, rec = pending
            if rec is not None:
                rm.on_close(inst.symbol, pnl)
                rec["equity_after"] = rm.equity
                trades.append(rec)
            pending = None

    for t in idxs:
        t = int(t)
        close_pending(t)
        rm.new_day(fxday[t])
        for tr in trackers:
            cid = int(times[t] - times[t] % tr.period_ns)
            if cid != tr.candle:
                old = tr.finish()
                if old is not None:
                    bump(f"tf{old.tf}:{old.reason}")
                    if record_setups and old.reason != INV_SESSION:
                        setups.append(old)
                setup_id += 1
                tr.start(cid, setup_id)
            if not tr.active:
                continue
            tr.update_bar(t)
            for direction, ext, sh in tr.check_signals(t):
                rec = tr.rec
                if pending is not None:
                    rec.notes.append((t, direction, SAFE_POSITION_OPEN))
                    rec.reason = SAFE_POSITION_OPEN
                    continue
                res = _execute(tr, book, g, atr, t, direction, ext, sh, inst, rm, slip, to_bo, fxday)
                rec.direction, rec.signal_time = direction, pd.Timestamp(times[t], tz="UTC")
                rec.shift_minute = tr.minute(t)
                rec.ext_E, rec.ext_O, rec.ext_pullback = ext.E, ext.O, ext.PB
                rec.ext_minutes = float((times[ext.e] - times[ext.o]) // NS_MIN + 1)
                rec.protected = sh[1]
                rec.gate = "pass"
                rec.reason = res["reason"]
                if res["reason"] == TRADE:
                    tr.active = False
                    pending = (res["release"], res["pnl"], res["trade"])
                    rm.on_open(OpenPosition(inst.symbol, direction, res["trade"]["lots"], res["trade"]["planned_risk_usd"]))
                    break
                if res.get("release") is not None:       # cancelled pending order blocked the book until then
                    tr.active = False
                    pending = (res["release"], 0.0, None)
                    break
    for tr in trackers:
        old = tr.finish()
        if old is not None:
            bump(f"tf{old.tf}:{old.reason}")
            if record_setups and old.reason != INV_SESSION:
                setups.append(old)
    if pending is not None and pending[2] is not None:
        rm.on_close(inst.symbol, pending[1])
        pending[2]["equity_after"] = rm.equity
        trades.append(pending[2])
    tdf = pd.DataFrame(trades)
    sdf = pd.DataFrame([s.__dict__ for s in setups], columns=[f.name for f in fields(SetupRecord)])
    return RunResult(tdf, sdf, counters)


def _execute(tr: CandleTracker, b: Book, g: Arrays, atr: np.ndarray, t: int, direction: int, ext: ExtTracker,
             sh, inst: Instrument, rm: RiskManager, slip: float, to_bo: np.ndarray, fxday) -> dict:
    p = tr.p
    n = len(b.bo)
    times = g.t
    a = atr[t] if np.isfinite(atr[t]) else 0.0
    buf = max(p.stop_buffer_price, p.stop_buffer_atr * a)
    E, O = ext.E, ext.O
    tp_level = O + 0.5 * (E - O)
    if p.entry_mode == "BREAK":
        fill = t + 1
        if fill >= n or times[fill] - times[t] > 5 * NS_MIN:
            return {"reason": INV_STALE}
        spread = b.ao[fill] - b.bo[fill]
        entry = b.bo[fill] - slip if direction == SELL else b.ao[fill] + slip
        cancel_release = None
    else:
        spread = b.ao[t] - b.bo[t]
        if direction == SELL:
            B = float(np.nanmin(b.bl[ext.e + 1: t + 1]))
        else:
            B = float(np.nanmax(b.bh[ext.e + 1: t + 1]))
        candle_end = tr.candle + p.candle_minutes * NS_MIN
        fill, entry, cancel_reason = None, None, INV_NO_PULLBACK
        k = t + 1
        while k < n and times[k] < candle_end:
            limit = B + 0.5 * (E - B)          # 50% of the breaking leg, on the bid chart
            if direction == SELL:
                if b.bl[k] <= tp_level:        # target traded first (or in the same bar: ambiguous -> no trade)
                    cancel_reason = INV_TARGET_REACHED
                    break
                if b.bh[k] >= limit:
                    fill, entry = k, max(limit, b.bo[k])
                    break
                B = min(B, b.bl[k])
            else:
                lim_ask = limit + spread       # buy limit triggers when the bid touches the level
                if b.bh[k] >= tp_level:
                    cancel_reason = INV_TARGET_REACHED
                    break
                if b.al[k] <= lim_ask:
                    fill, entry = k, min(lim_ask, b.ao[k])
                    break
                B = max(B, b.bh[k])
            k += 1
        if fill is None:
            return {"reason": cancel_reason, "release": min(k, n - 1)}
        cancel_release = fill
    if direction == SELL:
        sl = E + spread + buf
        tp = tp_level + (spread if p.adjust_sell_tp_for_spread else 0.0)
    else:
        sl = E - buf
        tp = tp_level
    if p.target_mode == "FIXED_R":
        risk = abs(sl - entry)
        tp = entry + direction * p.fixed_r * risk
    reward = (tp - entry) * direction
    risk_d = (entry - sl) * direction
    if reward <= 0 or risk_d <= 0:
        return {"reason": INV_TARGET_REACHED, "release": cancel_release}
    size = size_position(inst, rm.equity, rm.risk_per_trade_pct, entry, sl, slip / inst.tick_size)
    if size.lots <= 0:
        return {"reason": SAFE_SIZE}
    ok, why = rm.check_new_order(inst.symbol, direction, size.planned_risk_usd)
    if not ok:
        return {"reason": SAFE_RISK, "why": why}
    max_bars = int(min(p.max_hold_minutes, max(1, to_bo[fill])))
    last = min(fill + max_bars - 1, n - 1)
    x, xp, oc = run_exit(b, fill, direction, entry, sl, tp, last, slip, check_gap_on_fill_bar=False)
    pnl_px = (xp - entry) * direction
    comm = commission_round_trip(inst, size.lots)
    pnl = pnl_px * value_per_price_unit(inst, size.lots, entry) - comm
    trade = dict(symbol=inst.symbol, tf=p.candle_minutes, entry_mode=p.entry_mode, dxy_mode=p.dxy_mode,
                 signal_time=pd.Timestamp(times[t], tz="UTC"), entry_time=pd.Timestamp(times[fill], tz="UTC"),
                 exit_time=pd.Timestamp(times[x], tz="UTC"), direction=direction, lots=size.lots, entry=entry,
                 sl=sl, tp=tp, exit=xp, outcome=oc, minutes=int((times[x] - times[fill]) // NS_MIN + 1),
                 ext_E=E, ext_O=O, protected=sh[1], spread=spread, pnl_usd=pnl, commission_usd=comm,
                 planned_risk_usd=size.planned_risk_usd, R=pnl / size.planned_risk_usd,
                 planned_rr=reward / risk_d, fx_day=fxday[t])
    return {"reason": TRADE, "trade": trade, "pnl": pnl, "release": x}
