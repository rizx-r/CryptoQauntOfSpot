import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
import numpy as np
import time
from core.exchange_base import IExchange
from config.settings import Settings
from utils.logging import init_logger
from strategies.martingale_macd_spot import MartingaleMACDSpotStrategy

class DummyExchange(IExchange):
    def __init__(self):
        self.price = 100.0
    def load_markets(self):
        return {}
    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        if timeframe == "1h":
            closes = np.linspace(100, 101, 24)
        else:
            closes = np.concatenate([np.linspace(100, 99, 50), np.linspace(99, 101, 150)])
        now = int(time.time() * 1000)
        return [[now, 0, 0, 0, float(c)] for c in closes]
    def fetch_ticker(self, symbol):
        return {"last": self.price}
    def create_market_buy(self, symbol, quote_cost, params=None):
        amount = quote_cost / self.price
        return {"id": "demo_buy", "amount": amount}
    def create_market_sell(self, symbol, base_amount, params=None):
        return {"id": "demo_sell", "amount": base_amount}
    def fetch_balance(self):
        return {"free": {"ETH": 0}}
    def fetch_my_trades(self, symbol, since=None):
        return []

def run_demo():
    settings = Settings()
    settings.dry_run = True
    settings.poll_interval_sec = 1
    logger = init_logger(settings)
    ex = DummyExchange()
    strategy = MartingaleMACDSpotStrategy(ex, settings, logger)
    ex.price = 99.0
    strategy.run()

if __name__ == "__main__":
    run_demo()
