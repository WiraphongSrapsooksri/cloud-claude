import pandas as pd
import pytest

from bot.config import StrategyConfig
from bot.indicators import fvg
from bot.strategy import LONG, SHORT, entry_signal


def candles(rows):
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    df.index = pd.date_range("2026-01-01", periods=len(df), freq="h")
    return df


def flat_atr(df, value=1.0):
    return pd.Series(value, index=df.index)


# bar0 high 101, bar2 low 103 -> bullish gap [101, 103]
BULL = [
    (100, 101, 99, 100.5),
    (100.5, 104, 100.5, 103.8),
    (103.8, 106, 103, 105.5),
]


def test_bullish_fvg_detected_and_retest_signalled():
    df = candles(BULL + [
        (105.5, 106, 104, 105),     # stays above the gap
        (105, 105.2, 102, 104),     # dips into [101, 103], closes above 101 -> touch
        (104, 104.5, 101.5, 102),   # zone already used -> no second touch
    ])
    out = fvg(df, flat_atr(df), lookback=10, min_atr=0.2)
    assert out["fvg_bull"].tolist() == [False, False, True, False, False, False]
    assert out["fvg_long_touch"].tolist() == [False, False, False, False, True, False]
    assert out["fvg_bull_recent"].iloc[2:].all()
    assert not out["fvg_bear"].any()


def test_close_through_gap_invalidates_without_signal():
    df = candles(BULL + [(105.5, 105.6, 99, 100)])  # closes below the gap bottom
    out = fvg(df, flat_atr(df), lookback=10, min_atr=0.2)
    assert not out["fvg_long_touch"].any()


def test_gap_expires_after_lookback():
    # filler bars stay above the gap without forming a new one
    df = candles(BULL + [(105, 106, 103.5, 105)] * 3 + [(105, 105.2, 102, 104)])
    assert not fvg(df, flat_atr(df), lookback=2, min_atr=0.2)["fvg_long_touch"].any()
    assert fvg(df, flat_atr(df), lookback=10, min_atr=0.2)["fvg_long_touch"].iloc[-1]


def test_small_gaps_ignored():
    df = candles(BULL)
    assert not fvg(df, flat_atr(df, 10.0), lookback=10, min_atr=0.5)["fvg_bull"].any()  # gap 2 < 5


def test_bearish_fvg_mirror():
    df = candles([
        (105.5, 106, 104, 104.5),
        (104.5, 104.5, 101, 101.2),
        (101.2, 102, 99, 99.5),     # high 102 < bar0 low 104 -> bearish gap [102, 104]
        (99.5, 103, 99.4, 101),     # rallies into the gap, closes below 104 -> touch
    ])
    out = fvg(df, flat_atr(df), lookback=10, min_atr=0.2)
    assert out["fvg_bear"].tolist() == [False, False, True, False]
    assert out["fvg_short_touch"].tolist() == [False, False, False, True]


def _row_df(**cols):
    base = {"ema_fast": 0.0, "ema_slow": 0.0, "rsi": 55.0, "atr": 1.0,
            "fvg_bull_recent": False, "fvg_bear_recent": False,
            "fvg_long_touch": False, "fvg_short_touch": False}
    rows = [dict(base, ema_fast=99.0, ema_slow=100.0), {**base, "ema_fast": 101.0, "ema_slow": 100.0, **cols}]
    return pd.DataFrame(rows)


@pytest.mark.parametrize("mode,cols,expected", [
    ("off", {}, LONG),
    ("confirm", {}, 0),
    ("confirm", {"fvg_bull_recent": True}, LONG),
    ("retest", {}, 0),
    ("retest", {"fvg_long_touch": True}, LONG),
    ("retest", {"fvg_long_touch": True, "rsi": 75.0}, 0),   # overbought blocks
    ("retest", {"fvg_short_touch": True}, 0),                # against the trend
])
def test_entry_signal_fvg_modes(mode, cols, expected):
    cfg = StrategyConfig(fvg_mode=mode)
    assert entry_signal(_row_df(**cols), 1, cfg) == expected


def test_retest_short_in_downtrend():
    df = _row_df(ema_fast=99.0, ema_slow=100.0, fvg_short_touch=True, rsi=40.0)
    assert entry_signal(df, 1, StrategyConfig(fvg_mode="retest")) == SHORT


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        StrategyConfig(fvg_mode="sometimes")
