"""Per-stock metrics and signal lists for the SET100 scan.

Daily bars  -> trend, momentum, volume, breakouts, FVG (swing ideas)
15-min bars -> intraday range and which time of day a stock tends to rise
               or fall (day-trading ideas)
Everything uses only data up to the last bar, so a scan never peeks ahead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bot.indicators import atr, ema, fvg, rsi

EMA_FAST, EMA_SLOW = 20, 50
LOOKBACK = 20  # bars for highs/lows and average volume


def daily_metrics(df: pd.DataFrame) -> dict | None:
    """Metrics from daily OHLCV. Returns None if there is not enough history."""
    if len(df) < EMA_SLOW + 5:
        return None
    c, v = df["close"], df["volume"]
    e_fast, e_slow = ema(c, EMA_FAST), ema(c, EMA_SLOW)
    r = rsi(c, 14)
    a = atr(df, 14)
    gaps = fvg(df, a, lookback=10, min_atr=0.3)

    last = c.iloc[-1]
    prior_high = df["high"].iloc[-LOOKBACK - 1:-1].max()
    prior_low = df["low"].iloc[-LOOKBACK - 1:-1].min()
    avg_vol = v.iloc[-LOOKBACK - 1:-1].mean()

    if last > e_fast.iloc[-1] > e_slow.iloc[-1]:
        trend = "up"
    elif last < e_fast.iloc[-1] < e_slow.iloc[-1]:
        trend = "down"
    else:
        trend = "sideways"

    diff = (e_fast - e_slow).iloc[-4:]
    cross = "up" if (diff.iloc[0] <= 0 < diff.iloc[-1]) else "down" if (diff.iloc[0] >= 0 > diff.iloc[-1]) else ""

    def pct(n):
        return round(100 * (last / c.iloc[-1 - n] - 1), 2) if len(c) > n else np.nan

    return {
        "date": str(df.index[-1].date()),
        "close": round(float(last), 2),
        "chg_1d": pct(1),
        "chg_5d": pct(5),
        "chg_20d": pct(20),
        "rsi": round(float(r.iloc[-1]), 1),
        "trend": trend,
        "ema_cross_3d": cross,
        "atr_pct": round(float(100 * a.iloc[-1] / last), 2),
        "vol_ratio": round(float(v.iloc[-1] / avg_vol), 2) if avg_vol > 0 else np.nan,
        "value_mthb": round(float(last * v.iloc[-1] / 1e6), 1),
        "avg_value_mthb": round(float((c * v).iloc[-LOOKBACK - 1:-1].mean() / 1e6), 1),
        "high_20d": round(float(prior_high), 2),
        "low_20d": round(float(prior_low), 2),
        "breakout_20d": bool(last > prior_high),
        "breakdown_20d": bool(last < prior_low),
        "dist_high_pct": round(float(100 * (last / prior_high - 1)), 2),
        "dist_low_pct": round(float(100 * (last / prior_low - 1)), 2),
        "fvg_bull_retest": bool(gaps["fvg_long_touch"].iloc[-3:].any()),
        "fvg_bear_retest": bool(gaps["fvg_short_touch"].iloc[-3:].any()),
    }


def intraday_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Average 15-min return by time of day.

    Returns one row per bar time (e.g. "10:00") with:
      avg_ret_pct  mean close-to-close return of that bar
      up_pct       share of days that bar closed up
      days         number of days in the sample
    The first bar of each day is measured from its own open, so overnight
    gaps are kept out of the time-of-day pattern.
    """
    df = df.copy()
    day = df.index.date
    prev_close = df["close"].groupby(day).shift(1)
    base = prev_close.fillna(df["open"])
    df["ret"] = 100 * (df["close"] / base - 1)
    df["slot"] = df.index.strftime("%H:%M")
    g = df.groupby("slot")["ret"]
    return pd.DataFrame({
        "avg_ret_pct": g.mean().round(3),
        "up_pct": (g.apply(lambda s: (s > 0).mean()) * 100).round(0),
        "days": g.count(),
    })


def intraday_metrics(df: pd.DataFrame) -> dict | None:
    if df is None or len(df) < 100:
        return None
    prof = intraday_profile(df)
    prof = prof[prof["days"] >= 10]
    daily = df.groupby(df.index.date).agg(high=("high", "max"), low=("low", "min"), open=("open", "first"))
    rng = 100 * (daily["high"] - daily["low"]) / daily["open"]
    return {
        "avg_day_range_pct": round(float(rng.mean()), 2),
        "best_slot": prof["avg_ret_pct"].idxmax() if not prof.empty else "",
        "best_slot_ret": float(prof["avg_ret_pct"].max()) if not prof.empty else np.nan,
        "worst_slot": prof["avg_ret_pct"].idxmin() if not prof.empty else "",
        "worst_slot_ret": float(prof["avg_ret_pct"].min()) if not prof.empty else np.nan,
        "last_bar": str(df.index[-1]),
    }


def swing_score(m: dict) -> int:
    """Simple, transparent long score (0-6). Higher = more conditions lined up."""
    return int(
        (m["trend"] == "up")
        + (50 <= m["rsi"] <= 70)
        + (m["ema_cross_3d"] == "up")
        + m["breakout_20d"]
        + m["fvg_bull_retest"]
        + (m["vol_ratio"] >= 1.5)
    )


def scan(daily: dict[str, pd.DataFrame], intraday: dict[str, pd.DataFrame], universe: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, u in universe.iterrows():
        d = daily.get(u["symbol"])
        m = daily_metrics(d) if d is not None else None
        if m is None:
            continue
        m.update(intraday_metrics(intraday.get(u["symbol"])) or {})
        m["symbol"], m["sector"] = u["symbol"], u["sector"]
        m["swing_score"] = swing_score(m)
        rows.append(m)
    df = pd.DataFrame(rows).set_index("symbol")
    return df


def signal_lists(res: pd.DataFrame, top: int = 10) -> dict[str, pd.DataFrame]:
    """Named watchlists built from the scan table."""
    liquid = res[res["avg_value_mthb"] >= 50]  # skip thin names for trading lists
    lists = {
        "swing_long": liquid[(liquid["swing_score"] >= 3) & (liquid["trend"] == "up")]
        .sort_values(["swing_score", "vol_ratio"], ascending=False),
        "breakout": liquid[liquid["breakout_20d"]].sort_values("vol_ratio", ascending=False),
        "unusual_volume": res[res["vol_ratio"] >= 2].sort_values("vol_ratio", ascending=False),
        "oversold": res[res["rsi"] < 30].sort_values("rsi"),
        "overbought": res[res["rsi"] > 75].sort_values("rsi", ascending=False),
        "breakdown": liquid[liquid["breakdown_20d"]].sort_values("chg_1d"),
    }
    if "avg_day_range_pct" in res:
        lists["day_trade"] = (
            res[res["avg_value_mthb"] >= 300].sort_values("avg_day_range_pct", ascending=False)
        )
    return {k: v.head(top) for k, v in lists.items()}


def sector_summary(res: pd.DataFrame) -> pd.DataFrame:
    return (
        res.groupby("sector")
        .agg(stocks=("close", "size"), chg_1d=("chg_1d", "mean"), chg_5d=("chg_5d", "mean"),
             chg_20d=("chg_20d", "mean"), up_trend=("trend", lambda s: int((s == "up").sum())))
        .round(2)
        .sort_values("chg_5d", ascending=False)
    )
