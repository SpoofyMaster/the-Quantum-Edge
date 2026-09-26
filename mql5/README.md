# QuantumEdgeImpulseReversion.mq5 — MT5 test guide

This is an MQL5 port of `pine/quantum_edge_impulse_reversion.pine`, with the same signal, exits and
risk engine. It also implements `docs/deliverables/mql5_spec.md`. The project owner approved it for
**Strategy Tester and demo** testing on 2026-09-26.

> **Research verdict first:** the idea behind this EA did **not** validate in the Python study
> (FINAL_REPORT.md). On development data it gave +0.021R per trade with a CI that includes 0. On the
> untouched 2024–2025H1 validation data it gave −0.055R. Treat MT5 results as an **independent
> check**, not as a reason to go live. On a REAL account the EA runs in log-only mode, and no input
> overrides this.

> **Not yet compiled.** It was written without MetaEditor. If compilation fails, send the full error
> list and I'll fix it.

## 1. Install
1. MT5 → *File → Open Data Folder* → `MQL5/Experts/` → copy `QuantumEdgeImpulseReversion.mq5` there.
2. Open it in MetaEditor (F4) and press **Compile** (F7). The build must finish with 0 errors.

## 2. Strategy Tester settings (pre-registered EXP007 candidate)
| Setting | Value |
|---|---|
| Expert | QuantumEdgeImpulseReversion |
| Symbol | **XAUUSD** (IC Markets Raw) |
| Timeframe | **M1** (the EA always computes on M1) |
| Dates | **2020.01.01 → 2025.06.30**. Keep July 2025 onward untouched; it is the locked final-test period. |
| Modelling | **Every tick based on real ticks**. It is the only mode with realistic spreads. |
| Deposit / leverage | 100 000 USD / your account leverage |
| Commission | Uses the broker's real commission if your terminal is connected to IC Markets. Otherwise set a custom symbol commission. |
| Inputs | Defaults: Active fade, k = 5, H = 30, stop 1.0, target 1.5, risk 0.20%, day loss 1.00%, server time "NY + 7h" (correct for IC Markets) |

**Warm-up:** the seasonal model needs **at least 4 full weeks** of M1 history before the first trade,
and uses up to 20 weeks. The panel shows `Seasonal weeks loaded`. If the tester provides little
history before the start date, the first weeks produce no trades. That is expected; do not shorten
the warm-up.

**Do not optimise the inputs.** Scanning k, H or the stop multiple across 5.5 years is exactly the
multiple-testing trap the research was built to avoid. If you want to vary anything, tell me first
so it gets logged as a trial.

## 3. What to send back
1. The tester **Report** tab: screenshot, or *right-click → Report → HTML*.
2. `QE_tester_summary.csv` from `…/Terminal/Common/Files/`. It holds trades, mean R per trade, SD
   and t-statistic, directly comparable with EXP006/EXP007.
3. Optional: the per-day logs `QE_XAUUSD_26092601_YYYYMMDD.csv` from the same folder. They record
   every event, rejection (with reason), entry and exit.

## 4. How to read the result
- **Mean R per trade** is the number that matters, not net profit, which depends on the deposit.
  Python gives about +0.02R for dev 2020–2023 and −0.055R for validation 2024–2025H1.
- MT5 real-tick results use **real IC Markets spreads**, which the Python study had to model. If MT5
  shows a clearly *better* mean R over 2020–2023 **and** 2024–2025, that is new information worth a
  follow-up research cycle. It is still not a reason to trade live.
- A t-statistic below 3 is not evidence of an edge (see EXP008).

## 5. Parity with Python and Pine
| Component | Verified how |
|---|---|
| Seasonal model (buckets, weeks, median, √(π/2)) | Same algorithm as Pine; the Pine algorithm is tested against Python (`tests/test_pine_parity.py`) |
| Server time → UTC → New York/London (DST), sessions, FX day, blackout, bucket, week id | `qe/mql5_parity.py` mirrors the EA functions line by line; `tests/test_mql5_parity.py` checks them against `zoneinfo` every 30 minutes, 2020–2026 |
| Sizing, lockout, budget | Same formulas as `qe/risk.py` (commission input, rounded down to the lot step) |
| Known differences | The EA uses **bid** closes (Python used mid = bid + half the modelled spread). MT5 fills use real spreads and slippage. The tester's history before the start date may be shorter than 20 weeks. |

## 6. Safety features
- **Account mode:** Strategy Tester → trades; demo → trades (`InpAllowDemoOrders`); real → log-only,
  with no override.
- **Risk:** risk per trade capped at 0.20% and daily loss at 1.00% (inputs above the caps are
  rejected at init). No martingale, grid or averaging. One position per symbol.
- **Portfolio ledger across EA instances** (terminal global variables `QE.*`): at most 3 positions
  and at most 0.60% open planned risk. The correlation guard is configured in `InpCorrTable`.
- **Execution health:**
  - 3 consecutive order errors suspend trading for the FX day.
  - Signals are skipped when the spread exceeds 3× its hour-of-week median.
  - A disconnect watchdog closes positions that went overdue while offline.
  - Stale signals are rejected, for example across the weekend gap.
- **Forced exits:** time exit after H minutes, the 16:45–17:30 NY rollover blackout, and a hard
  120-minute maximum.
