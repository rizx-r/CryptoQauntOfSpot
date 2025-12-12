import logging
import time
import math
from typing import Dict, Any, List
import numpy as np
from core.exchange_base import IExchange
from config.settings import Settings
from utils.indicators import macd_cross_golden, compute_prev_day_1h_baseline
from utils.state import PositionState, StateStore, TradeLedger

class MartingaleMACDSpotStrategy:
    def __init__(self, exchange: IExchange, settings: Settings, logger):
        self.exchange = exchange
        self.settings = settings
        self.logger = logger
        self.symbol = settings.symbol
        self.store = StateStore(settings)
        self.ledger = TradeLedger(settings)
        self.state = self.store.load()
        print("b11", self.state.base_amount)
        self._ohlcv_cache: List[List[float]] = []
        self._ohlcv_limit = 200
        self._timeframe = "5m"
        self._baseline_cache: float = 0.0
        self._baseline_last_ts: float = 0.0
        self._bootstrap_state()
        print("b1", self.state.base_amount)

    def _get_latest_price(self) -> float:
        t = self.exchange.fetch_ticker(self.symbol)
        return float(t["last"])

    def _refresh_state_from_balance(self):
        if self.settings.dry_run:
            return
        b = self.exchange.fetch_balance()
        base = self.symbol.split("/")[0]
        bal = round(b.get("free", {}).get(base), 3)
        if bal is None:
            bal = 0.0
        self.state.base_amount = float(bal)
        if self.state.base_amount <= 0 and self.state.avg_cost > 0:
            self.state.avg_cost = 0.0
            self.store.save(self.state)

    def _bootstrap_state(self):
        try:
            if self.settings.reset_state_on_start:
                self.state.base_amount = 0.0
                self.state.avg_cost = 0.0
                self.store.save(self.state)
                return
            if self.settings.dry_run:
                if self.state.base_amount <= 0:
                    if self.state.avg_cost != 0.0:
                        avg, amt = self.ledger.rebuild_position(self.symbol)
                        if amt <= 0:
                            self.state.avg_cost = 0.0
                            self.store.save(self.state)
                        else:
                            self.state.avg_cost = avg
                            self.state.base_amount = amt
                            self.store.save(self.state)
                return
            b = self.exchange.fetch_balance()
            print("fetch_balance:", b)
            base = self.symbol.split("/")[0]
            amt = round(float(b.get("free", {}).get(base, 0.0)), 3)
            self.state.base_amount = amt
            if amt <= 0:
                if self.state.avg_cost != 0.0:
                    avg, ledger_amt = self.ledger.rebuild_position(self.symbol)
                    if ledger_amt <= 0:
                        self.state.avg_cost = 0.0
                        self.store.save(self.state)
                    else:
                        self.state.avg_cost = avg
                        self.state.base_amount = ledger_amt
                        self.store.save(self.state)
                return
            if self.state.avg_cost <= 0.0:
                trades = self.exchange.fetch_my_trades(self.symbol, None)
                buy_amt = 0.0
                sell_amt = 0.0
                buy_cost = 0.0
                for t in trades:
                    side = t.get("side", "")
                    amount = float(t.get("amount", 0.0))
                    price = float(t.get("price", 0.0))
                    if side == "buy":
                        buy_amt += amount
                        buy_cost += amount * price
                    elif side == "sell":
                        sell_amt += amount
                net_amt = buy_amt - sell_amt
                if net_amt > 0:
                    self.state.avg_cost = buy_cost / net_amt
                    self.state.base_amount = net_amt
                    self.store.save(self.state)
                else:
                    avg, ledger_amt = self.ledger.rebuild_position(self.symbol)
                    if ledger_amt > 0:
                        self.state.avg_cost = avg
                        self.state.base_amount = ledger_amt
                        self.store.save(self.state)
        except Exception:
            pass

    def _pnl_ratio(self, last_price: float) -> float:
        if self.state.base_amount <= 0 or self.state.avg_cost <= 0:
            return 0.0
        return (last_price - self.state.avg_cost) / self.state.avg_cost

    def _compute_limit_prices(self):
        t = self.exchange.fetch_ticker(self.symbol)
        bid = float(t.get("bid", t.get("last", 0.0)))
        ask = float(t.get("ask", t.get("last", 0.0)))
        bp = bid * (1.0 - self.settings.limit_slippage_pct)
        sp = ask * (1.0 + self.settings.limit_slippage_pct)
        return bp, sp

    def _buy_quote_cost_usdt(self, usdt_cost: float):
        if self.settings.order_type == "limit":
            bp, _ = self._compute_limit_prices()
            if self.settings.dry_run:
                price = bp
                base_amount = usdt_cost / price
                self.state.avg_cost = (self.state.avg_cost * self.state.base_amount + price * base_amount) / (self.state.base_amount + base_amount)
                self.state.base_amount += base_amount
                self.store.save(self.state)
                self.ledger.record("buy", self.symbol, price, base_amount, 0.0, "")
                self.logger.info(f"BUY-LIMIT {self.symbol} price={price:.6f} amount={base_amount:.8f} pos={self.state.base_amount:.8f} pnl={self._pnl_ratio(price):.5f}")
                return
            price = bp
            base_amount = usdt_cost / price
            o = self.exchange.create_limit_buy(self.symbol, base_amount, price, {})
            self.logger.info(f"PLACE BUY-LIMIT {self.symbol} price={price:.6f} amount={base_amount:.8f} order_id={o.get('id','')}")
            return
        else:
            if self.settings.dry_run:
                last_price = self._get_latest_price()
                base_amount = usdt_cost / last_price
                self.state.avg_cost = (self.state.avg_cost * self.state.base_amount + last_price * base_amount) / (self.state.base_amount + base_amount)
                self.state.base_amount += base_amount
                self.store.save(self.state)
                self.ledger.record("buy", self.symbol, last_price, base_amount, 0.0, "")
                self.logger.info(f"BUY {self.symbol} price={last_price:.6f} amount={base_amount:.8f} pos={self.state.base_amount:.8f} pnl={self._pnl_ratio(last_price):.5f}")
                return
            o = self.exchange.create_market_buy(self.symbol, usdt_cost, {})
            last_price = float(self._get_latest_price())
            base_amount = float(o.get("amount", 0.0)) if o else 0.0
            if base_amount > 0:
                self.state.avg_cost = (self.state.avg_cost * self.state.base_amount + last_price * base_amount) / (self.state.base_amount + base_amount)
                self.state.base_amount += base_amount
                self.store.save(self.state)
                self.ledger.record("buy", self.symbol, last_price, base_amount, 0.0, o.get("id", ""))
            self.logger.info(f"BUY {self.symbol} price={last_price:.6f} amount={base_amount:.8f} pos={self.state.base_amount:.8f} pnl={self._pnl_ratio(last_price):.5f}")

    def _sell_all(self):
        last_price = self._get_latest_price()
        base_amount = self.state.base_amount
        if base_amount <= 0:
            return
        if self.settings.order_type == "limit":
            _, sp = self._compute_limit_prices()
            if self.settings.dry_run:
                price = sp
                realized = base_amount * (price - self.state.avg_cost)
                self.ledger.record("sell", self.symbol, price, base_amount, 0.0, "")
                self.logger.info(f"SELL-LIMIT {self.symbol} price={price:.6f} amount={base_amount:.8f} realized={realized:.6f}")
            else:
                o = self.exchange.create_limit_sell(self.symbol, base_amount, sp, {})
                self.logger.info(f"PLACE SELL-LIMIT {self.symbol} price={sp:.6f} amount={base_amount:.8f} order_id={o.get('id','')}")
        else:
            if self.settings.dry_run:
                realized = base_amount * (last_price - self.state.avg_cost)
                self.ledger.record("sell", self.symbol, last_price, base_amount, 0.0, "")
                self.logger.info(f"SELL {self.symbol} price={last_price:.6f} amount={base_amount:.8f} realized={realized:.6f}")
            else:
                o = self.exchange.create_market_sell(self.symbol, base_amount, {})
                realized = base_amount * (last_price - self.state.avg_cost)
                self.ledger.record("sell", self.symbol, last_price, base_amount, 0.0, o.get("id", ""))
                self.logger.info(f"SELL {self.symbol} price={last_price:.6f} amount={base_amount:.8f} realized={realized:.6f}")
        self.state.base_amount = 0.0
        self.state.avg_cost = 0.0
        self.store.save(self.state)

    def _sell_all_but_remain_some_usdt(self):
        """
        逻辑和 _sell_all() 一样， 不同的是是这个函数是卖出所有 但保留0.5usdt的仓位
        :return:
        """
        last_price = self._get_latest_price()
        base_amount = self.state.base_amount
        if base_amount <= 0:
            return
        if self.settings.order_type == "limit":
            _, sp = self._compute_limit_prices()
            price = sp
            base_keep = self.settings.tp_remain_usdt / price
            if base_amount <= base_keep:
                return
            sell_amount = base_amount - base_keep
            if self.settings.dry_run:
                realized = sell_amount * (price - self.state.avg_cost)
                self.ledger.record("sell", self.symbol, price, sell_amount, 0.0, "")
                self.logger.info(f"SELL-LIMIT {self.symbol} price={price:.6f} amount={sell_amount:.8f} realized={realized:.6f}")
            else:
                o = self.exchange.create_limit_sell(self.symbol, sell_amount, price, {})
                self.logger.info(f"PLACE SELL-LIMIT {self.symbol} price={price:.6f} amount={sell_amount:.8f} order_id={o.get('id','')}")
            self.state.base_amount = base_keep
            self.store.save(self.state)
        else:
            price = last_price
            base_keep = 0.5 / price
            if base_amount <= base_keep:
                return
            sell_amount = base_amount - base_keep
            if self.settings.dry_run:
                realized = sell_amount * (price - self.state.avg_cost)
                self.ledger.record("sell", self.symbol, price, sell_amount, 0.0, "")
                self.logger.info(f"SELL {self.symbol} price={price:.6f} amount={sell_amount:.8f} realized={realized:.6f}")
            else:
                o = self.exchange.create_market_sell(self.symbol, sell_amount, {})
                realized = sell_amount * (price - self.state.avg_cost)
                self.ledger.record("sell", self.symbol, price, sell_amount, 0.0, o.get("id", ""))
                self.logger.info(f"SELL {self.symbol} price={price:.6f} amount={sell_amount:.8f} realized={realized:.6f}")
            self.state.base_amount = base_keep
            self.store.save(self.state)

    def _martingale_buy_if_needed(self, last_price: float, golden_cross: bool):
        if self.state.base_amount <= 0:
            return
        trigger_price = self.state.avg_cost * (1.0 - self.settings.drawdown_pct)
        if last_price > trigger_price:
            return
        if not golden_cross:
            return
        add_amount = self.state.base_amount * self.settings.multiplicator
        if self.settings.dry_run:
            cost = add_amount * last_price
            self._buy_quote_cost_usdt(cost)
            return
        ticker = self.exchange.fetch_ticker(self.symbol)
        price = float(ticker["last"])
        cost = add_amount * price
        self._buy_quote_cost_usdt(cost)

    def _initial_buy_if_needed(self, last_price: float, baseline: float):
        if self.state.base_amount > 0:
            self.logger.info(f"dont initial_buy because base_amount={self.state.base_amount} > 0")
            return
        if last_price >= baseline:
            self.logger.info(f"dont initial_buy because last_price={last_price} > baseline={baseline}")
            return
        self._buy_quote_cost_usdt(self.settings.base_buy_usdt)

    def _take_profit_if_needed(self, last_price: float):
        pnl = self._pnl_ratio(last_price)
        if pnl < self.settings.take_profit_pct:
            return
        self._sell_all()

    def _update_ohlcv_cache(self):
        if not self._ohlcv_cache:
            data = self.exchange.fetch_ohlcv(self.symbol, self._timeframe, None, self._ohlcv_limit)
            if data:
                self._ohlcv_cache = data
            return
        latest = self.exchange.fetch_ohlcv(self.symbol, self._timeframe, None, 1)
        if not latest:
            return
        candle = latest[0]
        ts = candle[0]
        if self._ohlcv_cache and self._ohlcv_cache[-1][0] == ts:
            self._ohlcv_cache[-1] = candle
        else:
            self._ohlcv_cache.append(candle)
            if len(self._ohlcv_cache) > self._ohlcv_limit:
                self._ohlcv_cache.pop(0)

    def _get_cached_baseline(self) -> float:
        now = time.time()
        if self._baseline_last_ts <= 0 or (now - self._baseline_last_ts) >= 3600:
            self._baseline_cache = compute_prev_day_1h_baseline(self.exchange, self.symbol, self.settings.timezone)
            self._baseline_last_ts = now
        return self._baseline_cache

    def run(self):
        while True:
            try:
                print("a1",self.state.base_amount)
                self._refresh_state_from_balance()
                print("a2",self.state.base_amount)
                baseline = self._get_cached_baseline()
                print("a3",self.state.base_amount)
                self._update_ohlcv_cache()
                print("a4",self.state.base_amount)
                closes = np.array([c[4] for c in self._ohlcv_cache], dtype=float) if self._ohlcv_cache else np.array([], dtype=float)
                print("a5",self.state.base_amount)
                golden_cross = macd_cross_golden(closes) if closes.size > 0 else False
                print("a6",self.state.base_amount)
                last_price = self._get_latest_price()
                print(self.state.base_amount)
                self._initial_buy_if_needed(last_price, baseline)
                self._martingale_buy_if_needed(last_price, golden_cross)
                self._take_profit_if_needed(last_price)
                time.sleep(self.settings.poll_interval_sec)
            except Exception as e:
                self.logger.error(str(e))
                time.sleep(self.settings.poll_interval_sec)
