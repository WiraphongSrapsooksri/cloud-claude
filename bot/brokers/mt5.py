"""MetaTrader 5 broker (Windows only; ``pip install MetaTrader5``).

Orders are only sent when ``LIVE_TRADING=yes``. Otherwise every order is
logged as a dry run, so you can watch the bot against live MT5 prices first.
Always start on a DEMO account.
"""
from __future__ import annotations

import logging
import os

import pandas as pd

from .base import Broker

log = logging.getLogger(__name__)

_TIMEFRAMES = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
               "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4", "D1": "TIMEFRAME_D1"}


class MT5Broker(Broker):
    def __init__(self, symbol: str, timeframe: str, **_):
        try:
            import MetaTrader5 as mt5
        except ImportError as e:
            raise RuntimeError("MetaTrader5 is not installed (Windows only: pip install MetaTrader5)") from e
        self.mt5 = mt5
        self.symbol = symbol
        self.tf = getattr(mt5, _TIMEFRAMES[timeframe])
        self.magic = int(os.getenv("MT5_MAGIC", "20261016"))
        self.live = os.getenv("LIVE_TRADING", "no").strip().lower() == "yes"

        init_kwargs = {}
        if os.getenv("MT5_PATH"):
            init_kwargs["path"] = os.environ["MT5_PATH"]
        if os.getenv("MT5_LOGIN"):
            init_kwargs.update(
                login=int(os.environ["MT5_LOGIN"]),
                password=os.getenv("MT5_PASSWORD", ""),
                server=os.getenv("MT5_SERVER", ""),
            )
        if not mt5.initialize(**init_kwargs):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"symbol {symbol} not found at this broker")
        acc = mt5.account_info()
        log.info("MT5 connected: account %s (%s), live=%s",
                 acc.login, "DEMO" if acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "REAL", self.live)

    def get_closed_bars(self, count: int) -> pd.DataFrame:
        rates = self.mt5.copy_rates_from_pos(self.symbol, self.tf, 1, count)  # start=1 skips the forming bar
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"no bars: {self.mt5.last_error()}")
        df = pd.DataFrame(rates)
        df.index = pd.to_datetime(df["time"], unit="s")
        return df[["open", "high", "low", "close"]].astype(float)

    def get_bid(self) -> float:
        return float(self.mt5.symbol_info_tick(self.symbol).bid)

    def _filling(self) -> int:
        mode = self.mt5.symbol_info(self.symbol).filling_mode
        if mode & 1:
            return self.mt5.ORDER_FILLING_FOK
        if mode & 2:
            return self.mt5.ORDER_FILLING_IOC
        return self.mt5.ORDER_FILLING_RETURN

    def _send(self, order_type: int, lots: float, position: int | None = None) -> float:
        mt5 = self.mt5
        tick = mt5.symbol_info_tick(self.symbol)
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": self.symbol, "volume": float(lots),
            "type": order_type, "price": price, "deviation": 30, "magic": self.magic,
            "comment": "xau-grid-bot", "type_time": mt5.ORDER_TIME_GTC, "type_filling": self._filling(),
        }
        if position is not None:
            req["position"] = position
        side = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"
        if not self.live:
            log.warning("[DRY RUN] %s %.2f %s @ %.2f (set LIVE_TRADING=yes to send)", side, lots, self.symbol, price)
            return price
        res = mt5.order_send(req)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"order_send failed: {res.retcode if res else mt5.last_error()} {res.comment if res else ''}")
        log.info("%s %.2f %s @ %.2f (ticket %s)", side, lots, self.symbol, res.price, res.order)
        return float(res.price)

    def open_market(self, direction: int, lots: float) -> float:
        return self._send(self.mt5.ORDER_TYPE_BUY if direction == 1 else self.mt5.ORDER_TYPE_SELL, lots)

    def close_all(self) -> None:
        for p in self.mt5.positions_get(symbol=self.symbol) or []:
            if p.magic != self.magic:
                continue
            opposite = self.mt5.ORDER_TYPE_SELL if p.type == self.mt5.POSITION_TYPE_BUY else self.mt5.ORDER_TYPE_BUY
            self._send(opposite, p.volume, position=p.ticket)

    def shutdown(self) -> None:
        self.mt5.shutdown()
