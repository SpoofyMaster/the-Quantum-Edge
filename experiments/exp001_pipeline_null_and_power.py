"""EXP001 — Pipeline null test and power test on SYNTHETIC data.

Purpose: before touching market data, prove the research pipeline (features, labels, execution
simulator, cost model, purged walk-forward, statistics) is
  (a) SPECIFIC: on a driftless random walk it must NOT report an edge (gross EV CI covers 0,
      out-of-sample AUC ~ 0.5, net EV ~ -cost);
  (b) SENSITIVE: when a known continuation edge is planted it must detect it, and we measure
      how large the edge must be to survive IC-Markets-like costs.
This is NOT evidence about real markets. All data here is synthetic.

Run:  python experiments/exp001_pipeline_null_and_power.py
Out:  results/exp001_pipeline_null_and_power.json
"""
from __future__ import annotations

import dataclasses
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe import backtest  # noqa: E402
from qe.config import ROOT, load_instruments, load_research  # noqa: E402
from qe.features import build_features  # noqa: E402
from qe.labels import OUTCOME_TARGET, triple_barrier_labels  # noqa: E402
from qe.registry import register_trial  # noqa: E402
from qe.stats import brier, reliability, trade_summary  # noqa: E402
from qe.synthetic import generate  # noqa: E402
from qe.validation import purged_train_mask, oos_mask, walk_forward_folds  # noqa: E402

EXP = "exp001_pipeline_null_and_power"
SEED = 20260926
EDGES = [0.0, 0.05, 0.10, 0.20]      # planted drift, in sigma per minute, for 20 minutes after an impulse
IMPULSE_KS = [2.5, 3.0, 3.5]          # strategy thresholds (3.0 matches the planted trigger)
FEATURES = ["ret_1", "ret_5", "ret_15", "ret_60", "rv_ratio_15_240", "impulse_z5", "impulse_z15", "eff_15",
            "eff_60", "range_z", "close_loc", "tv_imbalance_15", "tv_z", "spread_rel", "dist_prev_high",
            "dist_prev_low", "tod_sin", "tod_cos"]


def frictionless(bars: pd.DataFrame, instruments: dict) -> tuple[pd.DataFrame, dict]:
    b = bars.copy()
    for s in "ohlc":
        b["a" + s] = b["b" + s]
    inst = {k: dataclasses.replace(v, commission_per_lot_side_usd=0.0) for k, v in instruments.items()}
    return b, inst


def impulse_signals(bars, feats, k, mode):
    z = feats["impulse_z5"]
    vol_px = feats["rv_60"] * np.sqrt(15) * bars.bc
    trig = (z.abs() > k) & (z.abs().shift(1) <= k)  # first bar of crossing only
    sig = pd.DataFrame(index=bars.index[trig.fillna(False).to_numpy()])
    sgn = np.sign(z[sig.index])
    sig["direction"] = (sgn if mode == "continuation" else -sgn).astype(int)
    sig["stop_dist"] = 1.5 * vol_px[sig.index]
    sig["target_dist"] = 1.5 * sig["stop_dist"]
    return sig.dropna()


def probability_model(bars, feats, cfg, features=None):
    """Purged walk-forward logistic model for P(target before stop) of a long trade."""
    ev = bars.index[3000::5]
    stop = (feats["rv_60"] * np.sqrt(15) * bars.bc).reindex(ev)
    lab = triple_barrier_labels(bars, ev, +1, stop, 1.0, 60)
    X = feats.reindex(lab.index)[features or FEATURES]
    ok = X.notna().all(axis=1)
    X, lab = X[ok], lab[ok]
    y = (lab.outcome == OUTCOME_TARGET).astype(int).to_numpy()
    folds = walk_forward_folds(bars.index[0].tz_convert(None).normalize(), bars.index[-1].tz_convert(None), None, 30,
                               min_train_days=120)
    preds, ys = [], []
    emb = pd.Timedelta(minutes=cfg["splits"]["embargo_minutes"])
    for f in folds:
        f = type(f)(*(t.tz_localize("UTC") for t in (f.train_start, f.train_end, f.test_start, f.test_end)))
        tr = purged_train_mask(X.index, lab.exit_time, f, emb)
        te = oos_mask(X.index, f)
        if tr.sum() < 1000 or te.sum() < 100:
            continue
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=500))
        m.fit(X[tr], y[tr])
        preds.append(m.predict_proba(X[te])[:, 1])
        ys.append(y[te])
    p, yy = np.concatenate(preds), np.concatenate(ys)
    base = np.full_like(p, yy.mean())
    _, ece = reliability(p, yy)
    return {"oos_events": int(len(p)), "base_rate": float(yy.mean()), "auc": float(roc_auc_score(yy, p)),
            "brier": brier(p, yy), "brier_base_rate": brier(base, yy),
            "brier_skill": float(1 - brier(p, yy) / brier(base, yy)), "ece": ece}


def main():
    t0 = time.time()
    cfg, instruments = load_research(), load_instruments()
    out = {"experiment": EXP, "data": "SYNTHETIC (qe.synthetic.generate) - not market evidence", "seed": SEED,
           "runs": []}
    for edge in EDGES:
        bars = generate(start="2021-01-01", end="2022-01-01", edge=edge, seed=SEED)
        feats = build_features(bars)
        run = {"planted_edge_sigma_per_min": edge, "bars": int(len(bars)),
               "median_spread": float((bars.ac - bars.bc).median()), "strategies": []}
        fb, finst = frictionless(bars, instruments)
        for k in IMPULSE_KS:
            for mode in ("continuation", "reversal"):
                sig = impulse_signals(bars, feats, k, mode)
                res = {"k": k, "mode": mode, "signals": int(len(sig))}
                for label, b, inst, slip in (("gross", fb, finst, 0.0), ("net", bars, instruments, 1.0)):
                    bt = backtest.BacktestConfig(slippage_ticks=slip)
                    trades, _ = backtest.run({"EURUSD": b}, {"EURUSD": sig}, inst, cfg, bt)
                    summ = trade_summary(trades, 100_000.0)
                    summ["rejects"] = trades.attrs.get("rejects", {})
                    res[label] = summ
                register_trial(EXP, {"edge": edge, "k": k, "mode": mode}, {"net_ev_R": res["net"].get("ev_R")},
                               data_kind="synthetic")
                run["strategies"].append(res)
                print(f"edge={edge:.2f} k={k} {mode:12s} n={res['net'].get('trades', 0):5d} "
                      f"grossEV={res['gross'].get('ev_R', float('nan')):+.3f}R "
                      f"CI={np.round(res['gross'].get('ev_R_ci95', [np.nan, np.nan]), 3)} "
                      f"netEV={res['net'].get('ev_R', float('nan')):+.3f}R "
                      f"CI={np.round(res['net'].get('ev_R_ci95', [np.nan, np.nan]), 3)}", flush=True)
        run["probability_model"] = probability_model(bars, feats, cfg)
        print("  prob model:", {k: round(v, 4) if isinstance(v, float) else v for k, v in run["probability_model"].items()}, flush=True)
        out["runs"].append(run)
    out["runtime_sec"] = round(time.time() - t0, 1)
    path = ROOT / "results" / f"{EXP}.json"
    path.write_text(json.dumps(out, indent=2, default=float))
    print("wrote", path)


if __name__ == "__main__":
    main()
