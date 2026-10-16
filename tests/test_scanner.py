import numpy as np
import pandas as pd

from thai_stocks.report import md_table
from thai_stocks.scanner import daily_metrics, intraday_profile, scan, signal_lists, swing_score


def daily(closes, volumes=None):
    closes = np.asarray(closes, dtype=float)
    idx = pd.bdate_range("2026-01-01", periods=len(closes))
    vol = np.full(len(closes), 1e6) if volumes is None else np.asarray(volumes, dtype=float)
    return pd.DataFrame({"open": closes, "high": closes * 1.01, "low": closes * 0.99,
                         "close": closes, "volume": vol}, index=idx)


def test_uptrend_breakout_with_volume():
    closes = np.r_[np.linspace(10, 20, 80), 21.0]  # last bar clears the 20-day high
    vols = np.r_[np.full(80, 1e6), 3e6]
    m = daily_metrics(daily(closes, vols))
    assert m["trend"] == "up"
    assert m["breakout_20d"] and not m["breakdown_20d"]
    assert m["vol_ratio"] == 3.0
    assert m["chg_1d"] == 5.0
    assert m["value_mthb"] == 63.0


def test_downtrend_breakdown():
    m = daily_metrics(daily(np.r_[np.linspace(20, 10, 80), 9.0]))
    assert m["trend"] == "down" and m["breakdown_20d"] and m["rsi"] < 30


def test_short_history_skipped():
    assert daily_metrics(daily(np.linspace(10, 11, 30))) is None


def test_metrics_ignore_future_bars():
    closes = np.r_[np.linspace(10, 20, 80), 21.0, 5.0]
    a = daily_metrics(daily(closes[:-1]))
    b = daily_metrics(daily(closes)[:-1])
    assert a == b


def test_swing_score_counts_conditions():
    base = dict(trend="up", rsi=60, ema_cross_3d="up", breakout_20d=True, fvg_bull_retest=True, vol_ratio=2.0)
    assert swing_score(base) == 6
    assert swing_score({**base, "trend": "down", "rsi": 80, "vol_ratio": 1.0}) == 3


def test_intraday_profile_by_time_of_day():
    # 10:00 bar always +1% from its open, 10:15 bar always -1%; overnight gap ignored
    rows, idx = [], []
    price = 100.0
    for d in pd.bdate_range("2026-01-05", periods=12):
        o = price * 1.05  # gap up
        c1 = o * 1.01
        c2 = c1 * 0.99
        rows += [(o, c1, o, c1), (c1, c1, c2, c2)]
        idx += [d + pd.Timedelta(hours=10), d + pd.Timedelta(hours=10, minutes=15)]
        price = c2
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    prof = intraday_profile(df)
    assert prof.loc["10:00", "avg_ret_pct"] == 1.0
    assert prof.loc["10:15", "avg_ret_pct"] == -1.0
    assert prof.loc["10:00", "up_pct"] == 100 and prof.loc["10:15", "up_pct"] == 0
    assert prof.loc["10:00", "days"] == 12


def test_scan_and_lists_end_to_end():
    universe = pd.DataFrame({"symbol": ["UP", "DOWN"], "sector": ["A", "B"], "name": ["u", "d"]})
    up = daily(np.r_[np.linspace(10, 20, 80), 21.0], np.r_[np.full(80, 1e7), 3e7])
    down = daily(np.r_[np.linspace(20, 10, 80), 9.0], np.full(81, 1e7))
    res = scan({"UP": up, "DOWN": down}, {}, universe)
    lists = signal_lists(res)
    assert "UP" in lists["breakout"].index and "UP" in lists["swing_long"].index
    assert "DOWN" in lists["breakdown"].index and "DOWN" not in lists["swing_long"].index
    assert "| UP |" in md_table(lists["breakout"], ["close", "breakout_20d"])
