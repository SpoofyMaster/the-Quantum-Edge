"""EXP008 — Why a statistically real reversal is not a tradable edge: signal-to-noise vs cost.

Pure post-processing of results/exp005_event_study_dev.json (dev period; no new data looked at).
Per cell (symbol, family, horizon): gross mean signed move m, its per-event std s (recovered from
the stationary-bootstrap CI: s ~ (hi - lo) / 3.92 * sqrt(n)), round-trip cost c.
  net information ratio per event  IR = (m - c) / s
  events per year                   N = n / 4
  annual t-statistic                t = IR * sqrt(N)
  years of data needed for t = 3    Y = (3 / IR)^2 / N      (only if IR > 0)
Output: results/exp008_snr_cost_frontier.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe.config import ROOT  # noqa: E402

EXP = "exp008_snr_cost_frontier"


def main():
    e5 = json.loads((ROOT / "results" / "exp005_event_study_dev.json").read_text())
    rows = []
    for sym, fams in e5["symbols"].items():
        for fam, cell in fams.items():
            cost = cell.get("rt_cost_pips")
            for H, c in cell.get("by_h", {}).items():
                n = c["n"]
                s = (c["ci95"][1] - c["ci95"][0]) / 3.92 * np.sqrt(n)
                m = c["mean_pips"]
                if fam.startswith("H01_") and m < 0:  # express as the H-11 fade
                    fam_x, m = fam.replace("H01_", "H11_").replace("_active_cont", "_active_fade"), -m
                else:
                    fam_x = fam
                ir = (m - cost) / s if s > 0 else np.nan
                N = n / 4.0
                rows.append({"symbol": sym, "family": fam_x, "H": int(H), "n": n, "gross_mean_pips": m,
                             "std_pips": round(float(s), 3), "cost_pips": cost,
                             "gross_IR": round(m / s, 4), "net_IR": round(float(ir), 4),
                             "events_per_year": N, "annual_t": round(float(ir * np.sqrt(N)), 3),
                             "years_for_t3": round(float((3 / ir) ** 2 / N), 1) if ir > 0 else None})
    rows.sort(key=lambda r: -r["net_IR"])
    pos = [r for r in rows if r["net_IR"] > 0]
    out = {"experiment": EXP, "source": "results/exp005_event_study_dev.json (dev 2020-2023)",
           "cells": len(rows), "cells_with_positive_net_IR": len(pos), "top10": rows[:10],
           "median_gross_IR_abs": float(np.median([abs(r["gross_IR"]) for r in rows]))}
    for r in rows[:10]:
        print(r["symbol"], r["family"], r["H"], "grossIR", r["gross_IR"], "netIR", r["net_IR"],
              "t/yr", r["annual_t"], "years_for_t3", r["years_for_t3"])
    (ROOT / "results" / f"{EXP}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
