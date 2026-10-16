import pytest

from bot.config import MarketConfig, StrategyConfig
from bot.strategy import LONG, SHORT, Basket, Position, fill_price

CFG = StrategyConfig(grid_step_atr=1.0, max_grid_levels=2, tp_atr=1.5, sl_atr=1.0,
                     base_lot=0.01, lot_multiplier=2.0)
MKT = MarketConfig(spread=0.3, contract_size=100)


def basket(direction):
    b = Basket(direction=direction, ref_price=2000.0, atr=10.0, opened_at="t0")
    b.positions.append(Position(fill_price(direction, 2000.0, MKT), b.next_lot(CFG)))
    return b


def test_long_grid_levels_and_exits():
    b = basket(LONG)
    assert b.next_grid_price(CFG) == 1990.0
    b.positions.append(Position(fill_price(LONG, 1990.0, MKT), b.next_lot(CFG)))
    assert b.positions[-1].lots == 0.02          # martingale x2
    assert b.next_grid_price(CFG) == 1980.0
    b.positions.append(Position(fill_price(LONG, 1980.0, MKT), b.next_lot(CFG)))
    assert b.next_grid_price(CFG) is None        # max levels reached
    assert b.sl_price(CFG) == 1970.0             # last level 1980 - 1 ATR
    avg = (2000 * 0.01 + 1990 * 0.02 + 1980 * 0.04) / 0.07
    assert b.tp_price(CFG, MKT.spread) == pytest.approx(avg + 15)


def test_short_mirrors_long():
    b = basket(SHORT)
    assert b.next_grid_price(CFG) == 2010.0
    assert b.sl_price(CFG) == 2030.0
    assert b.tp_price(CFG, MKT.spread) == pytest.approx(1985.0)


def test_pnl_includes_spread():
    long_b, short_b = basket(LONG), basket(SHORT)
    # closing immediately at the same bid loses exactly the spread
    assert long_b.pnl(2000.0, MKT) == pytest.approx(-0.3 * 0.01 * 100)
    assert short_b.pnl(2000.0, MKT) == pytest.approx(-0.3 * 0.01 * 100)
    assert long_b.pnl(2010.0, MKT) == pytest.approx(9.7)


def test_basket_roundtrip_dict():
    b = basket(LONG)
    assert Basket.from_dict(b.to_dict()) == b


def test_bad_config_rejected():
    with pytest.raises(ValueError):
        StrategyConfig(ema_fast=50, ema_slow=20)


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("EMA_FAST", "9")
    monkeypatch.setenv("CLOSE_ON_REVERSE", "no")
    monkeypatch.setenv("TP_ATR", "2.5")
    c = StrategyConfig.from_env()
    assert (c.ema_fast, c.close_on_reverse, c.tp_atr) == (9, False, 2.5)
