"""Performance report (Phase 23) for trades from the Python reference or from the EA's CSV log.

    python -m qe.video_strategy.report path/to/VSEA_trades_XAUUSD_26100401.csv [--equity 100000]

Columns used: entry_time, exit_time, direction, R, and pnl_usd (Python) or profit+commission+swap (EA CSV).
Times in the EA CSV are broker server time; sessions are labelled from UTC (IC Markets server = New York + 7 h).
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from ..stats import bootstrap_ci, deflated_sharpe, max_drawdown


def _max_consecutive(mask: np.ndarray) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def session_label(ts_utc: pd.Series) -> pd.Series:
    """ASIA before 08:00 London, LONDON from 08:00 London to 16:00 UTC, else OTHER (DST-correct)."""
    t = pd.to_datetime(ts_utc, utc=True)
    ldn = t.dt.tz_convert("Europe/London")
    utc_min = t.dt.hour * 60 + t.dt.minute
    is_london = (ldn.dt.hour >= 8) & (utc_min < 16 * 60)
    out = np.where(is_london, "LONDON", np.where(utc_min < 9 * 60, "ASIA", "OTHER"))
    return pd.Series(out, index=ts_utc.index)


def performance(trades: pd.DataFrame, equity0: float = 100_000.0, n_trials: int = 1, var_sr: float = 0.01) -> dict:
    if trades is None or len(trades) == 0:
        return {"trades": 0}
    t = trades.sort_values("entry_time").reset_index(drop=True)
    pnl = t["pnl_usd"].to_numpy(float)
    R = t["R"].to_numpy(float)
    wins, losses = pnl > 0, pnl <= 0
    gp, gl = float(pnl[wins].sum()), float(-pnl[losses].sum())
    dur = (pd.to_datetime(t.exit_time) - pd.to_datetime(t.entry_time)).dt.total_seconds() / 60 + 1
    entry = pd.to_datetime(t.entry_time, utc=True)
    out = {
        "trades": int(len(t)),
        "win_rate": float(wins.mean()),
        "net_profit": float(pnl.sum()),
        "net_profit_pct": float(100 * pnl.sum() / equity0),
        "gross_profit": gp,
        "gross_loss": gl,
        "profit_factor": float(gp / gl) if gl > 0 else float("inf"),
        "expected_payoff": float(pnl.mean()),
        "ev_R": float(R.mean()),
        "ev_R_ci95": [float(v) for v in bootstrap_ci(R, B=1000)[1:]] if len(R) > 10 else None,
        "max_drawdown_usd": float(max_drawdown(pnl)),
        "max_drawdown_pct": float(100 * max_drawdown(pnl) / equity0),
        "avg_duration_min": float(dur.mean()),
        "avg_winner": float(pnl[wins].mean()) if wins.any() else 0.0,
        "avg_loser": float(pnl[losses].mean()) if losses.any() else 0.0,
        "avg_winner_R": float(R[wins].mean()) if wins.any() else 0.0,
        "avg_loser_R": float(R[losses].mean()) if losses.any() else 0.0,
        "max_consecutive_losses": _max_consecutive(losses),
        "long_trades": int((t.direction > 0).sum()),
        "short_trades": int((t.direction < 0).sum()),
    }
    if len(R) > 10:
        out["dsr"] = float(deflated_sharpe(R, max(n_trials, 1), var_sr))
    months = entry.dt.tz_convert(None).dt.to_period("M")
    span = max(1, (months.max() - months.min()).n + 1)
    out["trades_per_month"] = float(len(t) / span)
    out["by_month_count"] = {str(k): int(v) for k, v in months.value_counts().sort_index().items()}
    ses = session_label(entry)
    out["by_session"] = {k: {"trades": int(len(g)), "ev_R": float(g.R.mean()), "win_rate": float((g.pnl_usd > 0).mean())}
                         for k, g in t.groupby(ses.values)}
    out["by_year"] = {str(y): {"trades": int(len(g)), "ev_R": float(g.R.mean()), "net_profit": float(g.pnl_usd.sum()),
                               "win_rate": float((g.pnl_usd > 0).mean())}
                      for y, g in t.groupby(entry.dt.year.values)}
    if "symbol" in t:
        out["by_symbol"] = {s: {"trades": int(len(g)), "ev_R": float(g.R.mean())} for s, g in t.groupby("symbol")}
    if "tf" in t:
        out["by_candle_tf"] = {str(k): {"trades": int(len(g)), "ev_R": float(g.R.mean())} for k, g in t.groupby("tf")}
    if "outcome" in t:
        out["exits"] = {str(k): int(v) for k, v in t.outcome.map({1: "TP", -1: "SL", 0: "TIME"}).value_counts().items()}
    return out


def load_ea_csv(path: str, server_utc_offset_mode: str = "NY_PLUS_7") -> pd.DataFrame:
    df = pd.read_csv(path, sep=";")
    for c in ("signal_time", "entry_time", "exit_time"):
        ts = pd.to_datetime(df[c], format="%Y.%m.%d %H:%M")
        if server_utc_offset_mode == "NY_PLUS_7":      # server = New York + 7 h -> UTC
            ny = ts - pd.Timedelta(hours=7)
            df[c] = ny.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")
        else:
            df[c] = ts.dt.tz_localize("UTC")
    df["pnl_usd"] = df["profit"] + df["commission"] + df["swap"]
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv")
    ap.add_argument("--equity", type=float, default=100_000.0)
    ap.add_argument("--server", default="NY_PLUS_7", choices=["NY_PLUS_7", "UTC"])
    a = ap.parse_args()
    print(json.dumps(performance(load_ea_csv(a.csv, a.server), a.equity), indent=1, default=str))


if __name__ == "__main__":
    main()
