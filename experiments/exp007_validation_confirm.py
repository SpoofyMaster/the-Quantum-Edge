"""EXP007 — ONE-SHOT confirmation of pre-registered candidates on the VALIDATION period
(2024-01-01 .. 2025-06-30). The candidate list and every parameter are read from
config/preregistered_candidates.json, which must be committed BEFORE this experiment runs
(the commit hash is recorded in the output). No parameter may be changed after seeing this result;
a failing candidate is REJECTED, not re-tuned.

Acceptance (docs/research/hypotheses.md): net EV > 0 with 95% bootstrap CI above 0, Deflated Sharpe
> 0.95 given all market trials so far, and still positive under the x2 spread stress.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp006_strategy_wf_dev import evaluate, signals_for  # noqa: E402
from qe import backtest  # noqa: E402
from qe.config import ROOT, load_instruments, load_research  # noqa: E402
from qe.data.store import load_m1  # noqa: E402
from qe.events import all_events  # noqa: E402
from qe.features import build_features  # noqa: E402
from qe.registry import count_trials, register_trial  # noqa: E402
from qe.sessions import session_frame  # noqa: E402

EXP = "exp007_validation_confirm"
VAL_START, VAL_END = "2024-01-01", "2025-07-01"
WARMUP_START = "2023-07-01"  # features/seasonal need history; trades before VAL_START are discarded


def main():
    cfg, inst = load_research(), load_instruments()
    spec_path = ROOT / "config" / "preregistered_candidates.json"
    spec = json.loads(spec_path.read_text())
    commit = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(spec_path)], capture_output=True,
                            text=True, cwd=ROOT).stdout.strip()
    out = {"experiment": EXP, "period": [VAL_START, VAL_END], "spec_commit": commit, "spec": spec, "results": []}
    n_prior = count_trials("market_dev")
    for c in spec["candidates"]:
        sym, fam, H = c["symbol"], c["family"], int(c["H"])
        row = {**c, "variants": {}}
        for label, scale in (("base", 1.0), ("stress_spread2x", 2.0)):
            df = load_m1(sym, WARMUP_START, VAL_END, cfg=cfg, spread_scale=scale)
            f = build_features(df)
            mask, d = all_events(df, f, session_frame(df.index, cfg), sym)[fam]
            sig = signals_for(df, f, mask, d, H)
            sig = sig[sig.index >= VAL_START]
            tr, _ = backtest.run({sym: df}, {sym: sig}, inst, cfg, backtest.BacktestConfig(max_holding_minutes=H))
            register_trial(EXP, {"symbol": sym, "family": fam, "H": H, "variant": label}, {}, "market_validation")
            row["variants"][label] = evaluate(tr, label, n_prior + count_trials("market_validation")) if len(tr) else {"trades": 0}
        b, s2 = row["variants"]["base"], row["variants"]["stress_spread2x"]
        row["accepted"] = bool(b.get("trades", 0) > 30 and b["ev_R_ci95"][0] > 0 and b.get("dsr", 0) > 0.95
                               and s2.get("ev_R", -1) > 0)
        out["results"].append(row)
        print(sym, fam, H, {k: (v.get("trades"), v.get("ev_R"), v.get("ev_R_ci95"), v.get("dsr")) for k, v in row["variants"].items()},
              "ACCEPTED" if row["accepted"] else "REJECTED", flush=True)
    (ROOT / "results" / f"{EXP}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
