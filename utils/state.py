import os
import json
import csv
from dataclasses import dataclass, asdict
from typing import Optional
from config.settings import Settings

@dataclass
class PositionState:
    base_amount: float = 0.0
    avg_cost: float = 0.0

class StateStore:
    def __init__(self, settings: Settings):
        self.path = os.path.join("data", "state.json")
        os.makedirs("data", exist_ok=True)

    def load(self) -> PositionState:
        try:
            if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
                state = PositionState()
                self.save(state)
                return state
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
                base_amount = float(d.get("base_amount", 0.0))
                avg_cost = float(d.get("avg_cost", 0.0))
                return PositionState(base_amount=base_amount, avg_cost=avg_cost)
        except Exception:
            state = PositionState()
            self.save(state)
            return state

    def save(self, state: PositionState):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, ensure_ascii=False)

class TradeLedger:
    def __init__(self, settings: Settings):
        self.path = os.path.join("data", "trades.csv")
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["time", "side", "symbol", "price", "amount", "fee", "order_id"])

    def record(self, side: str, symbol: str, price: float, amount: float, fee: float, order_id: str):
        import time
        ts = int(time.time() * 1000)
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([ts, side, symbol, price, amount, fee, order_id])

    def rebuild_position(self, symbol: str):
        if not os.path.exists(self.path):
            return 0.0, 0.0
        buy_amt = 0.0
        buy_cost = 0.0
        sell_amt = 0.0
        with open(self.path, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                if row.get("symbol") != symbol:
                    continue
                side = (row.get("side") or "").lower()
                try:
                    amount = float(row.get("amount") or 0.0)
                    price = float(row.get("price") or 0.0)
                except Exception:
                    amount = 0.0
                    price = 0.0
                if side == "buy":
                    buy_amt += amount
                    buy_cost += amount * price
                elif side == "sell":
                    sell_amt += amount
        net_amt = buy_amt - sell_amt
        if net_amt > 0:
            avg_cost = buy_cost / net_amt
            return avg_cost, net_amt
        return 0.0, 0.0
