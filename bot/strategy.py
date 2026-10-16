"""Strategy logic shared by the backtester and the live runner.

Entry  : EMA fast crosses EMA slow, confirmed by RSI inside a band.
         Optional FVG filter (``fvg_mode``): ``confirm`` also needs a recent
         same-direction FVG; ``retest`` instead enters on a pullback into an
         FVG in the EMA trend direction.
Grid   : if price moves against the basket, add an order every
         ``grid_step_atr * ATR`` up to ``max_grid_levels`` extra orders.
Exits  : the whole basket closes at
         - take profit: average entry +/- ``tp_atr * ATR``
         - stop loss : last grid level -/+ ``sl_atr * ATR``
         - an opposite EMA cross (if ``close_on_reverse``)

All prices are bid prices. The spread is paid on entry for longs and on exit
for shorts, which is how a broker quoting bid/ask charges it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from .config import MarketConfig, StrategyConfig

LONG = 1
SHORT = -1


def cross(df: pd.DataFrame, i: int) -> int:
    """+1 if EMA fast crossed above EMA slow on bar ``i``, -1 if below, else 0."""
    if i < 1:
        return 0
    prev, cur = df.iloc[i - 1], df.iloc[i]
    if pd.isna(prev["ema_fast"]) or pd.isna(cur["ema_fast"]):
        return 0
    if prev["ema_fast"] <= prev["ema_slow"] and cur["ema_fast"] > cur["ema_slow"]:
        return LONG
    if prev["ema_fast"] >= prev["ema_slow"] and cur["ema_fast"] < cur["ema_slow"]:
        return SHORT
    return 0


def entry_signal(df: pd.DataFrame, i: int, cfg: StrategyConfig) -> int:
    """Signal on the close of bar ``i``: LONG, SHORT or 0."""
    row = df.iloc[i]
    if pd.isna(row["rsi"]) or pd.isna(row["atr"]) or row["atr"] <= 0:
        return 0

    if cfg.fvg_mode == "retest":
        # Pullback into an FVG in the trend direction; RSI only blocks extremes.
        if row["ema_fast"] > row["ema_slow"] and row["fvg_long_touch"] and row["rsi"] <= cfg.rsi_long_max:
            return LONG
        if row["ema_fast"] < row["ema_slow"] and row["fvg_short_touch"] and row["rsi"] >= cfg.rsi_short_min:
            return SHORT
        return 0

    c = cross(df, i)
    if c == LONG and cfg.rsi_long_min <= row["rsi"] <= cfg.rsi_long_max:
        if cfg.fvg_mode == "confirm" and not row["fvg_bull_recent"]:
            return 0
        return LONG
    if c == SHORT and cfg.rsi_short_min <= row["rsi"] <= cfg.rsi_short_max:
        if cfg.fvg_mode == "confirm" and not row["fvg_bear_recent"]:
            return 0
        return SHORT
    return 0


@dataclass
class Position:
    entry: float   # fill price (ask for longs, bid for shorts)
    lots: float


@dataclass
class Basket:
    """A group of same-direction positions managed as one trade."""

    direction: int
    ref_price: float          # bid at the first entry; grid levels hang off this
    atr: float                # ATR frozen at the first entry
    opened_at: str
    positions: list[Position] = field(default_factory=list)

    # --- grid geometry -------------------------------------------------
    def step(self, cfg: StrategyConfig) -> float:
        return self.atr * cfg.grid_step_atr

    @property
    def levels_filled(self) -> int:
        return max(len(self.positions) - 1, 0)

    def next_grid_price(self, cfg: StrategyConfig) -> float | None:
        if self.levels_filled >= cfg.max_grid_levels:
            return None
        return self.ref_price - self.direction * self.step(cfg) * (self.levels_filled + 1)

    def next_lot(self, cfg: StrategyConfig) -> float:
        return round(cfg.base_lot * cfg.lot_multiplier ** len(self.positions), 2)

    # --- exits -------------------------------------------------------
    @property
    def total_lots(self) -> float:
        return sum(p.lots for p in self.positions)

    def avg_bid_entry(self, spread: float) -> float:
        """Average entry expressed as a bid price (removes the spread from longs)."""
        adj = spread if self.direction == LONG else 0.0
        return sum((p.entry - adj) * p.lots for p in self.positions) / self.total_lots

    def tp_price(self, cfg: StrategyConfig, spread: float) -> float:
        return self.avg_bid_entry(spread) + self.direction * cfg.tp_atr * self.atr

    def sl_price(self, cfg: StrategyConfig) -> float:
        last_level = self.ref_price - self.direction * self.step(cfg) * cfg.max_grid_levels
        return last_level - self.direction * cfg.sl_atr * self.atr

    # --- money ----------------------------------------------------------
    def pnl(self, bid: float, mkt: MarketConfig) -> float:
        """Profit in USD if the basket were closed at ``bid`` now."""
        exit_price = bid if self.direction == LONG else bid + mkt.spread
        return sum(
            (exit_price - p.entry) * self.direction * p.lots * mkt.contract_size
            for p in self.positions
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Basket":
        d = dict(d)
        d["positions"] = [Position(**p) for p in d.get("positions", [])]
        return cls(**d)


def fill_price(direction: int, bid: float, mkt: MarketConfig) -> float:
    """Price a market order fills at, given the bid."""
    return bid + mkt.spread if direction == LONG else bid
