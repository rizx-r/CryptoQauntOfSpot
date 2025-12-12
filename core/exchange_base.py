from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class IExchange(ABC):
    @abstractmethod
    def load_markets(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, since: Optional[int] = None, limit: Optional[int] = None) -> List[List[float]]:
        pass

    @abstractmethod
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def create_market_buy(self, symbol: str, quote_cost: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def create_market_sell(self, symbol: str, base_amount: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def create_limit_buy(self, symbol: str, base_amount: float, price: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def create_limit_sell(self, symbol: str, base_amount: float, price: float, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def fetch_balance(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def fetch_my_trades(self, symbol: str, since: Optional[int] = None) -> List[Dict[str, Any]]:
        pass
