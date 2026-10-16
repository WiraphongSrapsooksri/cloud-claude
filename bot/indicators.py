"""Technical indicators (pandas only, no TA-Lib needed)."""
from __future__ import annotations

import pandas as pd

from .config import StrategyConfig


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss
    out = 100 - 100 / (1 + rs)
    # No losses in the window -> RSI 100; flat window -> 50
    out = out.where(loss != 0, 100.0)
    out = out.where(~((gain == 0) & (loss == 0)), 50.0)
    return out.where(gain.notna())


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's Average True Range."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def add_indicators(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = ema(out["close"], cfg.ema_fast)
    out["ema_slow"] = ema(out["close"], cfg.ema_slow)
    out["rsi"] = rsi(out["close"], cfg.rsi_period)
    out["atr"] = atr(out, cfg.atr_period)
    return out
