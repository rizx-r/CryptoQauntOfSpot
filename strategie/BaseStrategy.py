import time
import numpy as np
from typing import List
from core.exchange_base import IExchange
from config.settings import Settings
from utils.indicators import macd_cross_golden
from utils.state import PositionState, StateStore, TradeLedger


class BaseStrategy:
    def __init__(self, exchange: IExchange, settings: Settings, logger):
        self.exchange = exchange
        self.settings = settings
        self.logger = logger
        self.symbol = settings.symbol
        self.store = StateStore(settings)
        self.ledger = TradeLedger(settings)
        self.state = self.store.load()
        self._ohlcv_cache: List[List[float]] = []
        self._ohlcv_limit = 200
        self._timeframe = settings.sigma_macd_timeframe
        self._bootstrap_state()

    def _get_latest_price(self) -> float:
        t = self.exchange.fetch_ticker(self.symbol)
        return float(t.get("last", 0.0))

    def _compute_limit_prices(self):
        t = self.exchange.fetch_ticker(self.symbol)
        bid = float(t.get("bid", t.get("last", 0.0)))
        ask = float(t.get("ask", t.get("last", 0.0)))
        bp = bid * (1.0 - self.settings.limit_slippage_pct)
        sp = ask * (1.0 + self.settings.limit_slippage_pct)
        return bp, sp
    
    def _bootstrap_state(self):
        try:
            if self.settings.reset_state_on_start:
                self.state.base_amount = 0.0
                self.state.avg_cost = 0.0
                self.state.last_buy_ms = 0
                self.state.buy_count = 0
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
            base = self.symbol.split("/")[0]
            amt = float(b.get("free", {}).get(base, 0.0) or 0.0)
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
                    amount = float(t.get("amount", 0.0) or 0.0)
                    price = float(t.get("price", 0.0) or 0.0)
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
    
    def _rebuild_avg_cost_from_exchange_trades(self):
        try:
            trades = self.exchange.fetch_my_trades(self.symbol, None)
            buy_amt = 0.0
            sell_amt = 0.0
            buy_cost = 0.0
            for t in trades:
                side = t.get("side", "")
                amount = float(t.get("amount", 0.0) or 0.0)
                price = float(t.get("price", 0.0) or 0.0)
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
    
    def get_open_avg_cost(self) -> float:
        try:
            if self.settings.dry_run:
                avg, amt = self.ledger.rebuild_position(self.symbol)
                return avg if amt > 0 else 0.0
            trades = self.exchange.fetch_my_trades(self.symbol, None)
            buy_amt = 0.0
            sell_amt = 0.0
            buy_cost = 0.0
            for t in trades:
                side = t.get("side", "")
                amount = float(t.get("amount", 0.0) or 0.0)
                price = float(t.get("price", 0.0) or 0.0)
                if side == "buy":
                    buy_amt += amount
                    buy_cost += amount * price
                elif side == "sell":
                    sell_amt += amount
            net_amt = buy_amt - sell_amt
            if net_amt > 0:
                return buy_cost / net_amt
            avg, amt = self.ledger.rebuild_position(self.symbol)
            return avg if amt > 0 else 0.0
        except Exception:
            return 0.0

    def _refresh_state_from_balance(self):
        if self.settings.dry_run:
            return
        try:
            b = self.exchange.fetch_balance()
            base = self.symbol.split("/")[0]
            bal = float(b.get("free", {}).get(base, 0.0) or 0.0)
            self.state.base_amount = bal
            self.state.avg_cost = self.get_open_avg_cost()
            if self.state.base_amount <= 0 and self.state.avg_cost > 0:
                self.state.avg_cost = 0.0
                self.store.save(self.state)
        except Exception:
            pass

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

    def _buy_base_amount_eth(self, base_amount: float):
        if base_amount <= 0.0:
            return
        if self.settings.order_type == "limit":
            bp, _ = self._compute_limit_prices()
            price = bp
            if self.settings.dry_run:
                self.state.avg_cost = (self.state.avg_cost * self.state.base_amount + price * base_amount) / (
                            self.state.base_amount + base_amount) if (
                                                                                 self.state.base_amount + base_amount) > 0 else price
                self.state.base_amount += base_amount
                self.store.save(self.state)
                self.ledger.record("buy", self.symbol, price, base_amount, 0.0, "")
                self.logger.info(
                    f"BUY-LIMIT {self.symbol} price={price:.6f} amount={base_amount:.8f} pos={self.state.base_amount:.8f}")
                return
            o = self.exchange.create_limit_buy(self.symbol, base_amount, price, {})
            self.logger.info(
                f"PLACE BUY-LIMIT {self.symbol} price={price:.6f} amount={base_amount:.8f} order_id={o.get('id', '')}")
            return
        else:
            last_price = self._get_latest_price()
            if self.settings.dry_run:
                self.state.avg_cost = (self.state.avg_cost * self.state.base_amount + last_price * base_amount) / (
                            self.state.base_amount + base_amount) if (self.state.base_amount + base_amount) > 0 else last_price
                self.state.base_amount += base_amount
                self.store.save(self.state)
                self.ledger.record("buy", self.symbol, last_price, base_amount, 0.0, "")
                self.logger.info(
                    f"BUY {self.symbol} price={last_price:.6f} amount={base_amount:.8f} pos={self.state.base_amount:.8f}")
                return
            quote_cost = base_amount * last_price
            o = self.exchange.create_market_buy(self.symbol, quote_cost, {})
            amt = float(o.get("amount", 0.0) or 0.0)
            price = last_price
            if amt > 0:
                self._rebuild_avg_cost_from_exchange_trades()
                self.ledger.record("buy", self.symbol, price, amt, 0.0, o.get("id", ""))
            self.logger.info(f"BUY {self.symbol} price={price:.6f} amount={amt:.8f} pos={self.state.base_amount:.8f}")

    def _sell_but_keep_base(self, base_keep: float):
        base_amount = self.state.base_amount
        if base_amount <= base_keep:
            return
        sell_amount = base_amount - base_keep
        last_price = self._get_latest_price()
        if self.settings.order_type == "limit":
            _, sp = self._compute_limit_prices()
            price = sp
            if self.settings.dry_run:
                realized = sell_amount * (price - self.state.avg_cost) if self.state.avg_cost > 0 else 0.0
                self.ledger.record("sell", self.symbol, price, sell_amount, 0.0, "")
                self.logger.info(
                    f"SELL-LIMIT {self.symbol} price={price:.6f} amount={sell_amount:.8f} realized={realized:.6f}")
            else:
                print(self.state.base_amount, sell_amount, price)
                o = self.exchange.create_limit_sell(self.symbol, sell_amount, price, {})
                self.logger.info(
                    f"PLACE SELL-LIMIT {self.symbol} price={price:.6f} amount={sell_amount:.8f} order_id={o.get('id', '')}")
            self.state.base_amount = base_keep
            self.store.save(self.state)
            return
        else:
            price = last_price
            if self.settings.dry_run:
                realized = sell_amount * (price - self.state.avg_cost) if self.state.avg_cost > 0 else 0.0
                self.ledger.record("sell", self.symbol, price, sell_amount, 0.0, "")
                self.logger.info(
                    f"SELL {self.symbol} price={price:.6f} amount={sell_amount:.8f} realized={realized:.6f}")
            else:
                o = self.exchange.create_market_sell(self.symbol, sell_amount, {})
                realized = sell_amount * (price - self.state.avg_cost) if self.state.avg_cost > 0 else 0.0
                self.ledger.record("sell", self.symbol, price, sell_amount, 0.0, o.get("id", ""))
                self.logger.info(f"SELL {self.symbol} price={price:.6f} amount={sell_amount:.8f} realized={realized:.6f}")
            self.state.base_amount = base_keep
            self.store.save(self.state)

    def run(self):
        pass
