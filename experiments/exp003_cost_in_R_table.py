"""EXP003 — Deterministic cost arithmetic: round-trip cost as a fraction of risk (R) per instrument.

Inputs are the UNVERIFIED IC Markets Raw specs in config/instruments.toml and PLACEHOLDER spreads
(typical_raw_spread). Output is arithmetic, not market evidence; it will be recomputed with
measured spreads once real bid/ask data is available (BACKLOG D-3).
Break-even win rate assumes fixed target = reward_R x stop and costs paid on every trade.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe.config import ROOT, load_instruments  # noqa: E402
from qe.costs import breakeven_win_rate, commission_in_price_units, cost_in_R, round_trip_cost_price  # noqa: E402

EXP = "exp003_cost_in_R_table"
# reference prices (approximate, for unit conversion only; only USDJPY's result depends on price)
REF_PRICE = {"EURUSD": 1.10, "GBPUSD": 1.30, "USDJPY": 150.0, "XAUUSD": 2500.0, "XAGUSD": 30.0}
# "pip"/point unit per symbol used for stop grid
PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "USDJPY": 0.01, "XAUUSD": 0.10, "XAGUSD": 0.01}
STOPS_IN_PIPS = [3, 5, 8, 12, 20, 30]


def main():
    inst = load_instruments()
    out = {"experiment": EXP, "status": "ARITHMETIC on UNVERIFIED specs + placeholder spreads", "rows": []}
    lines = ["| Symbol | pip unit | RT cost (pips) | " + " | ".join(f"stop {s}p: cost R / BE win% @1.5R" for s in STOPS_IN_PIPS) + " |",
             "|---|---|---|" + "---|" * len(STOPS_IN_PIPS)]
    for sym, px in REF_PRICE.items():
        i = inst[sym]
        rt = round_trip_cost_price(i, px, i.typical_raw_spread, slippage_ticks=1.0)
        cells = []
        for s in STOPS_IN_PIPS:
            c = cost_in_R(i, px, i.typical_raw_spread, s * PIP[sym], slippage_ticks=1.0)
            be = breakeven_win_rate(1.5, c)
            cells.append(f"{c:.2f} / {100 * be:.1f}%")
            out["rows"].append({"symbol": sym, "stop_pips": s, "cost_R": c, "breakeven_winrate_1p5R": be})
        out[sym] = {"commission_price_units": commission_in_price_units(i, px), "round_trip_cost_price": rt,
                    "round_trip_cost_pips": rt / PIP[sym]}
        lines.append(f"| {sym} | {PIP[sym]} | {rt / PIP[sym]:.2f} | " + " | ".join(cells) + " |")
    out["markdown"] = "\n".join(lines)
    print(out["markdown"])
    (ROOT / "results" / f"{EXP}.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
