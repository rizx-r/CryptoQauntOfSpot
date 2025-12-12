import time
from typing import Any, Dict, List, Optional
import numpy as np
from core.exchange_base import IExchange

class SimulatedClient(IExchange):
    def __init__(self):
        self._price = 100.0

    def load_markets(self) -> Dict[str, Any]:
        return {}

    def fetch_ohlcv(self, symbol: str, timeframe: str, since: Optional[int] = None, limit: Optional[int] = None) -> List[List[float]]:
        now = int(time.time() * 1000)
        if timeframe == "1h":
            closes = np.linspace(100.0, 101.0, 24)
        else:
            closes = np.concatenate([np.linspace(100.0, 99.0, 50), np.linspace(99.0, 101.0, 150)])
        return [[now, 0.0, 0.0, 0.0, float(c)] for c in closes[:limit] if closes.size > 0]

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        return {"last": self._price}

    def create_market_buy(self, symbol: str, quote_cost: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        amount = quote_cost / max(self._price, 1e-9)
        return {"id": "sim_buy", "amount": amount}

    def create_market_sell(self, symbol: str, base_amount: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"id": "sim_sell", "amount": base_amount}

    def create_limit_buy(self, symbol: str, base_amount: float, price: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"id": "sim_limit_buy", "amount": base_amount, "price": price}

    def create_limit_sell(self, symbol: str, base_amount: float, price: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"id": "sim_limit_sell", "amount": base_amount, "price": price}

    def fetch_balance(self) -> Dict[str, Any]:
        return {"free": {}}

    def fetch_my_trades(self, symbol: str, since: Optional[int] = None) -> List[Dict[str, Any]]:
        return []
