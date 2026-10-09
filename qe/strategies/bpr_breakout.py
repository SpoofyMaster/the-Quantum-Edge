"""BprFvgEA v2: BPR rejection -> breakout -> Fibonacci pullback. Pure-Python reference of the setup detector.

Licence and attribution
-----------------------
(c) LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]').
Licensed under CC BY-NC-SA 4.0: https://creativecommons.org/licenses/by-nc-sa/4.0/
The FVG / BPR zones come from ``qe/indicators/luxalgo_bpr.py``, a port (a derivative work) of the FVG / BPR part of
that Pine v5 script. This file builds on that port and is shared under the same licence, for non-commercial research
use only. It is not affiliated with or endorsed by LuxAlgo. The setup rules are the project owner's (hypothesis H-14).

What this module is
-------------------
The single source of truth is ``research/indicators/BPR_BREAKOUT_FIB_SPEC.md`` ("spec" below). This module implements:

* ``BreakoutDetector``: spec sections 2-6. A pure state machine: closed bars plus an ``Env`` in, ``Intent`` objects
  out, one event record per state change in ``events`` (spec section 7). It owns a ``LuxBprEngine`` in **Historical**
  mode (no look-ahead).
* ``harness_run``: the spec section 7 parity harness (the MQL5 EA's pure detector is compared against this).

Status: the rules are hypothesis **H-14** (``HYPOTHESIS``, untested). Nothing here is evidence of an edge.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

from qe.indicators.luxalgo_bpr import BprParams, LuxBprEngine

__all__ = [
    "BreakoutParams",
    "Env",
    "Intent",
    "Level",
    "BkSetup",
    "BreakoutDetector",
    "harness_run",
    "harness_detector",
    "round_to_tick",
    "DIRECTIONS",
    "FVG_RULES",
    "REASONS",
    "EVENTS",
]

DIRECTIONS = ("BOTH", "LONG_ONLY", "SHORT_ONLY")
FVG_RULES = ("LUXALGO", "ANY_GAP", "NONE")

# setup phases (spec section 4)
WAIT, ZONE, BREAK, LEG, ORDERED, FILLED, CLOSED, DONE = (
    "WAIT", "ZONE", "BREAK", "LEG", "ORDERED", "FILLED", "CLOSED", "DONE")
PHASES = (WAIT, ZONE, BREAK, LEG, ORDERED, FILLED, CLOSED, DONE)
TRACKED = (WAIT, ZONE, BREAK, LEG, ORDERED, FILLED)

# level statuses
L_NONE, L_PENDING, L_FILLED, L_CLOSED, L_SKIPPED, L_CANCELLED, L_DROPPED = (
    "NONE", "PENDING", "FILLED", "CLOSED", "SKIPPED", "CANCELLED", "DROPPED")

# event records (spec section 7)
EV_ARMED, EV_TOUCH, EV_REJECT, EV_BREAKOUT, EV_BREAK_FAIL, EV_CONFIRM = (
    "ARMED", "TOUCH", "REJECT", "BREAKOUT", "BREAK_FAIL", "CONFIRM")
EV_PLACE_LIMIT, EV_SKIP, EV_CANCEL, EV_DROP, EV_CLOSED, EV_DONE = (
    "PLACE_LIMIT", "SKIP", "CANCEL", "DROP", "CLOSED", "DONE")
EVENTS = (EV_ARMED, EV_TOUCH, EV_REJECT, EV_BREAKOUT, EV_BREAK_FAIL, EV_CONFIRM, EV_PLACE_LIMIT, EV_SKIP, EV_CANCEL,
          EV_DROP, EV_CLOSED, EV_DONE)

REASONS = ("BAD_GEOMETRY", "BROKEN_AT_CREATION", "CAPACITY", "WARMUP", "BROKEN", "EXPIRED", "TOUCH_LIMIT",
           "LEG_BROKEN", "NEW_EXTREME", "TARGET", "SESSION_END", "NO_LEVEL", "MISSED", "RR", "COST", "BAD_LEVEL",
           "SIZE_BELOW_MIN", "ORDER_FAILED")

MAX_HOLD_CAP_MIN = 120
ENGINE_PERC_BODY = 0.36
ENGINE_BX_BACK = 10
ENGINE_EXT_BARS = 8


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def round_to_tick(x: float, tick: float, digits: int = 10) -> float:
    """MQL5 ``NormalizeDouble(MathRound(x / tick) * tick, digits)``: half away from zero at both steps."""
    if tick <= 0:
        return x
    q = x / tick
    r = math.floor(abs(q) + 0.5) * (1 if q >= 0 else -1)
    v = r * tick
    p = 10.0 ** digits
    w = v * p
    return (math.floor(abs(w) + 0.5) * (1 if w >= 0 else -1)) / p


@dataclass(frozen=True)
class BreakoutParams:
    """Spec section 1 (Python column). Defaults were fixed from the owner's rule before any data was looked at.

    ``tick_size`` / ``digits`` / ``contract_size`` describe the symbol (XAUUSD-like defaults, ``UNVERIFIED``).
    ``comm_price`` = round-trip commission per lot / value of a 1.0 price move per lot (USD-quoted symbols).
    Any non-default value used in a backtest is a new trial and must be registered.
    """

    direction: str = "BOTH"
    max_touches: int = 2
    confirm_closes: int = 2
    fvg_rule: str = "LUXALGO"
    setup_expiry_bars: int = 240
    leg_expiry_bars: int = 60
    fib_levels: tuple[float, float, float] = (50.0, 61.8, 71.0)
    stop_fib: float = 100.0
    stop_buffer_ticks: int = 10
    target_fib: float = 0.0
    min_rr: float = 0.0
    max_cost_r: float = 0.30
    max_hold_min: int = 120
    use_session: bool = True
    slippage_ticks: float = 1.0
    commission_per_lot_side: float = 3.5
    tick_size: float = 0.01
    digits: int = 2
    contract_size: float = 100.0
    capacity: int = 128
    length: int = 5
    vis_boxes: int = 2

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {DIRECTIONS}, got {self.direction!r}")
        if self.fvg_rule not in FVG_RULES:
            raise ValueError(f"fvg_rule must be one of {FVG_RULES}, got {self.fvg_rule!r}")
        for name, lo, hi in (("max_touches", 1, 5), ("confirm_closes", 1, 5), ("setup_expiry_bars", 1, 100000),
                             ("leg_expiry_bars", 1, 100000), ("stop_buffer_ticks", 0, 100000),
                             ("max_hold_min", 1, MAX_HOLD_CAP_MIN), ("capacity", 1, 128), ("length", 3, 10),
                             ("vis_boxes", 1, 20), ("digits", 0, 10)):
            v = getattr(self, name)
            if not _is_int(v) or not lo <= v <= hi:
                raise ValueError(f"{name} must be an int in {lo}..{hi}, got {v!r}")
        if not isinstance(self.use_session, bool):
            raise ValueError("use_session must be a bool")
        if len(self.fib_levels) != 3 or not all(_is_num(f) and 0.0 <= f < 100.0 for f in self.fib_levels):
            raise ValueError(f"fib_levels must be 3 numbers in [0, 100), got {self.fib_levels!r}")
        if not any(f > 0.0 for f in self.fib_levels):
            raise ValueError("at least one fib level must be > 0")
        if not _is_num(self.stop_fib) or not 0.0 < self.stop_fib <= 200.0:
            raise ValueError(f"stop_fib must be in (0, 200], got {self.stop_fib!r}")
        if not _is_num(self.target_fib) or not -200.0 <= self.target_fib < 100.0:
            raise ValueError(f"target_fib must be in [-200, 100), got {self.target_fib!r}")
        for name in ("min_rr", "max_cost_r", "slippage_ticks", "commission_per_lot_side"):
            v = getattr(self, name)
            if not _is_num(v) or v < 0:
                raise ValueError(f"{name} must be a number >= 0, got {v!r}")
        for name in ("tick_size", "contract_size"):
            v = getattr(self, name)
            if not _is_num(v) or v <= 0:
                raise ValueError(f"{name} must be a number > 0, got {v!r}")

    @property
    def comm_price(self) -> float:
        return 2.0 * self.commission_per_lot_side / self.contract_size

    def engine_params(self) -> BprParams:
        return BprParams(mode="Historical", length=self.length, perc_body=ENGINE_PERC_BODY, show_fvg=True, bpr=True,
                         fvg_mode="FVG", vis_boxes=self.vis_boxes, bx_back=ENGINE_BX_BACK, ext_bars=ENGINE_EXT_BARS)


@dataclass
class Env:
    """Environment of one closed bar (same meaning as the v1 EA): ``sp`` is the spread at the decision moment."""

    slot_free: bool
    session_entry_ok: bool
    session_cancel: bool
    risk_ok: bool
    spread_ok: bool
    sp: float


@dataclass(frozen=True)
class Intent:
    """``PLACE_LIMIT`` (level ``k``) or ``CANCEL`` (level ``k``, reason)."""

    type: str
    id: int
    dir: int
    k: int
    P: float | None = None
    SL: float | None = None
    TP: float | None = None
    reason: str | None = None


@dataclass
class Level:
    fib: float
    status: str = L_NONE
    P: float | None = None
    reason: str | None = None


@dataclass
class BkSetup:
    """One tracked BPR setup (spec sections 3-6)."""

    id: int
    dir: int
    created: int
    B: float
    T: float
    phase: str = WAIT
    reason: str | None = None
    touches: int = 0
    in_ep: bool = False
    ref: int = -1
    lvl: float = math.nan
    O: float = math.nan  # noqa: E741 (spec name)
    o_bar: int = -1
    X: float = math.nan
    x_bar: int = -1
    brk_bar: int = -1
    n_close: int = 0
    confirm_bar: int = -1
    decision_bar: int = -1
    ready: bool = False
    SL: float | None = None
    TP: float | None = None
    tgt: float | None = None
    dec_O: float | None = None
    dec_X: float | None = None
    touch_bars: list[int] = field(default_factory=list)
    levels: list[Level] = field(default_factory=list)
    ever_filled: bool = False
    end_bar: int | None = None


class BreakoutDetector:
    """The EA's v2 decision logic, driven by closed bars plus an ``Env``.

    ``on_bar_closed(u, o, h, l, c, env)`` must be called for ``u = 0, 1, 2, ...`` (bid prices of the closed bar) and
    returns the intents of that bar. The executor reports back with ``notify_filled``, ``notify_closed``,
    ``notify_cancelled`` and ``notify_retry``. ``stats`` counts diagnostics (not part of the parity records).
    """

    def __init__(self, params: BreakoutParams = BreakoutParams(), trade_from: int = 0) -> None:
        if not _is_int(trade_from) or trade_from < 0:
            raise ValueError(f"trade_from must be an int >= 0, got {trade_from!r}")
        self.params = params
        self.trade_from = trade_from
        self.engine = LuxBprEngine(params.engine_params())
        self.events: list[dict] = []
        self.setups: list[BkSetup] = []
        self.stats: dict[str, int] = {}
        self.last_bar = -1
        self._active: list[BkSetup] = []
        self._by_id: dict[int, BkSetup] = {}
        self._next_id = 1
        self._warm_ended = False
        self._fvg_bar = {1: -1, -1: -1}
        self._h3: list[float] = []
        self._l3: list[float] = []
        self._evs: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------------------------------- helpers
    def _stat(self, key: str) -> None:
        self.stats[key] = self.stats.get(key, 0) + 1

    def _log(self, n: int, st: BkSetup, ev: str, k: int = 0, reason: str | None = None, P: float | None = None,
             SL: float | None = None, TP: float | None = None, O: float | None = None,  # noqa: E741
             X: float | None = None) -> None:
        self.events.append({"n": n, "id": st.id, "ev": ev, "dir": st.dir, "k": k, "reason": reason, "P": P,
                            "SL": SL, "TP": TP, "O": O, "X": X})

    def _rt(self, x: float) -> float:
        return round_to_tick(x, self.params.tick_size, self.params.digits)

    def _done(self, st: BkSetup, n: int, reason: str) -> None:
        st.phase = DONE
        st.reason = reason
        st.end_bar = n
        self._active.remove(st)
        self._log(n, st, EV_DONE, reason=reason)
        self._stat("DONE_" + reason)

    def _closed(self, st: BkSetup, n: int) -> None:
        st.phase = CLOSED
        st.end_bar = n
        self._active.remove(st)
        self._log(n, st, EV_CLOSED)
        self._stat("CLOSED")

    def _cancel_pending(self, st: BkSetup, n: int, reason: str, intents: list[Intent] | None) -> None:
        for k, lv in enumerate(st.levels, start=1):
            if lv.status == L_PENDING:
                lv.status = L_CANCELLED
                lv.reason = reason
                self._log(n, st, EV_CANCEL, k=k, reason=reason)
                if intents is not None:
                    intents.append(Intent("CANCEL", st.id, st.dir, k, reason=reason))

    def _any(self, st: BkSetup, status: str) -> bool:
        return any(lv.status == status for lv in st.levels)

    def _maybe_closed(self, st: BkSetup, n: int, reason: str) -> None:
        """Nothing pending and nothing open: CLOSED if a level ever filled, otherwise DONE(reason)."""
        if self._any(st, L_PENDING) or self._any(st, L_FILLED):
            return
        if st.ever_filled:
            self._closed(st, n)
        else:
            self._done(st, n, reason)

    def has_order_or_position(self) -> bool:
        return any(st.phase in (ORDERED, FILLED) for st in self._active)

    def setup(self, sid: int) -> BkSetup:
        return self._by_id[sid]

    # ------------------------------------------------------------------------------------------- executor feedback
    def _level(self, sid: int, k: int) -> tuple[BkSetup, Level]:
        st = self._by_id[sid]
        if not 1 <= k <= len(st.levels):
            raise ValueError(f"setup {sid} has no level {k}")
        return st, st.levels[k - 1]

    def notify_filled(self, sid: int, k: int) -> None:
        st, lv = self._level(sid, k)
        if lv.status != L_PENDING or st.phase not in (ORDERED, FILLED):
            return  # a fill on a level the detector already cancelled: the executor manages it alone
        lv.status = L_FILLED
        st.ever_filled = True
        st.phase = FILLED

    def notify_closed(self, sid: int, k: int) -> None:
        st, lv = self._level(sid, k)
        if lv.status != L_FILLED:
            return
        lv.status = L_CLOSED
        if st.phase == FILLED:
            self._maybe_closed(st, self.last_bar, "ORDER_FAILED")

    def notify_cancelled(self, sid: int, k: int, reason: str) -> None:
        if reason not in REASONS:
            raise ValueError(f"unknown reason {reason!r}")
        st, lv = self._level(sid, k)
        if lv.status != L_PENDING or st.phase not in (ORDERED, FILLED):
            return
        lv.status = L_DROPPED
        lv.reason = reason
        self._log(self.last_bar, st, EV_DROP, k=k, reason=reason)
        self._stat("DROP_" + reason)
        self._maybe_closed(st, self.last_bar, reason)

    def notify_retry(self, sid: int) -> None:
        st = self._by_id[sid]
        if st.phase != ORDERED or st.ever_filled:
            return
        for lv in st.levels:
            lv.status = L_NONE
            lv.P = None
            lv.reason = None
        st.phase = LEG
        st.decision_bar = -1
        st.SL = st.TP = st.tgt = None
        self._stat("RETRY")

    # ------------------------------------------------------------------------------------------- one bar
    def on_bar_closed(self, u: int, o: float, h: float, l: float, c: float, env: Env) -> list[Intent]:  # noqa: E741
        if u != self.last_bar + 1:
            raise ValueError(f"bars must be consecutive from 0: expected {self.last_bar + 1}, got {u}")
        intents: list[Intent] = []
        # warm-up end (spec section 7): before anything else on the first bar >= trade_from
        if not self._warm_ended and u >= self.trade_from:
            self._warm_ended = True
            for st in list(self._active):
                if st.created < self.trade_from:
                    self._done(st, self.last_bar, "WARMUP")
        # step 1: engine
        self.engine.process_bar(u, o, h, l, c)
        evs = {(kind, what) for (n, kind, what) in self.engine.events if n == u}
        self.engine.events.clear()
        self._evs = evs
        self.last_bar = u
        self._h3 = (self._h3 + [h])[-3:]
        self._l3 = (self._l3 + [l])[-3:]
        # step 2: FVG bars
        rule = self.params.fvg_rule
        if rule == "LUXALGO":
            if ("FVG_UP", "new") in evs or ("FVG_UP", "update") in evs:
                self._fvg_bar[1] = u
            if ("FVG_DN", "new") in evs or ("FVG_DN", "update") in evs:
                self._fvg_bar[-1] = u
        elif rule == "ANY_GAP" and u >= 2:
            if l > self._h3[0]:
                self._fvg_bar[1] = u
            if h < self._l3[0]:
                self._fvg_bar[-1] = u
        # step 3: existing setups, creation order
        for st in list(self._active):
            self._step(st, u, h, l, c, env, intents)
        # step 4: new setups
        self._create(u)
        # step 5: decisions
        if u >= self.trade_from:
            self._decide(u, c, env, intents)
        return intents

    # ------------------------------------------------------------------------------------------- step 3
    def _beyond(self, st: BkSetup, c: float) -> bool:
        return c > st.lvl if st.dir > 0 else c < st.lvl

    def _track(self, st: BkSetup, u: int, h: float, l: float) -> None:  # noqa: E741
        if st.dir > 0:
            if l < st.O:
                st.O, st.o_bar, st.X, st.x_bar = l, u, h, u
            elif h > st.X:
                st.X, st.x_bar = h, u
        else:
            if h > st.O:
                st.O, st.o_bar, st.X, st.x_bar = h, u, l, u
            elif l < st.X:
                st.X, st.x_bar = l, u

    def _new_ext(self, st: BkSetup, h: float, l: float) -> bool:  # noqa: E741
        return h > st.X if st.dir > 0 else l < st.X

    def _origin_broken(self, st: BkSetup, h: float, l: float) -> bool:  # noqa: E741
        return l < st.O if st.dir > 0 else h > st.O

    def _confirm(self, st: BkSetup, u: int) -> None:
        st.phase = LEG
        st.confirm_bar = u
        self._log(u, st, EV_CONFIRM, O=st.O, X=st.X)
        self._stat("CONFIRM")

    def _step(self, st: BkSetup, u: int, h: float, l: float, c: float, env: Env,  # noqa: E741
              intents: list[Intent]) -> None:
        p = self.params
        d = st.dir
        st.ready = False
        if st.phase in (WAIT, ZONE, BREAK):
            # 4.1
            if (l < st.B) if d > 0 else (h > st.T):
                self._done(st, u, "BROKEN")
                return
            if u - st.created > p.setup_expiry_bars:
                self._done(st, u, "EXPIRED")
                return
            tn = (l <= st.T) if d > 0 else (h >= st.B)
            if st.phase == BREAK:
                if self._beyond(st, c):
                    st.n_close += 1
                    self._track(st, u, h, l)
                    if st.n_close >= p.confirm_closes:
                        self._confirm(st, u)
                    st.in_ep = tn
                    return
                self._log(u, st, EV_BREAK_FAIL)
                self._stat("BREAK_FAIL")
                st.phase = ZONE
                st.n_close = 0
            elif st.phase == ZONE and self._beyond(st, c):
                st.phase = BREAK
                st.brk_bar = u
                st.n_close = 1
                self._track(st, u, h, l)
                self._log(u, st, EV_BREAKOUT)
                self._stat("BREAKOUT")
                if st.n_close >= p.confirm_closes:
                    self._confirm(st, u)
                st.in_ep = tn
                return
            # step 6: touch logic
            if tn:
                if not st.in_ep:
                    st.touches += 1
                    if st.touches > p.max_touches:
                        self._done(st, u, "TOUCH_LIMIT")
                        return
                    self._log(u, st, EV_TOUCH, k=st.touches)
                    self._stat("TOUCH")
                    st.touch_bars.append(u)
                    if d > 0:
                        st.O, st.X = l, h
                    else:
                        st.O, st.X = h, l
                    st.o_bar = st.x_bar = u
                else:
                    self._track(st, u, h, l)
                st.ref = u
                st.lvl = h if d > 0 else l
                st.phase = ZONE
                st.in_ep = True
            else:
                if st.in_ep:
                    self._log(u, st, EV_REJECT)
                    st.in_ep = False
                if st.phase == ZONE:
                    self._track(st, u, h, l)
            return
        if st.phase == LEG:
            # 4.2
            if self._origin_broken(st, h, l):
                self._done(st, u, "LEG_BROKEN")
                return
            if u - st.confirm_bar > p.leg_expiry_bars:
                self._done(st, u, "EXPIRED")
                return
            if self._new_ext(st, h, l):
                st.X, st.x_bar = (h if d > 0 else l), u
                return
            if p.fvg_rule == "NONE" or self._fvg_bar[d] > st.ref:
                st.ready = True
            else:
                self._stat("WAIT_NO_FVG")
            return
        if st.phase == ORDERED:
            # 4.3
            if self._new_ext(st, h, l):
                self._cancel_pending(st, u, "NEW_EXTREME", intents)
                for lv in st.levels:
                    lv.status = L_NONE
                    lv.P = None
                    lv.reason = None
                st.X, st.x_bar = (h if d > 0 else l), u
                st.phase = LEG
                st.decision_bar = -1
                st.SL = st.TP = st.tgt = None
                self._stat("REANCHOR")
                return
            if self._origin_broken(st, h, l):
                self._cancel_pending(st, u, "LEG_BROKEN", intents)
                self._done(st, u, "LEG_BROKEN")
                return
            if u - st.confirm_bar > p.leg_expiry_bars:
                self._cancel_pending(st, u, "EXPIRED", intents)
                self._done(st, u, "EXPIRED")
                return
            if p.use_session and env.session_cancel:
                self._cancel_pending(st, u, "SESSION_END", intents)
                self._done(st, u, "SESSION_END")
            return
        if st.phase == FILLED:
            # 4.4
            if self._any(st, L_PENDING):
                assert st.tgt is not None
                touched = (h >= st.tgt) if d > 0 else (l <= st.tgt)
                if touched or self._new_ext(st, h, l):
                    self._cancel_pending(st, u, "TARGET", intents)
                elif u - st.confirm_bar > p.leg_expiry_bars:
                    self._cancel_pending(st, u, "EXPIRED", intents)
                elif p.use_session and env.session_cancel:
                    self._cancel_pending(st, u, "SESSION_END", intents)
            self._maybe_closed(st, u, "TARGET")

    # ------------------------------------------------------------------------------------------- step 4
    def _wanted(self, d: int) -> bool:
        if self.params.direction == "LONG_ONLY":
            return d > 0
        if self.params.direction == "SHORT_ONLY":
            return d < 0
        return True

    def _create(self, u: int) -> None:
        eng = self.engine
        up0 = eng.fvg_up[0].box if eng.fvg_up else None
        dn0 = eng.fvg_dn[0].box if eng.fvg_dn else None
        pair_ok = up0 is not None and dn0 is not None
        cands = []
        # spec section 3: the BPR_UP array first, then BPR_DN (same guards as v1)
        for kind, arr in (("BPR_UP", eng.bpr_up), ("BPR_DN", eng.bpr_dn)):
            if (kind, "new") in self._evs and pair_ok and arr and arr[0].box is not None and arr[0].pos in (1, -1):
                cands.append(arr[0])
        for z in cands:
            d = z.pos
            if not self._wanted(d):
                continue
            st = BkSetup(id=self._next_id, dir=d, created=u, B=z.box.bottom, T=z.box.top,
                         levels=[Level(f) for f in self.params.fib_levels])
            self._next_id += 1
            self.setups.append(st)
            self._by_id[st.id] = st
            reason = None
            if st.T <= st.B:
                reason = "BAD_GEOMETRY"
            elif not z.active:
                reason = "BROKEN_AT_CREATION"
            elif len(self._active) >= self.params.capacity:
                reason = "CAPACITY"
            if reason is not None:
                st.phase = DONE
                st.reason = reason
                st.end_bar = u
                self._log(u, st, EV_DONE, reason=reason)
                self._stat("DONE_" + reason)
                continue
            self._active.append(st)
            self._log(u, st, EV_ARMED)
            self._stat("ARMED")

    # ------------------------------------------------------------------------------------------- step 5
    def _decide(self, u: int, c: float, env: Env, intents: list[Intent]) -> None:
        ready = [st for st in self._active if st.phase == LEG and st.ready]
        if not ready:
            return
        blocked = None
        if not env.slot_free:
            blocked = "BLOCKED_SLOT"
        elif self.params.use_session and not env.session_entry_ok:
            blocked = "BLOCKED_SESSION"
        elif not env.risk_ok:
            blocked = "BLOCKED_RISK"
        elif not env.spread_ok:
            blocked = "BLOCKED_SPREAD"
        if blocked is not None:
            for _ in ready:
                self._stat(blocked)
            return
        for st in ready:
            if self._try_decide(st, u, c, env, intents):
                return

    def _try_decide(self, st: BkSetup, u: int, c: float, env: Env, intents: list[Intent]) -> bool:
        p = self.params
        d = st.dir
        sp = env.sp
        tk = p.tick_size
        L = d * (st.X - st.O)
        if L <= 0.0:
            self._done(st, u, "BAD_GEOMETRY")
            return False

        def F(f: float) -> float:
            return st.X - d * (f / 100.0) * L

        SL = F(p.stop_fib) - d * p.stop_buffer_ticks * tk + (sp if d < 0 else 0.0)
        tgt = F(p.target_fib)
        TP = tgt + (sp if d < 0 else 0.0)
        cost = sp + p.comm_price + 2.0 * p.slippage_ticks * tk
        placed: list[tuple[int, float]] = []
        skipped: list[tuple[int, str]] = []
        for k, lv in enumerate(st.levels, start=1):
            if lv.fib <= 0.0:
                continue
            P = F(lv.fib) + (sp if d > 0 else 0.0)
            risk = abs(P - SL)
            if d * (P - SL) <= 0.0 or d * (TP - P) <= 0.0:
                skipped.append((k, "BAD_LEVEL"))
            elif (d > 0 and c + sp <= P) or (d < 0 and c >= P):
                skipped.append((k, "MISSED"))
            elif p.min_rr > 0.0 and abs(TP - P) / risk < p.min_rr:
                skipped.append((k, "RR"))
            elif p.max_cost_r > 0.0 and cost / risk > p.max_cost_r:
                skipped.append((k, "COST"))
            else:
                placed.append((k, P))
        # records in level order
        rSL, rTP = self._rt(SL), self._rt(TP)
        sk = dict(skipped)
        pl = dict(placed)
        for k, lv in enumerate(st.levels, start=1):
            if k in sk:
                lv.status = L_SKIPPED
                lv.reason = sk[k]
                self._log(u, st, EV_SKIP, k=k, reason=sk[k])
                self._stat("SKIP_" + sk[k])
            elif k in pl:
                lv.status = L_PENDING
                lv.P = self._rt(pl[k])
                self._log(u, st, EV_PLACE_LIMIT, k=k, P=lv.P, SL=rSL, TP=rTP, O=st.O, X=st.X)
                intents.append(Intent("PLACE_LIMIT", st.id, d, k, P=lv.P, SL=rSL, TP=rTP))
                self._stat("PLACE_LIMIT")
        if not placed:
            self._done(st, u, "NO_LEVEL")
            return False
        st.SL, st.TP, st.tgt = rSL, rTP, self._rt(tgt)
        st.dec_O, st.dec_X = st.O, st.X
        st.phase = ORDERED
        st.decision_bar = u
        return True


# ============================================================================================== parity harness
def harness_run(bars: Sequence[Sequence[float]], params: BreakoutParams, sp: float, trade_from: int = 0,
                hold_bars: int = 120) -> list[dict]:
    """Spec section 7 parity harness: a simple bar-based executor around the detector; returns its records."""
    return harness_detector(bars, params, sp, trade_from=trade_from, hold_bars=hold_bars).events


def harness_detector(bars: Sequence[Sequence[float]], params: BreakoutParams, sp: float, trade_from: int = 0,
                     hold_bars: int = 120) -> BreakoutDetector:
    """``harness_run``, returning the detector (records in ``events``, diagnostic counters in ``stats``).

    On bar ``u``, before the detector: exits of positions filled on an earlier bar (long: ``l <= SL`` first, then
    ``h >= TP``, then ``u - fill_bar >= hold_bars``; short: ``h + sp >= SL``, ``l + sp <= TP``, time), then fills of
    levels decided on an earlier bar (long ``l + sp <= P``; short ``h >= P``), both in ``(id, k)`` order.
    """
    det = BreakoutDetector(params, trade_from=trade_from)
    pend: dict[tuple[int, int], dict] = {}   # (id, k) -> {"P", "SL", "TP", "dir", "bar"}
    pos: dict[tuple[int, int], dict] = {}    # (id, k) -> {"SL", "TP", "dir", "bar"}
    for u, bar in enumerate(bars):
        o, h, l, c = bar  # noqa: E741
        # exits of positions filled on an earlier bar (in (id, k) order)
        for key in sorted(pos):
            q = pos[key]
            if q["bar"] >= u:
                continue
            if q["dir"] > 0:
                out = l <= q["SL"] or h >= q["TP"] or u - q["bar"] >= hold_bars
            else:
                out = h + sp >= q["SL"] or l + sp <= q["TP"] or u - q["bar"] >= hold_bars
            if out:
                del pos[key]
                det.notify_closed(*key)
        # fills of levels decided on an earlier bar
        for key in sorted(pend):
            q = pend[key]
            if q["bar"] >= u:
                continue
            hit = (l + sp <= q["P"]) if q["dir"] > 0 else (h >= q["P"])
            if hit:
                del pend[key]
                pos[key] = {"SL": q["SL"], "TP": q["TP"], "dir": q["dir"], "bar": u}
                det.notify_filled(*key)
        env = Env(slot_free=not det.has_order_or_position(), session_entry_ok=True, session_cancel=False,
                  risk_ok=True, spread_ok=True, sp=sp)
        for it in det.on_bar_closed(u, o, h, l, c, env):
            key = (it.id, it.k)
            if it.type == "PLACE_LIMIT":
                pend[key] = {"P": it.P, "SL": it.SL, "TP": it.TP, "dir": it.dir, "bar": u}
            elif it.type == "CANCEL":
                pend.pop(key, None)
    return det
