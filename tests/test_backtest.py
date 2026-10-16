import numpy as np
import pandas as pd

from bot.backtest import run_backtest
from bot.config import MarketConfig, StrategyConfig


def make_df(closes, wiggle=0.5):
    closes = np.asarray(closes, dtype=float)
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="h")
    opens = np.r_[closes[0], closes[:-1]]
    return pd.DataFrame({"open": opens, "high": np.maximum(opens, closes) + wiggle,
                         "low": np.minimum(opens, closes) - wiggle, "close": closes}, index=idx)


CFG = StrategyConfig(ema_fast=5, ema_slow=20, rsi_period=14, atr_period=14,
                     rsi_long_min=50, rsi_long_max=100, rsi_short_min=0, rsi_short_max=50)
MKT = MarketConfig(spread=0.3)


def test_downtrend_then_rally_takes_profit_long():
    closes = np.r_[np.linspace(2100, 2000, 60), np.linspace(2000, 2100, 60)]
    res = run_backtest(make_df(closes), CFG, MKT)
    longs = res.trades[res.trades["direction"] == "LONG"]
    assert not longs.empty
    assert (longs["reason"] == "take_profit").any()
    assert longs["pnl"].iloc[0] > 0


def test_crash_after_long_entry_hits_stop_with_all_grid_orders():
    cfg = StrategyConfig(**{**CFG.__dict__, "close_on_reverse": False})
    base = np.r_[np.linspace(2100, 2000, 60), np.linspace(2000, 2060, 40)]
    first = run_backtest(make_df(base), cfg, MKT).trades.iloc[0]
    assert first["direction"] == "LONG"
    # crash straight down from the entry bar
    entry_i = make_df(base).index.get_loc(pd.Timestamp(first["opened_at"]))
    closes = np.r_[base[: entry_i + 1], np.linspace(base[entry_i], base[entry_i] - 150, 40)]
    res = run_backtest(make_df(closes), cfg, MKT)
    t = res.trades.iloc[0]
    assert t["direction"] == "LONG" and t["reason"] == "stop_loss"
    assert t["orders"] == cfg.max_grid_levels + 1
    assert t["pnl"] < 0


def test_equity_matches_trades():
    rng = np.random.default_rng(1)
    closes = 2000 + rng.normal(0, 3, 2000).cumsum()
    res = run_backtest(make_df(closes), CFG, MKT, initial_balance=10_000)
    assert res.stats["trades"] > 0
    assert abs(res.equity.iloc[-1] - (10_000 + res.trades["pnl"].sum())) < 0.05


def test_no_trades_on_flat_market():
    res = run_backtest(make_df([2000.0] * 300, wiggle=0.0), CFG, MKT)
    assert res.stats["trades"] == 0
