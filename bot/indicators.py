"""Technical indicators (pandas only, no TA-Lib needed)."""
from __future__ import annotations

import numpy as np
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


def fvg(df: pd.DataFrame, atr_s: pd.Series, lookback: int = 20, min_atr: float = 0.2) -> pd.DataFrame:
    """Fair Value Gaps (3-candle imbalances), using only bars up to each row.

    A bullish FVG forms on bar i when low[i] > high[i-2]; the gap is the zone
    [high[i-2], low[i]]. A bearish FVG forms when high[i] < low[i-2]; the zone
    is [high[i], low[i-2]]. Gaps smaller than ``min_atr * ATR`` are ignored.

    Columns returned:
      fvg_bull / fvg_bear              a qualifying FVG formed on this bar
      fvg_bull_recent / fvg_bear_recent  one formed within the last ``lookback`` bars
      fvg_long_touch    this bar dipped into an unused bullish FVG (formed on an
                        earlier bar, within ``lookback``) and closed above its bottom
      fvg_short_touch   mirror image for bearish FVGs
    A zone is used up by its first touch, or dropped once a close goes through it.
    """
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    a = atr_s.to_numpy()
    n = len(df)
    bull = [False] * n
    bear = [False] * n
    long_touch = [False] * n
    short_touch = [False] * n
    bull_zones: list[tuple[int, float, float]] = []  # (formed_at, bottom, top)
    bear_zones: list[tuple[int, float, float]] = []

    for i in range(n):
        # Touches of zones formed on earlier bars
        keep = []
        for k, bottom, top in bull_zones:
            if i - k > lookback or c[i] < bottom:
                continue  # expired or invalidated
            if l[i] <= top:
                if c[i] > bottom:
                    long_touch[i] = True
                continue  # used up
            keep.append((k, bottom, top))
        bull_zones = keep

        keep = []
        for k, bottom, top in bear_zones:
            if i - k > lookback or c[i] > top:
                continue
            if h[i] >= bottom:
                if c[i] < top:
                    short_touch[i] = True
                continue
            keep.append((k, bottom, top))
        bear_zones = keep

        # New zones formed on this bar
        if i >= 2 and not np.isnan(a[i]):
            min_gap = min_atr * a[i]
            if l[i] > h[i - 2] and l[i] - h[i - 2] >= min_gap:
                bull[i] = True
                bull_zones.append((i, h[i - 2], l[i]))
            if h[i] < l[i - 2] and l[i - 2] - h[i] >= min_gap:
                bear[i] = True
                bear_zones.append((i, h[i], l[i - 2]))

    out = pd.DataFrame(
        {"fvg_bull": bull, "fvg_bear": bear, "fvg_long_touch": long_touch, "fvg_short_touch": short_touch},
        index=df.index,
    )
    out["fvg_bull_recent"] = out["fvg_bull"].rolling(lookback, min_periods=1).max().astype(bool)
    out["fvg_bear_recent"] = out["fvg_bear"].rolling(lookback, min_periods=1).max().astype(bool)
    return out


def add_indicators(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = ema(out["close"], cfg.ema_fast)
    out["ema_slow"] = ema(out["close"], cfg.ema_slow)
    out["rsi"] = rsi(out["close"], cfg.rsi_period)
    out["atr"] = atr(out, cfg.atr_period)
    if cfg.fvg_mode != "off":
        out = out.join(fvg(out, out["atr"], cfg.fvg_lookback, cfg.fvg_min_atr))
    return out
