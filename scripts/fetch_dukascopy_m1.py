"""Fetch Dukascopy daily M1 BID+ASK candle files -> data/m1/{SYMBOL}/{YYYY-MM}.parquet.

Designed to run inside GitHub Actions (the research sandbox cannot reach Dukascopy). Raw data stays
in the runner / Actions cache and is never committed. Resumable: complete months are skipped.
    python scripts/fetch_dukascopy_m1.py EURUSD,XAUUSD 2020-01-01 2025-07-01
Writes data/fetch_report_{SYMBOL}.json with per-month bar counts and SHA-256 hashes.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe.config import ROOT  # noqa: E402
from qe.data.dukascopy import candle_url, candles_to_canonical, check_candle_order, decode_candles_bi5  # noqa: E402

OUT = ROOT / "data" / "m1"
UA = {"User-Agent": "Mozilla/5.0 (research; quantum-edge)"}


def fetch(url: str, tries: int = 6) -> bytes:
    err = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return b""
            err = e
        except Exception as e:  # noqa: BLE001  (timeouts, resets)
            err = e
        time.sleep(min(60, 2 ** k))
    raise RuntimeError(f"failed {url}: {err}")


def day_bars(symbol: str, day: pd.Timestamp) -> pd.DataFrame:
    d = day.to_pydatetime()
    bid = decode_candles_bi5(fetch(candle_url(symbol, d, "BID")), symbol, d)
    ask = decode_candles_bi5(fetch(candle_url(symbol, d, "ASK")), symbol, d)
    for side, df in (("BID", bid), ("ASK", ask)):
        bad = check_candle_order(df)
        if bad > 0.001:
            raise RuntimeError(f"{symbol} {day.date()} {side}: {bad:.2%} bars violate OHLC order - format assumption wrong")
    if bid.empty or ask.empty:
        return pd.DataFrame()
    return candles_to_canonical(bid, ask)


def main(symbols: str, start: str, end: str, workers: int = 8) -> None:
    months = pd.date_range(start, end, freq="MS", tz="UTC", inclusive="left")
    for sym in symbols.split(","):
        (OUT / sym).mkdir(parents=True, exist_ok=True)
        rep_path = ROOT / "data" / f"fetch_report_{sym}.json"
        report = json.loads(rep_path.read_text()) if rep_path.exists() else {}
        for m in months:
            f = OUT / sym / f"{m:%Y-%m}.parquet"
            if f.exists():
                continue
            days = [d for d in pd.date_range(m, m + pd.offsets.MonthBegin(1), freq="D", inclusive="left")
                    if d.dayofweek != 5]
            t0 = time.time()
            with ThreadPoolExecutor(workers) as ex:
                parts = [p for p in ex.map(lambda d: day_bars(sym, d), days) if not p.empty]
            if not parts:
                print(sym, f"{m:%Y-%m}", "no data", flush=True)
                continue
            df = pd.concat(parts).sort_index()
            df.to_parquet(f, compression="zstd")
            report[f"{m:%Y-%m}"] = {"bars": len(df), "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                                    "first": str(df.index[0]), "last": str(df.index[-1]),
                                    "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            rep_path.write_text(json.dumps(report, indent=1))
            print(sym, f"{m:%Y-%m}", len(df), "bars", f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
