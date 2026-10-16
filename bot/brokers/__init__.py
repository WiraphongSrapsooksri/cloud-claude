from .base import Broker


def make_broker(name: str, symbol: str, timeframe: str, **kwargs) -> Broker:
    name = name.lower()
    if name == "paper":
        from .paper import PaperBroker

        return PaperBroker(symbol, timeframe, **kwargs)
    if name == "mt5":
        from .mt5 import MT5Broker

        return MT5Broker(symbol, timeframe, **kwargs)
    raise ValueError(f"unknown broker: {name} (use paper or mt5)")
