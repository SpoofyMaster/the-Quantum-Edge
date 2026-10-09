# BprFvgEA v1 (hypothesis H-13), frozen

This is the BprFvgEA as it was at commit `e98f4d1`. It used the sketch-based rules:
- liquidity sweep and structure shift;
- a limit order near the far edge of the BPR / FVG;
- TP1 / TP2.

Spec: `research/indicators/BPR_FVG_EA_SPEC.md`.

**Status: `REJECTED`** by the pre-registered backtest EXP010 (`reports/EXP010_BPR_FVG_EA_REPORT.md`): −0.37 R per
trade after costs. It is kept so that `tests/test_bpr_fvg_ea_harness.py` (EA vs `qe/strategies/bpr_fvg.py`) and
EXP010 stay reproducible. Do not install it for trading.

**Why v1 placed so few limit orders** (owner report of 2026-10-09):
- Every decision silently required **round-trip cost ≤ 0.15 R** (`InpMaxCostR`) and **reward:risk ≥ 1.0 at TP1**.
- On M1, most BPR / FVG zones are smaller than the costs allow: on XAUUSD a zone needs a stop of about 1.3–2.6 price
  units; on EURUSD about 7–13 pips.
- The setups therefore stayed `ARMED` with no log line until they broke or expired.
- Together with the sweep and MSS filters, this left about 7 orders a month on XAUUSD in EXP010, and almost none on
  M1 FX.

The current EA (`mql5/BprFvgEA`, v2) logs every rejection and shows the counts on the panel.
