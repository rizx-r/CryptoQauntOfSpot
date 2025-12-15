import time
import numpy as np
from typing import List
from core.exchange_base import IExchange
from config.settings import Settings
from utils.indicators import macd_cross_golden
from utils.state import PositionState, StateStore, TradeLedger
from strategie.BaseStrategy import BaseStrategy


class SigmaSpotStrategy(BaseStrategy):
    def run(self):
        while True:
            try:
                # self.logger.info('1')
                self._refresh_state_from_balance()
                self._update_ohlcv_cache()
                closes = np.array([c[4] for c in self._ohlcv_cache], dtype=float) if self._ohlcv_cache else np.array([],
                                                                                                                     dtype=float)
                golden_cross = macd_cross_golden(closes) if closes.size > 0 else False
                last_price = self._get_latest_price()
                now_ms = int(time.time() * 1000)
                can_buy_time = (now_ms - int(self.state.last_buy_ms)) >= int(
                    self.settings.sigma_buy_cooldown_sec) * 1000
                price_ok = (self.state.base_amount <= 0.0) or (self.state.avg_cost > 0.0 and last_price <= self.state.avg_cost * (1.0 - float(self.settings.sigma_buy_price_drop_pct))) # or last_price <= self.state.avg_cost * (1.0 - 0.01)
                can_buy = price_ok and can_buy_time and golden_cross and (int(self.state.buy_count) < int(self.settings.sigma_max_adds))
                if can_buy:
                    self._buy_base_amount_eth(float(self.settings.sigma_buy_base_eth))
                    self.state.last_buy_ms = now_ms
                    self.state.buy_count = int(self.state.buy_count) + 1
                    self.store.save(self.state)
                else:
                    self.logger.info(
                        f"cant buy: {(price_ok if price_ok else f'({self.state.base_amount} <= 0.0) or ({self.state.avg_cost} > 0.0 and {last_price} <= {self.state.avg_cost} * (1.0 - {float(self.settings.sigma_buy_price_drop_pct)}))',
                                      can_buy_time if can_buy_time else f'({now_ms} - {int(self.state.last_buy_ms)}) >= {int(self.settings.sigma_buy_cooldown_sec)} * 1000',
                                      golden_cross if golden_cross else f'{macd_cross_golden(closes)} if {closes.size} > 0 else False',
                                      (int(self.state.buy_count) < int(self.settings.sigma_max_adds)))}")
                    # print('cant buy:', price_ok , can_buy_time , golden_cross , (int(self.state.buy_count) < int(self.settings.sigma_max_adds)))
                prev_bearish = False
                if len(self._ohlcv_cache) >= 2:
                    prev = self._ohlcv_cache[-2]
                    o = float(prev[1])
                    c = float(prev[4])
                    prev_bearish = o > c
                can_sell = (self.state.base_amount >= float(self.settings.sigma_sell_leave_base_eth)) and (
                            self.state.avg_cost > 0.0 and last_price >= self.state.avg_cost * (
                                1.0 + float(self.settings.sigma_sell_profit_pct))) and prev_bearish
                # self._sell_but_keep_base(float(self.settings.sigma_sell_leave_base_eth))
                if can_sell:
                    self._sell_but_keep_base(float(self.settings.sigma_sell_leave_base_eth))
                else:
                    self.logger.info(
                        f'cant sell: {(self.state.base_amount >= float(self.settings.sigma_sell_leave_base_eth)) if (self.state.base_amount >= float(self.settings.sigma_sell_leave_base_eth)) else f'({self.state.base_amount} >= float({self.settings.sigma_sell_leave_base_eth}))',
                        (self.state.avg_cost > 0.0 and last_price >= self.state.avg_cost * (1.0 + float(self.settings.sigma_sell_profit_pct))) if (self.state.avg_cost > 0.0 and last_price >= self.state.avg_cost * (1.0 + float(self.settings.sigma_sell_profit_pct))) else f'({self.state.avg_cost} > 0.0 and {last_price} >= {self.state.avg_cost} * (1.0 + {float(self.settings.sigma_sell_profit_pct)}))',
                        prev_bearish}')
                    # print('cant sell:', self.state.base_amount >= float(self.settings.sigma_sell_leave_base_eth), (
                    #             self.state.avg_cost > 0.0 and last_price >= self.state.avg_cost * (
                    #                 1.0 + float(self.settings.sigma_sell_profit_pct))), prev_bearish)
                b = self.exchange.fetch_balance()
                usdt = float(b.get("free", {}).get("USDT", 0.0) or 0.0)
                pnl_ratio = ((last_price - self.state.avg_cost) / self.state.avg_cost) if (self.state.avg_cost > 0.0 and self.state.base_amount > 0.0) else 0.0
                pnl_amount = (self.state.base_amount * (last_price - self.state.avg_cost)) if (self.state.avg_cost > 0.0 and self.state.base_amount > 0.0) else 0.0
                self.logger.info(f"state:{self.state} price={last_price:.6f} pnl_ratio={pnl_ratio:.6f} pnl_amount={pnl_amount:.6f} usdt_free={usdt:.2f}")
                time.sleep(self.settings.poll_interval_sec)
            except Exception as e:
                self.logger.error(str(e))
                time.sleep(self.settings.poll_interval_sec)
