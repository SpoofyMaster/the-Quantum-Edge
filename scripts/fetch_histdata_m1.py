"""FALLBACK source: HistData.com free M1 ASCII bars (BID only, EST without DST).

Used only if Dukascopy is unreachable. Spreads are NOT observed: the ask side is modelled as
bid + config typical_raw_spread and flagged spread_source='assumed'. Any cost conclusion drawn on
this data is weaker and must say so.
    python scripts/fetch_histdata_m1.py EURUSD,XAUUSD 2020 2025
Writes data/m1/{SYMBOL}/{YYYY-MM}.parquet (skips existing months) + data/fetch_report_{SYMBOL}.json.
Download flow per histdata.com's public form (as used by the open-source 'histdata' package):
GET the year/month page -> read hidden token 'tk' -> POST /get.php -> zip with one CSV.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qe.config import ROOT, load_instruments, load_research  # noqa: E402
from qe.data.histdata import parse_ascii_m1  # noqa: E402
from qe.validation import final_test_start  # noqa: E402

BASE = "https://www.histdata.com"
UA = "Mozilla/5.0 (research; quantum-edge)"


def _get(url, data=None, referer=None, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **({"Referer": referer} if referer else {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            print(f"retry {k + 1}/{tries} {url}: {e}", flush=True)
            time.sleep(2 ** (k + 1))
    raise RuntimeError(f"failed {url}")


def download(pair: str, year: int, month: int | None) -> str:
    path = f"/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{pair.lower()}/{year}"
    if month:
        path += f"/{month}"
    ref = BASE + path
    html = _get(ref).decode("utf-8", "ignore")
    m = re.search(r'id="tk"[^>]*value="([^"]+)"', html) or re.search(r'value="([^"]+)"[^>]*id="tk"', html)
    if not m:
        raise RuntimeError(f"token not found for {pair} {year} {month}")
    form = {"tk": m.group(1), "date": str(year), "datemonth": f"{year}{month:02d}" if month else str(year),
            "platform": "ASCII", "timeframe": "M1", "fxpair": pair.upper()}
    blob = _get(BASE + "/get.php", data=urllib.parse.urlencode(form).encode(), referer=ref)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        return z.read(name).decode()


def main(symbols: str, y0: str, y1: str) -> None:
    inst = load_instruments()
    now = datetime.now(timezone.utc)
    for sym in symbols.split(","):
        out = ROOT / "data" / "m1" / sym
        out.mkdir(parents=True, exist_ok=True)
        rep_path = ROOT / "data" / f"fetch_report_{sym}.json"
        report = json.loads(rep_path.read_text()) if rep_path.exists() else {}
        for year in range(int(y0), int(y1) + 1):
            chunks = [None] if year < now.year else list(range(1, now.month + 1))
            for month in chunks:
                if month is None and all((out / f"{year}-{mm:02d}.parquet").exists() for mm in range(1, 13)):
                    continue
                if month and (out / f"{year}-{month:02d}.parquet").exists():
                    continue
                df = parse_ascii_m1(download(sym, year, month), assumed_spread=inst[sym].typical_raw_spread)
                # the locked final-test period is not stored until a strategy freeze is journaled
                df = df[df.index < final_test_start(load_research())]
                for mk, g in df.groupby(df.index.strftime("%Y-%m")):
                    f = out / f"{mk}.parquet"
                    g.to_parquet(f, compression="zstd")
                    report[mk] = {"bars": len(g), "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                                  "source": "histdata.com M1 BID (ask assumed)",
                                  "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                rep_path.write_text(json.dumps(report, indent=1))
                print(sym, year, month or "full-year", len(df), "bars", flush=True)
                time.sleep(2)


if __name__ == "__main__":
    main(*sys.argv[1:4])
