"""Download Dukascopy ticks and build canonical M1 bid/ask parquet files + a SHA-256 manifest.

Usage (needs network access to datafeed.dukascopy.com — blocked in the default research sandbox):
    python scripts/fetch_dukascopy.py EURUSD 2020-01-01 2020-02-01
Output: data/m1/{SYMBOL}/{YYYY-MM}.parquet and data/manifest.json. Resumable: finished months are skipped.
Be polite: requests are sequential with retries. Check Dukascopy's terms of use before use.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe.config import ROOT  # noqa: E402
from qe.data.dukascopy import decode_bi5, ticks_to_m1, url_for  # noqa: E402

DATA = ROOT / "data"


def fetch(url: str, tries: int = 4) -> bytes:
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return b""
            err = e
        except (urllib.error.URLError, TimeoutError) as e:
            err = e
        time.sleep(2 ** (k + 1))
    raise RuntimeError(f"failed {url}: {err}")


def month_bars(symbol: str, month: pd.Timestamp) -> pd.DataFrame:
    hours = pd.date_range(month, month + pd.offsets.MonthBegin(1), freq="1h", inclusive="left", tz="UTC")
    parts = []
    for h in hours:
        if h.dayofweek == 5:  # Saturday: market closed
            continue
        hr = h.to_pydatetime()
        payload = fetch(url_for(symbol, hr))
        if payload:
            parts.append(ticks_to_m1(decode_bi5(payload, symbol, hr)))
    return pd.concat(parts) if parts else pd.DataFrame()


def main(symbol: str, start: str, end: str) -> None:
    out_dir = DATA / "m1" / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    man_path = DATA / "manifest.json"
    manifest = json.loads(man_path.read_text()) if man_path.exists() else {}
    for m in pd.date_range(start, end, freq="MS", tz="UTC", inclusive="left"):
        f = out_dir / f"{m:%Y-%m}.parquet"
        if f.exists():
            continue
        df = month_bars(symbol, m)
        if df.empty:
            continue
        df.to_parquet(f)
        manifest[str(f.relative_to(ROOT))] = {
            "sha256": hashlib.sha256(f.read_bytes()).hexdigest(), "bars": len(df), "source": "dukascopy ticks",
            "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        man_path.write_text(json.dumps(manifest, indent=1))
        print(symbol, f"{m:%Y-%m}", len(df), "bars", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
