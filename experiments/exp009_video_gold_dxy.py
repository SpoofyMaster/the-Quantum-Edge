"""EXP009 — first test of the video strategy (tomtrades gold reversal + DXY entry-model inversion) with the Python
reference implementation (qe/video_strategy), on XAUUSD M1 2020-01 .. 2025-06 (dev + validation; the final-test period
>= 2025-07-01 stays locked). This is a REPLICATION test, not an optimisation: every variant below is fixed in this file
before any market data was seen (the commit that adds this file is the pre-registration). No parameter may be changed
after seeing the result; a variant that fails is REJECTED, not re-tuned.

Variants (research/VIDEO_REPLICATION_TEST.md, research/AMBIGUITIES.md):
  V0  VIDEO_DEFAULT      H1, BREAK entry, DXY FULL                      (the rulebook defaults)
  V1  PULLBACK_50        H1, 50% pullback entry, DXY FULL               (A-01)
  V2  M15                M15 candle (experimental timings), BREAK, FULL (A-07)
  V3  H1_AND_M15         both trackers, BREAK, FULL                     (closest to what the video shows)
  V4  ABLATION_DXY_OFF   H1, BREAK, no DXY gate                         (measures the gate; NOT the strategy)
  V0  stress             spread x2; slippage 3 ticks                    (cost robustness of V0)

Acceptance (docs/research/hypotheses.md): net EV > 0 with the 95% stationary-bootstrap CI above 0, DSR > 0.95 given the
trial count, positive in >= 2 of 3 sub-periods, and still positive under the cost stress.
DXY: HistData UDXUSD (ICE dollar index, bid-only). Gold: HistData XAUUSD (bid-only, modelled spreads).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe.config import ROOT, load_instruments, load_research  # noqa: E402
from qe.data.store import load_m1  # noqa: E402
from qe.registry import count_trials, register_trial  # noqa: E402
from qe.video_strategy import Params, m15_preset  # noqa: E402
from qe.video_strategy.dxy import ohlc_from_bid_frame  # noqa: E402
from qe.video_strategy.engine import run  # noqa: E402
from qe.video_strategy.report import performance  # noqa: E402

EXP = "exp009_video_gold_dxy"
START, END = "2020-01-01", "2025-07-01"
SUBPERIODS = [("2020-01-01", "2021-12-31"), ("2022-01-01", "2023-12-31"), ("2024-01-01", "2025-06-30")]
DATA_KIND = "market_video"

H1 = Params()
VARIANTS = [
    ("V0_VIDEO_DEFAULT", [H1], {}),
    ("V1_PULLBACK_50", [replace(H1, entry_mode="PULLBACK_50")], {}),
    ("V2_M15", [m15_preset()], {}),
    ("V3_H1_AND_M15", [H1, m15_preset()], {}),
    ("V4_ABLATION_DXY_OFF", [replace(H1, dxy_mode="OFF")], {}),
    ("V0_STRESS_SPREAD2X", [H1], {"spread_scale": 2.0}),
    ("V0_STRESS_SLIP3", [H1], {"slippage_ticks": 3.0}),
]


def subperiod_ev(trades: pd.DataFrame) -> dict:
    out = {}
    if trades.empty:
        return out
    et = pd.to_datetime(trades.entry_time, utc=True)
    for a, b in SUBPERIODS:
        m = (et >= pd.Timestamp(a, tz="UTC")) & (et <= pd.Timestamp(b, tz="UTC") + pd.Timedelta(days=1))
        g = trades[m]
        out[f"{a[:4]}-{b[:4]}"] = {"trades": int(len(g)), "ev_R": float(g.R.mean()) if len(g) else None}
    return out


def main() -> None:
    cfg, inst = load_research(), load_instruments()
    commit = subprocess.run(["git", "log", "-1", "--format=%H", "--", __file__], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    out = {"experiment": EXP, "period": [START, END], "spec_commit": commit, "variants": {}, "notes": []}
    gold_by_scale = {}
    dxy_raw = load_m1("UDXUSD", START, END, cfg=cfg)
    dxy = ohlc_from_bid_frame(dxy_raw)
    out["data"] = {"dxy_bars": int(len(dxy)), "dxy_first": str(dxy.index.min()), "dxy_last": str(dxy.index.max())}
    for name, params, extra in VARIANTS:
        scale = extra.get("spread_scale", 1.0)
        if scale not in gold_by_scale:
            gold_by_scale[scale] = load_m1("XAUUSD", START, END, cfg=cfg, spread_scale=scale)
        gold = gold_by_scale[scale]
        out["data"]["gold_bars"] = int(len(gold))
        t0 = time.time()
        res = run(gold, dxy, params, inst["XAUUSD"], cfg, slippage_ticks=extra.get("slippage_ticks", 1.0),
                  record_setups=False)
        register_trial(EXP, {"variant": name, "params": [p.__dict__ for p in params], **extra}, {}, DATA_KIND)
        n_trials = count_trials(DATA_KIND)
        perf = performance(res.trades, n_trials=n_trials)
        perf["dsr_project_wide"] = None
        if perf.get("trades", 0) > 10:
            from qe.stats import deflated_sharpe
            perf["dsr_project_wide"] = float(deflated_sharpe(res.trades.R.to_numpy(), count_trials(), 0.01))
        perf["subperiods"] = subperiod_ev(res.trades)
        perf["setup_reasons"] = dict(sorted(res.counters.items(), key=lambda kv: -kv[1]))
        perf["runtime_s"] = round(time.time() - t0, 1)
        out["variants"][name] = perf
        print(name, {k: perf.get(k) for k in ("trades", "win_rate", "ev_R", "ev_R_ci95", "profit_factor", "dsr")},
              flush=True)
    v0 = out["variants"]["V0_VIDEO_DEFAULT"]
    sub = [s["ev_R"] for s in v0.get("subperiods", {}).values() if s["ev_R"] is not None]
    stress_ok = all(out["variants"][k].get("ev_R", -1) > 0 for k in ("V0_STRESS_SPREAD2X", "V0_STRESS_SLIP3"))
    out["acceptance_V0"] = {
        "ci_above_0": bool(v0.get("ev_R_ci95") and v0["ev_R_ci95"][0] > 0),
        "dsr_gt_0.95": bool(v0.get("dsr", 0) > 0.95),
        "positive_in_2_of_3_subperiods": bool(sum(e > 0 for e in sub) >= 2),
        "survives_cost_stress": bool(stress_ok),
    }
    out["acceptance_V0"]["accepted"] = all(out["acceptance_V0"].values())
    (ROOT / "results" / f"{EXP}.json").write_text(json.dumps(out, indent=1, default=str))
    print("ACCEPTED" if out["acceptance_V0"]["accepted"] else "REJECTED", out["acceptance_V0"])


if __name__ == "__main__":
    main()
