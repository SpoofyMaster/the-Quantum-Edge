# IC Markets Raw Spread — Instrument & Cost Specifications

**Status: UNVERIFIED.** On 2026-09-26 the sandbox egress policy blocked `www.icmarkets.com` (HTTP 403 at
the proxy), so the official pages could not be read. The values below come from secondary sources and
are used only as placeholders in `config/instruments.toml` (`status = "UNVERIFIED"`).

| Item | Working value | Source | Verified? |
|---|---|---|---|
| Raw Spread commission (MT4/MT5, USD account) | USD 3.50 per 1.00 lot per side (USD 7.00 round turn) | Web search summary citing icmarkets.com Raw Spread account page and compareforexbrokers.com (2026) | ❌ secondary |
| FX contract size | 100,000 base units | MT5 convention | ❌ |
| XAUUSD contract size | 100 oz | MT5 convention at most brokers | ❌ |
| XAGUSD contract size | 5,000 oz | MT5 convention at most brokers | ❌ |
| Metals commission | Assumed identical to FX (3.50/lot/side) | assumption | ❌ **high priority** |
| Min lot / step | 0.01 / 0.01 | common | ❌ |
| Stop level | assumed 0 | common for IC Markets Raw | ❌ |
| Swaps | not modelled: positions are never held across the 17:00 NY rollover | design | n/a |
| Commission currency conversion for USD-base pairs (USDJPY) | assumed charged in USD per lot | assumption | ❌ |

Secondary sources consulted (2026-09-26):
- https://www.icmarkets.com/global/en/trading-accounts/raw-spread-account (search-result summary only; page blocked)
- https://www.compareforexbrokers.com/reviews/ic-markets-review/raw-spread-vs-standard-account/

## How to verify (user action, ~10 minutes)
1. In MT5 (IC Markets Raw demo), right-click each symbol → *Specification*. Record: contract size,
   digits, tick size/value, min/max/step volume, stops level, swap, and trading sessions.
2. Place and close a 0.01-lot demo trade on EURUSD, XAUUSD and XAGUSD, and read the commission in the
   *History* tab.
3. Paste the values into `config/instruments.toml`, set `status = "VERIFIED"` and fill in
   `verified_source` (e.g. "MT5 spec screen, demo 2026-09-27").
