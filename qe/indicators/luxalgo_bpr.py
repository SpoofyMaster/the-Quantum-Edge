"""Fair Value Gap (FVG) and Balance Price Range (BPR) logic of "ICT Concepts [LuxAlgo]": pure-Python reference.

Licence and attribution
-----------------------
(c) LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]').
Licensed under CC BY-NC-SA 4.0: https://creativecommons.org/licenses/by-nc-sa/4.0/
This file is a port (a derivative work) of the FVG / BPR part of that Pine v5 script, for non-commercial
research use only, shared under the same licence. The original source is kept unmodified in
``research/indicators/luxalgo_ict_concepts.pine``. The changes made on purpose by the ports are listed in
``research/indicators/LUXALGO_BPR_SPEC.md`` section 10.

What this module is
-------------------
A bar-by-bar reference of Pine lines 548-553 (displacement), 565-566 (imbalance), 597-644 (FVG), 646-697 (BPR),
699-769 (breaks) and 956-1118 (Fibonacci, ``iFib = 'BPR'`` only). The authoritative description is
``research/indicators/LUXALGO_BPR_SPEC.md``; the QUIRKS numbered there are reproduced on purpose and marked
``QUIRK n`` in the code. It is the reference for the MT5 indicator and for the live preview page.

Pine semantics reproduced here:

* ``na`` values are ``None``; every comparison with ``na`` is false (so an ``na`` box never takes part in a BPR);
* ``array.unshift`` + ``array.pop`` is ``list.insert(0, ...)`` + ``list.pop()`` (index 0 = newest);
* the realtime bar rolls back to the committed state on every tick (``live_view``);
* ``per`` (Present mode window) gates only FVG creation/update.

Standard library only (no numpy/pandas), so the logic is easy to read next to the Pine and the MQL5 code.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

__all__ = [
    "BprParams",
    "Box",
    "Zone",
    "LuxBprEngine",
    "per_start_for",
    "run",
    "live_view",
    "fib_bpr",
    "FIB_LEVELS",
    "FIB_PLUS_BARS",
]

#: Fibonacci levels drawn by Pine lines 1111-1118 (1.0 is the ``_1`` line itself).
FIB_LEVELS: tuple[float, ...] = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.618)
#: ``plus`` (Pine line 126) for ``xloc.bar_index``: the level lines run from ``rt`` to ``rt + 50`` bars.
FIB_PLUS_BARS = 50

_MODES = ("Present", "Historical")
_FVG_MODES = ("FVG", "IFVG")
_BORDERS = ("solid", "dashed", "dotted")


@dataclass(frozen=True)
class BprParams:
    """Inputs that affect the FVG / BPR (spec section 1).

    ``mode`` = Pine ``i_mode``; ``present_bars`` = the 500 of ``per`` (line 122); ``length`` = Pine ``len``
    (3..10); ``perc_body`` = ``perc_Body``; ``show_fvg`` = ``shwFVG``; ``bpr`` = ``i_BPR`` (port default
    ``True``, spec section 10); ``fvg_mode`` = ``i_FVG``; ``vis_boxes`` = ``visBxs`` (1..20); ``bx_back`` =
    ``bxBack``; ``ext_bars`` = the ``+8`` used for ``right`` of active boxes.
    """

    mode: str = "Present"
    present_bars: int = 500
    length: int = 5
    perc_body: float = 0.36
    show_fvg: bool = True
    bpr: bool = True
    fvg_mode: str = "FVG"
    vis_boxes: int = 2
    bx_back: int = 10
    ext_bars: int = 8

    def __post_init__(self) -> None:
        if self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        if self.fvg_mode not in _FVG_MODES:
            raise ValueError(f"fvg_mode must be one of {_FVG_MODES}, got {self.fvg_mode!r}")
        if not 3 <= self.length <= 10:  # Pine input.int minval = 3, maxval = 10 (line 25)
            raise ValueError(f"length must be in 3..10 (Pine 'len'), got {self.length}")
        if not 1 <= self.vis_boxes <= 20:  # Pine input.int minval = 1, maxval = 20 (line 76-78)
            raise ValueError(f"vis_boxes must be in 1..20 (Pine 'visBxs'), got {self.vis_boxes}")
        if self.present_bars < 0:
            raise ValueError("present_bars must be >= 0")
        if self.bx_back < 0:
            raise ValueError("bx_back must be >= 0")
        if self.ext_bars < 0:
            raise ValueError("ext_bars must be >= 0")


@dataclass
class Box:
    """A Pine ``box``: coordinates as stored by ``box.new`` / setters (never normalised: top < bottom can occur,
    QUIRK 1). ``border`` is the border line style, ``broken_fill`` is True once the fill was switched to the
    break colour at 95 transparency."""

    left: int
    top: float
    right: int
    bottom: float
    border: str = "solid"
    broken_fill: bool = False


@dataclass
class Zone:
    """The Pine user type ``FVG`` (lines 197-200): ``box`` (``None`` = ``box(na)``), ``active`` and ``pos``."""

    box: Box | None = None
    active: bool = False
    pos: int | None = None


@dataclass(frozen=True)
class _Rec:
    """One processed bar as needed by later bars (history operator ``[k]``)."""

    n: int
    high: float
    low: float
    body: float
    disp_up: bool
    disp_dn: bool
    imb_up: bool
    imb_dn: bool


def per_start_for(last_bar_index: int, params: BprParams) -> int | None:
    """First bar index with ``per`` true (Pine line 122). ``None`` = always true (Historical mode).

    ``last_bar_index - bar_index <= present_bars``  <=>  ``bar_index >= last_bar_index - present_bars``.
    """
    if params.mode == "Present":
        return last_bar_index - params.present_bars
    return None


def _copy_zone(z: Zone) -> Zone:
    return Zone(box=None if z.box is None else replace(z.box), active=z.active, pos=z.pos)


class LuxBprEngine:
    """Bar-by-bar state machine of the FVG + BPR logic (spec section 4).

    Attributes ``fvg_up``, ``fvg_dn``, ``bpr_up``, ``bpr_dn`` are the four Pine arrays (index 0 = newest).
    ``events`` collects ``(bar_index, kind, what)`` with ``kind`` in FVG_UP/FVG_DN/BPR_UP/BPR_DN and ``what`` in
    new/update/broken. ``update`` is only emitted for the consecutive-imbalance FVG update (Pine 607-609 /
    627-629) when the box exists; the BPR block's same-left ``set_right`` (QUIRK 8, never visible) emits nothing.
    Within one bar the events follow the Pine order: FVG up, FVG down, BPR up, BPR down, FVG breaks, BPR breaks.
    ``disp_up`` / ``disp_dn`` are ``L_bodyUP`` / ``L_bodyDN`` of the last processed bar (not gated by ``per``).
    ``last_index`` is the index of the last processed bar.
    """

    def __init__(self, params: BprParams = BprParams(), per_start: int | None = None) -> None:
        self.params = params
        self.per_start = per_start
        # barstate.isfirst initialisation (lines 598-604): visBxs empty entries; BPR arrays only with i_BPR.
        self.fvg_up: list[Zone] = []
        self.fvg_dn: list[Zone] = []
        self.bpr_up: list[Zone] = []
        self.bpr_dn: list[Zone] = []
        for _ in range(params.vis_boxes):
            self.fvg_up.insert(0, Zone())
            self.fvg_dn.insert(0, Zone())
            if params.bpr:
                self.bpr_up.insert(0, Zone())
                self.bpr_dn.insert(0, Zone())
        self.events: list[tuple[int, str, str]] = []
        self.last_index: int | None = None
        self.disp_up: bool = False
        self.disp_dn: bool = False
        self._keep = max(params.length, 3) + 2
        self._hist: deque[_Rec] = deque(maxlen=self._keep)

    # ------------------------------------------------------------------ helpers
    def per(self, n: int) -> bool:
        """Pine ``per`` (line 122) for bar ``n``."""
        return self.per_start is None or n >= self.per_start

    def _back(self, k: int) -> _Rec | None:
        """Record of bar ``n - k`` (k >= 1) or ``None`` (na) if it was not processed."""
        if k <= len(self._hist):
            return self._hist[-k]
        return None

    def clone(self) -> "LuxBprEngine":
        """Deep, independent copy (used to evaluate the forming bar without touching committed state)."""
        e = LuxBprEngine.__new__(LuxBprEngine)
        e.params = self.params
        e.per_start = self.per_start
        e.fvg_up = [_copy_zone(z) for z in self.fvg_up]
        e.fvg_dn = [_copy_zone(z) for z in self.fvg_dn]
        e.bpr_up = [_copy_zone(z) for z in self.bpr_up]
        e.bpr_dn = [_copy_zone(z) for z in self.bpr_dn]
        e.events = list(self.events)
        e.last_index = self.last_index
        e.disp_up = self.disp_up
        e.disp_dn = self.disp_dn
        e._keep = self._keep
        e._hist = deque(self._hist, maxlen=self._keep)  # records are frozen
        return e

    # ------------------------------------------------------------------ one bar
    def process_bar(self, n: int, o: float, h: float, l: float, c: float) -> None:  # noqa: E741 (Pine names)
        """Run Pine's script body for bar ``n`` (spec section 4, steps 2-6) and commit the result."""
        if self.last_index is not None and n != self.last_index + 1:
            raise ValueError(f"bars must be consecutive: expected index {self.last_index + 1}, got {n}")
        p = self.params
        ext = p.ext_bars

        # --- Candles (lines 127-130, 548-553)
        mx = max(c, o)
        mn = min(c, o)
        body = abs(c - o)
        length = p.length
        mean_body: float | None = None
        if len(self._hist) >= length - 1:  # sma(body, len) is na until len bars exist
            s = 0.0
            for k in range(length - 1, 0, -1):  # oldest first: body[n-(len-1)] ... body[n-1]
                s += self._hist[-k].body
            s += body  # body[n]
            mean_body = s / length
        l_body = (h - mx < body * p.perc_body) and (mn - l < body * p.perc_body)
        disp_up = mean_body is not None and body > mean_body and l_body and c > o
        disp_dn = mean_body is not None and body > mean_body and l_body and c < o

        # --- Imbalance (lines 565-566); history before the first processed bar is na -> False
        b1 = self._back(1)  # bar n-1
        b2 = self._back(2)  # bar n-2
        fvg = p.fvg_mode == "FVG"
        imb_up = False
        imb_dn = False
        if b1 is not None and b2 is not None:
            if b1.disp_up:
                imb_up = (l > b2.high) if fvg else (l < b2.high)
            if b1.disp_dn:
                imb_dn = (h < b2.low) if fvg else (h > b2.low)
        prev_imb_up = b1 is not None and b1.imb_up  # imbalanceUP[1]
        prev_imb_dn = b1 is not None and b1.imb_dn  # imbalanceDN[1]
        per = self.per(n)

        # --- Bullish FVG (lines 606-624)
        if imb_up and per and p.show_fvg:
            assert b2 is not None
            if prev_imb_up:
                z = self.fvg_up[0]
                if z.box is not None:  # QUIRK 3: setters on box(na) do nothing
                    # QUIRK 1: FVG geometry even in IFVG mode; QUIRK 2: 'active' untouched.
                    z.box.left, z.box.top = n - 2, l  # set_lefttop(n -2, low)
                    z.box.right, z.box.bottom = n + ext, b2.high  # set_rightbottom(n +8, high[2])
                    self.events.append((n, "FVG_UP", "update"))
            else:
                top, bottom = (l, b2.high) if fvg else (b2.high, l)
                self.fvg_up.insert(0, Zone(Box(n - 2, top, n, bottom), True, None))
                self.fvg_up.pop()
                self.events.append((n, "FVG_UP", "new"))

        # --- Bearish FVG (lines 626-644)
        if imb_dn and per and p.show_fvg:
            assert b2 is not None
            if prev_imb_dn:
                z = self.fvg_dn[0]
                if z.box is not None:  # QUIRK 3
                    z.box.left, z.box.top = n - 2, b2.low  # set_lefttop(n -2, low[2])
                    z.box.right, z.box.bottom = n + ext, h  # set_rightbottom(n +8, high)
                    self.events.append((n, "FVG_DN", "update"))
            else:
                top, bottom = (b2.low, h) if fvg else (h, b2.low)
                self.fvg_dn.insert(0, Zone(Box(n - 2, top, n, bottom), True, None))
                self.fvg_dn.pop()
                self.events.append((n, "FVG_DN", "new"))

        # --- Balance Price Range (lines 646-697); runs on every bar, before the break loops (QUIRK 10)
        if p.bpr and len(self.fvg_up) > 0 and len(self.fvg_dn) > 0:
            up = self.fvg_up[0].box  # newest entries, active or broken (QUIRK 9)
            dn = self.fvg_dn[0].box
            if up is not None and dn is not None:  # na box: every comparison below is false
                left = min(up.left, dn.left)
                right = max(up.right, dn.right)
                if up.bottom < dn.top and dn.bottom < up.bottom:
                    z0 = self.bpr_up[0]
                    if z0.box is not None and left == z0.box.left:  # QUIRK 6: identity = left edge
                        if z0.active:
                            z0.box.right = right  # QUIRK 8: overwritten by the break loop below
                    else:
                        pos = 1 if c > up.bottom else (-1 if c < dn.top else 0)  # QUIRK 5: 0 unreachable
                        # QUIRK 4: top = other gap's top
                        self.bpr_up.insert(0, Zone(Box(left, dn.top, right, up.bottom), True, pos))
                        self.bpr_up.pop()
                        self.events.append((n, "BPR_UP", "new"))
                if dn.bottom < up.top and up.bottom < dn.bottom:
                    z0 = self.bpr_dn[0]
                    if z0.box is not None and left == z0.box.left:
                        if z0.active:
                            z0.box.right = right
                    else:
                        pos = 1 if c > dn.bottom else (-1 if c < up.top else 0)
                        self.bpr_dn.insert(0, Zone(Box(left, up.top, right, dn.bottom), True, pos))
                        self.bpr_dn.pop()
                        self.events.append((n, "BPR_DN", "new"))

        # --- FVG breaks (lines 699-724)
        for i in range(0, min(p.bx_back, len(self.fvg_up) - 1) + 1):
            z = self.fvg_up[i]
            if z.active:
                bx = z.box
                assert bx is not None
                bx.right = n + ext
                if l < bx.top and not p.bpr:
                    bx.border = "dashed"
                if l < bx.bottom:
                    if not p.bpr:
                        bx.broken_fill = True
                        bx.border = "dotted"
                    bx.right = n
                    z.active = False
                    self.events.append((n, "FVG_UP", "broken"))
        for i in range(0, min(p.bx_back, len(self.fvg_dn) - 1) + 1):
            z = self.fvg_dn[i]
            if z.active:
                bx = z.box
                assert bx is not None
                bx.right = n + ext
                if h > bx.bottom and not p.bpr:
                    bx.border = "dashed"
                if h > bx.top:
                    if not p.bpr:
                        bx.broken_fill = True
                        bx.border = "dotted"
                    bx.right = n
                    z.active = False
                    self.events.append((n, "FVG_DN", "broken"))

        # --- BPR breaks (lines 726-769)
        if p.bpr:
            for arr, kind in ((self.bpr_up, "BPR_UP"), (self.bpr_dn, "BPR_DN")):
                for i in range(0, min(p.bx_back, len(arr) - 1) + 1):
                    z = arr[i]
                    if z.active:
                        bx = z.box
                        assert bx is not None
                        bx.right = n + ext
                        if z.pos == -1:
                            if h > bx.bottom:
                                bx.border = "dashed"
                            if h > bx.top:
                                bx.broken_fill = True
                                bx.border = "dotted"
                                bx.right = n
                                z.active = False
                                self.events.append((n, kind, "broken"))
                        elif z.pos == 1:
                            if l < bx.top:
                                bx.border = "dashed"
                            if l < bx.bottom:
                                bx.broken_fill = True
                                bx.border = "dotted"
                                bx.right = n
                                z.active = False
                                self.events.append((n, kind, "broken"))

        # --- commit the series values of bar n
        self._hist.append(_Rec(n, h, l, body, disp_up, disp_dn, imb_up, imb_dn))
        self.last_index = n
        self.disp_up = disp_up
        self.disp_dn = disp_dn


def run(
    bars: Iterable[Sequence[float]],
    params: BprParams = BprParams(),
    last_bar_index: int | None = None,
    first_index: int = 0,
) -> LuxBprEngine:
    """Process ``bars`` (each ``(open, high, low, close)``; bar ``i`` has index ``first_index + i``).

    ``last_bar_index`` (Pine ``last_bar_index`` at load time) defaults to the index of the last bar given and
    only matters in Present mode, where it fixes the ``per`` window.
    """
    seq = list(bars)
    if last_bar_index is None:
        last_bar_index = first_index + len(seq) - 1
    eng = LuxBprEngine(params, per_start_for(last_bar_index, params))
    for i, bar in enumerate(seq):
        o, h, l, c = bar[0], bar[1], bar[2], bar[3]  # noqa: E741
        eng.process_bar(first_index + i, o, h, l, c)
    return eng


def live_view(engine: LuxBprEngine, n: int, bar: Sequence[float]) -> LuxBprEngine:
    """State shown while bar ``n`` is still forming (spec section 7, HYPOTHESIS on Pine's rollback model).

    Clones the committed ``engine`` and runs the forming bar ``(open, high, low, close)`` on the clone. The
    committed engine is not modified.
    """
    view = engine.clone()
    view.process_bar(n, bar[0], bar[1], bar[2], bar[3])
    return view


def fib_bpr(engine: LuxBprEngine) -> dict | None:
    """Fibonacci between the latest BPR up and BPR down (spec section 8, Pine lines 976-990 and 1093-1118).

    Returns ``None`` when either ``BPR_UP[0]`` or ``BPR_DN[0]`` has no box (or the BPR is off).
    """
    if not (len(engine.bpr_up) > 0 and len(engine.bpr_dn) > 0):
        return None
    up = engine.bpr_up[0].box
    dn = engine.bpr_dn[0].box
    if up is None or dn is None:
        return None
    dn_first = up.left > dn.left
    dn_bottm = up.top > dn.top
    x1 = dn.left if dn_first else up.left
    x2 = up.right if dn_first else dn.right
    if dn_first:
        y1 = dn.bottom if dn_bottm else dn.top
        y2 = up.top if dn_bottm else up.bottom
    else:
        y1 = up.top if dn_bottm else up.bottom
        y2 = dn.bottom if dn_bottm else dn.top
    rt = max(x1, x2)
    zero = y1 if rt == x1 else y2
    one = y2 if rt == x1 else y1
    df = one - zero
    levels: dict[float, float] = {}
    for k in FIB_LEVELS:
        if k == 0.0:
            levels[k] = zero  # _zero line at _0
        elif k == 1.0:
            levels[k] = one  # _one_ line at _1
        else:
            levels[k] = zero + df * k  # _0 + m0xxx with m0xxx = df * k
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "rt": rt,
        "zero": zero,
        "one": one,
        "levels": levels,
        "line_end": rt + FIB_PLUS_BARS,
    }
