import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    symbol: str = os.getenv("SYMBOL", "ETH/USDT")
    base_buy_usdt: float = float(os.getenv("BASE_BUY_USDT", "1"))
    tp_remain_usdt: float = float(os.getenv("TP_REMAIN_USDT", "0.5"))
    multiplicator: float = float(os.getenv("MULTIPLICATOR", "2"))
    take_profit_pct: float = float(os.getenv("TP_PCT", "0.01"))
    drawdown_pct: float = float(os.getenv("DD_PCT", "0.03"))
    poll_interval_sec: int = int(os.getenv("POLL_SEC", "30"))
    timezone: str = os.getenv("TIMEZONE", "UTC")
    api_key: str = os.getenv("OKX_API_KEY", "")
    api_secret: str = os.getenv("OKX_SECRET", "")
    api_password: str = os.getenv("OKX_PASSWORD", "")
    http_proxy: str = os.getenv("HTTP_PROXY", "")
    https_proxy: str = os.getenv("HTTPS_PROXY", "")
    testnet: bool = os.getenv("OKX_TESTNET", "false").lower() == "true"
    timeout_ms: int = int(os.getenv("TIMEOUT_MS", "10000"))
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() == "true"
    simulated_env: bool = os.getenv("SIMULATED_ENV", "false").lower() == "true"
    order_type: str = os.getenv("ORDER_TYPE", "market").lower()  # market or limit
    limit_slippage_pct: float = float(os.getenv("LIMIT_SLIPPAGE_PCT", "0.0005"))
    reset_state_on_start: bool = os.getenv("RESET_STATE_ON_START", "false").lower() == "true"

    def __post_init__(self):
        print(self.testnet)
        print(self.dry_run)
        if self.simulated_env:
            print("!TEST")
            self.dry_run = True
            self.testnet = True
        else:
            self.dry_run = False
            self.testnet = False
