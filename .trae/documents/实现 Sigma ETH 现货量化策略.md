## 目标
实现新的 ETH 现货量化策略（Sigma），按给定买卖规则运行，参数通过 `.env` 管理，入口为 `app/sigma.py`。

## 代码结构与复用
- 复用现有基础设施：`Settings` 配置加载（config/settings.py:7）、日志（utils/logging.py:6）、交易所封装（core/exchange_factory.py:6，core/okx_client.py:6）、指标（utils/indicators.py:9）、状态与流水（utils/state.py:8）。
- 参考现有策略结构：`MartingaleMACDSpotStrategy`（strategies/martingale_macd_spot.py:11）作为模板，保持 run 循环、OHLC 缓存与指标计算的模式。

## 新增/修改文件
- 新增 `strategies/sigma_spot.py`：实现 `SigmaSpotStrategy`，封装买卖条件与执行。
- 新增 `app/sigma.py`：作为启动入口，初始化 `Settings`、`Exchange`、`Logger`，运行 `SigmaSpotStrategy`。
- 修改 `config/settings.py`：添加 Sigma 参数读取（`os.getenv`）。
- 修改 `utils/state.py`：在 `PositionState` 增加 `last_buy_ms`、`buy_count` 字段并在 `StateStore.load()` 读取，确保买入冷却与加仓次数可持久化。
- 修改 `.env.example`：在 `# sigma` 后添加配置项。

## 配置项（追加到 .env.example 中 `# sigma` 后）
- `SIGMA_BUY_BASE_ETH=0.000003`：每次买入的 ETH 数量
- `SIGMA_MAX_ADDS=100`：最大买入次数（包含初次与加仓，若需仅统计加仓可调整实现）
- `SIGMA_BUY_COOLDOWN_SEC=180`：两次买入间最小间隔（秒）
- `SIGMA_BUY_PRICE_DROP_PCT=0.0025`：加仓触发价差，现价 ≤ 开仓均价 * (1 - 0.0025)
- `SIGMA_SELL_PROFIT_PCT=0.01`：止盈阈值，现价 ≥ 开仓均价 * (1 + 0.01)
- `SIGMA_SELL_LEAVE_BASE_ETH=0.000003`：卖出后保留的 ETH 数量
- `SIGMA_MACD_TIMEFRAME=1m`：MACD 金叉计算的周期（与 1 分 K 统一）

## 策略逻辑
- 时间周期与数据:
  - 使用 `settings.sigma_macd_timeframe`（默认 `1m`）维护 OHLCV 缓存，最多 200 根。
  - 金叉判定：复用 `macd_cross_golden(closes)`（utils/indicators.py:9），以 EMA 回退保证无 TA-Lib 时也可运行。
  - 前一根 1 分 K 收阴：`prev.open > prev.close`。
- 买入条件：
  - `(无持仓)` 或 `(现价 ≤ 开仓均价 * (1 - 0.0025))`；
  - 与上次买入间隔 ≥ 3 分钟（`settings.sigma_buy_cooldown_sec`）；
  - 且 MACD 金叉；
  - 且加仓次数未达上限 `settings.sigma_max_adds`。
- 买入执行：
  - 以固定基币数量 `settings.sigma_buy_base_eth` 买入；
  - `order_type=market/limit` 两种路径均支持；
  - 更新 `state.avg_cost` 与 `state.base_amount`，记录 `state.last_buy_ms` 与累计 `state.buy_count`，记账到 `TradeLedger.record()`（utils/state.py:47）。
- 卖出条件：
  - `state.base_amount ≥ settings.sigma_sell_leave_base_eth`；
  - 且 `现价 ≥ 开仓均价 * (1 + settings.sigma_sell_profit_pct)`；
  - 且上一根 1 分 K 收阴；
- 卖出执行：
  - 卖出全部持仓但保留 `settings.sigma_sell_leave_base_eth`；
  - 复用交易接口（market/limit），更新 `state.base_amount`，`avg_cost` 维持不变或按剩余仓位重估为现价（默认维持不变，简单直观）。

## 关键实现点
- OHLCV 更新：参考 `strategies/martingale_macd_spot.py:262-279` 的增量更新模式，改用 `1m` 周期，确保上一根 K 的判定准确。
- 价格获取：参考 `_get_latest_price()`（strategies/martingale_macd_spot.py:27）。
- 限价滑点：复用 `_compute_limit_prices()`（strategies/martingale_macd_spot.py:112）并以 `order_type` 分支处理。
- 记账与持久化：
  - 状态：`StateStore.save()`（utils/state.py:34）存储 `base_amount`、`avg_cost` 与新增字段。
  - 流水：`TradeLedger.record()`（utils/state.py:47）。

## 验证方案
- 干跑（`SIMULATED_ENV=true`）：
  - `.env` 设置 `SIMULATED_ENV=true`，运行 `python app/sigma.py`，观察 `logs/trade.log` 输出与 `data/trades.csv` 记录。
- 实盘/测试网：
  - 设置 OKX API、`OKX_TESTNET=true`，`DRY_RUN=false`，小额测试观察下单与状态更新。

## 兼容性与假设
- MACD 与 1 分 K 同周期（未另行指定），如需改为 `5m` 可通过 `SIGMA_MACD_TIMEFRAME` 调整。
- “最大加仓次数”当前实现为总买入次数上限；如需仅统计加仓次数，改为在首次建仓后开始计数。
- 保留仓位以固定 ETH 数量实现，区别于现有策略保留 USDT 的方法（strategies/martingale_macd_spot.py:186）。

## 交付内容
- 新策略类 `SigmaSpotStrategy`、入口 `app/sigma.py`。
- `.env.example` 追加 Sigma 参数。
- `Settings` 与 `State` 扩展以支持冷却与加仓计数。

确认后我将按此计划实现、运行干跑验证，并给出关键日志与数据产物。