"""EXP010 — first test of the BPR+FVG EA setups (hypothesis H-13, owner sketch 2026-10-07) with the Python reference
(qe/strategies/bpr_fvg.py, identical decisions to mql5/BprFvgEA), on XAUUSD 2020-01 .. 2025-06. Dev and validation
are included; the final-test period >= 2025-07-01 stays locked.

This is a REPLICATION test of fixed rules, not an optimisation. Every variant below, and every default in
research/indicators/BPR_FVG_EA_SPEC.md, was fixed before any market data was seen. The commit that adds this file is
the pre-registration. No parameter may be changed after seeing the result: a variant that fails is REJECTED, not
re-tuned.

Variants:
  V0  BPR_LIMIT_M1             EA defaults: BPR setups, sweep + MSS, front-run LIMIT, TP1 50% + TP2, M1
  V1  BPR_CONFIRM_M1           as V0 with the CONFIRM (rejection candle) entry
  V2  BPR_LIMIT_M1_NO_FILTERS  as V0 without sweep and MSS (measures the filters; NOT the strategy)
  V3  FVG_LIMIT_M1             FVG setups instead of BPR
  V4  BPR_LIMIT_M5             as V0 on M5 bars built from M1 bid bars
  V0  stress                   spread x2; slippage 3 ticks

Execution model: spec section 5 (bar-based, conservative same-bar rules).
Costs:
  - spread: HistData is bid-only, so the time-of-day spread model is used (assumed, not observed);
  - commission: 3.50 USD per lot per side (UNVERIFIED);
  - slippage: 1 tick.
Risk: 0.20 % per trade including costs, daily lockout at -5R, holding <= 120 min.
Sessions: entries from 08:00 Europe/London to 14:45 America/New_York, Monday to Friday; flat at 16:44 New York.

Acceptance (as EXP009, applied to V0):
  - net EV > 0 with the 95 % stationary-bootstrap CI above 0;
  - DSR > 0.95 given the trial count;
  - positive in >= 2 of 3 sub-periods;
  - still positive under both cost stresses.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe.config import ROOT, load_instruments, load_research  # noqa: E402
from qe.data.store import load_m1  # noqa: E402
from qe.registry import count_trials, register_trial  # noqa: E402
from qe.sessions import fx_trading_day  # noqa: E402
from qe.strategies.bpr_fvg import StrategyParams, simulate  # noqa: E402
from qe.video_strategy.report import performance  # noqa: E402

EXP = "exp010_bpr_fvg_ea"
SYMBOL = "XAUUSD"
START, END = "2020-01-01", "2025-07-01"
SUBPERIODS = [("2020-01-01", "2021-12-31"), ("2022-01-01", "2023-12-31"), ("2024-01-01", "2025-06-30")]
DATA_KIND = "market_bpr_ea"
EQUITY0, RISK_PCT = 100_000.0, 0.20

BASE = dict(tick_size=0.01, digits=2, contract_size=100.0, commission_per_lot_side=3.50)
VARIANTS = [
    ("V0_BPR_LIMIT_M1", "M1", StrategyParams(**BASE), {}),
    ("V1_BPR_CONFIRM_M1", "M1", StrategyParams(entry_mode="CONFIRM", **BASE), {}),
    ("V2_BPR_LIMIT_M1_NO_FILTERS", "M1", StrategyParams(use_sweep=False, use_mss=False, **BASE), {}),
    ("V3_FVG_LIMIT_M1", "M1", StrategyParams(source="FVG", **BASE), {}),
    ("V4_BPR_LIMIT_M5", "M5", StrategyParams(**BASE), {}),
    ("V0_STRESS_SPREAD2X", "M1", StrategyParams(**BASE), {"spread_scale": 2.0}),
    ("V0_STRESS_SLIP3", "M1", StrategyParams(slippage_ticks=3.0, **BASE), {}),
]


def to_m5(df: pd.DataFrame) -> pd.DataFrame:
    """M5 bid OHLC from M1 bid bars (bar-open labels). The M5 spread is the spread of its first M1 bar."""
    g = df.resample("5min", label="left", closed="left")
    out = pd.DataFrame({"bo": g["bo"].first(), "bh": g["bh"].max(), "bl": g["bl"].min(), "bc": g["bc"].last(),
                        "sp": (df["ao"] - df["bo"]).resample("5min", label="left", closed="left").first()})
    return out.dropna()


def session_arrays(idx: pd.DatetimeIndex) -> tuple[list, list, list, list]:
    """entry_ok / cancel_now / flat_now / fx_day per bar open (spec sections 1 and 5)."""
    ldn = idx.tz_convert("Europe/London")
    ny = idx.tz_convert("America/New_York")
    ldn_min = ldn.hour * 60 + ldn.minute
    ny_min = ny.hour * 60 + ny.minute
    weekday = ny.dayofweek < 5
    entry_ok = weekday & (ldn_min >= 8 * 60) & (ny_min < 14 * 60 + 45)
    flat_now = ny_min >= 16 * 60 + 44
    fx = fx_trading_day(idx)
    return (list(map(bool, entry_ok)), [not bool(x) for x in entry_ok], list(map(bool, flat_now)), list(fx))


def run_variant(frame: pd.DataFrame, params: StrategyParams) -> tuple[pd.DataFrame, dict]:
    idx = frame.index
    bars = list(zip(frame["bo"].to_numpy(float), frame["bh"].to_numpy(float), frame["bl"].to_numpy(float),
                    frame["bc"].to_numpy(float)))
    spreads = frame["sp"].to_numpy(float).tolist()
    times = (idx.as_unit("ns").asi8 // 1_000_000_000).tolist()
    entry_ok, cancel_now, flat_now, fx = session_arrays(idx)
    res = simulate(bars, spreads, times, entry_ok, cancel_now, flat_now, fx, params)
    rows = []
    for t in res.trades:
        rows.append({
            "entry_time": idx[t["fill_bar"]], "exit_time": idx[t["exit_bar"]], "direction": t["dir"],
            "src": t["src"], "R": t["R"], "pnl_usd": t["R"] * EQUITY0 * RISK_PCT / 100.0,
            "outcome": 1 if t["R"] > 0 else -1, "exit_reason": t["exit_reason"],
        })
    trades = pd.DataFrame(rows)
    reasons: dict[str, int] = {}
    for s in res.setups:
        key = s.get("status", "?") + (":" + s["reason"] if s.get("reason") else "")
        reasons[key] = reasons.get(key, 0) + 1
    return trades, {"counters": res.counters, "setup_outcomes": dict(sorted(reasons.items(), key=lambda kv: -kv[1]))}


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
    assert inst[SYMBOL].tick_size == BASE["tick_size"] and inst[SYMBOL].contract_size == BASE["contract_size"]
    commit = subprocess.run(["git", "log", "-1", "--format=%H", "--", __file__], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    out = {"experiment": EXP, "symbol": SYMBOL, "period": [START, END], "spec_commit": commit, "variants": {},
           "data": {}, "notes": ["HistData bid-only: spreads are modelled (assumed), not observed."]}
    frames: dict[tuple[str, float], pd.DataFrame] = {}
    for name, tf, params, extra in VARIANTS:
        scale = extra.get("spread_scale", 1.0)
        key = (tf, scale)
        if key not in frames:
            m1 = load_m1(SYMBOL, START, END, cfg=cfg, spread_scale=scale)
            m1 = m1.assign(sp=m1["ao"] - m1["bo"])
            frames[key] = m1[["bo", "bh", "bl", "bc", "sp"]] if tf == "M1" else to_m5(m1)
            out["data"][f"{tf}_x{scale}"] = {"bars": int(len(frames[key])), "first": str(frames[key].index.min()),
                                              "last": str(frames[key].index.max())}
        t0 = time.time()
        trades, diag = run_variant(frames[key], params)
        register_trial(EXP, {"variant": name, "tf": tf, "params": asdict(params), **extra}, {}, DATA_KIND)
        perf = performance(trades, equity0=EQUITY0, n_trials=count_trials(DATA_KIND))
        perf["dsr_project_wide"] = None
        if perf.get("trades", 0) > 10:
            from qe.stats import deflated_sharpe
            perf["dsr_project_wide"] = float(deflated_sharpe(trades.R.to_numpy(), count_trials(), 0.01))
            perf["by_source"] = {k: {"trades": int(len(g)), "ev_R": float(g.R.mean())} for k, g in trades.groupby("src")}
            perf["exit_reasons"] = {k: int(v) for k, v in trades.exit_reason.value_counts().items()}
            perf["R_quantiles"] = {q: float(np.quantile(trades.R, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)}
        perf["subperiods"] = subperiod_ev(trades)
        perf.update(diag)
        perf["runtime_s"] = round(time.time() - t0, 1)
        out["variants"][name] = perf
        print(name, {k: perf.get(k) for k in ("trades", "win_rate", "ev_R", "ev_R_ci95", "profit_factor", "dsr")},
              flush=True)
    v0 = out["variants"]["V0_BPR_LIMIT_M1"]
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
