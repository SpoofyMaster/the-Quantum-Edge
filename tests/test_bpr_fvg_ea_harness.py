"""BPR+FVG EA vs. the Python reference (research/indicators/BPR_FVG_EA_SPEC.md section 9).

The pure EA modules (mql5/BprFvgEA/include/BfDefines, BfEngine, BfDetector) are transliterated to C++
(tools/mql5_cpp_harness), compiled with g++ and run bar by bar under the harness environment:
- session always open, risk OK and a constant spread;
- orders never fill;
- slot free while no setup is ORDERED or FILLED.

Every detector event record (ARMED, DONE, MSS, PLACE_LIMIT, MARKET, CANCEL) must equal the record from
qe/strategies/bpr_fvg.harness_run. This checks the EA's decision logic, not MetaEditor compilation and not MT5
order execution. Skipped when g++ is missing.
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from qe.strategies.bpr_fvg import DIRECTIONS, ENTRY_MODES, SOURCES, TP_MODES, StrategyParams, harness_run

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools/mql5_cpp_harness"
INC = ROOT / "mql5/BprFvgEA/include"
GXX = shutil.which("g++")
pytestmark = pytest.mark.skipif(GXX is None, reason="g++ not installed")


@pytest.fixture(scope="module")
def exe(tmp_path_factory):
    d = tmp_path_factory.mktemp("bfh")
    sys.path.insert(0, str(HARNESS))
    try:
        from mq5_to_cpp import transform_pure
    finally:
        sys.path.pop(0)
    src = [(INC / f).read_text(encoding="utf-8") for f in ("BfDefines.mqh", "BfEngine.mqh", "BfDetector.mqh")]
    (d / "bf_pure.cpp").write_text(transform_pure(src))
    shutil.copy(HARNESS / "shim.h", d / "shim.h")
    shutil.copy(HARNESS / "bf_main.cpp", d / "bf_main.cpp")
    out = d / "bf_harness"
    res = subprocess.run([GXX, "-std=c++17", "-O1", "-w", "-o", str(out), str(d / "bf_main.cpp")],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr[-4000:]
    return out


def _bars(seed, n, tick=0.01):
    """Mean-reverting random walk with frequent displacement candles, so sweeps, BPRs and retests occur."""
    rnd = random.Random(seed)
    q = lambda x: round(round(x / tick) * tick, 2)  # noqa: E731
    out, c, anchor = [], 2000.0, 2000.0
    for _ in range(n):
        o = c
        if rnd.random() < 0.18:
            body = rnd.choice([-1, 1]) * rnd.uniform(1.5, 3.5)
            wick = 0.05
        else:
            body = rnd.gauss(0, 0.7) + (anchor - o) * 0.03
            wick = 0.6
        c = q(o + body)
        out.append((o, q(max(o, c) + abs(rnd.gauss(0, wick))), q(min(o, c) - abs(rnd.gauss(0, wick))), c))
    return out


def _cpp_args(p: StrategyParams, sp: float, trade_from: int) -> list[str]:
    kv = {
        "source": SOURCES.index(p.source), "direction": DIRECTIONS.index(p.direction),
        "entry_mode": ENTRY_MODES.index(p.entry_mode), "entry_offset_ticks": p.entry_offset_ticks,
        "use_sweep": int(p.use_sweep), "sweep_window": p.sweep_window, "range_bars": p.range_bars,
        "use_mss": int(p.use_mss), "mss_bars": p.mss_bars, "rally_bars": p.rally_bars, "expiry_bars": p.expiry_bars,
        "stop_zone_mult": repr(p.stop_zone_mult), "min_rr": repr(p.min_rr), "max_cost_r": repr(p.max_cost_r),
        "tp_mode": TP_MODES.index(p.tp_mode), "slippage_ticks": repr(float(p.slippage_ticks)),
        "tick_size": repr(p.tick_size), "digits": p.digits, "comm_price": repr(p.comm_price), "length": p.length,
        "vis_boxes": p.vis_boxes, "sp": repr(sp), "trade_from": trade_from,
    }
    return [f"{k}={v}" for k, v in kv.items()]


CASES = [
    # seed, n_bars, params, spread, trade_from, price tick
    (1, 3000, StrategyParams(), 0.10, 0, 0.01),
    (2, 3000, StrategyParams(entry_mode="CONFIRM"), 0.10, 0, 0.01),
    (3, 3000, StrategyParams(source="FVG"), 0.10, 0, 0.01),
    (4, 3000, StrategyParams(source="BOTH", tp_mode="TP1_ONLY"), 0.10, 0, 0.01),
    (5, 3000, StrategyParams(use_sweep=False, use_mss=False), 0.10, 0, 0.01),
    (6, 3000, StrategyParams(source="BOTH", direction="LONG_ONLY", entry_mode="CONFIRM"), 0.10, 0, 0.01),
    (7, 3000, StrategyParams(source="BOTH", direction="SHORT_ONLY", tp_mode="TP2_ONLY"), 0.10, 0, 0.01),
    (8, 3000, StrategyParams(source="BOTH", min_rr=0.0, max_cost_r=10.0), 0.30, 500, 0.01),   # warm-up
    (9, 3000, StrategyParams(source="BOTH", expiry_bars=15, vis_boxes=4, length=3), 0.10, 0, 0.5),  # ties
    (10, 3000, StrategyParams(source="BOTH", capacity=128, sweep_window=10, range_bars=10, mss_bars=5,
                              use_sweep=False, min_rr=0.0, max_cost_r=10.0), 0.05, 0, 0.01),
]


@pytest.mark.parametrize("case", CASES, ids=[f"seed{c[0]}" for c in CASES])
def test_ea_detector_matches_python_reference(exe, case, tmp_path):
    seed, n, params, sp, trade_from, tick = case
    bars = _bars(seed, n, tick)
    bf = tmp_path / "bars.txt"
    bf.write_text("".join(" ".join(repr(float(x)) for x in b) + "\n" for b in bars))
    res = subprocess.run([str(exe), str(bf), *_cpp_args(params, sp, trade_from)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "lost events 0 intents 0" in res.stderr
    got = [json.loads(ln) for ln in res.stdout.splitlines()]
    exp = harness_run(bars, params, sp, trade_from=trade_from)
    keys = ("n", "id", "ev", "dir", "src", "reason")
    for i, (g, e) in enumerate(zip(got, exp)):
        assert tuple(g[k] for k in keys) == tuple(e[k] for k in keys), (i, g, e)
        for k in ("P", "SL", "TP1", "TP2"):
            if e[k] is None:
                assert g[k] is None, (i, k, g, e)
            else:
                assert g[k] == pytest.approx(e[k], abs=1e-9 * 2000), (i, k, g, e)
    assert len(got) == len(exp)
    # the series must exercise the logic: setups armed, and orders decided unless the filters forbid it
    evs = {e["ev"] for e in exp}
    assert "ARMED" in evs and "DONE" in evs
    assert evs & {"PLACE_LIMIT", "MARKET"}, sorted(evs)
