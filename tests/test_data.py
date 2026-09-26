from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from qe.data.dukascopy import decode_bi5, encode_bi5, ticks_to_m1, url_for
from qe.data.histdata import parse_ascii_m1
from qe.data.schema import quality_report, validate


def test_bi5_roundtrip_and_m1():
    hour = datetime(2024, 1, 2, 10, tzinfo=timezone.utc)
    ts = pd.DatetimeIndex(["2024-01-02 10:00:00.250", "2024-01-02 10:00:40", "2024-01-02 10:01:05"], tz="UTC")
    ticks = pd.DataFrame({"ask": [1.10012, 1.10020, 1.10005], "bid": [1.10010, 1.10017, 1.10003],
                          "ask_vol": [1.5, 2.0, 0.5], "bid_vol": [1.0, 1.0, 1.0]}, index=ts)
    dec = decode_bi5(encode_bi5(ticks, "EURUSD", hour), "EURUSD", hour)
    np.testing.assert_allclose(dec.bid.values, ticks.bid.values)
    assert (dec.index == ts).all()
    m1 = ticks_to_m1(dec)
    assert list(m1.index) == [pd.Timestamp("2024-01-02 10:00", tz="UTC"), pd.Timestamp("2024-01-02 10:01", tz="UTC")]
    assert m1.iloc[0].bh == pytest.approx(1.10017) and m1.iloc[0].volume == 2


def test_url_month_is_zero_based():
    assert url_for("EURUSD", datetime(2024, 1, 2, 5)).endswith("EURUSD/2024/00/02/05h_ticks.bi5")


def test_histdata_est_to_utc():
    txt = "20240102 170000;1.1;1.2;1.0;1.15;0\n20240102 170100;1.15;1.16;1.14;1.15;0\n"
    df = parse_ascii_m1(txt, assumed_spread=0.00002)
    assert df.index[0] == pd.Timestamp("2024-01-02 22:00", tz="UTC")
    assert (df.spread_source == "assumed").all()
    assert df.ac.iloc[0] == pytest.approx(1.15002)


def test_quality_report_on_synthetic(small_bars):
    validate(small_bars)
    q = quality_report(small_bars)
    assert q["ohlc_inconsistent_bars"] == 0 and q["crossed_quote_bars"] == 0
    assert q["intraweek_gaps"] == 0


def test_quality_report_flags_gap(small_bars):
    q = quality_report(small_bars.drop(small_bars.index[100:110]))
    assert q["intraweek_gaps"] == 1 and q["intraweek_missing_minutes"] == 10


def test_candle_roundtrip_and_canonical():
    from qe.data.dukascopy import (candles_to_canonical, check_candle_order, decode_candles_bi5,
                                   encode_candles_bi5)
    day = datetime(2024, 1, 2)
    idx = pd.DatetimeIndex(["2024-01-02 00:00", "2024-01-02 00:01", "2024-01-02 00:02"], tz="UTC")
    bid = pd.DataFrame({"open": [2050.10, 2050.20, 2050.0], "high": [2050.5, 2050.3, 2050.0],
                        "low": [2050.0, 2049.9, 2050.0], "close": [2050.2, 2050.0, 2050.0],
                        "volume": [1.5, 2.0, 0.0]}, index=idx)
    ask = bid.copy()
    ask[["open", "high", "low", "close"]] += 0.15
    b = decode_candles_bi5(encode_candles_bi5(bid, "XAUUSD", day), "XAUUSD", day)
    a = decode_candles_bi5(encode_candles_bi5(ask, "XAUUSD", day), "XAUUSD", day)
    np.testing.assert_allclose(b.high.values, bid.high.values)
    assert (b.index == idx).all() and check_candle_order(b) == 0.0
    c = candles_to_canonical(b, a.assign(volume=0.0))
    assert len(c) == 2  # filler bar with zero volume on both sides dropped
    assert (c.ac - c.bc).round(6).eq(0.15).all()


def test_store_guard(tmp_path, monkeypatch, cfg):
    from qe.data import store
    from qe.synthetic import generate
    from qe.validation import FinalTestLocked
    monkeypatch.delenv("QE_UNLOCK_FINAL_TEST", raising=False)
    monkeypatch.setattr(store, "M1_DIR", tmp_path)
    df = generate(start="2025-06-25", end="2025-07-03", seed=1)
    (tmp_path / "EURUSD").mkdir()
    for m, g in df.groupby(df.index.strftime("%Y-%m")):
        g.to_parquet(tmp_path / "EURUSD" / f"{m}.parquet")
    got = store.load_m1("EURUSD", "2025-06-25", cfg=cfg)
    assert got.index.max() < pd.Timestamp("2025-07-01", tz="UTC")
    with pytest.raises(FinalTestLocked):
        store.load_m1("EURUSD", "2025-06-25", "2025-07-03", cfg=cfg)


def test_spread_model_widens_at_rollover():
    from qe.data.store import apply_spread_model
    idx = pd.DatetimeIndex(["2024-01-15 22:00", "2024-01-16 14:00"], tz="UTC")  # 17:00 NY, 09:00 NY
    df = pd.DataFrame({c: 1.1 for c in ["bo", "bh", "bl", "bc"]}, index=idx)
    out = apply_spread_model(df, 0.00002)
    sp = (out.ac - out.bc).to_numpy()
    assert sp[0] == pytest.approx(0.00008) and sp[1] == pytest.approx(0.00002)
