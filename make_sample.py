"""Write a ITCH 5.0 file, so the replay and tests can run without downloading a real one."""
import gzip
import random
from pathlib import Path

from itch import formats

second = 1_000_000_000


def clock(hours, minutes=0, seconds=0):
    return ((hours * 60 + minutes) * 60 + seconds) * second


def frame(kind, *fields):
    body = formats[kind].pack(kind, *fields)
    return len(body).to_bytes(2, "big") + body


def ts(time):
    return time.to_bytes(6, "big")


def system(time, event):
    return frame(b"S", 0, 0, ts(time), event.encode())


def directory(locate, symbol):
    return frame(b"R", locate, 0, ts(clock(3)), symbol.ljust(8).encode(), b"Q", b"N", 100, b"N", b"C", b"Z ", b"P", b"N", b"N", b" ", b"N", 0, b"N")


def add(locate, time, order, side, shares, symbol, price):
    return frame(b"A", locate, 0, ts(time), order, side.encode(), shares, symbol.ljust(8).encode(), price)


def execute(locate, time, order, shares, match):
    return frame(b"E", locate, 0, ts(time), order, shares, match)


def cancel(locate, time, order, shares):
    return frame(b"X", locate, 0, ts(time), order, shares)


def delete(locate, time, order):
    return frame(b"D", locate, 0, ts(time), order)


def replace(locate, time, order, new_order, shares, price):
    return frame(b"U", locate, 0, ts(time), order, new_order, shares, price)


def hidden_trade(locate, time, side, shares, symbol, price, match):
    return frame(b"P", locate, 0, ts(time), 0, side.encode(), shares, symbol.ljust(8).encode(), price, match)


def sample_day(symbol="DEMO", minutes=30, seed=0):
    rng = random.Random(seed)
    out = [system(clock(4), "O"), directory(1, symbol), directory(2, "OTHER"), system(clock(9, 30), "Q")]
    resting, next_id, match, mid = {}, 1, 1, 1_000_000
    time = clock(9, 30)
    for _ in range(minutes * 60 * 20):
        time += rng.randint(1, 100_000_000)
        bids = [o for o, (side, _, _) in resting.items() if side == "B"]
        asks = [o for o, (side, _, _) in resting.items() if side == "S"]
        best_bid = max((resting[o][1] for o in bids), default=mid - 100)
        best_ask = min((resting[o][1] for o in asks), default=mid + 100)
        roll = rng.random()
        if roll < 0.5 or len(resting) < 20:
            side = rng.choice("BS")
            if side == "B":
                price = rng.randint(best_ask - 2000, best_ask - 100) // 100 * 100
            else:
                price = (rng.randint(best_bid + 100, best_bid + 2000) + 99) // 100 * 100
            shares = rng.choice([100, 200, 300, 500])
            out.append(add(1, time, next_id, side, shares, symbol, price))
            resting[next_id] = (side, price, shares)
            next_id += 1
        elif roll < 0.65:
            order = rng.choice(list(resting))
            side, price, shares = resting[order]
            out.append(delete(1, time, order))
            del resting[order]
        elif roll < 0.75:
            order = rng.choice(list(resting))
            side, price, shares = resting[order]
            if shares > 100:
                out.append(cancel(1, time, order, 100))
                resting[order] = (side, price, shares - 100)
        elif roll < 0.85:
            order = rng.choice(list(resting))
            side, price, shares = resting[order]
            limit = best_ask - 100 if side == "B" else best_bid + 100
            new_price = min(price + 100, limit) if side == "B" else max(price - 100, limit)
            out.append(replace(1, time, order, next_id, shares, new_price))
            del resting[order]
            resting[next_id] = (side, new_price, shares)
            next_id += 1
        elif roll < 0.97:
            side = rng.choice("BS")
            pool = bids if side == "B" else asks
            if pool:
                best = max(pool, key=lambda o: (resting[o][1], -o)) if side == "B" else min(pool, key=lambda o: (resting[o][1], o))
                _, price, shares = resting[best]
                done = min(shares, rng.choice([100, 200]))
                out.append(execute(1, time, best, done, match))
                match += 1
                if done == shares:
                    del resting[best]
                else:
                    resting[best] = (side, price, shares - done)
        else:
            out.append(hidden_trade(1, time, rng.choice("BS"), 100, symbol, (best_bid + best_ask) // 2, match))
            match += 1
        if rng.random() < 0.2:
            out.append(add(2, time, 10_000_000 + next_id, "B", 100, "OTHER", 500_000))
            next_id += 1
    out += [system(time + second, "M"), system(time + 2 * second, "C")]
    return b"".join(out)


if __name__ == "__main__":
    path = Path("data/sample.itch.gz")
    path.parent.mkdir(exist_ok=True)
    with gzip.open(path, "wb") as file:
        file.write(sample_day())
    print(f"wrote {path}")
