from typing import Any, Dict, Optional
from core.exchange_base import IExchange
from core.okx_client import OkxClient
from core.simulated_client import SimulatedClient

class ExchangeFactory:
    @staticmethod
    def create(
        name: str,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        password: Optional[str] = None,
        proxies: Optional[Dict[str, str]] = None,
        testnet: bool = False,
        enable_rate_limit: bool = True,
        timeout_ms: int = 10000,
        simulated_env: bool = False,
    ) -> IExchange:
        if simulated_env:
            return SimulatedClient()
        if name.lower() == "okx":
            return OkxClient(
                api_key=api_key,
                secret=secret,
                password=password,
                proxies=proxies or {},
                testnet=testnet,
                enable_rate_limit=enable_rate_limit,
                timeout_ms=timeout_ms,
            )
        raise ValueError("unsupported exchange")
