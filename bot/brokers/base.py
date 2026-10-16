"""The small surface the live runner needs from a broker."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Broker(ABC):
    @abstractmethod
    def get_closed_bars(self, count: int) -> pd.DataFrame:
        """The last ``count`` *closed* bars (open/high/low/close), oldest first."""

    @abstractmethod
    def get_bid(self) -> float:
        """Current bid price."""

    @abstractmethod
    def open_market(self, direction: int, lots: float) -> float:
        """Open a market order (1 = buy, -1 = sell). Returns the fill price."""

    @abstractmethod
    def close_all(self) -> None:
        """Close every position this bot opened on the symbol."""

    def shutdown(self) -> None:
        pass
