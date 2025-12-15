# CQ Beta – Sigma ETH Spot Quant Strategy

## Overview
- Runs a quantitative strategy on OKX spot (or a simulated environment). Adds the “Sigma” strategy to systematically DCA and take profit on ETH/USDT.
- Strategy is implemented with inheritance: shared trading/account/market logic lives in a base class `BaseStrategy`, while individual strategies implement only their trading rules and loop.

## Directory Structure
- `app/sigma.py`: Strategy entrypoint. Initializes config, exchange and logging, then starts Sigma
- `strategies/BaseStratege.py`: Base class `BaseStrategy` (account state bootstrap, trade-based average-cost rebuild, order placement, OHLCV caching)
- `strategies/sigma_spot.py`: Sigma strategy subclass, extends `BaseStrategy` and implements the trading loop
- `config/settings.py`: Loads environment variables
- `utils/indicators.py`: Technical indicators (MACD golden cross)
- `utils/state.py`: Position state and trade ledger persistence
- `core/*`: Exchange clients (OKX, simulated)
- `data/state.json`, `data/trades.csv`: Runtime state and trade records
- `logs/trade.log`: Runtime logs

## Install & Run
- Python 3.10+ (Python 3.13 recommended)
- Install dependencies: `pip install -r requirements.txt`
  - Main deps: `ccxt`, `talib`
- Configure `.env` (see `.env.example`)
  - Make a copy: `.env.example` → `.env`
- Run:
  - Simulated: `SIMULATED_ENV=true python app/sigma.py`
  - Testnet or live: set `OKX_API_KEY/OKX_SECRET/OKX_PASSWORD`. For testnet set `OKX_TESTNET=true`. Run `python app/main.py` or `python app/sigma.py`. Entrypoints reside under `app/`, strategy code under `strategies/`.

## Configuration (.env)
- Basics:
  - `SYMBOL=ETH/USDT`
  - `ORDER_TYPE=market|limit`
  - `LIMIT_SLIPPAGE_PCT=0.0005`
  - `POLL_SEC=30`
  - `DRY_RUN=true|false` (set `false` for live trading)
  - `SIMULATED_ENV=true|false` (forces `DRY_RUN=true` and testnet-like behavior in simulation)
- Sigma:
  - `SIGMA_BUY_BASE_ETH=0.000003` ETH amount per buy
  - `SIGMA_MAX_ADDS=100` max number of buys
  - `SIGMA_BUY_COOLDOWN_SEC=180` minimum seconds between buys
  - `SIGMA_BUY_PRICE_DROP_PCT=0.0025` price drop threshold vs average cost (0.25%)
  - `SIGMA_SELL_PROFIT_PCT=0.01` take profit threshold (1%)
  - `SIGMA_SELL_LEAVE_BASE_ETH=0.000003` leave this ETH amount after selling
  - `SIGMA_MACD_TIMEFRAME=1m` timeframe used for MACD golden cross

## Strategy Rules (Sigma)
- Buy when:
  - No position, or last price ≤ average cost × (1 − 0.25%)
  - Last buy ≥ 3 minutes ago
  - MACD golden cross
  - Buy count < max
- Buy amount:
  - Fixed `0.000003 ETH` each time
- Sell when:
  - Position ≥ `0.000003 ETH`
  - Last price ≥ average cost × (1 + 1%)
  - Previous 1-minute candle closed bearish
- Sell execution:
  - Sell all but keep `0.000003 ETH`

## Key Implementation & Code References
- Base & inheritance:
  - Define base class: `strategies/BaseStratege.py:10`
  - Sigma subclass: `strategies/sigma_spot.py:11`
- Average cost:
  - Rebuild from exchange trades: `strategies/BaseStratege.py:100`
  - Get current average cost: `strategies/BaseStratege.py:129`
  - Refresh balance and sync avg cost: `strategies/BaseStratege.py:155`
- Buy & sell:
  - Fixed ETH buy: `strategies/BaseStratege.py:188`
  - Sell but keep fixed ETH: `strategies/BaseStratege.py:228`
- Market & indicators:
  - Latest price: `strategies/BaseStratege.py:24`
  - Limit slippage: `strategies/BaseStratege.py:28`
  - OHLCV cache: `strategies/BaseStratege.py:170`
  - MACD golden cross: `utils/indicators.py:9`
- Exchange clients:
  - OKX client: `core/okx_client.py:6`
  - Factory: `core/exchange_factory.py:6`

## Logs & Data
- Runtime logs: `logs/trade.log`
- Position state: `data/state.json`
- Trade ledger: `data/trades.csv`

## FAQ
- Inheritance import error (module vs class): ensure `from strategies.BaseStratege import BaseStrategy` and subclass as `class SigmaSpotStrategy(BaseStrategy)`.
- Inaccurate average cost: rebuild from exchange trades after live buys (avoid local weighted calc). See `strategies/BaseStratege.py:100`.
- TA-Lib unavailable: `utils/indicators.py:9` falls back to EMA-based MACD.

## Safety Notes
- Never commit your API keys
- Always validate in simulation or testnet with small amounts before going live
- Crypto markets are risky; trade responsibly
