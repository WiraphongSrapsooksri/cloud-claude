"""Settings for the strategy and the market, overridable through environment variables.

Every field can be set with an env var of the same name in upper case,
e.g. ``EMA_FAST=21`` or ``MAX_GRID_LEVELS=3`` (also read from a ``.env`` file).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, fields

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass


def _cast(value: str, typ):
    if typ is bool or typ == "bool":
        return value.strip().lower() in ("1", "true", "yes", "on")
    if typ is int or typ == "int":
        return int(value)
    if typ is float or typ == "float":
        return float(value)
    return value


class _EnvMixin:
    @classmethod
    def from_env(cls, **overrides):
        kwargs = {}
        for f in fields(cls):
            raw = os.getenv(f.name.upper())
            if raw is not None and raw.strip() != "":
                kwargs[f.name] = _cast(raw.strip(), f.type)
        kwargs.update(overrides)
        return cls(**kwargs)


@dataclass
class StrategyConfig(_EnvMixin):
    # Trend: EMA crossover
    ema_fast: int = 20
    ema_slow: int = 50
    # Momentum filter: RSI must sit in this band to confirm the cross
    rsi_period: int = 14
    rsi_long_min: float = 50.0
    rsi_long_max: float = 70.0
    rsi_short_min: float = 30.0
    rsi_short_max: float = 50.0
    # Fair Value Gap (3-candle imbalance) filter
    #   off     : not used
    #   confirm : the EMA-cross signal also needs a same-direction FVG in the last fvg_lookback bars
    #   retest  : no cross needed; in the EMA trend direction, enter when price pulls back
    #             into a still-unused FVG and closes back outside it
    fvg_mode: str = "off"
    fvg_lookback: int = 20          # bars an FVG stays valid
    fvg_min_atr: float = 0.2        # ignore gaps smaller than this many ATR
    # Volatility: ATR sizes the grid, take-profit and stop-loss
    atr_period: int = 14
    # Grid: extra orders added when price moves against the basket
    grid_step_atr: float = 1.0      # distance between grid levels, in ATR
    max_grid_levels: int = 4        # extra orders after the first one
    base_lot: float = 0.01
    lot_multiplier: float = 1.0     # 1.0 = equal lots; >1 = martingale (dangerous)
    # Exits for the whole basket
    tp_atr: float = 1.5             # take profit distance from the average entry, in ATR
    sl_atr: float = 1.0             # stop distance beyond the last grid level, in ATR
    close_on_reverse: bool = True   # close the basket on an opposite EMA cross

    def __post_init__(self):
        if self.ema_fast >= self.ema_slow:
            raise ValueError("ema_fast must be smaller than ema_slow")
        if self.max_grid_levels < 0:
            raise ValueError("max_grid_levels must be >= 0")
        if self.base_lot <= 0 or self.lot_multiplier <= 0:
            raise ValueError("base_lot and lot_multiplier must be > 0")
        if self.grid_step_atr <= 0 or self.tp_atr <= 0 or self.sl_atr < 0:
            raise ValueError("grid_step_atr and tp_atr must be > 0, sl_atr >= 0")
        self.fvg_mode = self.fvg_mode.lower()
        if self.fvg_mode not in ("off", "confirm", "retest"):
            raise ValueError("fvg_mode must be off, confirm or retest")
        if self.fvg_lookback < 1 or self.fvg_min_atr < 0:
            raise ValueError("fvg_lookback must be >= 1 and fvg_min_atr >= 0")

    @property
    def warmup_bars(self) -> int:
        return max(self.ema_slow, self.rsi_period, self.atr_period) + 1


@dataclass
class MarketConfig(_EnvMixin):
    symbol: str = "XAUUSD"
    contract_size: float = 100.0    # 1 lot of XAUUSD = 100 oz
    spread: float = 0.30            # USD per oz; charged once per position
