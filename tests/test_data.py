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
