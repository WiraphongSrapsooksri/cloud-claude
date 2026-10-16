"""Bar-by-bar backtester for the EMA/RSI/grid strategy.

Inside a bar the order of high/low is unknown, so the backtest assumes the
worst case: grid orders fill and the stop is checked before take profit.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import MarketConfig, StrategyConfig
from .indicators import add_indicators
from .strategy import LONG, Basket, Position, cross, entry_signal, fill_price


@dataclass
class Trade:
    direction: str
    opened_at: str
    closed_at: str
    orders: int
    lots: float
    avg_entry: float
    exit_bid: float
    reason: str
    pnl: float


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series
    stats: dict


def _adverse_hit(direction: int, bar, level: float) -> bool:
    return bar["low"] <= level if direction == LONG else bar["high"] >= level


def _favourable_hit(direction: int, bar, level: float) -> bool:
    return bar["high"] >= level if direction == LONG else bar["low"] <= level


def _gap_fill(direction: int, bar, level: float) -> float:
    """If the bar opened beyond an adverse level, fill at the open instead."""
    if direction == LONG:
        return min(level, bar["open"])
    return max(level, bar["open"])


def run_backtest(
    df: pd.DataFrame,
    cfg: StrategyConfig | None = None,
    mkt: MarketConfig | None = None,
    initial_balance: float = 10_000.0,
) -> BacktestResult:
    cfg = cfg or StrategyConfig()
    mkt = mkt or MarketConfig()
    data = add_indicators(df, cfg)

    balance = initial_balance
    basket: Basket | None = None
    trades: list[Trade] = []
    equity: list[tuple] = []

    def close_basket(bid: float, when, reason: str):
        nonlocal balance, basket
        pnl = basket.pnl(bid, mkt)
        balance += pnl
        trades.append(
            Trade(
                direction="LONG" if basket.direction == LONG else "SHORT",
                opened_at=basket.opened_at,
                closed_at=str(when),
                orders=len(basket.positions),
                lots=round(basket.total_lots, 2),
                avg_entry=round(basket.avg_bid_entry(mkt.spread), 2),
                exit_bid=round(bid, 2),
                reason=reason,
                pnl=round(pnl, 2),
            )
        )
        basket = None

    for i in range(cfg.warmup_bars, len(data)):
        bar = data.iloc[i]
        when = data.index[i]

        # 1) Manage an open basket using this bar's range.
        if basket is not None:
            d = basket.direction
            while True:
                level = basket.next_grid_price(cfg)
                if level is None or not _adverse_hit(d, bar, level):
                    break
                bid = _gap_fill(d, bar, level)
                basket.positions.append(Position(fill_price(d, bid, mkt), basket.next_lot(cfg)))

            sl = basket.sl_price(cfg)
            if _adverse_hit(d, bar, sl):
                close_basket(_gap_fill(d, bar, sl), when, "stop_loss")
            else:
                tp = basket.tp_price(cfg, mkt.spread)
                if _favourable_hit(d, bar, tp):
                    close_basket(tp, when, "take_profit")

        # 2) Decisions on the bar close.
        if basket is not None and cfg.close_on_reverse and cross(data, i) == -basket.direction:
            close_basket(bar["close"], when, "reverse_cross")

        if basket is None:
            sig = entry_signal(data, i, cfg)
            if sig:
                basket = Basket(
                    direction=sig,
                    ref_price=float(bar["close"]),
                    atr=float(bar["atr"]),
                    opened_at=str(when),
                )
                basket.positions.append(
                    Position(fill_price(sig, bar["close"], mkt), basket.next_lot(cfg))
                )

        open_pnl = basket.pnl(bar["close"], mkt) if basket else 0.0
        equity.append((when, balance + open_pnl))

    if basket is not None:
        close_basket(data["close"].iloc[-1], data.index[-1], "end_of_data")
        if equity:
            equity[-1] = (equity[-1][0], balance)

    trades_df = pd.DataFrame([t.__dict__ for t in trades])
    equity_s = pd.Series(
        [e for _, e in equity], index=[w for w, _ in equity], name="equity", dtype=float
    )
    return BacktestResult(trades_df, equity_s, _stats(trades_df, equity_s, initial_balance))


def _stats(trades: pd.DataFrame, equity: pd.Series, initial: float) -> dict:
    if trades.empty:
        return {"trades": 0, "net_profit": 0.0, "final_balance": initial}
    wins = trades[trades["pnl"] > 0]["pnl"]
    losses = trades[trades["pnl"] <= 0]["pnl"]
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return {
        "trades": int(len(trades)),
        "win_rate_pct": round(100 * len(wins) / len(trades), 1),
        "net_profit": round(float(trades["pnl"].sum()), 2),
        "final_balance": round(initial + float(trades["pnl"].sum()), 2),
        "return_pct": round(100 * float(trades["pnl"].sum()) / initial, 2),
        "profit_factor": round(float(wins.sum() / -losses.sum()), 2) if losses.sum() < 0 else None,
        "avg_win": round(float(wins.mean()), 2) if len(wins) else 0.0,
        "avg_loss": round(float(losses.mean()), 2) if len(losses) else 0.0,
        "max_drawdown_pct": round(float(-dd.min() * 100), 2),
        "max_orders_in_basket": int(trades["orders"].max()),
        "exit_reasons": trades["reason"].value_counts().to_dict(),
    }
