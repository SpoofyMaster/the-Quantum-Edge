"""EXP005 — Event studies for market hypotheses H-01..H-05, H-08 on the DEVELOPMENT period only
(2020-01-01 .. 2023-12-31). Validation (2024-01 .. 2025-06) is NOT touched here; it is reserved for
confirming the few pre-registered survivors. The final test (>= 2025-07) is locked.

For every event (decided at the CLOSE of bar t, all inputs causal) we measure the forward MID
return from the OPEN of bar t+1 to the CLOSE of bar t+H, signed by the hypothesised direction,
for H in {5, 15, 30, 60, 120} minutes. Reported in pips and in units of the round-trip cost
(median quoted spread at t+1 + IC Markets commission [UNVERIFIED] + 1 tick slippage per side).
A cell is interesting only if mean signed move / cost > 1 with a bootstrap CI that excludes 0.
Every cell counts as a trial in results/trial_registry.jsonl (data_kind="market_dev").
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe.config import ROOT, load_instruments, load_research  # noqa: E402
from qe.costs import commission_in_price_units  # noqa: E402
from qe.data.store import available_months, load_m1  # noqa: E402
from qe.events import all_events  # noqa: E402
from qe.features import build_features  # noqa: E402
from qe.registry import register_trial  # noqa: E402
from qe.sessions import session_frame  # noqa: E402
from qe.stats import bootstrap_ci  # noqa: E402

EXP = "exp005_event_study_dev"
HORIZONS = [5, 15, 30, 60, 120]
PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.10, "XAGUSD": 0.01}
DEV_START, DEV_END = "2020-01-01", "2024-01-01"


def forward_signed(df, pos, d, H):
    n = len(df)
    mo = ((df.bo + df.ao) / 2).to_numpy()
    mc = ((df.bc + df.ac) / 2).to_numpy()
    e = pos + 1
    x = pos + H
    ok = x < n
    out = np.full(len(pos), np.nan)
    out[ok] = d[ok] * (mc[x[ok]] - mo[e[ok]])
    # discard windows that span a data gap > 30 minutes (weekend / outage)
    t = df.index.as_unit("ns").asi8
    span = np.full(len(pos), np.inf)
    span[ok] = (t[x[ok]] - t[e[ok]]) / 6e10
    out[span > H + 30] = np.nan
    return out


def analyse(sym, cfg, inst):
    df = load_m1(sym, DEV_START, DEV_END, cfg=cfg)
    f = build_features(df)
    ses = session_frame(df.index, cfg)
    pip = PIP[sym]
    comm = commission_in_price_units(inst, float(df.bc.median()))
    spread_next = (df.ao - df.bo).shift(-1)
    fams = all_events(df, f, ses, sym)
    res = {}
    for name, (mask, d) in fams.items():
        mask = mask.fillna(False) & ~ses.rollover_blackout & f["seasonal_sigma"].notna()
        pos = np.flatnonzero(mask.to_numpy())
        if len(pos) < 30:
            res[name] = {"events": int(len(pos))}
            continue
        dd = np.asarray(d, float)[pos] if not np.isscalar(d) else np.full(len(pos), d)
        cost = np.nanmedian(spread_next.to_numpy()[pos]) + comm + 2 * inst.tick_size
        cell = {"events": int(len(pos)), "events_per_year": round(len(pos) / 4.0, 1),
                "rt_cost_pips": round(cost / pip, 3), "by_h": {}}
        years = df.index[pos].year
        for H in HORIZONS:
            r = forward_signed(df, pos, dd, H)
            v = ~np.isnan(r)
            mean, lo, hi = bootstrap_ci(r[v] / pip, B=1000, mean_block=5.0)
            by_year = {str(y): round(float(np.nanmean(r[(years == y) & v]) / pip), 3) for y in sorted(set(years))}
            cell["by_h"][H] = {"n": int(v.sum()), "mean_pips": round(mean, 3), "ci95": [round(lo, 3), round(hi, 3)],
                               "hit_rate": round(float((r[v] > 0).mean()), 4),
                               "mean_over_cost": round(mean / (cost / pip), 3), "mean_pips_by_year": by_year}
            register_trial(EXP, {"symbol": sym, "family": name, "H": H},
                           {"mean_over_cost": cell["by_h"][H]["mean_over_cost"], "ci95": [lo, hi]}, "market_dev")
        res[name] = cell
        best = max(cell["by_h"].items(), key=lambda kv: kv[1]["mean_over_cost"])
        print(f"{sym} {name:34s} n={len(pos):6d} best H={best[0]:3d} mean={best[1]['mean_pips']:+.2f}p "
              f"CI={best[1]['ci95']} x_cost={best[1]['mean_over_cost']:+.2f}", flush=True)
    return res


def add_fdr(out, q=0.10):
    """Benjamini-Hochberg across ALL cells (symbol x family x horizon). Picking the best horizon on
    noise produces 'significant' cells (seen on synthetic data), so only q-values are trusted."""
    from scipy.stats import norm
    cells = []
    for sym, fams in out["symbols"].items():
        for fam, cell in fams.items():
            for H, c in cell.get("by_h", {}).items():
                se = (c["ci95"][1] - c["ci95"][0]) / 3.92
                z = c["mean_pips"] / se if se > 0 else 0.0
                c["p_two_sided"] = float(2 * (1 - norm.cdf(abs(z))))
                cells.append(c)
    ps = np.array([c["p_two_sided"] for c in cells])
    order = np.argsort(ps)
    m = len(ps)
    qv = np.empty(m)
    run = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        run = min(run, ps[i] * m / rank)
        qv[i] = run
    for c, qq in zip(cells, qv):
        c["q_bh"] = round(float(qq), 4)
    out["fdr"] = {"cells": m, "q_threshold": q,
                  "survivors": [(sym, fam, H, c["mean_over_cost"], c["q_bh"])
                                for sym, fams in out["symbols"].items() for fam, cell in fams.items()
                                for H, c in cell.get("by_h", {}).items() if c["q_bh"] <= q]}
    print("FDR survivors (q<=%.2f):" % q, out["fdr"]["survivors"], flush=True)


def main():
    cfg, instruments = load_research(), load_instruments()
    out = {"experiment": EXP, "period": [DEV_START, DEV_END], "data": "Dukascopy M1 bid/ask (proxy)",
           "note": "descriptive event study; mean_over_cost > 1 with CI excluding 0 is required to proceed",
           "symbols": {}}
    for sym in instruments:
        if not available_months(sym):
            continue
        out["symbols"][sym] = analyse(sym, cfg, instruments[sym])
    add_fdr(out)
    (ROOT / "results" / f"{EXP}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
