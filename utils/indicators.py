import datetime
import numpy as np
from typing import List, Any

try:
    import talib
except Exception:
    talib = None

def macd_cross_golden(closes: np.ndarray) -> bool:
    if talib is not None:
        macd, signal, hist = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
    else:
        ema_fast = _ema(closes, 12)
        ema_slow = _ema(closes, 26)
        macd = ema_fast - ema_slow
        signal = _ema(macd, 9)
    if len(macd) < 2 or len(signal) < 2:
        return False
    return bool(macd[-2] <= signal[-2] and macd[-1] > signal[-1])

def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1)
    res = np.zeros_like(arr)
    res[0] = arr[0]
    for i in range(1, len(arr)):
        res[i] = alpha * arr[i] + (1 - alpha) * res[i - 1]
    return res

def compute_prev_day_1h_baseline(exchange, symbol: str, timezone: str) -> float:
    try:
        now = datetime.datetime.utcnow()
        prev_day = now.date() - datetime.timedelta(days=1)
        ohlcv = exchange.fetch_ohlcv(symbol, "1h", None, 48)
        closes = []
        for c in ohlcv:
            ts = int(c[0])
            dt = datetime.datetime.utcfromtimestamp(ts / 1000.0)
            if dt.date() == prev_day:
                closes.append(float(c[4]))
        if len(closes) == 0:
            closes = [float(c[4]) for c in ohlcv[-24:]]
        return float(np.mean(np.array(closes)))
    except Exception:
        return 0.0
