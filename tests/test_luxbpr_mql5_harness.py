"""MT5 indicator logic vs. the Python reference.

The .mq5 is transliterated to C++ (tools/mql5_cpp_harness), compiled with g++ and driven like MT5:
- a full calculation at load;
- new bars, each delivered in ticks;
- optionally a reload.

The committed state, the forming-bar state, the displacement buffers, the alert count and the parity export must all
match qe/indicators/luxalgo_bpr.py.

This does NOT prove that MetaEditor compiles the file. Skipped when g++ is missing.
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from qe.indicators.luxalgo_bpr import BprParams, LuxBprEngine

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools/mql5_cpp_harness"
MQ5 = ROOT / "mql5/Indicators/LuxAlgo_BPR/LuxAlgo_BPR.mq5"
GXX = shutil.which("g++")
pytestmark = pytest.mark.skipif(GXX is None, reason="g++ not installed")


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    d = tmp_path_factory.mktemp("mql5h")
    sys.path.insert(0, str(HARNESS))
    try:
        from mq5_to_cpp import transform
    finally:
        sys.path.pop(0)
    (d / "lxbpr.cpp").write_text(transform(MQ5.read_text(encoding="utf-8")))
    shutil.copy(HARNESS / "shim.h", d / "shim.h")
    shutil.copy(HARNESS / "luxbpr_main.cpp", d / "main.cpp")
    exe = d / "harness"
    res = subprocess.run([GXX, "-std=c++17", "-O1", "-w", "-o", str(exe), str(d / "main.cpp")], capture_output=True,
                         text=True)
    assert res.returncode == 0, res.stderr[-4000:]
    return d, exe


def _bars(seed, n, tick=0.01):
    """Random walk with frequent large-body candles. A coarse tick makes price ties (close == box edge) common."""
    rnd = random.Random(seed)
    q = lambda x: round(round(x / tick) * tick, 2)  # noqa: E731
    out, c = [], 2000.0
    for _ in range(n):
        o = c
        if rnd.random() < 0.2:
            body, wick = rnd.choice([-1, 1]) * rnd.uniform(1.5, 3.0), 0.05
        else:
            body, wick = rnd.gauss(0, 0.6), 0.5
        c = q(o + body)
        out.append((o, q(max(o, c) + abs(rnd.gauss(0, wick))), q(min(o, c) - abs(rnd.gauss(0, wick))), c))
    return out


def _ser(zones):
    rows = []
    for z in zones:
        if z.box is None:
            rows.append([0, None, None, None, None, int(z.active), None, None, None])
        else:
            b = z.box
            rows.append([1, b.left, b.top, b.right, b.bottom, int(z.active), z.pos, b.border, int(b.broken_fill)])
    return rows


CASES = [
    # seed, N, K(bars at load), mode(0 Present/1 Historical), length, fvg(0/1 IFVG), vis, bpr, showFVG, live,
    # presentBars, ticks, reloadAt, price tick
    (7, 1200, 800, 0, 5, 0, 2, 1, 1, 1, 500, 3, -1, 0.01),
    (8, 1200, 800, 1, 5, 0, 2, 1, 1, 1, 500, 2, -1, 0.01),
    (9, 900, 300, 0, 5, 0, 2, 1, 1, 1, 500, 2, -1, 0.01),      # history shorter than the Present window
    (10, 900, 600, 1, 3, 1, 5, 1, 1, 1, 500, 2, -1, 0.01),     # IFVG
    (11, 900, 600, 1, 10, 0, 20, 1, 1, 0, 500, 2, -1, 0.01),   # 20 boxes (QUIRK 11), live bar off
    (12, 900, 600, 1, 5, 0, 2, 0, 1, 1, 500, 2, -1, 0.01),     # BPR off
    (13, 900, 600, 1, 5, 0, 3, 1, 0, 1, 500, 2, -1, 0.01),     # Show FVG off -> no BPR
    (14, 900, 600, 1, 7, 1, 12, 1, 1, 1, 500, 4, 750, 0.01),   # IFVG + full reload
    (15, 1500, 1100, 0, 4, 0, 4, 1, 1, 1, 200, 2, -1, 0.01),   # Present, 200-bar window
    (16, 1500, 900, 1, 5, 0, 3, 1, 1, 1, 500, 2, -1, 0.5),     # coarse prices: ties at box edges
    (17, 1500, 900, 1, 5, 1, 3, 1, 1, 1, 500, 2, -1, 0.5),     # coarse prices, IFVG
    (18, 1200, 800, 0, 5, 0, 3, 1, 1, 1, 300, 2, 1000, 0.01),  # Present + reload: the window stays anchored by time
]


@pytest.mark.parametrize("case", CASES, ids=[f"seed{c[0]}" for c in CASES])
def test_mql5_logic_matches_python_reference(harness, case, tmp_path):
    d, exe = harness
    seed, n_bars, k, mode, length, fvg, vis, bpr, show, live, present, ticks, reload_at, tick = case
    bars = _bars(seed, n_bars, tick)
    bf = tmp_path / "bars.txt"
    bf.write_text("".join(" ".join(repr(float(x)) for x in b) + "\n" for b in bars))
    args = [str(exe), str(bf), str(mode), str(length), str(fvg), str(vis), str(bpr), str(show), str(live), str(k),
            str(present), str(ticks), str(reload_at), "0"]
    res = subprocess.run(args, capture_output=True, text=True, cwd=tmp_path)
    assert res.returncode == 0, res.stderr[-2000:]
    recs = [json.loads(ln) for ln in res.stdout.splitlines()]

    params = BprParams(mode="Present" if mode == 0 else "Historical", present_bars=present, length=length,
                       show_fvg=bool(show), bpr=bool(bpr), fvg_mode="IFVG" if fvg else "FVG", vis_boxes=vis)
    per_start = (k - 1) - present if mode == 0 else None
    eng = LuxBprEngine(params, per_start)
    states, disp = [], []
    for i, b in enumerate(bars):
        eng.process_bar(i, *b)
        states.append({"fu": _ser(eng.fvg_up), "fd": _ser(eng.fvg_dn), "bu": _ser(eng.bpr_up),
                       "bd": _ser(eng.bpr_dn)})
        disp.append((int(eng.disp_up), int(eng.disp_dn)))

    n_c = n_l = 0
    for r in recs:
        if r["t"] in ("C", "L"):
            for key in ("fu", "fd", "bu", "bd"):
                assert r[key] == states[r["n"]][key], (r["t"], r["n"], key)
            n_c += r["t"] == "C"
            n_l += r["t"] == "L"
    assert n_c == n_bars - k + 1 and n_l == (n_bars - k + 1 if live else 0)

    # displacement arrows on committed bars: shown only from the processing start and inside 'per'
    proc_start = max(0, per_start) if mode == 0 else 0
    got = {r["n"]: (r["u"], r["d"]) for r in recs if r["t"] == "D"}
    for i in range(0, n_bars - 1):
        assert got.get(i, (0, 0)) == (disp[i] if i >= proc_start else (0, 0)), i

    summary = [r for r in recs if r["t"] == "A"][0]
    assert summary["load"] == 0  # never alert on history
    assert summary["perStart"] == (per_start if mode == 0 else summary["perStart"])
    # one alert per new BPR on every bar that closed after loading, also across a full reload
    new_live = sum(1 for e in eng.events if e[1].startswith("BPR") and e[2] == "new" and k - 1 <= e[0] <= n_bars - 2)
    assert summary["total"] == (new_live if bpr else 0)
    if bpr and show:
        assert any(e[1].startswith("BPR") and e[2] == "new" for e in eng.events)


@pytest.mark.parametrize("mode, fvg, vis, bpr", [(0, 0, 2, 1), (1, 1, 5, 1), (1, 0, 2, 0)])
def test_mql5_export_passes_the_parity_tool(harness, tmp_path, mode, fvg, vis, bpr):
    """InpExportCSV=true: the file the indicator writes must be accepted as IDENTICAL by tools/luxbpr_parity.py."""
    d, exe = harness
    bars = _bars(100 + vis, 1000)
    bf = tmp_path / "bars.txt"
    bf.write_text("".join(" ".join(repr(float(x)) for x in b) + "\n" for b in bars))
    args = [str(exe), str(bf), str(mode), "5", str(fvg), str(vis), str(bpr), "1", "1", "700", "500", "2", "-1", "1"]
    subprocess.run(args, capture_output=True, text=True, cwd=tmp_path, check=True)
    exports = list(tmp_path.glob("LuxAlgo_BPR_*.csv"))
    assert len(exports) == 1
    res = subprocess.run([sys.executable, str(ROOT / "tools/luxbpr_parity.py"), str(exports[0])], capture_output=True,
                         text=True)
    assert res.returncode == 0, res.stdout + res.stderr
