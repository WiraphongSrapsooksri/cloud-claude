"""Backtest the strategy.

    python run_backtest.py                      # Yahoo GC=F, H1, ~2 years
    python run_backtest.py --timeframe M15      # last 60 days
    python run_backtest.py --csv data/XAUUSD_M15.csv
"""
import argparse
import json
from pathlib import Path

from bot.backtest import run_backtest
from bot.config import MarketConfig, StrategyConfig
from bot.data import download_yf, load_csv


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", help="OHLC CSV (e.g. exported from MT5)")
    p.add_argument("--yf-symbol", default="GC=F")
    p.add_argument("--timeframe", default="H1", choices=["M5", "M15", "M30", "H1", "H4", "D1"])
    p.add_argument("--balance", type=float, default=10_000)
    p.add_argument("--out", default="logs/backtest")
    a = p.parse_args()

    df = load_csv(a.csv) if a.csv else download_yf(a.yf_symbol, a.timeframe)
    cfg, mkt = StrategyConfig.from_env(), MarketConfig.from_env()
    res = run_backtest(df, cfg, mkt, a.balance)

    print(f"Data: {len(df)} bars {df.index[0]} -> {df.index[-1]}")
    print(json.dumps(res.stats, indent=2, default=str))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res.trades.to_csv(out / "trades.csv", index=False)
    res.equity.to_csv(out / "equity.csv")
    print(f"Trades and equity curve saved to {out}/")


if __name__ == "__main__":
    main()
