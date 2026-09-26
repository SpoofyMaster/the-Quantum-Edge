# Reproducing the research

## Local (no market data needed)
```bash
pip install -r requirements.txt
python -m pytest -q                                   # 43 tests
python experiments/exp001_pipeline_null_and_power.py  # synthetic null/power (≈3 min)
python experiments/exp002_null_auc_diagnostic.py
python experiments/exp003_cost_in_R_table.py
python experiments/exp008_snr_cost_frontier.py        # post-processes results/exp005 JSON
```

## Market-data experiments (GitHub Actions)
The research sandbox cannot reach data vendors. Market-data experiments run in
`.github/workflows/research.yml` (Actions tab → *research* → *Run workflow*):

| Input | Value used |
|---|---|
| experiment | `exp004_data_quality`, `exp005_event_study_dev`, `exp006_strategy_wf_dev`, `exp007_validation_confirm` |
| symbols | `EURUSD,GBPUSD,USDJPY,XAUUSD,XAGUSD` |
| source | `histdata` (Dukascopy returned HTTP 503 to GitHub runners on 2026-09-26) |
| start / end | `2020-01-01` / `2025-07-01` (end is exclusive; the final-test period stays locked) |

- Data lands in the Actions cache (`m1-histdata-v1-*`). It is never committed.
- Results and logs are pushed to the `ci-results` branch, then copied into `results/` on the
  working branch.
- Per-month SHA-256 hashes of the stored parquet files are in `results/fetch_report_<SYMBOL>.json`.

## Locally with your own data
Put canonical parquet files in `data/m1/<SYMBOL>/<YYYY-MM>.parquet`: UTC bar-open index, columns
`bo bh bl bc ao ah al ac volume spread_source`. Or run `scripts/fetch_histdata_m1.py` or
`scripts/fetch_dukascopy_m1.py` on a machine with internet access. Then run the experiment scripts
directly.

## Order and dependencies
EXP004 → EXP005 → EXP006 (reads EXP005 JSON) → EXP007 (reads `config/preregistered_candidates.json`)
→ EXP008 (reads EXP005 JSON).
Do not re-run EXP007 with changed candidates: the validation period has been looked at once.
