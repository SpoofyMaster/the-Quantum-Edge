# Literature Review — Short-Horizon Directional Persistence in FX and Metals

Status: **Day 1 draft.** Every item below is labelled `PUBLISHED`: it summarises a claim made in the
literature. None of it has been verified on our data yet. The citations were written from memory in a
sandbox that could not reach academic sites. Bibliographic details (year, journal, exact findings) must
be checked before the final report (BACKLOG R-2).

## 1. Market microstructure and price formation
- **Kyle (1985), *Econometrica*; Glosten & Milgrom (1985), *JFE*.** Informed order flow moves prices
  permanently. Market makers widen spreads when adverse selection is high. *Implication:* short-horizon
  continuation should follow **informed** flow, and spreads widen exactly when information arrives.
- **Evans & Lyons (2002), *JPE*, "Order Flow and Exchange Rate Dynamics".** Interdealer order flow explains
  a large share of daily FX returns. *Implication:* our M1 data has no true order flow (tick volume is
  only a proxy), so any order-flow feature we build is a noisy stand-in.
- **Cont, Kukanov & Stoikov (2014), *J. Financial Econometrics*, "The Price Impact of Order Book
  Events".** Order-flow imbalance at the best quotes has an approximately linear, contemporaneous price
  impact. The impact is contemporaneous, not predictive at minutes-long horizons.
- **Osler (2003), *JF*, "Currency Orders and Exchange-Rate Dynamics".** Stop-loss orders cluster just
  beyond round numbers and take-profits at them. Breaking through a round number tends to accelerate
  the move (stop cascades), and approaching one tends to stall it. → Hypotheses H-05 and H-06.

## 2. Intraday volatility seasonality and clustering
- **Andersen & Bollerslev (1997, 1998).** FX return volatility has a strong intraday periodic
  pattern tied to regional market opens and to macro announcements, plus long-memory volatility
  clustering. Any threshold must be **de-seasonalised**, otherwise a "3-sigma impulse" at the London
  open is really a 1.5-sigma one.
- **Ito & Hashimoto (2006), *JJIE*.** Intraday seasonality in EBS activity, spreads and volatility.
  Activity peaks at the London open and in the London–NY overlap. Spreads are widest in the late NY and
  early Asia hours.
- **Bollerslev (1986)**, GARCH. **Engle & Russell (1998)**, the Autoregressive Conditional Duration
  model for irregularly spaced data.

## 3. Momentum, continuation and reversal at intraday horizons
- **Gao, Han, Li & Zhou (2018), *JFE*, "Market Intraday Momentum".** In US equity index ETFs, the
  first half-hour return predicts the last half-hour return. This is an equity result; it does not
  automatically transfer to 24h FX.
- **Elaut, Frömmel & Lampaert (2018), *J. Financial Markets*.** Intraday momentum in FX (USD/RUB),
  linked to informed trading versus liquidity provision.
- **Krohn, Mueller & Whelan (2024), *JF*, "Foreign Exchange Fixings and Returns Around the Clock".**
  Systematic intraday FX return patterns around the major fixes: USD appreciates into fixes and
  depreciates after. → H-08 (London 4pm WM/R fix window).
- **Breedon & Ranaldo (2013), *JMCB*.** Time-of-day patterns in FX returns: currencies tend to
  depreciate during their own local trading hours.
- **Moskowitz, Ooi & Pedersen (2012), *JFE*.** Time-series momentum at monthly horizons. Relevant only
  as context for the H4 regime filter.

## 4. Macro announcements
- **Andersen, Bollerslev, Diebold & Vega (2003), *AER*.** Macro news causes conditional-mean "jumps"
  in FX that happen within minutes. The sign depends on the surprise relative to consensus. Volatility
  stays elevated afterwards. *Implication:* in the first minutes after a release, spreads blow out and
  fills are unreliable. We treat this as an execution-risk regime (trading suspended) unless we get
  consensus data to measure surprises.

## 5. Statistical methodology (backtest overfitting)
- **Bailey & López de Prado (2012, 2014).** The Probabilistic Sharpe Ratio and the Deflated Sharpe
  Ratio, which corrects the Sharpe ratio for the number of trials, skew and kurtosis. Implemented in
  `qe/stats.py`.
- **Bailey, Borwein, López de Prado & Zhu (2014/2017).** Probability of Backtest Overfitting (CSCV).
  → BACKLOG V-4.
- **López de Prado (2018), *Advances in Financial Machine Learning*.** Triple-barrier labelling,
  purged k-fold CV with embargo, and meta-labelling. Implemented in `qe/labels.py` and
  `qe/validation.py`.
- **White (2000), "Reality Check"; Hansen (2005), SPA test; Harvey, Liu & Zhu (2016).** Data-snooping
  corrections. Harvey et al. argue for t > 3 when many strategies have been tried.
- **Politis & Romano (1994).** The stationary bootstrap. Implemented.

## 6. What the literature does NOT give us
- No credible public evidence of a **persistent, cost-surviving** M1 directional edge in major FX
  pairs for retail ECN costs. Published intraday effects are small: typically a few basis points,
  often measured on mid prices without costs.
- Most microstructure results need true order-book or order-flow data, which we do not have.
- **Prior belief (explicit):** most or all candidate M1 strategies will fail after costs. The
  research is designed so that this outcome is detected quickly and reported honestly.
