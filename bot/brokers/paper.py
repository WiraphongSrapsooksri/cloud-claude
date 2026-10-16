"""Paper trading: real Yahoo prices, simulated fills. No account needed."""
from __future__ import annotations

import logging

import pandas as pd

from ..data import download_yf
from .base import Broker

log = logging.getLogger(__name__)


class PaperBroker(Broker):
    def __init__(self, symbol: str, timeframe: str, spread: float = 0.30, yf_symbol: str = "GC=F", **_):
        self.symbol = symbol
        self.timeframe = timeframe
        self.spread = spread
        self.yf_symbol = yf_symbol
        self.open_lots = 0.0

    def get_closed_bars(self, count: int) -> pd.DataFrame:
        df = download_yf(self.yf_symbol, self.timeframe, period="60d")
        return df.iloc[:-1].tail(count)  # the last Yahoo bar is still forming

    def get_bid(self) -> float:
        return float(download_yf(self.yf_symbol, "M5", period="1d")["close"].iloc[-1])

    def open_market(self, direction: int, lots: float) -> float:
        bid = self.get_bid()
        price = bid + self.spread if direction == 1 else bid
        self.open_lots += lots
        log.info("[PAPER] %s %.2f lots %s @ %.2f", "BUY" if direction == 1 else "SELL", lots, self.symbol, price)
        return price

    def close_all(self) -> None:
        log.info("[PAPER] close all %s (%.2f lots)", self.symbol, self.open_lots)
        self.open_lots = 0.0
