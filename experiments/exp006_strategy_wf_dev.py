"""EXP006 — Executable strategies from EXP005 candidate families, DEVELOPMENT period only.

Candidates = EXP005 cells with q_bh <= 0.10 (FDR survivors), or if none, the 3 cells with the highest
mean_over_cost that have a CI excluding 0 (explicitly labelled 'exploratory', not evidence).
For each (symbol, family, horizon H):
  1. Rule strategy with the full execution/risk stack (qe.backtest): entry next-bar open at ask/bid,
     stop = 1.0 x expected move over H (max of seasonal and realised sigma), target = 1.5 x stop,
     time exit at H (<= 120), rollover exit, 0.20% risk incl. costs, 1% daily lockout, 1 tick slippage.
  2. Meta-label filter: purged anchored walk-forward logistic model on causal features predicting
     P(trade R > 0); trade only when p > 0.5 + margin. Compared against a COST/REGIME-ONLY baseline
     model (rule M-03): the directional filter must beat it out of sample.
Stress: +50% spread proxy (extra slippage) and +1 bar latency.
Outputs results/exp006_strategy_wf_dev.json; every variant is registered as a trial.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe import backtest  # noqa: E402
from qe.config import ROOT, load_instruments, load_research  # noqa: E402
from qe.data.store import load_m1  # noqa: E402
from qe.events import all_events  # noqa: E402
from qe.features import build_features  # noqa: E402
from qe.registry import count_trials, register_trial  # noqa: E402
from qe.sessions import session_frame  # noqa: E402
from qe.stats import deflated_sharpe, mc_drawdown, trade_summary  # noqa: E402
from qe.validation import oos_mask, purged_train_mask, walk_forward_folds  # noqa: E402

EXP = "exp006_strategy_wf_dev"
DEV_START, DEV_END = "2020-01-01", "2024-01-01"
DIR_FEATS = ["ret_5", "ret_15", "ret_60", "impulse_ds5", "impulse_ds15", "close_loc", "tv_imbalance_15",
             "dist_prev_high", "dist_prev_low", "eff_15", "eff_60"]
COST_FEATS = ["spread_rel", "vol_regime_60", "rv_ratio_15_240", "range_z", "tv_z", "tod_sin", "tod_cos"]


def candidates(exp005: dict, max_n: int = 6) -> list[tuple[str, str, int, str]]:
    """FDR survivors (q<=0.10) in the hypothesised direction, plus H-01 survivors with NEGATIVE sign
    re-expressed as the H-11 fade family (a hypothesis generated on this same dev data). One horizon
    per (symbol, family) — the strongest — ranked by |mean_over_cost|, top `max_n`."""
    best = {}
    for s, f, h, x, _ in exp005.get("fdr", {}).get("survivors", []):
        if x > 0:
            fam = f
        elif f.startswith("H01_"):
            fam, x = f.replace("H01_", "H11_").replace("_active_cont", "_active_fade"), -x
        else:
            continue
        if x > best.get((s, fam), (0, 0))[0]:
            best[(s, fam)] = (x, int(h))
    ranked = sorted(((x, s, fam, h) for (s, fam), (x, h) in best.items()), reverse=True)[:max_n]
    return [(s, fam, h, f"fdr_survivor x_cost={x:.2f}") for x, s, fam, h in ranked]


def signals_for(df, f, mask, d, H, stop_mult=1.0, target_mult=1.5):
    idx = df.index[mask.fillna(False).to_numpy()]
    sigma = np.maximum(f["seasonal_sigma"], f["rv_60"]).reindex(idx)
    move = sigma * np.sqrt(H) * df.bc.reindex(idx)
    dd = pd.Series(np.asarray(d, float) if not np.isscalar(d) else d, index=df.index).reindex(idx)
    tgt = target_mult * move if target_mult else move * np.nan
    sig = pd.DataFrame({"direction": dd, "stop_dist": stop_mult * move, "target_dist": tgt}, index=idx)
    return sig.dropna(subset=["direction", "stop_dist"])


def meta_filter(trades, f, cfg, feats, margin=0.03):
    """Walk-forward P(R>0) on causal features at decision time; returns kept-trade mask + OOS stats."""
    F = f.reindex(trades.decision_time)[feats]
    F = F.loc[:, F.notna().mean() > 0.9]  # drop features the data source cannot support (e.g. volume)
    X = F.to_numpy()
    y = (trades.R.to_numpy() > 0).astype(int)
    t = pd.DatetimeIndex(trades.decision_time)
    ends = pd.Series(pd.DatetimeIndex(trades.exit_time), index=t)
    folds = walk_forward_folds(t[0].tz_convert(None).normalize(), t[-1].tz_convert(None), None, 91, min_train_days=365)
    emb = pd.Timedelta(minutes=cfg["splits"]["embargo_minutes"])
    keep = np.zeros(len(trades), bool)
    scored = np.zeros(len(trades), bool)
    for fo in folds:
        fo = type(fo)(*(x.tz_localize("UTC") for x in (fo.train_start, fo.train_end, fo.test_start, fo.test_end)))
        tr = purged_train_mask(t, ends, fo, emb) & ~np.isnan(X).any(1)
        te = oos_mask(t, fo) & ~np.isnan(X).any(1)
        if tr.sum() < 100 or te.sum() == 0 or len(set(y[tr])) < 2:
            continue
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=500)).fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[:, 1]
        keep[np.flatnonzero(te)] = p > y[tr].mean() + margin
        scored[np.flatnonzero(te)] = True
    return keep, scored


def evaluate(trades, label, n_trials, var_sr=0.01):
    s = trade_summary(trades, 100_000.0)
    if s.get("trades", 0) > 10:
        s["dsr"] = deflated_sharpe(trades.R.to_numpy(), max(n_trials, 1), var_sr)
        s.update(mc_drawdown(trades.pnl_usd.to_numpy() / 1000.0, B=500))  # in % of 100k equity
        s["by_year_R"] = {str(y): round(float(g.R.sum()), 2) for y, g in trades.groupby(pd.DatetimeIndex(trades.entry_time).year)}
    s["variant"] = label
    return s


def main():
    cfg, inst = load_research(), load_instruments()
    e5 = json.loads((ROOT / "results" / "exp005_event_study_dev.json").read_text())
    cands = candidates(e5)
    out = {"experiment": EXP, "period": [DEV_START, DEV_END], "candidates": cands, "results": []}
    cache = {}
    for sym, fam, H, why in cands:
        if sym not in cache:
            df = load_m1(sym, DEV_START, DEV_END, cfg=cfg)
            f = build_features(df)
            cache = {sym: (df, f, all_events(df, f, session_frame(df.index, cfg), sym))}
        df, f, evs = cache[sym]
        mask, d = evs[fam]
        sig = signals_for(df, f, mask, d, H)
        base_cfg = dict(max_holding_minutes=H)
        row = {"symbol": sym, "family": fam, "H": H, "selection": why, "signals": int(len(sig)), "variants": {}}
        for label, extra in (("base", {}), ("stress_slip3", {"slippage_ticks": 3.0}), ("stress_latency1", {"latency_bars": 1})):
            bt = backtest.BacktestConfig(**base_cfg, **extra)
            tr, _ = backtest.run({sym: df}, {sym: sig}, inst, cfg, bt)
            register_trial(EXP, {"symbol": sym, "family": fam, "H": H, "variant": label}, {}, "market_dev")
            row["variants"][label] = evaluate(tr, label, count_trials("market_dev")) if len(tr) else {"trades": 0}
            if label == "base" and len(tr) > 200:
                for name, feats in (("meta_directional", DIR_FEATS + COST_FEATS), ("meta_cost_only_baseline", COST_FEATS)):
                    keep, scored = meta_filter(tr, f, cfg, feats)
                    register_trial(EXP, {"symbol": sym, "family": fam, "H": H, "variant": name}, {}, "market_dev")
                    row["variants"][name] = evaluate(tr[keep], name, count_trials("market_dev"))
                    row["variants"][name]["oos_scored_trades"] = int(scored.sum())
                    row["variants"][name + "_unfiltered_same_oos_window"] = evaluate(tr[scored], "unfiltered_oos", count_trials("market_dev"))
        # exit variant B: time exit at H with a wide catastrophe stop (closest to what EXP005 measured)
        sigB = signals_for(df, f, mask, d, H, stop_mult=2.0, target_mult=None)
        trB, _ = backtest.run({sym: df}, {sym: sigB}, inst, cfg, backtest.BacktestConfig(**base_cfg))
        register_trial(EXP, {"symbol": sym, "family": fam, "H": H, "variant": "exitB_time_2x_stop"}, {}, "market_dev")
        row["variants"]["exitB_time_2x_stop"] = evaluate(trB, "exitB_time_2x_stop", count_trials("market_dev")) if len(trB) else {"trades": 0}
        # cost stress: whole modelled spread profile x2 (bid-only data) — signals unchanged
        df2 = load_m1(sym, DEV_START, DEV_END, cfg=cfg, spread_scale=2.0)
        tr2, _ = backtest.run({sym: df2}, {sym: sig}, inst, cfg, backtest.BacktestConfig(**base_cfg))
        register_trial(EXP, {"symbol": sym, "family": fam, "H": H, "variant": "stress_spread2x"}, {}, "market_dev")
        row["variants"]["stress_spread2x"] = evaluate(tr2, "stress_spread2x", count_trials("market_dev")) if len(tr2) else {"trades": 0}
        del df2
        out["results"].append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "variants"}),
              {k: (v.get("trades"), v.get("ev_R"), v.get("ev_R_ci95")) for k, v in row["variants"].items()}, flush=True)
    out["trial_count_market_dev"] = count_trials("market_dev")
    (ROOT / "results" / f"{EXP}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
