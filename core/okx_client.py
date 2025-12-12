import time
from typing import Any, Dict, List, Optional
import ccxt
from core.exchange_base import IExchange

class OkxClient(IExchange):
    def __init__(
        self,
        api_key: Optional[str],
        secret: Optional[str],
        password: Optional[str],
        proxies: Dict[str, str],
        testnet: bool,
        enable_rate_limit: bool,
        timeout_ms: int,
    ):
        params = {
            "apiKey": api_key,
            "secret": secret,
            "password": password,
            "enableRateLimit": enable_rate_limit,
            "timeout": timeout_ms,
            "proxies": proxies,
            "options": {"defaultType": "spot"},
        }
        self.exchange = ccxt.okx(params)
        if testnet:
            self.exchange.setSandboxMode(True)
        try:
            self.exchange.load_markets()
        except Exception:
            pass

    def load_markets(self) -> Dict[str, Any]:
        return self.exchange.markets

    def fetch_ohlcv(self, symbol: str, timeframe: str, since: Optional[int] = None, limit: Optional[int] = None) -> List[List[float]]:
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        return self.exchange.fetch_ticker(symbol)

    def _amount_to_precision(self, symbol: str, amount: float) -> float:
        s = self.exchange.amount_to_precision(symbol, amount)
        return float(s)

    def _price_to_precision(self, symbol: str, price: float) -> float:
        s = self.exchange.price_to_precision(symbol, price)
        return float(s)

    def _normalize_order_amount(self, symbol: str, base_amount: float, price: Optional[float] = None) -> float:
        m = self.exchange.markets.get(symbol)
        amt = float(base_amount)
        if m:
            limits = m.get("limits", {})
            min_amt = float(limits.get("amount", {}).get("min", 0.0) or 0.0)
            min_cost = float(limits.get("cost", {}).get("min", 0.0) or 0.0)
            if min_amt and amt < min_amt:
                amt = min_amt
            if price is not None and min_cost:
                if amt * float(price) < min_cost:
                    amt = min_cost / float(price)
        amt = self._amount_to_precision(symbol, amt)
        return amt

    def create_market_buy(self, symbol: str, quote_cost: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ticker = self.fetch_ticker(symbol)
        price = float(ticker["last"])
        base_amount = self._normalize_order_amount(symbol, quote_cost / price, price)
        p = {"tdMode": "cash"}
        if params:
            p.update(params)
        return self.exchange.create_order(symbol, "market", "buy", base_amount, None, p)

    def create_market_sell(self, symbol: str, base_amount: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ticker = self.fetch_ticker(symbol)
        price = float(ticker["last"])
        base_amount = self._normalize_order_amount(symbol, base_amount, price)
        p = {"tdMode": "cash"}
        if params:
            p.update(params)
        return self.exchange.create_order(symbol, "market", "sell", base_amount, None, p)

    def create_limit_buy(self, symbol: str, base_amount: float, price: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base_amount = self._normalize_order_amount(symbol, base_amount, price)
        price = self._price_to_precision(symbol, price)
        p = {"tdMode": "cash"}
        if params:
            p.update(params)
        return self.exchange.create_order(symbol, "limit", "buy", base_amount, price, p)

    def create_limit_sell(self, symbol: str, base_amount: float, price: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base_amount = self._normalize_order_amount(symbol, base_amount, price)
        price = self._price_to_precision(symbol, price)
        p = {"tdMode": "cash"}
        if params:
            p.update(params)
        return self.exchange.create_order(symbol, "limit", "sell", base_amount, price, p)

    def fetch_balance(self) -> Dict[str, Any]:
        return self.exchange.fetch_balance()

    def fetch_my_trades(self, symbol: str, since: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.exchange.fetch_my_trades(symbol, since=since)
