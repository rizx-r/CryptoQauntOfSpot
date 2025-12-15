# CQ Beta – Sigma ETH 现货量化策略  
**Languages:** [English](README.md) |
## 概览  
- 本项目在 OKX 现货（或模拟环境）上运行量化策略，新增 “Sigma” 策略，按固定规则进行 ETH/USDT 的定投与止盈。  
- 架构采用策略继承：通用交易/账户/行情逻辑在基类 `BaseStrategy` 中，具体策略仅负责交易条件与循环。  
  
## 目录结构  
- `app/sigma.py`：策略入口，初始化配置、交易所与日志，启动 Sigma  
- `strategies/BaseStratege.py`：通用基类 `BaseStrategy`（账户状态、成交重建、下单、行情缓存）  
- `strategies/sigma_spot.py`：Sigma 策略子类，继承 `BaseStrategy`，实现交易循环  
- `config/settings.py`：环境变量配置读取  
- `utils/indicators.py`：指标计算（MACD 金叉）  
- `utils/state.py`：持仓状态与交易流水持久化  
- `core/*`：交易所封装（OKX、模拟）  
- `data/state.json`、`data/trades.csv`：运行时状态与交易记录  
- `logs/trade.log`：运行日志  
  
## 安装与运行  
- Python 3.10+（建议 Python3.13）  
- 安装依赖：`pip install -r requirements.txt`
	- 主要依赖：`ccxt`, `talib`
- 配置 `.env`（参考 `.env.example`）  
	- 将`.env.example`复制一份为`.env`
- 运行策略：  
  - 模拟环境：`SIMULATED_ENV=true python app/sigma.py`  
  - 测试网或实盘：设置 `OKX_API_KEY/OKX_SECRET/OKX_PASSWORD`，测试环境需要配置 `OKX_TESTNET=true`，运行 `python app/main.py` or  `python app/sigma.py` 等， 入口程序都放在`app/`目录下，策略框架代码放在`startagy/`文件夹下
  
## 配置项（.env）  
- 基本：  
  - `SYMBOL=ETH/USDT`  
  - `ORDER_TYPE=market|limit`  
  - `LIMIT_SLIPPAGE_PCT=0.0005`  
  - `POLL_SEC=30`  
  - `DRY_RUN=true|false`（实盘建议 `false`）  
  - `SIMULATED_ENV=true|false`（模拟环境自动强制 `DRY_RUN=true` 与测试网）  
- Sigma：  
  - `SIGMA_BUY_BASE_ETH=0.000003` 每次买入 ETH 数量  
  - `SIGMA_MAX_ADDS=100` 最大买入次数  
  - `SIGMA_BUY_COOLDOWN_SEC=180` 买入冷却时间  
  - `SIGMA_BUY_PRICE_DROP_PCT=0.0025` 现价相对均价的下跌阈值（0.25%）  
  - `SIGMA_SELL_PROFIT_PCT=0.01` 止盈阈值（1%）  
  - `SIGMA_SELL_LEAVE_BASE_ETH=0.000003` 卖出后保留的 ETH 数量  
  - `SIGMA_MACD_TIMEFRAME=1m` 金叉判定周期  
  
## 策略规则（Sigma）  
核心：计算一条今日预测基线baseline，在baseline下方买入吸筹，上方卖出跑路，低吸高抛，预计每日1%收益，最求低sharpe比例。由于没有写割肉逻辑，可能有被套牢风险。
- 买入条件：  
  - 无持仓，或现价 ≤ 开仓均价×(1−0.25%)  
  - 与上一次买入间隔 ≥ 3 分钟  
  - MACD 金叉  
  - 买入次数未达上限  
- 买入数量：  
  - 每次固定买入 `0.000003 ETH`  
- 卖出条件：  
  - 持仓 ≥ `0.000003 ETH`  
  - 现价 ≥ 开仓均价×(1+1%)  
  - 上一根 1 分 K 收阴  
- 卖出执行：  
  - 卖出全部持仓但保留 `0.000003 ETH`  
  
## 关键实现与代码参考  
- 基类与继承：  
  - `strategies/BaseStratege.py:10` 定义 `BaseStrategy`  
  - `strategies/sigma_spot.py:11` 定义 `SigmaSpotStrategy(BaseStrategy)`  
- 开仓均价计算：  
  - 通过成交历史重建：`strategies/BaseStratege.py:100`  
  - 获取当前开仓均价：`strategies/BaseStratege.py:129`  
  - 刷新余额并同步均价：`strategies/BaseStratege.py:155`  
- 买入与卖出：  
  - 固定 ETH 数量买入：`strategies/BaseStratege.py:188`  
  - 卖出但保留固定 ETH：`strategies/BaseStratege.py:228`  
- 行情与指标：  
  - 最新价：`strategies/BaseStratege.py:24`  
  - 限价滑点：`strategies/BaseStratege.py:28`  
  - OHLCV 缓存：`strategies/BaseStratege.py:170`  
  - MACD 金叉：`utils/indicators.py:9`  
- 交易所封装：  
  - OKX 客户端：`core/okx_client.py:6`  
  - 工厂：`core/exchange_factory.py:6`  
  
## 日志与数据  
- 运行日志：`logs/trade.log`  
- 仓位状态：`data/state.json`  
- 成交流水：`data/trades.csv`  
  
## 常见问题  
- 继承错误（模块当类）：确保导入为 `from strategies.BaseStratege import BaseStrategy`，并在子类声明 `class SigmaSpotStrategy(BaseStrategy)`.  
- 均价不准确：实盘买入后通过成交历史重建均价（避免用本地加权），参考 `strategies/BaseStratege.py:100`.  
- TA-Lib 不可用：`utils/indicators.py:9` 自动使用 EMA 回退实现 MACD。  
  
## 安全提示  
- 切勿在仓库中提交 API 密钥  
- 实盘前先在模拟环境或测试网做小额验证
- 加密货币市场有风险，本人合约交易已爆仓1万usdt