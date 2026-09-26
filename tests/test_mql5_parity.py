import numpy as np
import pandas as pd

from qe import mql5_parity as mq
from qe.sessions import session_frame


def _grid():
    idx = pd.date_range("2020-01-01", "2026-12-31", freq="30min", tz="UTC")
    ny = idx.tz_convert("America/New_York")
    # exclude the weekend window around DST switches (FX market closed: Fri 17:00 -> Sun 17:00 NY)
    closed = (ny.dayofweek == 5) | ((ny.dayofweek == 6) & (ny.hour < 17)) | ((ny.dayofweek == 4) & (ny.hour >= 17))
    return idx[~closed]


def test_server_ny_plus_7_to_utc_matches_zoneinfo():
    idx = _grid()
    ny_local = idx.tz_convert("America/New_York").tz_localize(None)
    server = ((ny_local - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)).to_numpy() + 7 * 3600
    utc_true = (idx.tz_localize(None) - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)
    got = np.array([mq.server_to_utc(int(s), mq.NY_PLUS_7) for s in server])
    assert (got == utc_true.to_numpy()).all()


def test_server_eu_dst_to_utc_matches_zoneinfo():
    idx = _grid()
    # EU-DST servers: UTC+2 in winter, UTC+3 in EU summer time (same dates as Europe/London)
    ldn = idx.tz_convert("Europe/London")
    off = np.where([t.dst() != pd.Timedelta(0) for t in ldn], 3, 2)
    utc_s = ((idx.tz_localize(None) - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)).to_numpy()
    got = np.array([mq.server_to_utc(int(u + o * 3600), mq.EU_DST) for u, o in zip(utc_s, off)])
    assert (got == utc_s).all()


def test_sessions_match_python_research_definitions(cfg):
    idx = _grid()[::7]
    ref = session_frame(idx, cfg)
    utc_s = ((idx.tz_localize(None) - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)).to_numpy()
    ny_local = idx.tz_convert("America/New_York").tz_localize(None)
    server = ((ny_local - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)).to_numpy() + 7 * 3600
    rows = [mq.sessions(int(s)) for s in server]
    assert (np.array([r["utc"] for r in rows]) == utc_s).all()
    for key, col in (("london", "london"), ("newyork", "newyork"), ("blackout", "rollover_blackout")):
        assert (np.array([r[key] for r in rows]) == ref[col].to_numpy()).all(), key
    fx = pd.to_datetime([str(d) for d in ref["fx_day"]])
    fx_days = ((fx - pd.Timestamp("1970-01-01")).days).to_numpy()
    assert (np.array([r["fx_day"] for r in rows]) == fx_days).all()


def test_bucket_and_week_match_seasonal_model():
    idx = _grid()[::11]
    ny = idx.tz_convert("America/New_York")
    local = ny.tz_localize(None)
    week_py = ((local - pd.Timestamp("2000-01-02")).days // 7).to_numpy()
    bucket_py = ((np.asarray(ny.dayofweek) + 1) % 7) * 288 + (np.asarray(ny.hour) * 60 + np.asarray(ny.minute)) // 5
    server = ((local - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)).to_numpy() + 7 * 3600
    rows = [mq.sessions(int(s)) for s in server]
    assert (np.array([r["week_id"] for r in rows]) == week_py).all()
    assert (np.array([r["bucket"] for r in rows]) == bucket_py).all()
