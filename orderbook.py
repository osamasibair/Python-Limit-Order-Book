"""Level 3 limit order book, every resting order by id, a level 2 view of total shares per price and usual metrics."""
from sortedcontainers import SortedDict


class BookError(Exception):
    pass


class OrderBook:
    def __init__(self, strict=True):
        self.strict = strict
        self.orders = {}
        self.levels = {"B": SortedDict(), "S": SortedDict()}
        self.queues = {"B": {}, "S": {}}
        self.last_time = 0
        self.problems = {}

    def problem(self, kind, detail):
        if self.strict:
            raise BookError(f"{kind}: {detail}")
        self.problems[kind] = self.problems.get(kind, 0) + 1

    def check_time(self, time):
        if time < self.last_time:
            self.problem("time went backwards", f"{time} after {self.last_time}")
        self.last_time = max(self.last_time, time)

    def check_crossed(self):
        bid, ask = self.best_bid(), self.best_ask()
        if bid is not None and ask is not None and bid >= ask:
            self.problem("crossed book", f"bid {bid} >= ask {ask}")

    def add(self, order_id, side, price, shares, time=0):
        self.check_time(time)
        if order_id in self.orders:
            self.problem("duplicate order", order_id)
            return
        if shares <= 0 or price <= 0:
            self.problem("invalid order", order_id)
            return
        self.orders[order_id] = [side, price, shares]
        self.levels[side][price] = self.levels[side].get(price, 0) + shares
        self.queues[side].setdefault(price, {})[order_id] = shares
        self.check_crossed()

    def reduce(self, order_id, shares, time=0):
        self.check_time(time)
        order = self.orders.get(order_id)
        if order is None:
            self.problem("unknown order", order_id)
            return
        side, price, remaining = order
        if shares > remaining:
            self.problem("reduced by more than remaining", order_id)
            shares = remaining
        order[2] -= shares
        self.levels[side][price] -= shares
        queue = self.queues[side][price]
        queue[order_id] -= shares
        if order[2] == 0:
            del self.orders[order_id]
            del queue[order_id]
        if self.levels[side][price] == 0:
            del self.levels[side][price]
            del self.queues[side][price]

    def delete(self, order_id, time=0):
        order = self.orders.get(order_id)
        if order is None:
            self.problem("unknown order", order_id)
            return
        self.reduce(order_id, order[2], time)

    def replace(self, order_id, new_id, shares, price, time=0):
        order = self.orders.get(order_id)
        if order is None:
            self.problem("unknown order", order_id)
            return
        side = order[0]
        self.delete(order_id, time)
        self.add(new_id, side, price, shares, time)

    def apply(self, message):
        kind, time = message["type"], message["time"]
        if kind == "A":
            self.add(message["order"], message["side"], message["price"], message["shares"], time)
        elif kind in ("E", "C", "X"):
            self.reduce(message["order"], message["shares"], time)
        elif kind == "D":
            self.delete(message["order"], time)
        elif kind == "U":
            self.replace(message["order"], message["new_order"], message["shares"], message["price"], time)
        else:
            self.check_time(time)

    def best_bid(self):
        return self.levels["B"].peekitem(-1)[0] if self.levels["B"] else None

    def best_ask(self):
        return self.levels["S"].peekitem(0)[0] if self.levels["S"] else None

    def spread(self):
        bid, ask = self.best_bid(), self.best_ask()
        return None if bid is None or ask is None else ask - bid

    def mid(self):
        bid, ask = self.best_bid(), self.best_ask()
        return None if bid is None or ask is None else (bid + ask) / 2

    def microprice(self):
        bid, ask = self.best_bid(), self.best_ask()
        if bid is None or ask is None:
            return None
        bid_size, ask_size = self.levels["B"][bid], self.levels["S"][ask]
        return (bid * ask_size + ask * bid_size) / (bid_size + ask_size)

    def depth(self, side, n):
        levels = self.levels[side]
        prices = reversed(levels) if side == "B" else iter(levels)
        return [(price, levels[price]) for price, _ in zip(prices, range(n))]

    def total_depth(self, side, n=None):
        if n is None:
            return sum(self.levels[side].values())
        return sum(shares for _, shares in self.depth(side, n))

    def imbalance(self, n=1):
        bid, ask = self.total_depth("B", n), self.total_depth("S", n)
        return None if bid + ask == 0 else (bid - ask) / (bid + ask)

    def queue_position(self, order_id):
        side, price, _ = self.orders[order_id]
        ahead = 0
        for other, shares in self.queues[side][price].items():
            if other == order_id:
                return ahead
            ahead += shares
