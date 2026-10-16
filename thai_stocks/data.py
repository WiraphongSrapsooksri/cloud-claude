"""Download SET100 prices from Yahoo Finance (symbols end in .BK).

Yahoo's Thai prices are delayed (~15-20 min) and 15-minute history only goes
back 60 days. Good enough for pre-market / end-of-day scans, not for scalping.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

UNIVERSE_CSV = Path(__file__).with_name("set100.csv")
INDEX_SYMBOL = "^SET.BK"


def load_universe(path: str | Path = UNIVERSE_CSV) -> pd.DataFrame:
    """SET100 constituents: symbol, name, sector."""
    return pd.read_csv(path)


def _split(raw: pd.DataFrame, tickers: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for t in tickers:
        if t not in raw.columns.get_level_values(0):
            continue
        df = raw[t].rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(
            subset=["close"]
        )
        if not df.empty:
            out[t.removesuffix(".BK")] = df.astype(float)
    return out


def download(symbols: list[str], period: str, interval: str) -> dict[str, pd.DataFrame]:
    """{symbol: OHLCV DataFrame}. ``symbols`` without the .BK suffix; ^SET.BK is passed through."""
    import yfinance as yf

    tickers = [s if s.startswith("^") else f"{s}.BK" for s in symbols]
    raw = yf.download(
        tickers, period=period, interval=interval, group_by="ticker",
        auto_adjust=False, progress=False, threads=True,
    )
    if raw.empty:
        raise RuntimeError(f"no data from Yahoo ({interval}, {period})")
    if not isinstance(raw.columns, pd.MultiIndex):  # single ticker
        raw.columns = pd.MultiIndex.from_product([tickers, raw.columns])
    return _split(raw, tickers)
