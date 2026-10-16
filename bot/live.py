"""Live / paper trading loop.

Polls the broker every ``poll_seconds``:
  * on every poll: manage the open basket against the current bid
    (add grid orders, stop loss, take profit)
  * once per newly closed bar: opposite-cross exit, then new entries

The open basket is saved to ``state/basket.json`` so a restart resumes it.
Every closed basket is appended to ``logs/journal.csv`` — the trade journal
used to review and improve the strategy.
"""
from __future__ import annotations

import csv
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .brokers.base import Broker
from .config import MarketConfig, StrategyConfig
from .indicators import add_indicators
from .strategy import LONG, Basket, Position, cross, entry_signal

log = logging.getLogger(__name__)

JOURNAL_FIELDS = [
    "opened_at", "closed_at", "direction", "orders", "lots", "avg_entry", "exit_bid",
    "reason", "pnl", "atr_at_entry", "rsi_at_entry", "ema_fast_at_entry", "ema_slow_at_entry",
    "max_adverse_usd", "max_favourable_usd", "config",
]


class LiveRunner:
    def __init__(
        self,
        broker: Broker,
        cfg: StrategyConfig,
        mkt: MarketConfig,
        poll_seconds: int = 10,
        state_dir: str | Path = "state",
        log_dir: str | Path = "logs",
    ):
        self.broker = broker
        self.cfg = cfg
        self.mkt = mkt
        self.poll_seconds = poll_seconds
        self.state_path = Path(state_dir) / "basket.json"
        self.journal_path = Path(log_dir) / "journal.csv"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.basket: Basket | None = None
        self.entry_context: dict = {}
        self.last_bar_time: str | None = None
        self.mae = 0.0  # worst open P/L of the current basket
        self.mfe = 0.0  # best open P/L of the current basket
        self._load_state()

    # --- persistence ------------------------------------------------------
    def _load_state(self):
        if not self.state_path.exists():
            return
        s = json.loads(self.state_path.read_text())
        self.basket = Basket.from_dict(s["basket"]) if s.get("basket") else None
        self.entry_context = s.get("entry_context", {})
        self.last_bar_time = s.get("last_bar_time")
        self.mae, self.mfe = s.get("mae", 0.0), s.get("mfe", 0.0)
        if self.basket:
            log.info("resumed %s basket with %d orders", self._side(), len(self.basket.positions))

    def _save_state(self):
        self.state_path.write_text(json.dumps({
            "basket": self.basket.to_dict() if self.basket else None,
            "entry_context": self.entry_context,
            "last_bar_time": self.last_bar_time,
            "mae": self.mae, "mfe": self.mfe,
        }, indent=2))

    def _journal(self, exit_bid: float, reason: str, pnl: float):
        new = not self.journal_path.exists()
        with self.journal_path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=JOURNAL_FIELDS)
            if new:
                w.writeheader()
            w.writerow({
                "opened_at": self.basket.opened_at,
                "closed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "direction": self._side(),
                "orders": len(self.basket.positions),
                "lots": round(self.basket.total_lots, 2),
                "avg_entry": round(self.basket.avg_bid_entry(self.mkt.spread), 2),
                "exit_bid": round(exit_bid, 2),
                "reason": reason,
                "pnl": round(pnl, 2),
                **self.entry_context,
                "max_adverse_usd": round(self.mae, 2),
                "max_favourable_usd": round(self.mfe, 2),
                "config": json.dumps(asdict(self.cfg)),
            })

    # --- trading actions ----------------------------------------------------
    def _side(self) -> str:
        return "LONG" if self.basket and self.basket.direction == LONG else "SHORT"

    def _open(self, direction: int, row, when: str):
        self.basket = Basket(direction=direction, ref_price=float(row["close"]),
                             atr=float(row["atr"]), opened_at=when)
        lots = self.basket.next_lot(self.cfg)
        price = self.broker.open_market(direction, lots)
        self.basket.positions.append(Position(price, lots))
        self.entry_context = {
            "atr_at_entry": round(float(row["atr"]), 2),
            "rsi_at_entry": round(float(row["rsi"]), 1),
            "ema_fast_at_entry": round(float(row["ema_fast"]), 2),
            "ema_slow_at_entry": round(float(row["ema_slow"]), 2),
        }
        self.mae = self.mfe = 0.0
        log.info("OPEN %s basket: ref %.2f, ATR %.2f, TP %.2f, SL %.2f", self._side(),
                 self.basket.ref_price, self.basket.atr,
                 self.basket.tp_price(self.cfg, self.mkt.spread), self.basket.sl_price(self.cfg))

    def _close(self, bid: float, reason: str):
        pnl = self.basket.pnl(bid, self.mkt)
        self.broker.close_all()
        log.info("CLOSE %s basket (%s) at %.2f, P/L %.2f USD", self._side(), reason, bid, pnl)
        self._journal(bid, reason, pnl)
        self.basket = None
        self.entry_context = {}

    def manage(self, bid: float):
        """Grid adds, stop loss and take profit against the live bid."""
        b, cfg, d = self.basket, self.cfg, self.basket.direction
        while (level := b.next_grid_price(cfg)) is not None and (bid - level) * d <= 0:
            lots = b.next_lot(cfg)
            b.positions.append(Position(self.broker.open_market(d, lots), lots))
            log.info("GRID level %d filled near %.2f", b.levels_filled, level)

        pnl = b.pnl(bid, self.mkt)
        self.mae, self.mfe = min(self.mae, pnl), max(self.mfe, pnl)
        if (bid - b.sl_price(cfg)) * d <= 0:
            self._close(bid, "stop_loss")
        elif (bid - b.tp_price(cfg, self.mkt.spread)) * d >= 0:
            self._close(bid, "take_profit")

    def on_new_bar(self, data):
        i = len(data) - 1
        when = str(data.index[i])
        if self.basket and self.cfg.close_on_reverse and cross(data, i) == -self.basket.direction:
            self._close(float(data["close"].iloc[i]), "reverse_cross")
        if self.basket is None:
            sig = entry_signal(data, i, self.cfg)
            if sig:
                self._open(sig, data.iloc[i], when)

    def step(self):
        bars = self.broker.get_closed_bars(self.cfg.warmup_bars + 300)
        data = add_indicators(bars, self.cfg)
        bar_time = str(data.index[-1])
        if self.basket:
            self.manage(self.broker.get_bid())
        if bar_time != self.last_bar_time:
            if self.last_bar_time is not None:  # don't act on a stale bar right after start
                self.on_new_bar(data)
            self.last_bar_time = bar_time
        self._save_state()

    def run(self):
        log.info("bot started: %s, poll every %ss", self.mkt.symbol, self.poll_seconds)
        try:
            while True:
                try:
                    self.step()
                except Exception:
                    log.exception("step failed; retrying next poll")
                time.sleep(self.poll_seconds)
        except KeyboardInterrupt:
            log.info("stopped by user (open positions are left as they are)")
        finally:
            self._save_state()
            self.broker.shutdown()
