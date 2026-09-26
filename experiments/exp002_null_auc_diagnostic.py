"""EXP002 — Diagnose the AUC ~0.51 seen by the EXP001 probability model on NULL synthetic data.

Question: is the small out-of-sample AUC on a driftless random walk caused by leakage, or by
features that legitimately predict the COST-driven base rate (spread, volatility regime)?
Test: repeat the model (a) on frictionless null bars (bid = ask) and (b) with friction but only
cost/regime features (spread_rel, rv_ratio, tod) vs only directional features.
If (a) gives AUC ~0.50 and the cost-only model reproduces the 0.51, the effect is cost structure,
not leakage and not a directional edge. SYNTHETIC data only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp001_pipeline_null_and_power as e1  # noqa: E402
from qe.config import ROOT, load_instruments, load_research  # noqa: E402
from qe.features import build_features  # noqa: E402
from qe.synthetic import generate  # noqa: E402

EXP = "exp002_null_auc_diagnostic"
COST_FEATS = ["spread_rel", "rv_ratio_15_240", "range_z", "tv_z", "tod_sin", "tod_cos"]
DIR_FEATS = ["ret_1", "ret_5", "ret_15", "ret_60", "impulse_z5", "impulse_z15", "close_loc", "tv_imbalance_15",
             "dist_prev_high", "dist_prev_low"]


def main():
    cfg, inst = load_research(), load_instruments()
    bars = generate(start="2021-01-01", end="2022-01-01", edge=0.0, seed=e1.SEED)
    feats = build_features(bars)
    out = {"experiment": EXP, "data": "SYNTHETIC null (same seed as EXP001)"}
    fb, _ = e1.frictionless(bars, inst)
    # spread_rel is undefined (0/0) without a spread, so it is dropped in the frictionless run
    no_spread = [f for f in e1.FEATURES if f != "spread_rel"]
    out["frictionless_all_features_ex_spread"] = e1.probability_model(fb, build_features(fb), cfg, no_spread)
    for name, fs in (("friction_cost_features_only", COST_FEATS), ("friction_directional_features_only", DIR_FEATS),
                     ("friction_all_features", e1.FEATURES)):
        out[name] = e1.probability_model(bars, feats, cfg, fs)
    for k, v in out.items():
        print(k, v)
    (ROOT / "results" / f"{EXP}.json").write_text(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
