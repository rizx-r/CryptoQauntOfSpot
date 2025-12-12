import os
import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import Settings
from utils.logging import init_logger
from core.exchange_factory import ExchangeFactory
from strategies.martingale_macd_spot import MartingaleMACDSpotStrategy

def main():
    settings = Settings()
    logger = init_logger(settings)
    proxies = {}
    if settings.http_proxy:
        proxies["http"] = settings.http_proxy
    if settings.https_proxy:
        proxies["https"] = settings.https_proxy
    exchange = ExchangeFactory.create(
        "okx",
        api_key=settings.api_key,
        secret=settings.api_secret,
        password=settings.api_password,
        proxies=proxies,
        testnet=settings.testnet,
        enable_rate_limit=True,
        timeout_ms=settings.timeout_ms,
        simulated_env=settings.simulated_env,
    )
    strategy = MartingaleMACDSpotStrategy(
        exchange=exchange,
        settings=settings,
        logger=logger,
    )
    print(strategy.state.base_amount)
    strategy.run()

if __name__ == "__main__":
    main()
