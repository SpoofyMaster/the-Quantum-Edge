import pandas as pd

from qe.sessions import fx_trading_day, session_frame


def _flags(ts, cfg):
    return session_frame(pd.DatetimeIndex([pd.Timestamp(ts, tz="UTC")]), cfg).iloc[0]


def test_london_open_moves_with_bst(cfg):
    # winter: London 08:00 local = 08:00 UTC ; summer (BST): 07:00 UTC
    assert _flags("2024-01-15 08:00", cfg).london and not _flags("2024-01-15 07:59", cfg).london
    assert _flags("2024-07-15 07:00", cfg).london and not _flags("2024-07-15 06:59", cfg).london


def test_overlap_during_us_uk_dst_mismatch(cfg):
    # 2024-03-12: US already on DST (NY open 08:00 EDT = 12:00 UTC), UK not yet (London close 16:30 UTC)
    assert _flags("2024-03-12 12:00", cfg).overlap
    assert not _flags("2024-03-12 11:59", cfg).overlap
    # a week later (UK still GMT until 31 Mar) - same; in January NY opens 13:00 UTC
    assert not _flags("2024-01-16 12:30", cfg).overlap
    assert _flags("2024-01-16 13:00", cfg).overlap


def test_fx_day_rolls_at_5pm_new_york():
    idx = pd.DatetimeIndex(["2024-01-15 21:59", "2024-01-15 22:00", "2024-07-15 20:59", "2024-07-15 21:00"], tz="UTC")
    d = [str(x) for x in fx_trading_day(idx)]
    assert d == ["2024-01-15", "2024-01-16", "2024-07-15", "2024-07-16"]


def test_rollover_blackout(cfg):
    assert _flags("2024-01-15 21:50", cfg).rollover_blackout   # 16:50 NY
    assert _flags("2024-01-15 22:20", cfg).rollover_blackout   # 17:20 NY
    assert not _flags("2024-01-15 22:40", cfg).rollover_blackout
