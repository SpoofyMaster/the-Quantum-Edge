"""BprFvgEA v2 (BPR rejection -> breakout -> Fibonacci pullback) vs. the Python reference.

The pure EA modules (mql5/BprFvgEA/include/BfDefines, BfEngine, BfDetector) are transliterated to C++
(tools/mql5_cpp_harness), compiled with g++ and run bar by bar under the parity-harness executor of
research/indicators/BPR_BREAKOUT_FIB_SPEC.md section 7 (bar-based fills and exits, session and risk always OK, a
constant spread). Every event record and every diagnostic counter must equal qe/strategies/bpr_breakout.harness_run.
This checks the EA's decision logic, not MetaEditor compilation and not MT5 order execution. Skipped without g++.
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from qe.strategies.bpr_breakout import DIRECTIONS, FVG_RULES, REASONS, BreakoutParams, harness_detector, harness_run

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools/mql5_cpp_harness"
INC = ROOT / "mql5/BprFvgEA/include"
GXX = shutil.which("g++")
pytestmark = pytest.mark.skipif(GXX is None, reason="g++ not installed")

# BF_STAT_* order of BfDefines.mqh -> Python 'stats' keys
STAT_KEYS = (["DONE_NONE"] + [f"DONE_{r}" for r in REASONS] + ["SKIP_NONE"] + [f"SKIP_{r}" for r in REASONS]
             + ["DROP_NONE"] + [f"DROP_{r}" for r in REASONS]
             + ["BLOCKED_SLOT", "BLOCKED_SESSION", "BLOCKED_RISK", "BLOCKED_SPREAD", "WAIT_NO_FVG", "REANCHOR",
                "RETRY", "BREAK_FAIL", "CONFIRM", "PLACE_LIMIT", "ARMED", "CLOSED", "TOUCH", "BREAKOUT"])


@pytest.fixture(scope="module")
def exe(tmp_path_factory):
    d = tmp_path_factory.mktemp("bkh")
    sys.path.insert(0, str(HARNESS))
    try:
        from mq5_to_cpp import transform_pure
    finally:
        sys.path.pop(0)
    src = [(INC / f).read_text(encoding="utf-8") for f in ("BfDefines.mqh", "BfEngine.mqh", "BfDetector.mqh")]
    (d / "bf_pure.cpp").write_text(transform_pure(src))
    shutil.copy(HARNESS / "shim.h", d / "shim.h")
    shutil.copy(HARNESS / "bk_main.cpp", d / "bk_main.cpp")
    out = d / "bk_harness"
    res = subprocess.run([GXX, "-std=c++17", "-O1", "-w", "-o", str(out), str(d / "bk_main.cpp")],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr[-4000:]
    return out


def _bars(seed, n, tick=0.01):
    """Mean-reverting random walk with frequent displacement candles, so BPRs, touches and breakouts occur."""
    rnd = random.Random(seed)
    dg = 2 if tick >= 0.01 else 5
    q = lambda x: round(round(x / tick) * tick, dg)  # noqa: E731
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


def _cpp_args(p: BreakoutParams, sp: float, trade_from: int, hold_bars: int) -> list[str]:
    kv = {
        "direction": DIRECTIONS.index(p.direction), "max_touches": p.max_touches,
        "confirm_closes": p.confirm_closes, "reject_before_break": int(p.reject_before_break),
        "fvg_rule": FVG_RULES.index(p.fvg_rule),
        "setup_expiry_bars": p.setup_expiry_bars, "leg_expiry_bars": p.leg_expiry_bars,
        "fib1": repr(float(p.fib_levels[0])), "fib2": repr(float(p.fib_levels[1])),
        "fib3": repr(float(p.fib_levels[2])), "stop_fib": repr(float(p.stop_fib)),
        "stop_buffer_ticks": p.stop_buffer_ticks, "target_fib": repr(float(p.target_fib)),
        "min_rr": repr(float(p.min_rr)), "max_cost_r": repr(float(p.max_cost_r)),
        "slippage_ticks": repr(float(p.slippage_ticks)), "tick_size": repr(p.tick_size), "digits": p.digits,
        "comm_price": repr(p.comm_price), "use_session": int(p.use_session), "length": p.length,
        "vis_boxes": p.vis_boxes, "sp": repr(sp), "trade_from": trade_from, "hold_bars": hold_bars,
    }
    return [f"{k}={v}" for k, v in kv.items()]


CASES = [
    # seed, n_bars, params, spread, trade_from, hold_bars, price tick
    (1, 4000, BreakoutParams(), 0.10, 0, 120, 0.01),
    (2, 4000, BreakoutParams(direction="LONG_ONLY"), 0.10, 0, 120, 0.01),
    (3, 4000, BreakoutParams(direction="SHORT_ONLY", fvg_rule="ANY_GAP"), 0.10, 0, 30, 0.01),
    (4, 4000, BreakoutParams(fvg_rule="NONE", confirm_closes=1, max_touches=1, reject_before_break=True), 0.10, 0,
     120, 0.01),
    (5, 4000, BreakoutParams(min_rr=1.0, max_cost_r=0.0, fib_levels=(38.2, 0.0, 78.6)), 0.10, 0, 60, 0.01),
    (6, 4000, BreakoutParams(target_fib=-27.0, stop_fib=110.0, stop_buffer_ticks=0, confirm_closes=3), 0.20, 0,
     120, 0.01),
    (7, 4000, BreakoutParams(max_cost_r=0.05, max_touches=3, leg_expiry_bars=15, setup_expiry_bars=40), 0.10, 700,
     120, 0.01),
    (8, 4000, BreakoutParams(vis_boxes=4, length=3, fvg_rule="ANY_GAP"), 0.5, 0, 10, 0.5),       # coarse ticks: ties
    (9, 4000, BreakoutParams(max_cost_r=0.0, fib_levels=(50.0, 61.8, 71.0)), 0.0, 0, 5, 0.01),    # zero spread
    (10, 4000, BreakoutParams(direction="BOTH", max_touches=5, confirm_closes=1, fvg_rule="NONE", max_cost_r=0.0),
     0.30, 250, 3, 0.01),
]


@pytest.mark.parametrize("case", CASES, ids=[f"seed{c[0]}" for c in CASES])
def test_ea_v2_detector_matches_python_reference(exe, case, tmp_path):
    seed, n, params, sp, trade_from, hold_bars, tick = case
    if tick != 0.01:
        params = BreakoutParams(**{**params.__dict__, "tick_size": tick, "digits": 1})
    bars = _bars(seed, n, tick)
    bf = tmp_path / "bars.txt"
    bf.write_text("".join(" ".join(repr(float(x)) for x in b) + "\n" for b in bars))
    res = subprocess.run([str(exe), str(bf), *_cpp_args(params, sp, trade_from, hold_bars)], capture_output=True,
                         text=True)
    assert res.returncode == 0, res.stderr
    assert "lost events 0 intents 0" in res.stderr
    lines = res.stdout.splitlines()
    assert lines[-1].startswith("STATS")
    got = [json.loads(ln) for ln in lines[:-1]]
    cpp_stats = [int(x) for x in lines[-1].split()[1:]]
    det = harness_detector(bars, params, sp, trade_from=trade_from, hold_bars=hold_bars)
    exp = det.events
    keys = ("n", "id", "ev", "dir", "k", "reason")
    for i, (g, e) in enumerate(zip(got, exp)):
        assert tuple(g[k] for k in keys) == tuple(e[k] for k in keys), (i, g, e)
        for k in ("P", "SL", "TP", "O", "X"):
            if e[k] is None:
                assert g[k] is None, (i, k, g, e)
            else:
                assert g[k] == pytest.approx(e[k], abs=1e-9 * 2000), (i, k, g, e)
    assert len(got) == len(exp)
    # diagnostic counters
    assert len(cpp_stats) == len(STAT_KEYS)
    for name, v in zip(STAT_KEYS, cpp_stats):
        assert det.stats.get(name, 0) == v, (name, det.stats.get(name, 0), v)
    # the series must exercise the logic
    evs = {e["ev"] for e in exp}
    assert {"ARMED", "TOUCH", "BREAKOUT", "CONFIRM", "PLACE_LIMIT"} <= evs, sorted(evs)


def test_cases_cover_every_path():
    """Across the cases the harness must reach fills, closes, re-anchors and the main DONE reasons."""
    seen_ev, seen_reason = set(), set()
    for seed, n, params, sp, trade_from, hold_bars, tick in CASES:
        if tick != 0.01:
            params = BreakoutParams(**{**params.__dict__, "tick_size": tick, "digits": 1})
        for e in harness_run(_bars(seed, n, tick), params, sp, trade_from=trade_from, hold_bars=hold_bars):
            seen_ev.add(e["ev"])
            if e["reason"]:
                seen_reason.add(e["reason"])
    assert {"REJECT", "BREAK_FAIL", "SKIP", "CANCEL", "CLOSED", "DONE"} <= seen_ev, sorted(seen_ev)
    assert {"BROKEN", "EXPIRED", "TOUCH_LIMIT", "LEG_BROKEN", "NEW_EXTREME", "TARGET", "MISSED", "COST",
            "WARMUP"} <= seen_reason, sorted(seen_reason)


def _run_both(exe, tmp_path, bars, params, sp, trade_from=0, hold_bars=120):
    bf = tmp_path / "bars.txt"
    bf.write_text("".join(" ".join(repr(float(x)) for x in b) + "\n" for b in bars))
    res = subprocess.run([str(exe), str(bf), *_cpp_args(params, sp, trade_from, hold_bars)], capture_output=True,
                         text=True)
    assert res.returncode == 0, res.stderr
    lines = res.stdout.splitlines()
    got = [json.loads(ln) for ln in lines[:-1]]
    det = harness_detector(bars, params, sp, trade_from=trade_from, hold_bars=hold_bars)
    return got, det


def _crafted():
    from bk_scenarios import boundary_cases, scenarios

    out = []
    for name, bars in scenarios().items():
        for rule in ("ANY_GAP", "LUXALGO", "NONE"):
            out.append((f"{name}-{rule}", bars, {"fvg_rule": rule}))
        out.append((f"{name}-strict", bars, {"fvg_rule": "ANY_GAP", "reject_before_break": True}))
    for name, (bars, ov) in boundary_cases().items():
        out.append((name, bars, {"fvg_rule": "ANY_GAP", **ov}))
    return out


CRAFTED = _crafted()


@pytest.mark.parametrize("case", CRAFTED, ids=[c[0] for c in CRAFTED])
def test_ea_v2_detector_matches_python_on_crafted_sequences(exe, case, tmp_path):
    name, bars, ov = case
    params = BreakoutParams(**ov)
    got, det = _run_both(exe, tmp_path, bars, params, 0.1, hold_bars=3)
    exp = det.events
    assert [(g["n"], g["id"], g["ev"], g["dir"], g["k"], g["reason"]) for g in got] == \
        [(e["n"], e["id"], e["ev"], e["dir"], e["k"], e["reason"]) for e in exp]
    for g, e in zip(got, exp):
        for k in ("P", "SL", "TP", "O", "X"):
            assert (g[k] is None) == (e[k] is None) and (e[k] is None or g[k] == pytest.approx(e[k], abs=1e-9)), \
                (k, g, e)
