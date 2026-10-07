"""Parity: the JavaScript engine of the BPR live-replay page (tools/luxbpr_preview/engine.js) must give the same state
as the Python reference (qe/indicators/luxalgo_bpr.py) after every bar. Skipped when Node.js is not installed."""
import json
import math
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from qe.indicators.luxalgo_bpr import BprParams, LuxBprEngine, fib_bpr, per_start_for

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js not installed")


def _bars(seed, n, tick=0.001):
    """Random walk with frequent large-body candles, so FVGs and BPRs occur often. A coarse tick makes ties common."""
    rnd = random.Random(seed)
    q = lambda x: round(round(x / tick) * tick, 3)  # noqa: E731
    out, c = [], 100.0
    for _ in range(n):
        o = c
        if rnd.random() < 0.2:
            body = rnd.choice([-1, 1]) * rnd.uniform(1.5, 3.0)
            wick = 0.05
        else:
            body = rnd.gauss(0, 0.6)
            wick = 0.5
        c = q(o + body)
        h = q(max(o, c) + abs(rnd.gauss(0, wick)))
        lo = q(min(o, c) - abs(rnd.gauss(0, wick)))
        out.append((o, h, lo, c))
    return out


def _ser(zones):
    rows = []
    for z in zones:
        if z.box is None:
            rows.append([0, None, None, None, None, int(z.active), z.pos, None, None])
        else:
            b = z.box
            rows.append([1, b.left, b.top, b.right, b.bottom, int(z.active), z.pos, b.border, int(b.broken_fill)])
    return rows


def _js_states(params, per_start, bars):
    req = {"params": {"mode": params.mode, "present_bars": params.present_bars, "length": params.length,
                      "perc_body": params.perc_body, "show_fvg": params.show_fvg, "bpr": params.bpr,
                      "fvg_mode": params.fvg_mode, "vis_boxes": params.vis_boxes, "bx_back": params.bx_back,
                      "ext_bars": params.ext_bars},
           "per_start": per_start, "first_index": 0, "bars": [list(b) for b in bars]}
    res = subprocess.run([NODE, str(ROOT / "tools/luxbpr_preview/dump_states.js")], input=json.dumps(req),
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


@pytest.mark.parametrize("seed, params, tick", [
    (1, BprParams(mode="Historical"), 0.001),
    (2, BprParams(mode="Historical", fvg_mode="IFVG"), 0.001),
    (3, BprParams(mode="Historical", vis_boxes=13, length=3), 0.001),
    (4, BprParams(mode="Present", present_bars=150), 0.001),
    (5, BprParams(mode="Historical", bpr=False), 0.001),
    (6, BprParams(mode="Historical", length=10, vis_boxes=1), 0.001),
    (7, BprParams(mode="Historical", vis_boxes=3), 0.5),
    (8, BprParams(mode="Historical", fvg_mode="IFVG", vis_boxes=3), 0.5),
])
def test_js_engine_matches_python_reference(seed, params, tick):
    bars = _bars(seed, 600, tick)
    per_start = per_start_for(len(bars) - 1, params)
    js = _js_states(params, per_start, bars)
    eng = LuxBprEngine(params, per_start)
    for i, b in enumerate(bars):
        eng.process_bar(i, *b)
        st = js[i]
        for key, zones in (("fu", eng.fvg_up), ("fd", eng.fvg_dn), ("bu", eng.bpr_up), ("bd", eng.bpr_dn)):
            assert st[key] == _ser(zones), (seed, i, key)
        assert st["disp"] == [int(eng.disp_up), int(eng.disp_dn)], (seed, i)
        fib = fib_bpr(eng)
        if fib is None:
            assert st["fib"] is None, (seed, i)
        else:
            for k in ("x1", "y1", "x2", "y2", "rt"):
                assert st["fib"][k] == fib[k], (seed, i, k)
            for lvl, price in fib["levels"].items():
                js_lvl = st["fib"]["levels"][str(int(lvl)) if float(lvl).is_integer() else repr(float(lvl))]
                assert math.isclose(js_lvl, price, rel_tol=0, abs_tol=1e-9), (seed, i, lvl)
    assert [list(e) for e in eng.events] == js[-1]["events"]
    # the series must actually exercise the BPR logic
    if params.bpr:
        assert any(e[1].startswith("BPR") and e[2] == "new" for e in eng.events)
