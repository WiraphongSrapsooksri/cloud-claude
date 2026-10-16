"""Run the bot live (MT5 on Windows) or in paper mode (anywhere).

    python run_live.py                 # uses BROKER from .env (default: paper)
    python run_live.py --broker mt5
"""
import argparse
import logging
import os
from pathlib import Path

from bot.brokers import make_broker
from bot.config import MarketConfig, StrategyConfig
from bot.live import LiveRunner


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--broker", default=os.getenv("BROKER", "paper"))
    p.add_argument("--timeframe", default=os.getenv("TIMEFRAME", "M15"))
    p.add_argument("--poll", type=int, default=int(os.getenv("POLL_SECONDS", "10")))
    a = p.parse_args()

    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("logs/bot.log", encoding="utf-8")],
    )
    cfg, mkt = StrategyConfig.from_env(), MarketConfig.from_env()
    broker = make_broker(a.broker, mkt.symbol, a.timeframe, spread=mkt.spread)
    LiveRunner(broker, cfg, mkt, poll_seconds=a.poll).run()


if __name__ == "__main__":
    main()
