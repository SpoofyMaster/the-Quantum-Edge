# Historical Data Provenance & Quality Report

## Update 2026-09-26 (Day 2): data path via GitHub Actions

The research workflow (`.github/workflows/research.yml`) runs on GitHub-hosted runners, which have
unrestricted internet access. Data is downloaded into the repo-private **Actions cache**. It is never
committed. Only aggregated results and logs are pushed to the `ci-results` branch.

Connectivity probe from the runner (logs/probe.log on `ci-results`):
- `datafeed.dukascopy.com` returned **HTTP 503** (107 bytes) for both candle and tick files.
  Dukascopy refuses these cloud IPs, so the preferred bid/ask source is unavailable for now.
- `www.histdata.com` returned **HTTP 200**, so HistData M1 is used: BID only, EST without DST,
  converted to UTC.

Consequence: **spreads are not observed.** The ask side is modelled as
`typical_raw_spread × NY-hour multiplier` (`qe/data/store.py::NY_HOUR_SPREAD_MULT`, an explicit
assumption). All cost conclusions must be stress-tested with the spread scaled ×2 and ×3, and
re-checked against IC Markets MT5 spread exports (`tools/mql5/ExportM1WithSpread.mq5`) when the user
provides them.

## Original status (2026-09-26, Day 1): BLOCKED — no market data acquired

The sandbox egress policy returned HTTP 403 for every candidate data host that was tested:

| Host | Purpose | Result |
|---|---|---|
| datafeed.dukascopy.com | tick bid/ask 2003→present (preferred research source) | 403 blocked |
| www.histdata.com | M1 bid bars (no ask) | blocked |
| www.icmarkets.com | official specs | blocked |
| query1.finance.yahoo.com, stooq.com | not M1-capable for 2020+ anyway | blocked |
| www.kaggle.com, zenodo.org, huggingface.co | public dataset mirrors | blocked |

Only PyPI and GitHub (restricted to this repository) are reachable. **No experiment in this repository
has used real market data yet.** All results so far are synthetic pipeline tests.

## Source plan (ranked)

1. **Dukascopy tick data → our own M1 bid/ask bars** (`qe/data/dukascopy.py`, decoder unit-tested).
   It covers 2020→present for all target symbols and has a real bid and ask, which gives a spread
   *proxy*. Dukascopy is not IC Markets.
2. **IC Markets MT5 history export**: M1 bars plus the `spread` field from the user's MT5 terminal
   (Tools → History Center, or a script `CopyRates` → CSV). This is the only source of *broker-specific*
   spreads. MT5 M1 spread is the spread at the bar's open/minimum, not the average, so check it
   against tick data.
3. **HistData.com M1**: bid-only, EST without DST (`qe/data/histdata.py`). Fallback only; spreads
   would be *assumed*.
4. **TradingView**: used for the Pine prototype only. Its M1 history depth depends on the subscription
   plan. Use `pine/tools/m1_coverage_probe.pine` to measure it; never assume it.

## Data rules
- Raw data is never committed (licensing + size). `data/` is git-ignored. We commit
  quality reports and SHA-256 manifests (`data/manifest.json` → copied to `results/`).
- Canonical schema: `qe/data/schema.py` (UTC bar-open, bid & ask OHLC, `spread_source` flag).
- Quality checks: `qe.data.schema.quality_report` (intraweek gaps, OHLC consistency, crossed quotes,
  MAD-based spikes, spread percentiles).
