# 架构概览

* 技术栈：Python 3.10+、`ccxt`（交易所连接）、`TA‑Lib`（技术指标）、`pandas`/`numpy`（数据处理）、内置 `logging`（日志）、`python‑dotenv`（加载密钥和代理）。

* 交易对象：OKX 现货 `ETH/USDT`。

* 设计模式：工厂模式封装交易所客户端，统一接口，支持代理与后续新增币种/交易所扩展。

* 运行方式：轮询驱动（轻量定时任务），实时计算基准价、MACD 金叉和风控逻辑，自动下单与止盈。

* Python版本：Anaconda Python3.13

# 目录与文件

* `app/main.py`：程序入口，加载配置，创建交易所实例，启动策略循环。

* `core/exchange_factory.py`：交易所工厂（返回统一接口 `IExchange` 的实现）。

* `core/exchange_base.py`：`IExchange` 接口定义（行情、下单、账户、历史交易等方法）。

* `core/okx_client.py`：OKX 客户端实现（封装 `ccxt.okx`，支持代理、参数、重试）。

* `strategies/martingale_macd_spot.py`：策略实现（基准价、马丁加仓、MACD 金叉检测、止盈）。

* `utils/indicators.py`：TA‑Lib 指标封装（MACD、均值），时间框架转换工具。

* `utils/logging.py`：日志初始化（控制台 + 文件轮转）。

* `utils/state.py`：策略持仓状态与均价跟踪（本地持久化 `data/state.json` 与交易流水 `data/trades.csv`）。

* `config/settings.py`：配置模型（品种、资金、风控阈值、代理、密钥来源）。

* `requirements.txt` / `pyproject.toml`：依赖定义。

* `logs/trade.log`：交易日志文件。

# 依赖与安装

* 必需：`ccxt`、`pandas`、`numpy`、`python‑dotenv`、`TA‑Lib`。

* TA‑Lib 安装提示（Windows）：优先安装预编译 wheel；若失败可临时降级为 `pandas_ta` 以测试运行，正式版仍使用 TA‑Lib。

# 统一交易接口（IExchange）

* `load_markets()`：加载交易对信息。

* `fetch_ohlcv(symbol, timeframe, since, limit)`：拉取 K 线。

* `fetch_ticker(symbol)`：最新行情。

* `create_market_buy(symbol, quote_cost, params)`：按报价货币成本买入（内部换算为 base 数量）。

* `create_market_sell(symbol, base_amount, params)`：按 base 数量卖出。

* `fetch_balance()`：获取余额。

* `fetch_my_trades(symbol, since)`：交易历史（用于均价与盈亏核算）。

* 细节：OKX 下单附带 `{'tdMode': 'cash'}` 保证现货模式；考虑 `enableRateLimit` 与超时、重试与错误分类。

# 工厂模式与代理支持

* `ExchangeFactory.create(name, api_key, secret, password, proxies, testnet)`：返回具体客户端；`proxies` 接受 `{'http': 'http://...', 'https': 'http://...'}` 并透传给 ccxt。

* 为后续扩展（如 `binance`）保留入口，统一符号标准（`ETH/USDT`）。

# 策略规则（现货马丁 + MACD）

* 基准价：取“前一自然日”的 1h 线收盘价均值（约 24 根），作为 `baseline`。

* 首次开仓：当前最新价 `< baseline` 时，市价买入价值 `1 USDT` 的 `ETH`（换算为 base 数量）。

* 马丁加仓：当 `价格 ≤ 持仓均价 × (1 - 0.03)` 且 5m MACD 出现金叉（`MACD` 由负转正并上穿 `signal`），以市价买入“当前持仓 base 数量的 2 倍”（将仓位总量翻倍）。

* 止盈：当总持仓的浮动盈亏比 `PnL >= 1%`，市价一键清仓（卖出全部 `ETH`）。

* 均价维护：根据本策略的成交记录（从 `data/trades.csv` 与/或 `fetch_my_trades`）动态计算加权平均持仓成本；兼容外部手动仓位的识别与忽略策略标记。

# 指标与数据

* 5m MACD：`TA‑Lib.MACD(close, fast=12, slow=26, signal=9)`；判定金叉：`macd[-2] <= signal[-2]` 且 `macd[-1] > signal[-1]`。

* 1h 基准：上一自然日（本地时区或 UTC 统一）取 `close` 均值。

* K 线拉取：轮询拉取 5m 与 1h 数据，防止缺口；使用 `limit` 合理控制体量。

# 执行循环与风控

* 轮询周期：30s（可配置）。

* 步骤：

  1. 刷新余额与最新价；
  2. 取 1h 历史并计算 `baseline`；
  3. 取 5m 历史并计算 `MACD` 与金叉；
  4. 维护本地持仓状态（数量、均价、累计买入/卖出）；
  5. 评估入场/加仓/止盈条件并下单；
  6. 记录日志与持久化状态；
  7. 捕获错误并退避重试（网络、限频、交易参数）。

* 下单参数与约束：

  * 按交易所最小下单量与精度进行数量与价格的舍入；

  * 检查可用 `USDT` 余额；当不足时跳过并告警；

  * 重复信号保护（同一根 K 内只响应一次）；

  * 加仓深度上限（可选，避免无限加倍）。

# 盈亏与日志

* 浮动盈亏：`(last_price - avg_cost) / avg_cost`。

* 实现收益：清仓后汇总卖出与买入差额（以 USDT 计）。

* 日志：写入 `logs/trade.log`（文件轮转），包含：

  * 开仓：时间、价格、买入 base 数量、累计持仓与浮动盈亏；

  * 加仓：时间、价格、买入数量、最新均价与浮动盈亏；

  * 平仓：时间、价格、卖出数量、实现收益（USDT），本轮总收益；

  * 系统：启动、异常、重试、余额不足、精度调整等信息。

* 交易流水：`data/trades.csv`（时间、方向、价格、数量、费用、订单ID）。

# 配置与密钥

* `.env`：`OKX_API_KEY`、`OKX_SECRET`、`OKX_PASSWORD`、`HTTP_PROXY`、`HTTPS_PROXY`、`SYMBOL=ETH/USDT`、`TP_PCT=0.01`、`DD_PCT=0.03`、`BASE_BUY_USDT=1`、`POLL_SEC=30` 等。

* `config/settings.py`：从环境读取并校验类型；`testnet` 切换与时区统一设置。

# 错误处理与重试

* 分类处理：网络异常、限频（429）、余额不足、最小下单量错误、交易所维护。

* 重试策略：指数退避，幂等保证（基于客户端订单 idempotency key）。

* 失败保护：连续失败上限触发暂停，并记录报警日志。

# 测试与验证

* 单元测试：

  * MACD 金叉检测函数；

  * 均价与盈亏计算；

  * 数量舍入与最小下单量校验。

* 干跑模式（`dry_run`）：只记录信号与拟下单，不实际发送交易，验证逻辑与日志。

# 交付与后续

* 首次交付：完整代码与运行说明（安装、配置、干跑、实盘）。

* 可选增强：

  * 交易所/币种扩展（Binance、BTC/USDT 等）；

  * 风控参数动态化（追踪止盈、最大加仓次数）；

  * 指标缓存与多时区对齐；

  * Telegram/钉钉告警；

  * 回测模块与报告输出。

请确认该方案；确认后我将开始在仓库中按以上结构落地实现、编写代码与日志，并提供干跑与实盘两种运行模式。
