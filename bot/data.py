"""Price data loading: CSV files or Yahoo Finance.

Yahoo has no spot XAUUSD, so ``GC=F`` (COMEX gold futures) is used as a
proxy. It tracks spot closely but trades at a small premium and has its own
session gaps. For serious testing, export XAUUSD history from your MT5
broker to CSV and load that instead.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

YF_INTERVALS = {"M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h", "H4": "1h", "D1": "1d"}
# Yahoo's limits on how far back intraday data goes
YF_MAX_PERIOD = {"5m": "60d", "15m": "60d", "30m": "60d", "1h": "730d", "1d": "max"}


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)
    missing = {"open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise ValueError(f"price data is missing columns: {sorted(missing)}")
    df = df[["open", "high", "low", "close"]].astype(float).dropna()
    return df[~df.index.duplicated()].sort_index()


def load_csv(path: str | Path) -> pd.DataFrame:
    """CSV with a time column (time/date/datetime) plus open, high, low, close.

    MT5 exports (tab separated, <DATE> <TIME> <OPEN> ...) are handled too.
    """
    path = Path(path)
    sep = "\t" if "\t" in path.open().readline() else ","
    df = pd.read_csv(path, sep=sep)
    df.columns = [c.strip("<>").lower() for c in df.columns]
    if "date" in df.columns and "time" in df.columns:
        df.index = pd.to_datetime(df["date"] + " " + df["time"])
    else:
        tcol = next((c for c in ("time", "datetime", "date", "timestamp") if c in df.columns), None)
        if tcol is None:
            raise ValueError("CSV needs a time/datetime/date column")
        df.index = pd.to_datetime(df[tcol])
    return _normalise(df)


def download_yf(symbol: str = "GC=F", timeframe: str = "H1", period: str | None = None) -> pd.DataFrame:
    import yfinance as yf

    interval = YF_INTERVALS[timeframe]
    period = period or YF_MAX_PERIOD[interval]
    raw = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=False)
    if raw.empty:
        raise RuntimeError(f"no data from Yahoo for {symbol} {interval} {period}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = _normalise(raw)
    if timeframe == "H4":
        df = resample(df, "4h")
    return df


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return (
        df.resample(rule)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )
