"""BPR + FVG Expert Advisor: pure-Python reference of the trading logic, plus a bar-based execution simulator.

Licence and attribution
-----------------------
(c) LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]').
Licensed under CC BY-NC-SA 4.0: https://creativecommons.org/licenses/by-nc-sa/4.0/
The FVG / BPR zones used here come from ``qe/indicators/luxalgo_bpr.py``, a port (a derivative work) of the FVG /
BPR part of that Pine v5 script. This file builds on that port and is shared under the same licence, for
non-commercial research use only. It is not affiliated with or endorsed by LuxAlgo. The original source is kept
unmodified in ``research/indicators/luxalgo_ict_concepts.pine``; the changes made on purpose by the ports are listed
in ``research/indicators/LUXALGO_BPR_SPEC.md`` section 10.

What this module is
-------------------
The single source of truth is ``research/indicators/BPR_FVG_EA_SPEC.md`` ("spec" below). This module implements:

* ``SetupDetector``: spec sections 2-4. A pure state machine: closed bars plus an ``Env`` in, ``Intent`` objects
  out. It owns a ``LuxBprEngine`` in **Historical** mode (no look-ahead, LUXALGO_BPR_SPEC section 7) and logs one
  record per intent and per status change in ``events`` (spec section 9).
* ``harness_run``: the spec section 9 parity-harness environment (the MQL5 EA is compared against this).
* ``simulate``: the bar-based execution simulator of spec section 5 (fills, exits, R accounting, daily lockout).

Status: the trading rules are hypothesis **H-13** (``HYPOTHESIS``, untested; ``docs/research/hypotheses.md``).
Nothing here is evidence of an edge. Broker values (tick, contract size, commission) are ``UNVERIFIED`` defaults.

Interpretations of the spec made by this port (each one is also stated where it is coded):

1. Setup ids start at 1 and are given only to candidates that pass the ``source`` / ``direction`` filters
   (candidates created ``DONE`` at birth also get an id).
2. Checks at creation run in this order: ``BAD_GEOMETRY``, ``BROKEN_AT_CREATION`` (BPR only), range window
   ``s - range_bars >= 0``, ``NO_SWEEP`` (only with ``use_sweep``), MSS window ``s - mss_bars >= 0``, then
   ``CAPACITY``; a failed window check gives ``INSUFFICIENT_HISTORY``. The two window requirements are stated
   without condition in the spec, so they also apply when ``use_sweep`` / ``use_mss`` is false (only ``sweepOK``
   / the MSS itself are then treated as true); ``R`` and ``M`` are always computed. The sweep window
   ``[u - sweep_window, u]`` is clipped at bar 0 like the ``O`` window (only the range and MSS windows must exist).
   "Tracked" setups for the capacity are those in ``ARMED``, ``ORDERED`` or ``FILLED``.
3. An ``MSS`` record is logged when the MSS is found (at creation with ``n = u``, right after ``ARMED``), and also
   at creation when ``use_mss`` is false.
4. A detector cancellation of an ``ORDERED`` setup logs ``DONE(reason)`` and then ``CANCEL(reason)``; the
   ``ORDERED`` status itself is the ``PLACE_LIMIT`` / ``MARKET`` record. ``FILLED`` / ``CLOSED`` are not logged.
5. Step 3 treats every ``ORDERED`` setup as pending, including a ``MARKET`` order that has not filled (only in the
   harness, where orders never fill): 3c says "pending LIMIT only" while 3d says "pending only", so "pending" is
   wider than LIMIT. Break, expiry and session cancel therefore apply to it; runaway (3c) applies to ``LIMIT``
   orders only and uses ``env.sp`` as the spread.
6. ``session_entry_ok`` / ``session_cancel`` are ignored when ``use_session`` is false.
7. LIMIT/CONFIRM levels: marketability and the RR / cost checks use the raw (unrounded) levels; rounding to the tick
   (``MathRound(x / tick) * tick``, half away from zero) happens last, as in the spec text. ``TP1_TP2`` with TP2 not
   beyond TP1: ``TP2`` is set equal to ``TP1`` (the whole position then exits at TP1). ``TP1_ONLY`` still records the
   computed ``TP2``; the executor ignores it.
8. Warm-up: setups created on bars ``< trade_from`` become ``DONE(WARMUP)`` at the end of bar ``trade_from - 1``;
   step 5 does not run on warm-up bars.
9. ``StrategyParams.max_hold_min`` above 120 is rejected (``ValueError``) rather than silently capped.
10. Simulator: trade R uses the actual fill price (``P`` in the spec's R formula = the entry); ``R_unit`` uses the
    planned ``P`` of the intent. A market fill is followed by the full exit check on its own bar (the fill is at the
    open). Forced exits (time stop, rollover) are at the open of bars after the fill bar, with slippage. A position
    still open at the end of the data is closed at the last close (reason ``END``). The daily lockout is the EA's
    pre-trade check in R: an order may be decided only while ``-realised_R_today + 1 <= 5`` (1 % / 0.2 %). As the
    spec says, a stop exits at ``SL -/+ slippage`` even when the bar opens beyond the stop (gaps are not modelled,
    which flatters losses slightly). The break-even level is rounded to the tick.
11. ``Env.slot_free`` is evaluated before the bar is processed (the harness: no setup ``ORDERED`` / ``FILLED`` before
    ``on_bar_closed(u)``), so a slot freed by a cancel in step 3 of bar ``u`` is usable from bar ``u + 1``.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Hashable, Sequence

from qe.indicators.luxalgo_bpr import BprParams, LuxBprEngine, Zone

__all__ = [
    "StrategyParams",
    "Env",
    "Intent",
    "Setup",
    "SetupDetector",
    "harness_run",
    "SimResult",
    "simulate",
    "round_to_tick",
    "r_unit",
    "trade_r",
]

# ----------------------------------------------------------------------------------------------- names (spec s.1, s.9)
SOURCES = ("BPR", "FVG", "BOTH")
DIRECTIONS = ("BOTH", "LONG_ONLY", "SHORT_ONLY")
ENTRY_MODES = ("LIMIT", "CONFIRM")
TP_MODES = ("TP1_TP2", "TP1_ONLY", "TP2_ONLY")

SRC_BPR = "BPR"
SRC_FVG = "FVG"

ARMED = "ARMED"
ORDERED = "ORDERED"
FILLED = "FILLED"
CLOSED = "CLOSED"
DONE = "DONE"
STATUSES = (ARMED, ORDERED, FILLED, CLOSED, DONE)

BAD_GEOMETRY = "BAD_GEOMETRY"
BROKEN_AT_CREATION = "BROKEN_AT_CREATION"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
NO_SWEEP = "NO_SWEEP"
CAPACITY = "CAPACITY"
WARMUP = "WARMUP"
BROKEN = "BROKEN"
EXPIRED = "EXPIRED"
RUNAWAY = "RUNAWAY"
SESSION_END = "SESSION_END"
SIZE_BELOW_MIN = "SIZE_BELOW_MIN"
ORDER_FAILED = "ORDER_FAILED"
RUNAWAY_SAME_BAR = "RUNAWAY_SAME_BAR"  # Python simulator only
REASONS = (
    BAD_GEOMETRY,
    BROKEN_AT_CREATION,
    INSUFFICIENT_HISTORY,
    NO_SWEEP,
    CAPACITY,
    WARMUP,
    BROKEN,
    EXPIRED,
    RUNAWAY,
    SESSION_END,
    SIZE_BELOW_MIN,
    ORDER_FAILED,
    RUNAWAY_SAME_BAR,
)

EV_ARMED = "ARMED"
EV_DONE = "DONE"
EV_MSS = "MSS"
EV_PLACE_LIMIT = "PLACE_LIMIT"
EV_MARKET = "MARKET"
EV_CANCEL = "CANCEL"
EVENTS = (EV_ARMED, EV_DONE, EV_MSS, EV_PLACE_LIMIT, EV_MARKET, EV_CANCEL)

#: CLAUDE.md hard rules (spec "Hard rules"): every position closed <= 120 minutes after entry; 0.20 % per trade and
#: 1.00 % planned daily loss, so the daily budget is 1.00 / 0.20 = 5 R.
MAX_HOLD_CAP_MIN = 120
DAILY_LOSS_R = 5.0

#: Engine constants of spec section 2 (LUXALGO_BPR_SPEC sections 1 and 4).
ENGINE_PERC_BODY = 0.36
ENGINE_BX_BACK = 10
ENGINE_EXT_BARS = 8


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


@dataclass(frozen=True)
class StrategyParams:
    """Setup / execution inputs (spec section 1, Python column; defaults fixed before any data was seen).

    ``tick_size`` and ``contract_size`` describe the symbol (defaults: XAUUSD-like 0.01 / 100, ``UNVERIFIED``).
    ``comm_price`` = round-trip commission per lot / value of a 1.0 price move per lot, for USD-quoted symbols.
    ``capacity``, ``length`` and ``vis_boxes`` are the tracked-setup limit and the engine's ``len`` / ``visBxs``.
    Any non-default value is a new trial and must be registered in ``results/trial_registry.jsonl``.
    """

    source: str = "BPR"
    direction: str = "BOTH"
    entry_mode: str = "LIMIT"
    entry_offset_ticks: int = 5
    use_sweep: bool = True
    sweep_window: int = 30
    range_bars: int = 30
    use_mss: bool = True
    mss_bars: int = 20
    rally_bars: int = 10
    expiry_bars: int = 60
    stop_zone_mult: float = 1.2
    min_rr: float = 1.0
    max_cost_r: float = 0.15
    tp_mode: str = "TP1_TP2"
    tp1_fraction: float = 0.5
    break_even: bool = True
    max_hold_min: int = 120
    use_session: bool = True
    slippage_ticks: float = 1
    commission_per_lot_side: float = 3.5
    tick_size: float = 0.01
    digits: int = 2
    contract_size: float = 100.0
    capacity: int = 128
    length: int = 5
    vis_boxes: int = 2

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}, got {self.source!r}")
        if self.direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {DIRECTIONS}, got {self.direction!r}")
        if self.entry_mode not in ENTRY_MODES:
            raise ValueError(f"entry_mode must be one of {ENTRY_MODES}, got {self.entry_mode!r}")
        if self.tp_mode not in TP_MODES:
            raise ValueError(f"tp_mode must be one of {TP_MODES}, got {self.tp_mode!r}")
        for name in ("use_sweep", "use_mss", "break_even", "use_session"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a bool")
        for name, lo in (
            ("entry_offset_ticks", 0),
            ("sweep_window", 1),
            ("range_bars", 1),
            ("mss_bars", 1),
            ("rally_bars", 0),
            ("expiry_bars", 1),
            ("max_hold_min", 1),
            ("capacity", 1),
        ):
            v = getattr(self, name)
            if not _is_int(v) or v < lo:
                raise ValueError(f"{name} must be an int >= {lo}, got {v!r}")
        if self.max_hold_min > MAX_HOLD_CAP_MIN:
            # Interpretation 9: the EA caps the input at 120; the reference refuses it so a trial is never mislabelled.
            raise ValueError(f"max_hold_min is capped at {MAX_HOLD_CAP_MIN} (CLAUDE.md), got {self.max_hold_min}")
        for name in ("stop_zone_mult", "max_cost_r", "tick_size", "contract_size"):
            v = getattr(self, name)
            if not _is_num(v) or v <= 0:
                raise ValueError(f"{name} must be a number > 0, got {v!r}")
        for name in ("min_rr", "slippage_ticks", "commission_per_lot_side"):
            v = getattr(self, name)
            if not _is_num(v) or v < 0:
                raise ValueError(f"{name} must be a number >= 0, got {v!r}")
        if not _is_num(self.tp1_fraction) or not 0.0 < self.tp1_fraction < 1.0:
            raise ValueError(f"tp1_fraction must be in (0, 1), got {self.tp1_fraction!r}")
        if not _is_int(self.digits) or not 0 <= self.digits <= 10:
            raise ValueError(f"digits must be an int in 0..10, got {self.digits!r}")
        if not _is_int(self.length) or not 3 <= self.length <= 10:
            raise ValueError(f"length must be an int in 3..10, got {self.length!r}")
        if not _is_int(self.vis_boxes) or not 1 <= self.vis_boxes <= 20:
            raise ValueError(f"vis_boxes must be an int in 1..20, got {self.vis_boxes!r}")

    @property
    def comm_price(self) -> float:
        """Round-trip commission as a price distance: ``2 * commission_per_lot_side / contract_size``."""
        return 2.0 * self.commission_per_lot_side / self.contract_size

    def engine_params(self) -> BprParams:
        """The LuxAlgo engine of spec section 2: Historical mode, FVG gaps, BPR always computed."""
        return BprParams(
            mode="Historical",
            length=self.length,
            perc_body=ENGINE_PERC_BODY,
            show_fvg=True,
            bpr=True,
            fvg_mode="FVG",
            vis_boxes=self.vis_boxes,
            bx_back=ENGINE_BX_BACK,
            ext_bars=ENGINE_EXT_BARS,
        )


@dataclass
class Env:
    """Environment of one closed bar ``u`` (spec section 4, "The detector is pure").

    ``slot_free``: no pending order or position of this EA; ``session_entry_ok``: an entry is allowed at the next
    bar's open; ``session_cancel``: the next bar's open is at or after the last entry time; ``risk_ok``: no lockout and
    the trade limit not reached; ``spread_ok``: spread filter passed; ``sp``: the spread at the decision moment (the
    first tick of bar ``u + 1``; Python: the modelled spread of bar ``u + 1``).
    """

    slot_free: bool
    session_entry_ok: bool
    session_cancel: bool
    risk_ok: bool
    spread_ok: bool
    sp: float


@dataclass(frozen=True)
class Intent:
    """An order intent (spec section 4): ``PLACE_LIMIT``, ``MARKET`` or ``CANCEL(id, reason)``."""

    type: str
    id: int
    dir: int
    src: str
    P: float | None = None
    SL: float | None = None
    TP1: float | None = None
    TP2: float | None = None
    reason: str | None = None


@dataclass
class Setup:
    """One tracked setup (spec sections 3-4). Prices are copied at creation (``B``, ``T``, ``h``, ``Lo_or_Hi`` can
    change only through the FVG consecutive-update refresh while ``ARMED``).

    ``Lo_or_Hi`` is ``Lo`` for longs and ``Hi`` for shorts; ``break_level`` is the price of the break rule (long:
    broken when ``l[k] < break_level``; short: when ``h[k] > break_level``). ``zone_top`` / ``zone_bottom`` are the
    LuxAlgo box (for a BPR the box top can lie above ``T``, QUIRK 4). ``sweep_extreme`` = ``legLow`` / ``legHigh``,
    ``sweep_ref`` = ``R`` of spec section 3.2. ``end_bar`` is the bar of the last status change to ``DONE`` /
    ``CLOSED``. ``zone_seq`` (FVG setups) is the number of same-side FVGs created up to this one.
    """

    id: int
    src: str
    dir: int
    created: int
    status: str = ARMED
    reason: str | None = None
    B: float = math.nan
    T: float = math.nan
    h: float = math.nan
    Lo_or_Hi: float = math.nan
    break_level: float = math.nan
    zone_top: float = math.nan
    zone_bottom: float = math.nan
    s: int | None = None
    sweep_extreme: float | None = None
    sweep_ref: float | None = None
    M: float | None = None
    mss_bar: int | None = None
    X: float | None = None
    O: float | None = None  # noqa: E741 (spec name)
    order: str | None = None
    decision_bar: int | None = None
    P: float | None = None
    SL: float | None = None
    TP1: float | None = None
    TP2: float | None = None
    end_bar: int | None = None
    zone_seq: int | None = None


def round_to_tick(x: float, tick: float, digits: int = 10) -> float:
    """Round a price like the EA: ``NormalizeDouble(MathRound(x / tick) * tick, digits)``.

    ``MathRound`` rounds half away from zero on the quotient; ``NormalizeDouble`` is ``round(v * 10^d) / 10^d``
    (half away from zero), so ``201734 * 0.01`` (= 2017.3400000000001 in binary) becomes exactly 2017.34, the same
    double as a 2017.34 bar price.
    """
    q = x / tick
    k = math.floor(q + 0.5) if q >= 0 else -math.floor(-q + 0.5)
    v = k * tick
    p = 10.0 ** digits
    w = v * p
    r = math.floor(w + 0.5) if w >= 0 else -math.floor(-w + 0.5)
    return r / p


def r_unit(P: float, SL: float, params: StrategyParams) -> float:
    """Planned risk per unit, costs included (spec section 5): ``|P - SL| + slippage_ticks * tick + comm_price``."""
    return abs(P - SL) + params.slippage_ticks * params.tick_size + params.comm_price


def trade_r(direction: int, entry: float, parts: Sequence[tuple[float, float, str]], unit: float,
            comm_price: float) -> float:
    """Trade result in R (spec section 5): ``sum(fraction * (exit - entry) * dir) / R_unit - comm_price / R_unit``."""
    gross = sum(f * (x - entry) * direction for f, x, _ in parts)
    return gross / unit - comm_price / unit


# ============================================================================================== detector (s.2-s.4)
class SetupDetector:
    """The EA's decision logic (spec sections 2-4), driven by closed bars plus an ``Env``.

    ``on_bar_closed(u, o, h, l, c, env)`` must be called for ``u = 0, 1, 2, ...`` (bid prices of the closed bar).
    It runs the engine on bar ``u`` and then spec section 4 steps 2-5, and returns the intents of that bar.
    The executor reports back with ``notify_filled``, ``notify_cancelled`` and ``notify_closed``.

    ``events`` holds the spec section 9 records ``{"n", "id", "ev", "dir", "src", "reason", "P", "SL", "TP1",
    "TP2"}`` (absent values ``None``). ``setups`` holds every setup ever created, in creation order.
    """

    def __init__(self, params: StrategyParams = StrategyParams(), trade_from: int = 0) -> None:
        if not _is_int(trade_from) or trade_from < 0:
            raise ValueError(f"trade_from must be an int >= 0, got {trade_from!r}")
        self.params = params
        self.trade_from = trade_from
        self.engine = LuxBprEngine(params.engine_params())
        self.events: list[dict] = []
        self.setups: list[Setup] = []
        self.last_bar: int | None = None
        self._active: list[Setup] = []  # ARMED / ORDERED / FILLED, in creation order
        self._by_id: dict[int, Setup] = {}
        self._next_id = 1  # interpretation 1
        self._fvg_seq = {1: 0, -1: 0}
        self._last_fvg_setup: dict[int, Setup | None] = {1: None, -1: None}
        # bar storage (absolute index i is stored at i - _base); only the window the rules need is kept
        self._keep = params.sweep_window + max(params.range_bars, params.mss_bars) + params.rally_bars + 2
        self._base = 0
        self._o: list[float] = []
        self._h: list[float] = []
        self._l: list[float] = []
        self._c: list[float] = []

    # ------------------------------------------------------------------------------------------- public helpers
    def has_order_or_position(self) -> bool:
        """True while a setup is ``ORDERED`` (pending or decided) or ``FILLED``."""
        return any(st.status in (ORDERED, FILLED) for st in self._active)

    def setup(self, sid: int) -> Setup:
        return self._by_id[sid]

    def notify_filled(self, sid: int) -> None:
        """Executor: the order of setup ``sid`` was filled (``ORDERED`` -> ``FILLED``)."""
        st = self._by_id[sid]
        if st.status != ORDERED:
            raise ValueError(f"setup {sid} is {st.status}, cannot be filled")
        st.status = FILLED

    def notify_cancelled(self, sid: int, reason: str, n: int | None = None) -> None:
        """Executor: the order of setup ``sid`` was not placed or was cancelled (``ORDERED`` -> ``DONE(reason)``).

        A setup the detector already finished (its own ``CANCEL`` intent) is left unchanged. ``n`` is the bar index
        logged with the ``DONE`` record (default: the last processed bar).
        """
        if reason not in REASONS:
            raise ValueError(f"unknown reason {reason!r}")
        st = self._by_id[sid]
        if st.status == DONE:
            return
        if st.status != ORDERED:
            raise ValueError(f"setup {sid} is {st.status}, cannot be cancelled")
        self._finish(st, reason, self.last_bar if n is None else n, None)

    def notify_closed(self, sid: int, n: int | None = None) -> None:
        """Executor: the position of setup ``sid`` was closed (``FILLED`` -> ``CLOSED``)."""
        st = self._by_id[sid]
        if st.status != FILLED:
            raise ValueError(f"setup {sid} is {st.status}, cannot be closed")
        st.status = CLOSED
        st.end_bar = self.last_bar if n is None else n
        self._active.remove(st)

    # ------------------------------------------------------------------------------------------- bar storage
    def _push(self, o: float, h: float, l: float, c: float) -> None:  # noqa: E741
        self._o.append(o)
        self._h.append(h)
        self._l.append(l)
        self._c.append(c)
        if len(self._h) > 2 * self._keep + 64:
            drop = len(self._h) - self._keep
            for arr in (self._o, self._h, self._l, self._c):
                del arr[:drop]
            self._base += drop

    def _hs(self, a: int, b: int) -> list[float]:
        """Highs of bars ``a..b`` inclusive."""
        return self._h[a - self._base: b - self._base + 1]

    def _ls(self, a: int, b: int) -> list[float]:
        return self._l[a - self._base: b - self._base + 1]

    def _cs(self, a: int, b: int) -> list[float]:
        return self._c[a - self._base: b - self._base + 1]

    # ------------------------------------------------------------------------------------------- logging
    def _log(self, n: int, st: Setup, ev: str, reason: str | None = None, P: float | None = None,
             SL: float | None = None, TP1: float | None = None, TP2: float | None = None) -> None:
        self.events.append(
            {"n": n, "id": st.id, "ev": ev, "dir": st.dir, "src": st.src, "reason": reason,
             "P": P, "SL": SL, "TP1": TP1, "TP2": TP2}
        )

    def _finish(self, st: Setup, reason: str, n: int, intents: list[Intent] | None) -> None:
        """``ARMED`` / ``ORDERED`` -> ``DONE(reason)``; a detector-side cancel of an order also emits ``CANCEL``
        (interpretation 4: ``DONE`` is logged first, then ``CANCEL``)."""
        was_ordered = st.status == ORDERED
        st.status = DONE
        st.reason = reason
        st.end_bar = n
        self._active.remove(st)
        self._log(n, st, EV_DONE, reason=reason)
        if was_ordered and intents is not None:
            intents.append(Intent(EV_CANCEL, st.id, st.dir, st.src, reason=reason))
            self._log(n, st, EV_CANCEL, reason=reason)

    # ------------------------------------------------------------------------------------------- one bar
    def on_bar_closed(self, u: int, o: float, h: float, l: float, c: float, env: Env) -> list[Intent]:  # noqa: E741
        """Process closed bar ``u`` (spec section 4, steps 1-5, in this order) and return its intents."""
        expected = 0 if self.last_bar is None else self.last_bar + 1
        if u != expected:
            raise ValueError(f"bars must be consecutive from 0: expected {expected}, got {u}")
        self._push(o, h, l, c)
        # step 1: engine (Historical mode). Only the current bar's events are read; the list is then emptied so a
        # long run does not keep every event in memory.
        self.engine.process_bar(u, o, h, l, c)
        evs = {(kind, what) for (n, kind, what) in self.engine.events if n == u}
        self.engine.events.clear()
        self.last_bar = u
        intents: list[Intent] = []
        # step 2: FVG consecutive-update refresh
        if ("FVG_UP", "update") in evs:
            self._refresh(1)
        if ("FVG_DN", "update") in evs:
            self._refresh(-1)
        # step 3: existing setups
        self._manage(u, h, l, c, env, intents)
        # step 4: new candidates
        self._create(u, evs)
        # step 5: entry decisions (never on warm-up bars)
        if u >= self.trade_from:
            self._decide(u, o, h, l, c, env, intents)
        # interpretation 8: warm-up ends after the last warm-up bar
        if u == self.trade_from - 1:
            for st in list(self._active):
                self._finish(st, WARMUP, u, intents)
        return intents

    # ------------------------------------------------------------------------------------------- step 2
    def _refresh(self, d: int) -> None:
        """Spec section 4 step 2: copy ``B``, ``T`` and ``Lo`` / ``Hi`` from ``FVG_UP[0]`` (``FVG_DN[0]``) into the
        most recent FVG setup of that direction, if it is ``ARMED`` and no newer same-side FVG was created since."""
        st = self._last_fvg_setup[d]
        if st is None or st.status != ARMED or st.zone_seq != self._fvg_seq[d]:
            return
        z = (self.engine.fvg_up if d > 0 else self.engine.fvg_dn)[0].box
        if z is None:
            return
        st.zone_top, st.zone_bottom = z.top, z.bottom
        st.B, st.T = z.bottom, z.top
        st.h = st.T - st.B
        st.Lo_or_Hi = st.B if d > 0 else st.T
        st.break_level = st.B if d > 0 else st.T

    # ------------------------------------------------------------------------------------------- step 3
    def _manage(self, u: int, h: float, l: float, c: float, env: Env, intents: list[Intent]) -> None:  # noqa: E741
        p = self.params
        for st in list(self._active):
            if st.status not in (ARMED, ORDERED):
                continue
            d = st.dir
            # a. break (spec section 3.1)
            if (l < st.break_level) if d > 0 else (h > st.break_level):
                self._finish(st, BROKEN, u, intents)
                continue
            # b. expiry
            if u - st.created > p.expiry_bars:
                self._finish(st, EXPIRED, u, intents)
                continue
            if st.status == ORDERED:
                # c. runaway, pending LIMIT only (the short TP1 is an ask level; interpretation 5: spread = env.sp)
                if st.order == "LIMIT":
                    assert st.TP1 is not None
                    if (h >= st.TP1) if d > 0 else (l <= st.TP1 - env.sp):
                        self._finish(st, RUNAWAY, u, intents)
                        continue
                # d. session cancel, pending only
                if p.use_session and env.session_cancel:
                    self._finish(st, SESSION_END, u, intents)
                continue
            # e. ARMED: extreme X (spec section 3.4), then the MSS (spec section 3.3)
            assert st.X is not None
            st.X = max(st.X, h) if d > 0 else min(st.X, l)
            if st.mss_bar is None:
                assert st.M is not None
                if (c > st.M) if d > 0 else (c < st.M):
                    st.mss_bar = u
                    self._log(u, st, EV_MSS)

    # ------------------------------------------------------------------------------------------- step 4
    def _wanted(self, src: str, d: int) -> bool:
        p = self.params
        if p.source != "BOTH" and p.source != src:
            return False
        if p.direction == "LONG_ONLY" and d != 1:
            return False
        if p.direction == "SHORT_ONLY" and d != -1:
            return False
        return True

    def _bpr_candidate(self, z: Zone) -> dict:
        """Spec section 3.1, BPR rows: direction from ``pos``; ``T`` = the true overlap top ``min(up.top, dn.top)``."""
        if z.pos not in (1, -1):  # QUIRK 5: pos = 0 cannot occur
            raise RuntimeError(f"BPR with pos {z.pos!r}")
        up = self.engine.fvg_up[0].box
        dn = self.engine.fvg_dn[0].box
        assert z.box is not None and up is not None and dn is not None
        d = z.pos
        return {
            "src": SRC_BPR,
            "dir": d,
            "B": z.box.bottom,
            "T": min(up.top, dn.top),
            "lohi": min(up.bottom, dn.bottom) if d > 0 else max(up.top, dn.top),
            "brk": z.box.bottom if d > 0 else z.box.top,
            "top": z.box.top,
            "bottom": z.box.bottom,
            "active": z.active,
            "seq": None,
        }

    def _fvg_candidate(self, z: Zone, d: int) -> dict:
        """Spec section 3.1, FVG rows: bullish ``Lo = B``, break ``l < B``; bearish ``Hi = T``, break ``h > T``."""
        assert z.box is not None
        B, T = z.box.bottom, z.box.top
        return {
            "src": SRC_FVG,
            "dir": d,
            "B": B,
            "T": T,
            "lohi": B if d > 0 else T,
            "brk": B if d > 0 else T,
            "top": T,
            "bottom": B,
            "active": z.active,
            "seq": self._fvg_seq[d],
        }

    def _create(self, u: int, evs: set[tuple[str, str]]) -> None:
        eng = self.engine
        cands: list[dict] = []
        # candidate order within one bar (spec section 3.1): BPR UP array, BPR DN array, bullish FVG, bearish FVG
        if ("BPR_UP", "new") in evs:
            cands.append(self._bpr_candidate(eng.bpr_up[0]))
        if ("BPR_DN", "new") in evs:
            cands.append(self._bpr_candidate(eng.bpr_dn[0]))
        if ("FVG_UP", "new") in evs:
            self._fvg_seq[1] += 1
            cands.append(self._fvg_candidate(eng.fvg_up[0], 1))
        if ("FVG_DN", "new") in evs:
            self._fvg_seq[-1] += 1
            cands.append(self._fvg_candidate(eng.fvg_dn[0], -1))
        for cd in cands:
            if not self._wanted(cd["src"], cd["dir"]):
                continue  # filtered candidates are never logged and get no id
            st = Setup(
                id=self._next_id,
                src=cd["src"],
                dir=cd["dir"],
                created=u,
                B=cd["B"],
                T=cd["T"],
                h=cd["T"] - cd["B"],
                Lo_or_Hi=cd["lohi"],
                break_level=cd["brk"],
                zone_top=cd["top"],
                zone_bottom=cd["bottom"],
                zone_seq=cd["seq"],
            )
            self._next_id += 1
            self.setups.append(st)
            self._by_id[st.id] = st
            if st.src == SRC_FVG:
                self._last_fvg_setup[st.dir] = st
            reason = self._qualify(st, u, cd["active"])
            if reason is None and len(self._active) >= self.params.capacity:
                reason = CAPACITY
            if reason is not None:
                st.status = DONE
                st.reason = reason
                st.end_bar = u
                self._log(u, st, EV_DONE, reason=reason)
                continue
            self._active.append(st)
            self._log(u, st, EV_ARMED)
            if st.mss_bar is not None:
                self._log(u, st, EV_MSS)

    def _qualify(self, st: Setup, u: int, zone_active: bool) -> str | None:
        """Creation checks (interpretation 2) and the sweep / MSS / extremes of spec sections 3.2-3.4."""
        p = self.params
        d = st.dir
        if st.h <= 0:
            return BAD_GEOMETRY
        if st.src == SRC_BPR and not zone_active:
            return BROKEN_AT_CREATION
        a = max(0, u - p.sweep_window)  # interpretation 2: clipped at bar 0
        # s: the lowest low (long) / highest high (short) of [u - sweep_window, u]; ties -> the LATEST bar
        if d > 0:
            vals = self._ls(a, u)
            best = math.inf
            s = a
            for i, v in enumerate(vals):
                if v <= best:
                    best, s = v, a + i
        else:
            vals = self._hs(a, u)
            best = -math.inf
            s = a
            for i, v in enumerate(vals):
                if v >= best:
                    best, s = v, a + i
        st.s = s
        st.sweep_extreme = best
        # extremes for the targets (spec section 3.4): X over [s, u]; O over [u - rally_bars, u] clipped at 0
        ra = max(0, u - p.rally_bars)
        if d > 0:
            st.X = max(self._hs(s, u))
            st.O = min(self._ls(ra, u))
        else:
            st.X = min(self._ls(s, u))
            st.O = max(self._hs(ra, u))
        # the range window must exist (also without the sweep filter, interpretation 2)
        if s - p.range_bars < 0:
            return INSUFFICIENT_HISTORY
        if d > 0:
            st.sweep_ref = min(self._ls(s - p.range_bars, s - 1))
            ok = best < st.sweep_ref
        else:
            st.sweep_ref = max(self._hs(s - p.range_bars, s - 1))
            ok = best > st.sweep_ref
        if p.use_sweep and not ok:
            return NO_SWEEP
        # the MSS window must exist (also without the MSS filter, interpretation 2)
        if s - p.mss_bars < 0:
            return INSUFFICIENT_HISTORY
        if d > 0:
            st.M = max(self._hs(s - p.mss_bars, s - 1))
        else:
            st.M = min(self._ls(s - p.mss_bars, s - 1))
        if p.use_mss:
            # at creation, bars (s, u] are checked; the first close beyond M is the MSS bar
            for i, cv in enumerate(self._cs(s + 1, u)):
                if (cv > st.M) if d > 0 else (cv < st.M):
                    st.mss_bar = s + 1 + i
                    break
        else:
            st.mss_bar = u  # treated as having happened at creation (interpretation 3)
        return None

    # ------------------------------------------------------------------------------------------- step 5
    def _decide(self, u: int, o: float, h: float, l: float, c: float, env: Env,  # noqa: E741
                intents: list[Intent]) -> None:
        p = self.params
        session_ok = (not p.use_session) or env.session_entry_ok  # interpretation 6
        if not (env.slot_free and session_ok and env.risk_ok and env.spread_ok):
            return
        for st in self._active:
            if st.status != ARMED or st.mss_bar is None:
                continue
            lv = self._levels(st, o, h, l, c, env.sp)
            if lv is None:
                continue  # stays ARMED and is retried on the next bar
            P, SL, TP1, TP2 = lv
            limit = p.entry_mode == "LIMIT"
            st.status = ORDERED
            st.order = "LIMIT" if limit else "MARKET"
            st.decision_bar = u
            st.P, st.SL, st.TP1, st.TP2 = P, SL, TP1, TP2  # X is frozen from here on (ORDERED skips step 3e)
            ev = EV_PLACE_LIMIT if limit else EV_MARKET
            intents.append(Intent(ev, st.id, st.dir, st.src, P, SL, TP1, TP2))
            self._log(u, st, ev, P=P, SL=SL, TP1=TP1, TP2=TP2)
            return  # at most one order per bar

    def _levels(self, st: Setup, o: float, h: float, l: float, c: float,  # noqa: E741
                sp: float) -> tuple[float, float, float, float] | None:
        """Entry levels of spec section 4 step 5, or ``None`` when the setup must wait (interpretation 7).

        Expression order (kept identical in the MQL5 port so the doubles match): long ``P = (B + δ·tk) + sp``,
        decision ask ``c + sp``; short ``P = T - δ·tk``.
        """
        p = self.params
        d = st.dir
        tk = p.tick_size
        B, T, hz = st.B, st.T, st.h
        X, O = st.X, st.O  # noqa: E741
        assert X is not None and O is not None
        if p.entry_mode == "LIMIT":
            if d > 0:
                P = B + p.entry_offset_ticks * tk + sp
                if c + sp <= P:  # marketability: the ask is already at or through P
                    return None
            else:
                P = T - p.entry_offset_ticks * tk
                if c >= P:  # the bid is already at or through P
                    return None
        else:  # CONFIRM: rejection candle on this bar (the zone is not broken: step 3a ran first)
            if d > 0:
                if not (l <= B + hz / 4 and c >= B + hz / 2 and c > o):
                    return None
                P = c + sp
            else:
                if not (h >= T - hz / 4 and c <= T - hz / 2 and c < o):
                    return None
                P = c
        if d > 0:
            SL = min(B - p.stop_zone_mult * hz, st.Lo_or_Hi - 2 * sp)
            TP1 = X - 2 * sp
            TP2 = P + (X - O)
        else:
            SL = max(T + p.stop_zone_mult * hz, st.Lo_or_Hi + 2 * sp) + sp
            TP1 = X + 2 * sp
            TP2 = P - (O - X)
        risk = abs(P - SL)
        if risk <= 0:
            return None
        if (TP1 - P) * d <= 0:  # TP1 must be on the profit side
            return None
        if abs(TP1 - P) / risk < p.min_rr:
            return None
        cost_r = (sp + p.comm_price + 2 * p.slippage_ticks * tk) / risk
        if cost_r > p.max_cost_r:
            return None
        if p.tp_mode == "TP1_TP2" and (TP2 - TP1) * d <= 0:
            TP2 = TP1  # TP2 not beyond TP1: the trade uses TP1 only (interpretation 7)
        dg = p.digits
        return (round_to_tick(P, tk, dg), round_to_tick(SL, tk, dg), round_to_tick(TP1, tk, dg),
                round_to_tick(TP2, tk, dg))


# ============================================================================================== parity harness (s.9)
def harness_run(bars: Sequence[Sequence[float]], params: StrategyParams, sp: float, trade_from: int = 0) -> list[dict]:
    """Run the detector under the spec section 9 harness environment and return its event records.

    Session always open, risk always OK, spread OK and constant ``sp``, ``slot_free`` = no setup ``ORDERED`` or
    ``FILLED``, and orders never fill. ``bars`` are ``(open, high, low, close)`` with indices ``0..``.
    ``trade_from`` is the first bar that may trade (earlier bars are warm-up), as in the EA.
    """
    det = SetupDetector(params, trade_from=trade_from)
    for u, bar in enumerate(bars):
        env = Env(
            slot_free=not det.has_order_or_position(),
            session_entry_ok=True,
            session_cancel=False,
            risk_ok=True,
            spread_ok=True,
            sp=sp,
        )
        det.on_bar_closed(u, bar[0], bar[1], bar[2], bar[3], env)
    return det.events


# ============================================================================================== simulator (s.5)
@dataclass
class SimResult:
    """``trades``: one dict per closed trade; ``setups``: every setup as a dict; ``counters``: run statistics."""

    trades: list[dict]
    setups: list[dict]
    counters: dict


def simulate(
    bid_ohlc: Sequence[Sequence[float]],
    spreads: Sequence[float],
    times: Sequence[int],
    entry_ok: Sequence[bool],
    cancel_now: Sequence[bool],
    flat_now: Sequence[bool],
    fx_day: Sequence[Hashable],
    params: StrategyParams,
    trade_from: int = 0,
    *,
    detector: Any = None,
) -> SimResult:
    """Bar-based execution simulator of spec section 5 (``ask = bid + spreads[k]`` on bar ``k``).

    Per bar ``k``: first the fills / exits of bar ``k``, then ``detector.on_bar_closed(k, ...)`` with
    ``Env(slot_free = no order or position, session_entry_ok = entry_ok[k+1], session_cancel = cancel_now[k+1],
    risk_ok = daily budget, spread_ok = True, sp = spreads[k+1])``. On the last bar nothing can be decided.

    * ``times``: epoch seconds of each bar's open (time stop ``fill_time + max_hold_min``; ``fill_time`` is the open
      of the fill bar, so the hold is never longer than ``max_hold_min``).
    * ``entry_ok[k]``: an entry is allowed at bar ``k``'s open; ``cancel_now[k]``: bar ``k``'s open is at or after
      the last entry time (14:45 New York); ``flat_now[k]``: forced exit at bar ``k``'s open (16:44 New York
      rollover); ``fx_day[k]``: the FX day of bar ``k`` (for the daily lockout).
    * ``detector``: optional replacement for the ``SetupDetector`` (tests drive scripted intents through it).

    Trade dicts: ``id, src, dir, decision_bar, fill_bar, fill_price, P, SL, TP1, TP2, exit_bar, exit_reason, R,
    R_unit, parts`` with ``parts`` = ``[(fraction, exit_price, reason), ...]`` and exit reasons ``SL`` (initial
    stop), ``BE`` (break-even stop), ``TP1``, ``TP2``, ``TIME``, ``FLAT``, ``END`` (end of data).
    """
    n = len(bid_ohlc)
    for name, seq in (("spreads", spreads), ("times", times), ("entry_ok", entry_ok), ("cancel_now", cancel_now),
                      ("flat_now", flat_now), ("fx_day", fx_day)):
        if len(seq) != n:
            raise ValueError(f"{name} has {len(seq)} values, expected {n}")
    p = params
    det = detector if detector is not None else SetupDetector(p, trade_from)
    tk = p.tick_size
    slip = p.slippage_ticks * tk
    comm = p.comm_price
    hold_s = p.max_hold_min * 60

    trades: list[dict] = []
    day_r: dict[Hashable, float] = {}
    locked_days: set[Hashable] = set()
    counters: dict[str, Any] = {
        "bars": n,
        "orders_limit": 0,
        "orders_market": 0,
        "cancels": 0,
        "fills": 0,
        "runaway_same_bar": 0,
        "trades": 0,
        "pending_at_end": 0,
    }
    pending: Intent | None = None
    pending_bar = -1
    pos: dict | None = None

    def open_position(it: Intent, k: int, fill: float) -> dict:
        if it.TP2 is None or p.tp_mode == "TP1_ONLY" or (p.tp_mode == "TP1_TP2" and it.TP2 == it.TP1):
            mode = "TP1"
        elif p.tp_mode == "TP2_ONLY":
            mode = "TP2"
        else:
            mode = "SPLIT"
        assert it.P is not None and it.SL is not None
        return {
            "it": it,
            "decision_bar": pending_bar,
            "fill_bar": k,
            "fill": fill,
            "fill_time": times[k],
            "sl": it.SL,
            "be_active": False,
            "be_next": False,
            "tp1_done": False,
            "remaining": 1.0,
            "parts": [],
            "mode": mode,
            "unit": r_unit(it.P, it.SL, p),
        }

    def close_position(k: int) -> None:
        nonlocal pos
        assert pos is not None
        it: Intent = pos["it"]
        R = trade_r(it.dir, pos["fill"], pos["parts"], pos["unit"], comm)
        trades.append({
            "id": it.id,
            "src": it.src,
            "dir": it.dir,
            "decision_bar": pos["decision_bar"],
            "fill_bar": pos["fill_bar"],
            "fill_price": pos["fill"],
            "P": it.P,
            "SL": it.SL,
            "TP1": it.TP1,
            "TP2": it.TP2,
            "exit_bar": k,
            "exit_reason": pos["parts"][-1][2],
            "R": R,
            "R_unit": pos["unit"],
            "parts": list(pos["parts"]),
        })
        day_r[fx_day[k]] = day_r.get(fx_day[k], 0.0) + R
        counters["trades"] += 1
        det.notify_closed(it.id, n=k)
        pos = None

    def exit_rest(k: int, price: float, reason: str) -> None:
        assert pos is not None
        pos["parts"].append((pos["remaining"], price, reason))
        pos["remaining"] = 0.0
        close_position(k)

    def bar_exits(k: int, h: float, l: float, sp: float) -> None:  # noqa: E741
        """Intrabar exits in the spec order: stop first, then TP1 partial, then TP2."""
        assert pos is not None
        it: Intent = pos["it"]
        d = it.dir
        # 1. stop (bid for longs, ask for shorts); stop first when both are touched
        if (l <= pos["sl"]) if d > 0 else (h + sp >= pos["sl"]):
            exit_rest(k, pos["sl"] - slip if d > 0 else pos["sl"] + slip, "BE" if pos["be_active"] else "SL")
            return

        def reached(level: float) -> bool:
            return (h >= level) if d > 0 else (l + sp <= level)

        assert it.TP1 is not None
        if pos["mode"] == "SPLIT":
            assert it.TP2 is not None
            if not pos["tp1_done"] and reached(it.TP1):
                pos["parts"].append((p.tp1_fraction, it.TP1, "TP1"))
                pos["remaining"] = 1.0 - p.tp1_fraction
                pos["tp1_done"] = True
                pos["be_next"] = p.break_even
            if pos["tp1_done"] and reached(it.TP2):
                exit_rest(k, it.TP2, "TP2")
                return
        elif pos["mode"] == "TP1":
            if reached(it.TP1):
                exit_rest(k, it.TP1, "TP1")
                return
        else:
            assert it.TP2 is not None
            if reached(it.TP2):
                exit_rest(k, it.TP2, "TP2")
                return
        if pos["be_next"]:  # break-even from the NEXT bar: entry + comm_price (long), entry - comm_price (short)
            pos["sl"] = round_to_tick(pos["fill"] + d * comm, tk, params.digits)
            pos["be_active"] = True
            pos["be_next"] = False

    for k in range(n):
        bar = bid_ohlc[k]
        o, h, l, c = bar[0], bar[1], bar[2], bar[3]  # noqa: E741
        sp = spreads[k]
        if pos is not None:
            d = pos["it"].dir
            if times[k] >= pos["fill_time"] + hold_s or flat_now[k]:
                reason = "TIME" if times[k] >= pos["fill_time"] + hold_s else "FLAT"
                exit_rest(k, o - slip if d > 0 else o + sp + slip, reason)
            else:
                bar_exits(k, h, l, sp)
        elif pending is not None:
            it = pending
            d = it.dir
            assert it.P is not None and it.SL is not None and it.TP1 is not None
            if it.type == EV_MARKET:
                pending = None
                pos = open_position(it, k, (o + sp + slip) if d > 0 else (o - slip))
                counters["fills"] += 1
                det.notify_filled(it.id)
                bar_exits(k, h, l, sp)  # the fill is at the open, so the whole bar follows it
            elif (l + sp <= it.P) if d > 0 else (h >= it.P):
                pending = None
                if (h >= it.TP1) if d > 0 else (l + sp <= it.TP1):
                    counters["runaway_same_bar"] += 1
                    det.notify_cancelled(it.id, RUNAWAY_SAME_BAR, n=k)
                else:
                    pos = open_position(it, k, min(it.P, o + sp) if d > 0 else max(it.P, o))
                    counters["fills"] += 1
                    det.notify_filled(it.id)
                    if (l <= it.SL) if d > 0 else (h + sp >= it.SL):  # stop on the fill bar: a loss on that bar
                        exit_rest(k, it.SL - slip if d > 0 else it.SL + slip, "SL")
        # decision steps of bar k run after its fill check
        nxt = k + 1 < n
        risk_ok = False
        if nxt:
            realised = day_r.get(fx_day[k + 1], 0.0)
            risk_ok = -realised + 1.0 <= DAILY_LOSS_R + 1e-9
            if not risk_ok:
                locked_days.add(fx_day[k + 1])
        env = Env(
            slot_free=pending is None and pos is None,
            session_entry_ok=bool(entry_ok[k + 1]) if nxt else False,
            session_cancel=bool(cancel_now[k + 1]) if nxt else False,
            risk_ok=risk_ok,
            spread_ok=True,
            sp=spreads[k + 1] if nxt else sp,
        )
        for it in det.on_bar_closed(k, o, h, l, c, env):
            if it.type in (EV_PLACE_LIMIT, EV_MARKET):
                if pending is not None or pos is not None:
                    raise RuntimeError("the detector broke the one-order-at-a-time rule")
                pending = it
                pending_bar = k
                counters["orders_limit" if it.type == EV_PLACE_LIMIT else "orders_market"] += 1
            elif it.type == EV_CANCEL:
                if pending is not None and pending.id == it.id:
                    pending = None
                counters["cancels"] += 1
    if pos is not None:  # end of data: close at the last close
        bar = bid_ohlc[n - 1]
        d = pos["it"].dir
        exit_rest(n - 1, bar[3] - slip if d > 0 else bar[3] + spreads[n - 1] + slip, "END")
    if pending is not None:
        counters["pending_at_end"] = 1
    counters["locked_days"] = len(locked_days)
    setups = [asdict(s) if is_dataclass(s) else dict(s) for s in getattr(det, "setups", [])]
    status: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for s in setups:
        status[s["status"]] = status.get(s["status"], 0) + 1
        if s.get("reason"):
            reasons[s["reason"]] = reasons.get(s["reason"], 0) + 1
    counters["setup_status"] = status
    counters["setup_reasons"] = reasons
    counters["total_R"] = sum(t["R"] for t in trades)
    return SimResult(trades=trades, setups=setups, counters=counters)
