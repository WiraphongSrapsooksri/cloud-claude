import numpy as np
import pandas as pd

from bot.indicators import atr, ema, rsi


def test_ema_of_constant_is_constant():
    s = pd.Series([5.0] * 30)
    assert np.allclose(ema(s, 10), 5.0)


def test_rsi_extremes_and_range():
    up = pd.Series(np.arange(1, 50, dtype=float))
    down = up[::-1].reset_index(drop=True)
    assert rsi(up, 14).iloc[-1] == 100
    assert rsi(down, 14).iloc[-1] == 0
    noisy = pd.Series(np.random.default_rng(0).normal(0, 1, 500).cumsum() + 100)
    r = rsi(noisy, 14).dropna()
    assert ((r >= 0) & (r <= 100)).all()
    assert rsi(noisy, 14).iloc[:13].isna().all()


def test_atr_uses_gaps():
    df = pd.DataFrame({"open": [10, 20] * 20, "high": [11, 21] * 20,
                       "low": [9, 19] * 20, "close": [10, 20] * 20}, dtype=float)
    # true range after the first bar is |high - prev close| = 11; ATR converges to it
    assert abs(atr(df, 5).iloc[-1] - 11) < 0.01
