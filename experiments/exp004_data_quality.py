"""EXP004 — Data quality, spread and volatility seasonality on Dukascopy M1 bid/ask (2020-01 → 2025-06).

Runs inside GitHub Actions (`research` workflow) where the data lives. Writes ONLY aggregated
statistics (no bars) to results/exp004_data_quality.json.
Answers BACKLOG D-3/D-4: coverage, gaps, OHLC sanity, price levels, spread by hour/session/year,
volatility by hour/session, and cost-in-R recomputed with MEASURED (Dukascopy) spreads.
Dukascopy spreads are a proxy for, not a measurement of, IC Markets Raw spreads.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe.config import ROOT, load_instruments, load_research  # noqa: E402
from qe.costs import commission_in_price_units  # noqa: E402
from qe.data.schema import mid, quality_report, spread  # noqa: E402
from qe.data.store import available_months, load_m1  # noqa: E402
from qe.sessions import session_frame  # noqa: E402

EXP = "exp004_data_quality"
PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.10, "XAGUSD": 0.01,
       "AUDUSD": 0.0001, "USDCAD": 0.0001, "USDCHF": 0.0001}


def _r(x, k=3):
    return None if x is None or not np.isfinite(x) else round(float(x), k)


def analyse(sym: str, cfg: dict, inst) -> dict:
    df = load_m1(sym, cfg["splits"]["data_start"], cfg=cfg)
    pip = PIP[sym]
    out = {"months_available": len(available_months(sym)), "bars": int(len(df)),
           "spread_source": df["spread_source"].value_counts().to_dict() if "spread_source" in df else {},
           "first": str(df.index[0]), "last": str(df.index[-1])}
    out["quality_by_year"] = {str(y): quality_report(g) for y, g in df.groupby(df.index.year)}
    out["close_range_by_year"] = {str(y): [_r(g.bc.min(), 4), _r(g.bc.max(), 4)] for y, g in df.groupby(df.index.year)}
    sp = spread(df) / pip
    ses = session_frame(df.index, cfg)
    r1 = np.log(mid(df)).diff()
    absr_pips = (r1.abs() * mid(df)) / pip
    # 60-minute rolling high-low range (pips) as a scale for stop distances
    rng60 = ((df.bh.rolling(60).max() - df.bl.rolling(60).min()) / pip)
    hour = df.index.hour
    out["spread_pips_by_utc_hour"] = {int(h): {"median": _r(g.median()), "p90": _r(g.quantile(0.9))}
                                      for h, g in sp.groupby(hour)}
    out["spread_pips_by_year"] = {str(y): {"median": _r(g.median()), "p90": _r(g.quantile(0.9)),
                                           "p99": _r(g.quantile(0.99))} for y, g in sp.groupby(df.index.year)}
    out["abs_ret_pips_by_utc_hour"] = {int(h): _r(g.median()) for h, g in absr_pips.groupby(hour)}
    sessions = {"asia_only": ses.asia & ~ses.london & ~ses.newyork, "london_only": ses.london & ~ses.newyork,
                "overlap": ses.overlap, "newyork_only": ses.newyork & ~ses.london,
                "off_hours": ~(ses.asia | ses.london | ses.newyork), "rollover_blackout": ses.rollover_blackout}
    comm = commission_in_price_units(inst, float(df.bc.iloc[-1])) / pip
    out["commission_rt_pips_at_last_price"] = _r(comm)
    per = {}
    for name, m in sessions.items():
        m = m.to_numpy()
        if m.sum() == 0:
            continue
        med_sp = float(sp[m].median())
        med_rng = float(rng60[m].median())
        cost = med_sp + comm + 2 * inst.tick_size / pip  # spread + commission + 1 tick slippage per side
        per[name] = {"share_of_bars": _r(m.mean()), "spread_median": _r(med_sp), "spread_p90": _r(float(sp[m].quantile(0.9))),
                     "abs_ret_1m_median": _r(float(absr_pips[m].median())), "range_60m_median": _r(med_rng),
                     "rt_cost_pips": _r(cost),
                     "cost_R_stop_0p5_range60": _r(cost / (0.5 * med_rng)),
                     "cost_R_stop_1p0_range60": _r(cost / med_rng)}
    out["by_session"] = per
    return out


def main():
    cfg, instruments = load_research(), load_instruments()
    syms = [s for s in instruments if available_months(s)]
    res = {"experiment": EXP, "data": "M1 bars from the source in each symbol's spread_source field "
                                      "('quoted' = Dukascopy bid/ask; 'assumed' = HistData bid + modelled spread, "
                                      "spread statistics then carry NO information)", "symbols": {}}
    for s in syms:
        print("analysing", s, flush=True)
        res["symbols"][s] = analyse(s, cfg, instruments[s])
        print(json.dumps({k: v for k, v in res["symbols"][s].items() if k in ("bars", "first", "last", "by_session")},
                         indent=1), flush=True)
    (ROOT / "results" / f"{EXP}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
